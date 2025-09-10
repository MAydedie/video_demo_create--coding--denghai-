from .base_processor import BaseProcessor
from .seeding import SeedingProcessor
from .evaluation import EvaluationProcessor


def create_processor(processor_type: str, volcano_client, additional_info: str = "") -> BaseProcessor:
    """创建处理器实例"""
    if processor_type == "seeding":
        return SeedingProcessor(volcano_client, additional_info)
    elif processor_type == "evaluation":
        return EvaluationProcessor(volcano_client, additional_info)
    else:
        raise ValueError(f"未知的处理器类型: {processor_type}")