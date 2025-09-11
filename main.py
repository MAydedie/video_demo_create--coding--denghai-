from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, List
import asyncio
import json
import time
import os
import sys
import logging
from contextlib import asynccontextmanager
import glob
import re
from typing import Dict, List, Any, Optional

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 添加当前目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 本地达人主页资源路径
LOCAL_INFLUENCER_PATH = r"D:\众灿\视频脚本创作-coding（邓海模块）\整体代码\input\达人主页"

# 延迟导入非必要模块，加快启动速度
from config import (
    VOLCANO_API_KEY, VOLCANO_API_URL, VOLCANO_MODEL_NAME,
    DEFAULT_PPT_PATH, DEFAULT_URL, DEFAULT_CREATOR_STYLE_DESC,
    DEFAULT_BRAND_NAME, DEFAULT_ADDITIONAL_INFO, DEFAULT_VIDEO_OUTLINE_PATH,
    GRAPHIC_OUTLINE_TEMPLATE_URL
)

# 导入提示词和工具函数
from prompts import (
    PROMPT_SELLING_POINTS_SYSTEM, PROMPT_SELLING_POINTS_USER,
    PROMPT_CONTENT_DIRECTION_SYSTEM, PROMPT_CONTENT_DIRECTION_USER,
    PROMPT_CREATOR_STYLE_SYSTEM, PROMPT_CREATOR_STYLE_USER,
    PROMPT_FINAL_CONTENT_SYSTEM, PROMPT_FINAL_CONTENT_USER,
    PROMPT_VIDEO_SCRIPT_SYSTEM, PROMPT_VIDEO_SCRIPT_USER
)
from text_utils import extract_json_from_text, extract_direction_from_content


def read_local_influencer_resources() -> Dict[str, any]:
    """
    读取本地达人主页资源（txt文本和webp图片）
    返回格式与网络爬取结果一致，便于后续处理
    """
    result = {
        "document": "",
        "image_urls": []
    }

    # 检查目录是否存在
    if not os.path.exists(LOCAL_INFLUENCER_PATH):
        logger.warning(f"本地达人主页目录不存在: {LOCAL_INFLUENCER_PATH}")
        return result

    # 读取所有txt文件内容
    txt_files = glob.glob(os.path.join(LOCAL_INFLUENCER_PATH, "*.txt"))
    if txt_files:
        logger.info(f"找到{len(txt_files)}个本地文本文件，将合并内容")
        for txt_file in txt_files:
            try:
                with open(txt_file, 'r', encoding='utf-8') as f:
                    file_content = f.read()
                    result["document"] += f"\n\n【{os.path.basename(txt_file)}】\n{file_content}"
            except Exception as e:
                logger.warning(f"读取文本文件{txt_file}失败: {str(e)}")

    # 读取所有webp图片
    webp_files = glob.glob(os.path.join(LOCAL_INFLUENCER_PATH, "*.webp"))
    if webp_files:
        logger.info(f"找到{len(webp_files)}个本地webp图片")
        # 将本地路径转换为file://格式的URL，便于后续处理
        result["image_urls"] = [f"file:///{path.replace(os.sep, '/')}" for path in webp_files]

    # 验证是否读取到内容
    if not result["document"] and not result["image_urls"]:
        logger.warning(f"本地达人主页目录{LOCAL_INFLUENCER_PATH}中未找到任何txt或webp文件")

    return result


# 定义生命周期管理器
@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    try:
        from utils.feishu_spreadsheet import FeishuSheetManager
        logger.info("资源释放完成")
    except Exception as e:
        logger.warning(f"关闭资源时出错: {str(e)}")


app = FastAPI(
    title="内容策略生成系统",
    version="1.0.0",
    lifespan=lifespan
)

# 导入处理器类
try:
    from processors.seeding import SeedingProcessor
    from processors.evaluation import EvaluationProcessor


    def create_processor(processor_type, volcano_client, additional_info=""):
        if processor_type == "seeding":
            return SeedingProcessor(volcano_client, additional_info)
        elif processor_type == "evaluation":
            return EvaluationProcessor(volcano_client, additional_info)
        else:
            raise ValueError(f"未知的处理器类型: {processor_type}")
except ImportError:
    def create_processor(processor_type, volcano_client, additional_info=""):
        raise ImportError("无法导入 processors 模块")


class ProcessingRequest(BaseModel):
    """请求参数模型，适配默认配置"""
    ppt_path: str = DEFAULT_PPT_PATH
    url: str = DEFAULT_URL
    style_type: str = DEFAULT_CREATOR_STYLE_DESC
    brand_name: str = DEFAULT_BRAND_NAME
    additional_info: Optional[str] = DEFAULT_ADDITIONAL_INFO
    video_outline_path: str = DEFAULT_VIDEO_OUTLINE_PATH
    download_images: Optional[bool] = False
    use_local_influencer: Optional[bool] = False  # 新增：是否强制使用本地达人资源


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
    user_prompt = PROMPT_SELLING_POINTS_USER.format(
        brand_name=brand_name,
        ppt_content=ppt_content
    )
    result = await process_with_volcano(PROMPT_SELLING_POINTS_SYSTEM, user_prompt)
    return extract_json_from_text(result)


async def process_content_direction(ppt_content, brand_name):
    """处理内容方向分析"""
    user_prompt = PROMPT_CONTENT_DIRECTION_USER.format(
        brand_name=brand_name,
        ppt_content=ppt_content
    )
    result = await process_with_volcano(PROMPT_CONTENT_DIRECTION_SYSTEM, user_prompt)
    return extract_json_from_text(result)


async def process_creator_style(url_content, image_paths):
    """处理达人风格解析"""
    user_prompt = PROMPT_CREATOR_STYLE_USER.format(
        url_content=url_content
    )
    result = await process_with_volcano(PROMPT_CREATOR_STYLE_SYSTEM, user_prompt, image_paths)
    return extract_json_from_text(result)


async def process_final_content(content_direction, creator_style_analysis, style_type, additional_info):
    """处理最终内容策略（final子系统）"""
    user_prompt = PROMPT_FINAL_CONTENT_USER.format(
        content_direction=content_direction,
        creator_style_analysis=creator_style_analysis,
        style_type=style_type,
        additional_info=additional_info
    )
    result = await process_with_volcano(PROMPT_FINAL_CONTENT_SYSTEM, user_prompt)
    return extract_json_from_text(result)


async def process_video_script(creator_style, selling_points, final_strategy, style_type, additional_info):
    """生成视频脚本配文"""
    user_prompt = PROMPT_VIDEO_SCRIPT_USER.format(
        creator_style=json.dumps(creator_style, ensure_ascii=False),
        selling_points=json.dumps(selling_points, ensure_ascii=False),
        final_strategy=json.dumps(final_strategy, ensure_ascii=False),
        style_type=style_type,
        additional_info=additional_info
    )
    result = await process_with_volcano(PROMPT_VIDEO_SCRIPT_SYSTEM, user_prompt)
    return extract_json_from_text(result)


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


# 增强版：从文本（包括自然语言）中提取信息并转换为JSON
def extract_json_from_text(text: str) -> Any:
    """增强版：从文本（包括自然语言）中提取信息并转换为JSON"""
    # 1. 先尝试提取纯JSON
    json_pattern = re.compile(r'(\{.*\})|(\[.*\])', re.DOTALL)
    match = json_pattern.search(text)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass  # 继续尝试自然语言解析

    # 2. 尝试解析简单键值对格式（如"direction: 单品测评"）
    if ":" in text and len(text.splitlines()) == 1:
        try:
            key, value = text.split(":", 1)
            return {key.strip(): value.strip()}
        except:
            pass

    # 3. 若没有纯JSON，尝试从自然语言（Markdown列表）中提取信息
    try:
        # 分割标题和内容
        sections = re.split(r'###+', text)
        result = {}
        for section in sections:
            if not section.strip():
                continue
            # 提取 section 标题（如"一、必提内容"）
            section_lines = [line.strip() for line in section.splitlines() if line.strip()]
            if not section_lines:
                continue
            section_title = section_lines[0].replace('、', '').strip()  # 清理标题
            # 提取 section 下的列表项
            section_content = []
            for line in section_lines[1:]:  # 跳过标题行
                # 匹配列表项（如"1. **产品核心信息**""- 无水压限制"）
                item_match = re.match(r'^[\d•\-]+[\.\s]*(.*)$', line)
                if item_match:
                    section_content.append(item_match.group(1).strip())
            if section_content:
                result[section_title] = section_content
        return result if result else {"raw_content": text}
    except Exception as e:
        return {"raw_content": text, "error": f"解析自然语言失败: {str(e)}"}


# 从内容中提取方向（核心缺失函数）
def extract_direction_from_content(content: Any) -> Optional[str]:
    """
    从内容中提取核心方向（如"单品种草""对比测评"等）
    :param content: 可能是字典、JSON字符串或文本
    :return: 提取到的方向字符串，无则返回None
    """
    # 若输入是字符串，先尝试解析为JSON
    if isinstance(content, str):
        content = parse_json_safely(content, default=content)

    # 若为字典，尝试从常见字段提取
    if isinstance(content, dict):
        # 检查可能存储方向的字段
        direction_fields = ["direction", "content_direction", "主题", "方向"]
        for field in direction_fields:
            if field in content and isinstance(content[field], str):
                return content[field].strip()

        # 若字段中无，尝试从"summary"或"description"中提取
        for field in ["summary", "description", "内容摘要"]:
            if field in content and isinstance(content[field], str):
                # 从摘要中匹配常见方向关键词
                direction_keywords = ["种草", "测评", "推荐", "对比", "教程", "解析"]
                for keyword in direction_keywords:
                    if keyword in content[field]:
                        return keyword
        return None

    # 若为其他类型（如列表），取第一个元素尝试提取
    if isinstance(content, list) and len(content) > 0:
        return extract_direction_from_content(content[0])

    # 提取失败
    return None


def parse_json_safely(text: str, default: Any = None) -> Any:
    """安全解析JSON字符串，失败时返回默认值"""
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return default


@app.post("/generate-content-strategy")
async def generate_content_strategy(request: ProcessingRequest):
    """主接口：生成内容策略+视频脚本+飞书表格写入（包含seeding和evaluation步骤）"""
    try:
        timing = {}
        is_crawl_success = True  # 标记爬虫是否成功

        # 1. 验证风格类型
        if request.style_type not in ["测评类", "种草类"]:
            raise HTTPException(status_code=400, detail="风格类型必须是'测评类'或'种草类'")

        # 2. 提取基础内容
        from content_extractor import extract_text_from_ppt, extract_content_from_url, read_text_file
        content_extract_start = time.time()
        ppt_content = await asyncio.to_thread(extract_text_from_ppt, request.ppt_path)

        # 处理达人主页内容（网络或本地）
        if request.use_local_influencer:
            # 强制使用本地资源
            logger.info("强制使用本地达人主页资源")
            url_content_result = read_local_influencer_resources()
            is_crawl_success = False  # 标记为未爬取
        else:
            # 先尝试网络爬取
            url_content_result = await extract_content_from_url(request.url)

            # 判断是否需要使用本地资源
            if url_content_result.get("document", "").startswith(
                    ("请求失败", "获取网页内容时出错", "请求被重定向到安全验证页面")
            ):
                logger.warning(f"网页爬取失败，将使用本地达人主页资源: {url_content_result.get('document', '未知错误')}")
                url_content_result = read_local_influencer_resources()
                is_crawl_success = False

        video_outline = await asyncio.to_thread(read_text_file, request.video_outline_path)
        timing["内容提取耗时"] = time.time() - content_extract_start

        # 验证PPT和视频大纲提取结果
        if ppt_content.startswith(("错误", "读取PPT文件时出错")):
            raise HTTPException(status_code=400, detail=ppt_content)
        if video_outline.startswith("读取文件时出错"):
            raise HTTPException(status_code=400, detail=video_outline)

        # 3. 处理达人主页内容
        url_content = url_content_result["document"]
        downloaded_images = url_content_result.get("image_urls", [])

        # 日志显示使用的资源情况
        if not is_crawl_success:
            txt_count = len(glob.glob(os.path.join(LOCAL_INFLUENCER_PATH, "*.txt")))
            img_count = len(glob.glob(os.path.join(LOCAL_INFLUENCER_PATH, "*.webp")))
            logger.info(f"使用本地达人资源 - 文本文件: {txt_count}个, 图片: {img_count}个")

        # 4. 并行执行基础模型任务
        parallel_start = time.time()
        # 必选任务：卖点解析和内容方向分析
        selling_points_task = process_selling_points(ppt_content, request.brand_name)
        content_direction_task = process_content_direction(ppt_content, request.brand_name)

        # 达人风格分析任务（使用网络或本地资源）
        creator_style_task = process_creator_style(url_content, downloaded_images)
        selling_points, content_direction, creator_style = await asyncio.gather(
            selling_points_task, content_direction_task, creator_style_task
        )

        timing["并行基础任务耗时"] = time.time() - parallel_start

        # 5. 验证基础任务结果
        default_creator_style = {
            "style_type": request.style_type,
            "style_analysis": "使用默认风格（因达人风格分析失败）",
            "content_suggestions": "突出产品核心卖点，语言简洁明了"
        }

        for name, result in [
            ("卖点解析", selling_points),
            ("内容方向分析", content_direction),
            ("达人风格分析", creator_style)
        ]:
            if isinstance(result, dict):
                # 达人风格分析允许有错误，使用默认值兜底
                if name == "达人风格分析" and ("error" in result or "raw_content" in result):
                    error_msg = result.get("error", "未知错误")
                    logger.warning(f"{name}有错误，使用默认值: {error_msg}")
                    creator_style = default_creator_style
                # 其他任务有错误则中断
                elif "error" in result or "raw_content" in result:
                    error_msg = result.get("error", "未知错误")
                    raise HTTPException(status_code=500, detail=f"{name}失败: {error_msg}")
            elif isinstance(result, str) and result.startswith("处理失败"):
                # 达人风格分析允许失败
                if name != "达人风格分析":
                    raise HTTPException(status_code=500, detail=f"{name}失败: {result}")
                else:
                    logger.warning(f"{name}失败，使用默认值: {result}")
                    creator_style = default_creator_style

        # 6. 提取风格类型
        try:
            if isinstance(creator_style, dict):
                extracted_style_type = creator_style.get("style_type", request.style_type)
            else:
                style_data = json.loads(creator_style)
                extracted_style_type = style_data.get("style_type", request.style_type)
        except (json.JSONDecodeError, TypeError):
            extracted_style_type = request.style_type
        timing["风格类型提取耗时"] = time.time() - (parallel_start + timing["并行基础任务耗时"])
        logger.debug(f"提取到的风格类型: {extracted_style_type}（用于二重判断）")

        # 7. 提取初始内容方向（仅用于日志）
        initial_direction = extract_direction_from_content(content_direction)
        if initial_direction:
            logger.debug(f"初始内容方向（不用于二次判断）: {initial_direction}")

        # 8. 生成最终策略结果（final子系统）
        final_strategy_start = time.time()
        final_content = await process_final_content(
            content_direction, creator_style, extracted_style_type, request.additional_info
        )
        timing["最终策略生成耗时"] = time.time() - final_strategy_start

        # 9. 提取最终方向（增强容错处理）
        final_direction = None
        if isinstance(final_content, dict):
            # 尝试从常见字段获取方向
            for field in ["direction", "content_direction", "主题", "方向"]:
                if field in final_content:
                    final_direction = final_content[field]
                    break

            # 如果字典中没有明确方向字段，尝试从内容中提取
            if not final_direction:
                final_direction = extract_direction_from_content(final_content)
        elif isinstance(final_content, str):
            # 直接处理字符串类型的响应
            if "direction:" in final_content.lower():
                final_direction = final_content.split("direction:")[1].strip()
            else:
                final_direction = extract_direction_from_content(final_content)

        # 日志记录最终方向
        if final_direction:
            logger.info(f"提取的最终内容方向: {final_direction}")
        else:
            logger.warning("无法从final子系统中提取方向字段，将使用空值执行后续步骤")
            final_direction = ""

        # 10. 二重判断：执行seeding/evaluation
        logger.debug("执行最终处理器（seeding/evaluation）")
        style_type = extracted_style_type
        additional_info = request.additional_info or DEFAULT_ADDITIONAL_INFO
        final_result = None
        shot_list = []  # 初始化分镜列表

        # 根据风格类型执行对应处理器
        if style_type == "种草类":
            logger.debug("进入种草类处理器 - 执行seeding")
            seeding_start = time.time()
            seeding_inputs = {
                "selling_points": selling_points,
                "creator_style": creator_style,
                "video_outline": video_outline,
                "direction": final_direction,
                "additional_info": additional_info,
                "final_content": final_content
            }
            volcano_client = await get_volcano_client()
            processor = create_processor("seeding", volcano_client, additional_info)
            final_result = await processor.process(seeding_inputs)
            timing["seeding处理耗时"] = time.time() - seeding_start
        elif style_type == "测评类":
            logger.debug("进入测评类处理器 - 执行evaluation")
            evaluation_start = time.time()
            evaluation_inputs = {
                "selling_points": selling_points,
                "creator_style": creator_style,
                "video_outline": video_outline,
                "direction": final_direction,
                "additional_info": additional_info,
                "final_content": final_content
            }
            volcano_client = await get_volcano_client()
            processor = create_processor("evaluation", volcano_client, additional_info)
            # 直接获取分镜列表
            shot_list = await processor.process(evaluation_inputs)
            timing["evaluation处理耗时"] = time.time() - evaluation_start

            # 记录分镜数据
            logger.info(f"成功获取分镜数据，共 {len(shot_list)} 个镜头")
            if shot_list:
                logger.info(f"第一个镜头内容: {shot_list[0]}")

        # 11. 生成视频脚本配文
        video_script_start = time.time()
        video_script = await process_video_script(
            creator_style=creator_style,
            selling_points=selling_points,
            final_strategy=final_result,
            style_type=style_type,
            additional_info=additional_info
        )
        timing["视频脚本配文生成耗时"] = time.time() - video_script_start

        # 12. 写入飞书表格
        sheet_start = time.time()
        try:
            spreadsheet_util = await get_spreadsheet_util()
            logger.info("初始化飞书表格工具成功")

            # 确保video_script是字符串
            if isinstance(video_script, dict):
                video_script_str = json.dumps(video_script, ensure_ascii=False)
            else:
                video_script_str = str(video_script)

            # 确保final_result是字符串
            if isinstance(final_result, dict):
                strategy_result_str = json.dumps(final_result, ensure_ascii=False)
            else:
                strategy_result_str = str(final_result)

            logger.info(f"视频脚本长度: {len(video_script_str)}")
            logger.info(f"策略结果长度: {len(strategy_result_str)}")
            logger.info(f"分镜列表长度: {len(shot_list)}")

            # 调用飞书工具
            sheet_result = await spreadsheet_util.full_flow(
                video_script=video_script_str,
                strategy_result=strategy_result_str,
                shot_list=shot_list  # 直接传入分镜列表
            )
            logger.info(f"飞书表格处理结果: {sheet_result}")

            # 记录耗时
            timing["飞书表格处理耗时"] = time.time() - sheet_start
        except Exception as e:
            logger.error(f"飞书表格处理失败: {str(e)}", exc_info=True)
            sheet_result = {"status": "error", "message": f"飞书表格处理失败: {str(e)}"}
            timing["飞书表格处理耗时"] = time.time() - sheet_start

        # 13. 生成时间可视化
        timing_visualization = generate_timing_visualization(timing)
        logger.info(f"\n{timing_visualization}\n")

        # 14. 返回结果
        if sheet_result.get("status") == "success":
            return {
                "status": "success",
                "spreadsheet_url": sheet_result.get("spreadsheet_url"),
                "message": "内容策略已生成并保存到飞书表格" +
                           ("（使用本地达人资源）" if not is_crawl_success else ""),
                "style_type_used": style_type,
                "final_direction_used": final_direction,
                "resource_type": "local" if not is_crawl_success else "online"
            }
        else:
            return {
                "status": "error",
                "message": f"内容策略生成成功，但保存到飞书表格失败: {sheet_result.get('message')}",
                "final_strategy": final_result,
                "video_script": video_script,
                "resource_type": "local" if not is_crawl_success else "online"
            }

    except Exception as e:
        logger.error(f"处理请求时出错: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"处理请求时出错: {str(e)}")

        # 14. 生成时间可视化
        timing_visualization = generate_timing_visualization(timing)
        logger.info(f"\n{timing_visualization}\n")

        # 15. 返回结果
        if sheet_result.get("status") == "success":
            return {
                "status": "success",
                "spreadsheet_url": sheet_result.get("spreadsheet_url"),
                "message": "内容策略已生成并保存到飞书表格" +
                           ("（使用本地达人资源）" if not is_crawl_success else ""),
                "style_type_used": style_type,
                "final_direction_used": final_direction,
                "resource_type": "local" if not is_crawl_success else "online"
            }
        else:
            return {
                "status": "error",
                "message": f"内容策略生成成功，但保存到飞书表格失败: {sheet_result.get('message')}",
                "final_strategy": final_result,
                "video_script": video_script,
                "resource_type": "local" if not is_crawl_success else "online"
            }

    except Exception as e:
        logger.error(f"处理请求时出错: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"处理请求时出错: {str(e)}")

        # 15. 返回结果
        if sheet_result.get("status") == "success":
            return {
                "status": "success",
                "spreadsheet_url": sheet_result.get("spreadsheet_url"),
                "message": "内容策略已生成并保存到飞书表格" +
                           ("（使用本地达人资源）" if not is_crawl_success else ""),
                "style_type_used": style_type,
                "final_direction_used": final_direction,
                "resource_type": "local" if not is_crawl_success else "online"
            }
        else:
            return {
                "status": "error",
                "message": f"内容策略生成成功，但保存到飞书表格失败: {sheet_result.get('message')}",
                "final_strategy": final_result,
                "video_script": video_script,
                "resource_type": "local" if not is_crawl_success else "online"
            }

    except Exception as e:
        logger.error(f"处理请求时出错: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"处理请求时出错: {str(e)}")


@app.get("/")
async def root():
    return {
        "message": "内容策略生成系统（支持本地达人资源）",
        "template_used": GRAPHIC_OUTLINE_TEMPLATE_URL,
        "local_influencer_path": LOCAL_INFLUENCER_PATH
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)