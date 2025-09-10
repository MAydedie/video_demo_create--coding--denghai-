import os
import json
import time  # 新增：用于记录耗时
import logging  # 新增：用于日志追踪
from typing import Dict, Any
from .base_processor import BaseProcessor
from prompts import (
    PROMPT_EVALUATION_SINGLE_SYSTEM, PROMPT_EVALUATION_SINGLE_USER,
    PROMPT_EVALUATION_HORIZONTAL_SYSTEM, PROMPT_EVALUATION_HORIZONTAL_USER,
    PROMPT_EVALUATION_MATRIX_SYSTEM, PROMPT_EVALUATION_MATRIX_USER,
    PROMPT_EVALUATION_COMPARISON_SYSTEM, PROMPT_EVALUATION_COMPARISON_USER
)

# 新增：初始化日志器
logger = logging.getLogger(__name__)


class EvaluationProcessor(BaseProcessor):
    """测评类处理器"""

    def __init__(self, volcano_client, additional_info=""):
        super().__init__(volcano_client)
        self.additional_info = additional_info

    async def process(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """处理测评类任务"""
        # 新增：记录process方法开始时间
        process_start = time.time()

        # 提取输入参数
        selling_points = inputs.get("selling_points", {})
        creator_style = inputs.get("creator_style", {})
        video_outline = inputs.get("video_outline", "")
        direction = inputs.get("direction", "")

        # 新增：日志记录输入参数（便于排查参数问题）
        logger.debug(
            f"测评处理器接收参数 - "
            f"direction: {direction}, "
            f"selling_points是否为空: {not bool(selling_points)}, "
            f"creator_style是否为空: {not bool(creator_style)}, "
            f"video_outline长度: {len(video_outline)}"
        )

        # 新增：检查关键参数是否存在
        if not direction:
            logger.warning("测评处理器接收的direction为空，可能导致分支匹配失败")

        # 根据direction选择调用哪个大模型
        result = await self.select_and_call_model(direction, selling_points, creator_style, video_outline)

        # 新增：记录process方法总耗时
        logger.debug(f"测评处理器process方法总耗时: {time.time() - process_start:.2f}s")

        # 返回结果
        return {
            "content_type": "evaluation",
            "direction": direction,
            "result": result,
            "additional_info": self.additional_info
        }

    async def select_and_call_model(self, direction, selling_points, creator_style, video_outline):
        """根据direction选择并调用对应的大模型"""
        # 新增：记录模型选择开始时间
        select_start = time.time()

        # 新增：日志记录当前要匹配的方向
        logger.debug(f"开始匹配测评方向: {direction}")

        # 测评类的4个方向
        if direction == "单品测评":
            logger.debug("匹配到'单品测评'方向，开始构建提示词并调用模型")  # 新增：分支匹配日志
            user_prompt = PROMPT_EVALUATION_SINGLE_USER.format(
                selling_points=json.dumps(selling_points, ensure_ascii=False),
                creator_style=json.dumps(creator_style, ensure_ascii=False),
                video_outline=video_outline,
                additional_info=self.additional_info
            )
            # 新增：记录模型调用开始时间
            call_start = time.time()
            result = await self.call_model(PROMPT_EVALUATION_SINGLE_SYSTEM, user_prompt)
            # 新增：记录模型调用耗时
            logger.debug(f"'单品测评'模型调用耗时: {time.time() - call_start:.2f}s")

        elif direction == "横向测评":
            logger.debug("匹配到'横向测评'方向，开始构建提示词并调用模型")  # 新增：分支匹配日志
            user_prompt = PROMPT_EVALUATION_HORIZONTAL_USER.format(
                selling_points=json.dumps(selling_points, ensure_ascii=False),
                creator_style=json.dumps(creator_style, ensure_ascii=False),
                video_outline=video_outline,
                additional_info=self.additional_info
            )
            call_start = time.time()
            result = await self.call_model(PROMPT_EVALUATION_HORIZONTAL_SYSTEM, user_prompt)
            logger.debug(f"'横向测评'模型调用耗时: {time.time() - call_start:.2f}s")

        elif direction == "同品牌矩阵":
            logger.debug("匹配到'同品牌矩阵'方向，开始构建提示词并调用模型")  # 新增：分支匹配日志
            user_prompt = PROMPT_EVALUATION_MATRIX_USER.format(
                selling_points=json.dumps(selling_points, ensure_ascii=False),
                creator_style=json.dumps(creator_style, ensure_ascii=False),
                video_outline=video_outline,
                additional_info=self.additional_info
            )
            call_start = time.time()
            result = await self.call_model(PROMPT_EVALUATION_MATRIX_SYSTEM, user_prompt)
            logger.debug(f"'同品牌矩阵'模型调用耗时: {time.time() - call_start:.2f}s")

        elif direction == "正盗版对比":
            logger.debug("匹配到'正盗版对比'方向，开始构建提示词并调用模型")  # 新增：分支匹配日志
            user_prompt = PROMPT_EVALUATION_COMPARISON_USER.format(
                selling_points=json.dumps(selling_points, ensure_ascii=False),
                creator_style=json.dumps(creator_style, ensure_ascii=False),
                video_outline=video_outline,
                additional_info=self.additional_info
            )
            call_start = time.time()
            result = await self.call_model(PROMPT_EVALUATION_COMPARISON_SYSTEM, user_prompt)
            logger.debug(f"'正盗版对比'模型调用耗时: {time.time() - call_start:.2f}s")

        else:
            # 保留原逻辑：返回字符串类型的错误信息
            logger.warning(f"未匹配到任何测评方向（输入方向: {direction}），返回错误结果")  # 新增：警告日志
            result = json.dumps({"error": f"未知的测评方向: {direction}"}, ensure_ascii=False)

        # 新增：记录模型选择总耗时
        logger.debug(f"测评方向选择及模型调用总耗时: {time.time() - select_start:.2f}s")

        return self.parse_json_response(result)
