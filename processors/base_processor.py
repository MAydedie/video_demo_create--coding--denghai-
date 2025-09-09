from abc import ABC, abstractmethod
from typing import Dict, Any


class BaseProcessor(ABC):
    """处理器抽象基类，定义统一接口"""
    @abstractmethod
    async def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行并行模型调用
        :param params: 包含所有必要参数的字典
        :return: 原始模型调用结果
        """
        pass

    @abstractmethod
    def integrate_results(self, raw_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        整合模型结果
        :param raw_results: run方法返回的原始结果
        :return: 整合后的结构化结果
        """
        pass
