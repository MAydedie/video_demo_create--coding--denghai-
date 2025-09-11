from typing import Dict, List, Any, Optional
import json
import re


def merge_text_results(results: Dict[str, str], prefix: str = "- ", join_str: str = "\n") -> str:
    """合并多个文本结果为一个摘要"""
    merged = []
    for task_name, result in results.items():
        cleaned = "\n".join([line.strip() for line in result.splitlines() if line.strip()])
        merged.append(f"{prefix}{task_name}：{cleaned}")
    return join_str.join(merged)


def parse_json_safely(text: str, default: Any = None) -> Any:
    """安全解析JSON字符串，失败时返回默认值"""
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return default


def extract_key_points(text: str, max_points: int = 5) -> List[str]:
    """从文本中提取关键要点"""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    key_points = [line for line in lines if line.startswith(("•", "-", "1.", "2.", "3."))]
    if len(key_points) < max_points:
        remaining = [line for line in lines if not line.startswith(("•", "-", "1.", "2.", "3."))]
        key_points += remaining[:max_points - len(key_points)]
    return key_points[:max_points]


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

# 新增：从内容中提取方向（核心缺失函数）
def extract_direction_from_content(content: Any) -> Optional[str]:
    """
    从内容中提取核心方向（如“单品种草”“对比测评”等）
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
