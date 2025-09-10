from typing import Dict, List, Any
import json


def merge_text_results(results: Dict[str, str], prefix: str = "- ", join_str: str = "\n") -> str:
    """
    合并多个文本结果为一个摘要
    :param results: 任务名称到结果的字典
    :param prefix: 每个结果前的前缀（如列表符号）
    :param join_str: 连接符（如换行）
    :return: 合并后的字符串
    """
    merged = []
    for task_name, result in results.items():
        # 移除结果中的空行和多余空格
        cleaned = "\n".join([line.strip() for line in result.splitlines() if line.strip()])
        merged.append(f"{prefix}{task_name}：{cleaned}")
    return join_str.join(merged)


def parse_json_safely(text: str, default: Any = None) -> Any:
    """
    安全解析JSON字符串，失败时返回默认值
    :param text: 可能包含JSON的文本
    :param default: 解析失败时的返回值
    :return: 解析后的JSON或默认值
    """
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return default


def extract_key_points(text: str, max_points: int = 5) -> List[str]:
    """
    从文本中提取关键要点（基于换行和列表符号）
    :param text: 输入文本
    :param max_points: 最大要点数量
    :return: 关键要点列表
    """
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    # 优先保留带列表符号的行
    key_points = [line for line in lines if line.startswith(("•", "-", "1.", "2.", "3."))]
    # 不足时补充其他行
    if len(key_points) < max_points:
        remaining = [line for line in lines if not line.startswith(("•", "-", "1.", "2.", "3."))]
        key_points += remaining[:max_points - len(key_points)]
    return key_points[:max_points]
