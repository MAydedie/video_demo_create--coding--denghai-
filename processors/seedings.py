from base_processor import BaseProcessor
from volcano_api import VolcanoAPI
from config import VOLCANO_API_KEY, VOLCANO_API_URL, VOLCANO_MODEL_NAME, DEFAULT_ADDITIONAL_INFO
from prompts import (  # 假设prompts.py中定义了以下种草类提示词
    PROMPT_SEEDING_TASK1_SYSTEM, PROMPT_SEEDING_TASK1_USER,
    PROMPT_SEEDING_TASK2_SYSTEM, PROMPT_SEEDING_TASK2_USER,
    PROMPT_SEEDING_TASK3_SYSTEM, PROMPT_SEEDING_TASK3_USER,
    PROMPT_SEEDING_TASK4_SYSTEM, PROMPT_SEEDING_TASK4_USER,
    PROMPT_SEEDING_TASK5_SYSTEM, PROMPT_SEEDING_TASK5_USER,
    PROMPT_SEEDING_TASK6_SYSTEM, PROMPT_SEEDING_TASK6_USER
)
import asyncio
from typing import Dict, Any


class SeedingProcessor(BaseProcessor):
    def __init__(self):
        # 复用火山API客户端（与主程序配置一致）
        self.volcano_client = VolcanoAPI(
            api_key=VOLCANO_API_KEY,
            api_url=VOLCANO_API_URL,
            model_name=VOLCANO_MODEL_NAME
        )
        # 6个种草类任务名称（与提示词对应）
        self.task_names = [
            "场景化种草文案",
            "用户痛点激发",
            "产品优势转化",
            "社交证明构建",
            "行动指令设计",
            "情感共鸣强化"
        ]

    async def _call_model(self, system_prompt: str, user_prompt: str) -> str:
        """封装模型调用，复用火山API"""
        return await self.volcano_client.call_volcano_api(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            image_paths=None  # 种草类暂不涉及图片
        )

    async def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行6个并行种草任务
        :param params: 入参字典，包含：
            - content_direction: 内容方向结果（含content和direction）
            - selling_points: 卖点解析结果
            - creator_style: 达人风格解析结果
            - ppt_content: PPT提取内容
            - additional_info: 额外信息（来自config）
        """
        # 解析入参
        content_dir = params["content_direction"]
        selling_points = params["selling_points"]
        creator_style = params["creator_style"]
        ppt_content = params["ppt_content"]
        additional_info = params.get("additional_info", DEFAULT_ADDITIONAL_INFO)

        # 构建6个并行任务（每个任务对应一个模型调用）
        tasks = [
            # 任务1：场景化种草文案
            self._call_model(
                system_prompt=PROMPT_SEEDING_TASK1_SYSTEM,
                user_prompt=PROMPT_SEEDING_TASK1_USER.format(
                    content=content_dir["content"],
                    direction=content_dir["direction"],
                    selling_points=selling_points
                )
            ),
            # 任务2：用户痛点激发
            self._call_model(
                system_prompt=PROMPT_SEEDING_TASK2_SYSTEM,
                user_prompt=PROMPT_SEEDING_TASK2_USER.format(
                    creator_style=creator_style,
                    ppt_content=ppt_content
                )
            ),
            # 任务3：产品优势转化
            self._call_model(
                system_prompt=PROMPT_SEEDING_TASK3_SYSTEM,
                user_prompt=PROMPT_SEEDING_TASK3_USER.format(
                    selling_points=selling_points,
                    additional_info=additional_info
                )
            ),
            # 任务4：社交证明构建
            self._call_model(
                system_prompt=PROMPT_SEEDING_TASK4_SYSTEM,
                user_prompt=PROMPT_SEEDING_TASK4_USER.format(
                    content_direction=content_dir["direction"],
                    creator_style=creator_style
                )
            ),
            # 任务5：行动指令设计
            self._call_model(
                system_prompt=PROMPT_SEEDING_TASK5_SYSTEM,
                user_prompt=PROMPT_SEEDING_TASK5_USER.format(
                    selling_points=selling_points,
                    additional_info=additional_info
                )
            ),
            # 任务6：情感共鸣强化
            self._call_model(
                system_prompt=PROMPT_SEEDING_TASK6_SYSTEM,
                user_prompt=PROMPT_SEEDING_TASK6_USER.format(
                    content=content_dir["content"],
                    creator_style=creator_style,
                    ppt_content=ppt_content
                )
            )
        ]

        # 并行执行并按任务名封装结果
        results = await asyncio.gather(*tasks)
        return {self.task_names[i]: results[i] for i in range(6)}

    def integrate_results(self, raw_results: Dict[str, Any]) -> Dict[str, Any]:
        """整合6个任务结果为结构化种草策略"""
        from utils import merge_text_results  # 复用工具类
        return {
            "seeding_strategy": {
                "core_summary": merge_text_results(raw_results, prefix="• "),  # 合并核心要点
                "task_details": raw_results,  # 保留各任务原始结果
                "application_advice": "1. 优先使用场景化文案结合用户痛点；2. 社交证明部分可搭配真实用户评价；3. 行动指令需明确且低门槛"
            }
        }
