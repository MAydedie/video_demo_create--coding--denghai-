from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, List
import asyncio
import json
import time
import logging
from contextlib import asynccontextmanager

# 延迟导入非必要模块，加快启动速度
from config import (
    VOLCANO_API_KEY, VOLCANO_API_URL, VOLCANO_MODEL_NAME,
    DEFAULT_PPT_PATH, DEFAULT_URL, DEFAULT_CREATOR_STYLE_DESC,
    DEFAULT_BRAND_NAME, DEFAULT_ADDITIONAL_INFO, DEFAULT_VIDEO_OUTLINE_PATH,
    GRAPHIC_OUTLINE_TEMPLATE_URL
)

# 初始化日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# 定义生命周期管理器
@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    try:
        from utils.feishu_spreadsheet import FeishuSheetManager
        # 这里不需要关闭客户端，因为FeishuSheetManager使用局部客户端
        logger.info("资源释放完成")
    except Exception as e:
        logger.warning(f"关闭资源时出错: {str(e)}")


app = FastAPI(
    title="内容策略生成系统",
    version="1.0.0",
    lifespan=lifespan
)


class ProcessingRequest(BaseModel):
    """请求参数模型，适配默认配置"""
    ppt_path: str = DEFAULT_PPT_PATH
    url: str = DEFAULT_URL
    style_type: str = DEFAULT_CREATOR_STYLE_DESC
    brand_name: str = DEFAULT_BRAND_NAME
    additional_info: Optional[str] = DEFAULT_ADDITIONAL_INFO
    video_outline_path: str = DEFAULT_VIDEO_OUTLINE_PATH
    download_images: Optional[bool] = False


# 延迟初始化火山客户端
async def get_volcano_client():
    from volcano_api import VolcanoAPI
    return VolcanoAPI(VOLCANO_API_KEY, VOLCANO_API_URL, VOLCANO_MODEL_NAME)


# 延迟初始化飞书工具
async def get_spreadsheet_util():
    from utils.feishu_spreadsheet import FeishuSpreadsheetUtil
    return FeishuSpreadsheetUtil()


async def process_with_volcano(system_prompt, user_prompt, image_paths=None):
    """通用火山大模型调用方法"""
    volcano_client = await get_volcano_client()
    return await volcano_client.call_volcano_api(system_prompt, user_prompt, image_paths)


async def process_selling_points(ppt_content, brand_name):
    """处理产品卖点解析"""
    from prompts import PROMPT_SELLING_POINTS_SYSTEM, PROMPT_SELLING_POINTS_USER
    user_prompt = PROMPT_SELLING_POINTS_USER.format(
        brand_name=brand_name,
        ppt_content=ppt_content
    )
    return await process_with_volcano(PROMPT_SELLING_POINTS_SYSTEM, user_prompt)


async def process_content_direction(ppt_content, brand_name):
    """处理内容方向分析"""
    from prompts import PROMPT_CONTENT_DIRECTION_SYSTEM, PROMPT_CONTENT_DIRECTION_USER
    user_prompt = PROMPT_CONTENT_DIRECTION_USER.format(
        brand_name=brand_name,
        ppt_content=ppt_content
    )
    return await process_with_volcano(PROMPT_CONTENT_DIRECTION_SYSTEM, user_prompt)


async def process_creator_style(url_content, image_paths):
    """处理达人风格解析"""
    from prompts import PROMPT_CREATOR_STYLE_SYSTEM, PROMPT_CREATOR_STYLE_USER
    user_prompt = PROMPT_CREATOR_STYLE_USER.format(
        url_content=url_content
    )
    return await process_with_volcano(PROMPT_CREATOR_STYLE_SYSTEM, user_prompt, image_paths)


async def process_final_content(content_direction, creator_style_analysis, style_type, additional_info):
    """处理最终内容策略"""
    from prompts import PROMPT_FINAL_CONTENT_SYSTEM, PROMPT_FINAL_CONTENT_USER
    user_prompt = PROMPT_FINAL_CONTENT_USER.format(
        content_direction=content_direction,
        creator_style_analysis=creator_style_analysis,
        style_type=style_type,
        additional_info=additional_info
    )
    return await process_with_volcano(PROMPT_FINAL_CONTENT_SYSTEM, user_prompt)


async def process_video_script(creator_style, selling_points, final_strategy, style_type):
    """生成视频脚本配文"""
    from prompts import PROMPT_VIDEO_SCRIPT_SYSTEM, PROMPT_VIDEO_SCRIPT_USER
    user_prompt = PROMPT_VIDEO_SCRIPT_USER.format(
        creator_style=json.dumps(creator_style, ensure_ascii=False),
        selling_points=json.dumps(selling_points, ensure_ascii=False),
        final_strategy=json.dumps(final_strategy, ensure_ascii=False),
        style_type=style_type
    )
    return await process_with_volcano(PROMPT_VIDEO_SCRIPT_SYSTEM, user_prompt)


def generate_timing_visualization(timing_data: Dict[str, float]) -> str:
    """生成时间统计可视化"""
    if not timing_data:
        return "无时间统计数据"
    max_time = max(timing_data.values()) if timing_data else 0
    if max_time == 0:
        return "所有环节耗时为0"
    bar_length = 30
    visualization = ["运行时间可视化 (单位: 秒):"]
    for stage, duration in sorted(timing_data.items(), key=lambda x: x[1], reverse=True):
        length = int((duration / max_time) * bar_length)
        bar = "■" * length + "□" * (bar_length - length)
        visualization.append(f"{stage}: {duration:.2f}s | {bar}")
    return "\n".join(visualization)


@app.post("/generate-content-strategy")
async def generate_content_strategy(request: ProcessingRequest):
    """主接口：生成内容策略+视频脚本+飞书表格写入"""
    try:
        timing = {}

        # 1. 验证风格类型
        if request.style_type not in ["测评类", "中草类"]:
            raise HTTPException(status_code=400, detail="风格类型必须是'测评类'或'中草类'")

        # 2. 提取基础内容
        from content_extractor import extract_text_from_ppt, extract_content_from_url, read_text_file
        content_extract_start = time.time()
        ppt_content = await asyncio.to_thread(extract_text_from_ppt, request.ppt_path)
        url_content_result = await extract_content_from_url(request.url)
        video_outline = await asyncio.to_thread(read_text_file, request.video_outline_path)
        timing["内容提取耗时"] = time.time() - content_extract_start

        # 验证内容提取结果
        if ppt_content.startswith(("错误", "读取PPT文件时出错")):
            raise HTTPException(status_code=400, detail=ppt_content)
        if url_content_result["document"].startswith(("请求失败", "获取网页内容时出错")):
            raise HTTPException(status_code=400, detail=url_content_result["document"])
        if video_outline.startswith("读取文件时出错"):
            raise HTTPException(status_code=400, detail=video_outline)

        url_content = url_content_result["document"]
        downloaded_images = url_content_result.get("image_urls", [])

        # 3. 并行执行基础模型任务
        parallel_start = time.time()
        selling_points_task = process_selling_points(ppt_content, request.brand_name)
        content_direction_task = process_content_direction(ppt_content, request.brand_name)
        creator_style_task = process_creator_style(url_content, downloaded_images)

        selling_points, content_direction, creator_style = await asyncio.gather(
            selling_points_task, content_direction_task, creator_style_task
        )
        timing["并行基础任务耗时"] = time.time() - parallel_start

        # 验证基础任务结果
        for name, result in [
            ("卖点解析", selling_points),
            ("内容方向分析", content_direction),
            ("达人风格分析", creator_style)
        ]:
            if isinstance(result, str) and result.startswith("处理失败"):
                raise HTTPException(status_code=500, detail=f"{name}失败: {result}")

        # 4. 提取风格类型
        try:
            style_data = json.loads(creator_style)
            extracted_style_type = style_data.get("style_type", request.style_type)
        except (json.JSONDecodeError, TypeError):
            extracted_style_type = request.style_type
        timing["风格类型提取耗时"] = time.time() - (parallel_start + timing["并行基础任务耗时"])

        # 5. 生成最终策略结果
        final_strategy_start = time.time()
        final_strategy = await process_final_content(
            content_direction, creator_style, extracted_style_type, request.additional_info
        )
        timing["最终策略生成耗时"] = time.time() - final_strategy_start

        # 6. 生成视频脚本配文
        video_script_start = time.time()
        video_script = await process_video_script(
            creator_style=creator_style,
            selling_points=selling_points,
            final_strategy=final_strategy,
            style_type=extracted_style_type
        )
        timing["视频脚本配文生成耗时"] = time.time() - video_script_start

        # 7. 写入飞书表格
        sheet_start = time.time()
        spreadsheet_util = await get_spreadsheet_util()
        sheet_result = await spreadsheet_util.full_flow(
            video_script=video_script,
            strategy_result=final_strategy
        )
        timing["飞书表格处理耗时"] = time.time() - sheet_start

        # 8. 生成时间可视化
        timing_visualization = generate_timing_visualization(timing)
        logger.info(f"\n{timing_visualization}\n")

        # 9. 返回飞书表格链接（根据要求，只返回链接）
        if sheet_result.get("status") == "success":
            return {
                "status": "success",
                "spreadsheet_url": sheet_result.get("spreadsheet_url"),
                "message": "内容策略已生成并保存到飞书表格"
            }
        else:
            return {
                "status": "error",
                "message": f"内容策略生成成功，但保存到飞书表格失败: {sheet_result.get('message')}"
            }

    except Exception as e:
        logger.error(f"处理请求时出错: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"处理请求时出错: {str(e)}")


@app.get("/")
async def root():
    return {
        "message": "内容策略生成系统（已集成飞书表格功能）",
        "template_used": GRAPHIC_OUTLINE_TEMPLATE_URL
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)