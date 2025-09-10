import os
import json
from typing import Dict, Any
from .base_processor import BaseProcessor
from prompts import (
    PROMPT_SEEDING_SINGLE_SYSTEM, PROMPT_SEEDING_SINGLE_USER,
    PROMPT_SEEDING_UNBOXING_SYSTEM, PROMPT_SEEDING_UNBOXING_USER,
    PROMPT_SEEDING_VLOG_SYSTEM, PROMPT_SEEDING_VLOG_USER,
    PROMPT_SEEDING_COLLECTION_SYSTEM, PROMPT_SEEDING_COLLECTION_USER,
    PROMPT_SEEDING_DAILY_SYSTEM, PROMPT_SEEDING_DAILY_USER,
    PROMPT_SEEDING_TUTORIAL_SYSTEM, PROMPT_SEEDING_TUTORIAL_USER  # 只导入一个教程干货提示词
)


class SeedingProcessor(BaseProcessor):
    """种草类处理器"""

    def __init__(self, volcano_client, additional_info=""):
        super().__init__(volcano_client)
        self.additional_info = additional_info

    async def process(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """处理种草类任务"""
        # 提取输入参数
        selling_points = inputs.get("selling_points", {})
        creator_style = inputs.get("creator_style", {})
        video_outline = inputs.get("video_outline", "")
        direction = inputs.get("direction", "")

        # 根据direction选择调用哪个大模型
        result = await self.select_and_call_model(direction, selling_points, creator_style, video_outline)

        # 返回结果
        return {
            "content_type": "seeding",
            "direction": direction,
            "result": result,
            "additional_info": self.additional_info
        }

    async def select_and_call_model(self, direction, selling_points, creator_style, video_outline):
        """根据direction选择并调用对应的大模型"""
        # 种草类的8个方向
        if direction == "单品种草":
            user_prompt = PROMPT_SEEDING_SINGLE_USER.format(
                selling_points=json.dumps(selling_points, ensure_ascii=False),
                creator_style=json.dumps(creator_style, ensure_ascii=False),
                video_outline=video_outline,
                additional_info=self.additional_info
            )
            result = await self.call_model(PROMPT_SEEDING_SINGLE_SYSTEM, user_prompt)

        elif direction == "开箱种草":
            user_prompt = PROMPT_SEEDING_UNBOXING_USER.format(
                selling_points=json.dumps(selling_points, ensure_ascii=False),
                creator_style=json.dumps(creator_style, ensure_ascii=False),
                video_outline=video_outline,
                additional_info=self.additional_info
            )
            result = await self.call_model(PROMPT_SEEDING_UNBOXING_SYSTEM, user_prompt)

        elif direction == "vlog植入":
            user_prompt = PROMPT_SEEDING_VLOG_USER.format(
                selling_points=json.dumps(selling_points, ensure_ascii=False),
                creator_style=json.dumps(creator_style, ensure_ascii=False),
                video_outline=video_outline,
                additional_info=self.additional_info
            )
            result = await self.call_model(PROMPT_SEEDING_VLOG_SYSTEM, user_prompt)

        elif direction == "好物合集":
            user_prompt = PROMPT_SEEDING_COLLECTION_USER.format(
                selling_points=json.dumps(selling_points, ensure_ascii=False),
                creator_style=json.dumps(creator_style, ensure_ascii=False),
                video_outline=video_outline,
                additional_info=self.additional_info
            )
            result = await self.call_model(PROMPT_SEEDING_COLLECTION_SYSTEM, user_prompt)

        elif direction == "日常种草":
            user_prompt = PROMPT_SEEDING_DAILY_USER.format(
                selling_points=json.dumps(selling_points, ensure_ascii=False),
                creator_style=json.dumps(creator_style, ensure_ascii=False),
                video_outline=video_outline,
                additional_info=self.additional_info
            )
            result = await self.call_model(PROMPT_SEEDING_DAILY_SYSTEM, user_prompt)

        # 教程干货类的3个方向共用一个大模型和一个提示词
        elif direction in ["技巧型教程干货", "美食/DIY教程植入教程干货", "解决方案型教程干货"]:
            # 使用统一的教程干货提示词，但传入direction参数
            user_prompt = PROMPT_SEEDING_TUTORIAL_USER.format(
                direction=direction,
                selling_points=json.dumps(selling_points, ensure_ascii=False),
                creator_style=json.dumps(creator_style, ensure_ascii=False),
                video_outline=video_outline,
                additional_info=self.additional_info
            )

            # 使用统一的系统提示词调用大模型
            result = await self.call_model(PROMPT_SEEDING_TUTORIAL_SYSTEM, user_prompt)

        else:
            result = {"error": f"未知的种草方向: {direction}"}

        return self.parse_json_response(result)