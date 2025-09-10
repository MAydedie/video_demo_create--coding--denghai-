from abc import ABC, abstractmethod
from typing import Dict, Any, List
import asyncio
import json
import re


class BaseProcessor(ABC):
    """处理器抽象基类"""

    def __init__(self, volcano_client):
        self.volcano_client = volcano_client

    @abstractmethod
    async def process(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """处理输入并返回结果"""
        pass

    async def call_model(self, system_prompt: str, user_prompt: str, image_paths: List[str] = None) -> str:
        """调用大模型"""
        return await self.volcano_client.call_volcano_api(system_prompt, user_prompt, image_paths)

    @staticmethod
    def parse_json_response(response: Any) -> Dict:
        """尝试解析JSON响应（增加类型检查）"""
        try:
            # 确保输入是字符串类型
            if not isinstance(response, str):
                response_str = str(response)
                # 记录类型转换日志
                print(f"警告：响应类型不是字符串，已转换为字符串处理: {type(response)}")
            else:
                response_str = response

            # 尝试提取JSON部分
            json_match = re.search(r'\{.*\}', response_str, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            return json.loads(response_str)
        except json.JSONDecodeError:
            # 返回原始响应文本
            return {"raw_response": response_str}
        except Exception as e:
            # 捕获其他可能的异常
            return {"error": f"解析响应失败: {str(e)}", "raw_response": str(response)}
