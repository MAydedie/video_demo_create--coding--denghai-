from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, List
import asyncio
import json
import time  # 引入时间统计模块

from prompts import (
    PROMPT_SELLING_POINTS_SYSTEM, PROMPT_SELLING_POINTS_USER,
    PROMPT_CONTENT_DIRECTION_SYSTEM, PROMPT_CONTENT_DIRECTION_USER,
    PROMPT_CREATOR_STYLE_SYSTEM, PROMPT_CREATOR_STYLE_USER,
    PROMPT_FINAL_CONTENT_SYSTEM, PROMPT_FINAL_CONTENT_USER
)
from content_extractor import extract_text_from_ppt, extract_content_from_url, read_text_file
from volcano_api import VolcanoAPI
from config import VOLCANO_API_KEY, VOLCANO_API_URL, VOLCANO_MODEL_NAME

app = FastAPI(title="内容策略生成系统", version="1.0.0")

# 初始化火山API客户端
volcano_client = VolcanoAPI(VOLCANO_API_KEY, VOLCANO_API_URL, VOLCANO_MODEL_NAME)


class ProcessingRequest(BaseModel):
    ppt_path: str
    url: str
    style_type: str  # 测评类或中草类
    brand_name: str
    additional_info: Optional[str] = ""
    video_outline_path: str
    download_images: Optional[bool] = False  # 兼容字段，实际已不使用


async def process_with_volcano(system_prompt, user_prompt, image_paths=None):
    """使用火山大模型异步处理任务"""
    return await volcano_client.call_volcano_api(system_prompt, user_prompt, image_paths)


async def process_selling_points(ppt_content, brand_name):
    """处理卖点解析任务"""
    user_prompt = PROMPT_SELLING_POINTS_USER.format(
        brand_name=brand_name,
        ppt_content=ppt_content
    )
    return await process_with_volcano(PROMPT_SELLING_POINTS_SYSTEM, user_prompt)


async def process_content_direction(ppt_content, brand_name):
    """处理内容方向任务"""
    user_prompt = PROMPT_CONTENT_DIRECTION_USER.format(
        brand_name=brand_name,
        ppt_content=ppt_content
    )
    return await process_with_volcano(PROMPT_CONTENT_DIRECTION_SYSTEM, user_prompt)


async def process_creator_style(url_content, image_paths):
    """处理达人风格解析任务"""
    user_prompt = PROMPT_CREATOR_STYLE_USER.format(
        url_content=url_content
    )
    return await process_with_volcano(PROMPT_CREATOR_STYLE_SYSTEM, user_prompt, image_paths)


async def process_final_content(content_direction, creator_style_analysis, style_type, additional_info):
    """处理最终内容创作建议"""
    user_prompt = PROMPT_FINAL_CONTENT_USER.format(
        content_direction=content_direction,
        creator_style_analysis=creator_style_analysis,
        style_type=style_type,
        additional_info=additional_info
    )
    return await process_with_volcano(PROMPT_FINAL_CONTENT_SYSTEM, user_prompt)


def generate_timing_visualization(timing_data: Dict[str, float]) -> str:
    """生成时间统计的文本可视化（条形图）"""
    if not timing_data:
        return "无时间统计数据"

    # 计算最大时间值，用于比例缩放
    max_time = max(timing_data.values())
    if max_time == 0:
        return "所有环节耗时为0"

    # 定义图表参数
    bar_length = 30  # 最长条形的字符数
    visualization = ["运行时间可视化 (单位: 秒):"]

    # 修复语法错误：在for和变量之间添加空格
    for 环节, duration in sorted(timing_data.items(), key=lambda x: x[1], reverse=True):
        # 计算条形长度（按比例）
        length = int((duration / max_time) * bar_length)
        bar = "■" * length + "□" * (bar_length - length)
        visualization.append(f"{环节}: {duration:.2f}s | {bar}")

    return "\n".join(visualization)


@app.post("/generate-content-strategy")
async def generate_content_strategy(request: ProcessingRequest):
    """生成内容策略的主端点（含运行时间统计）"""
    try:
        # 初始化时间统计字典
        timing = {}

        # 验证风格类型
        if request.style_type not in ["测评类", "中草类"]:
            raise HTTPException(status_code=400, detail="风格类型必须是'测评类'或'中草类'")

        # 提取内容 - 使用异步方式
        ppt_content = await asyncio.to_thread(extract_text_from_ppt, request.ppt_path)
        url_content_result = await extract_content_from_url(request.url)
        video_outline = await asyncio.to_thread(read_text_file, request.video_outline_path)

        # 检查内容提取是否成功
        if ppt_content.startswith("错误") or ppt_content.startswith("读取PPT文件时出错"):
            raise HTTPException(status_code=400, detail=ppt_content)
        if url_content_result["document"].startswith("请求失败") or url_content_result["document"].startswith(
                "获取网页内容时出错"):
            raise HTTPException(status_code=400, detail=url_content_result["document"])
        if video_outline.startswith("读取文件时出错"):
            raise HTTPException(status_code=400, detail=video_outline)

        url_content = url_content_result["document"]
        downloaded_images = []

        # 并行执行三个大模型任务（记录总耗时）
        parallel_start = time.time()  # 开始计时

        # 为每个子任务单独计时（可选，用于更详细的分析）
        start1 = time.time()
        selling_points_task = process_selling_points(ppt_content, request.brand_name)
        start2 = time.time()
        content_direction_task = process_content_direction(ppt_content, request.brand_name)
        start3 = time.time()
        creator_style_task = process_creator_style(url_content, downloaded_images)

        # 等待所有并行任务完成
        selling_points, content_direction, creator_style = await asyncio.gather(
            selling_points_task, content_direction_task, creator_style_task
        )

        # 记录并行环节总耗时
        timing["并行任务总耗时"] = time.time() - parallel_start
        # 记录各子任务单独耗时（实际执行是并行的，这里仅作参考）
        timing["卖点解析耗时"] = time.time() - start1
        timing["内容方向分析耗时"] = time.time() - start2
        timing["达人风格分析耗时"] = time.time() - start3

        # 检查大模型任务是否成功
        if selling_points.startswith("处理失败"):
            raise HTTPException(status_code=500, detail=f"卖点解析失败: {selling_points}")
        if content_direction.startswith("处理失败"):
            raise HTTPException(status_code=500, detail=f"内容方向分析失败: {content_direction}")
        if creator_style.startswith("处理失败"):
            raise HTTPException(status_code=500, detail=f"达人风格分析失败: {creator_style}")

        # 提取风格类型
        try:
            style_data = json.loads(creator_style)
            extracted_style_type = style_data.get("style_type", request.style_type)
        except:
            extracted_style_type = request.style_type

        # 最终内容创作建议（记录耗时）
        final_start = time.time()
        final_result = await process_final_content(
            content_direction, creator_style, extracted_style_type, request.additional_info
        )
        timing["最终内容创作耗时"] = time.time() - final_start  # 记录最终环节耗时

        if final_result.startswith("处理失败"):
            raise HTTPException(status_code=500, detail=f"最终内容创作建议失败: {final_result}")

        # 生成时间可视化
        timing_visualization = generate_timing_visualization(timing)
        print("\n" + timing_visualization + "\n")  # 在终端打印可视化结果

        # 返回结果（包含时间统计）
        return {
            "selling_points_analysis": selling_points,
            "content_direction_analysis": content_direction,
            "creator_style_analysis": creator_style,
            "final_content_strategy": final_result,
            "style_type": extracted_style_type,
            "timing": {  # 时间统计数据
                "各环节耗时(秒)": {k: round(v, 2) for k, v in timing.items()},
                "可视化": timing_visualization
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"处理请求时出错: {str(e)}")


@app.get("/")
async def root():
    return {"message": "内容策略生成系统已就绪（含运行时间统计功能）"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
