"""分类模块"""

import re
from typing import Any, Dict, List

from ..ingest.models import Item
from ..utils.logger import get_logger

logger = get_logger("classify")


def classify_item(item: Item, topics: List[Dict[str, Any]]) -> List[str]:
    """为Item分配主题标签

    Args:
        item: 待分类的Item
        topics: 主题配置列表

    Returns:
        主题标签列表
    """
    tags = set()

    # 从来源自动继承标签
    source_tags = item.raw_data.get("source_tags", [])
    tags.update(source_tags)

    # 合并所有可搜索文本
    searchable_text = " ".join(
        filter(
            None,
            [
                item.title,
                item.summary or "",
                item.content or "",
                item.source,
            ],
        )
    )
    searchable_text_lower = searchable_text.lower()

    # 遍历所有主题
    for topic in topics:
        topic_name = topic.get("name")
        if not topic_name:
            continue

        matched = False

        # 关键词匹配
        keywords = topic.get("keywords", [])
        for keyword in keywords:
            if keyword.lower() in searchable_text_lower:
                matched = True
                logger.debug(f"关键词匹配: {topic_name} ('{keyword}' in '{item.title}')")
                break

        # 正则表达式匹配
        if not matched:
            patterns = topic.get("patterns", [])
            for pattern in patterns:
                try:
                    if re.search(pattern, searchable_text, re.IGNORECASE):
                        matched = True
                        logger.debug(
                            f"正则匹配: {topic_name} ('{pattern}' in '{item.title}')"
                        )
                        break
                except re.error as e:
                    logger.warning(f"正则表达式错误 '{pattern}': {e}")

        if matched:
            tags.add(topic_name)

    return list(tags)


def classify_batch(items: List[Item], topics: List[Dict[str, Any]]) -> List[Item]:
    """批量分类

    Args:
        items: Item列表
        topics: 主题配置列表

    Returns:
        分类后的Item列表（原地修改）
    """
    logger.info(f"开始分类: {len(items)} 条数据，{len(topics)} 个主题")

    tag_counts = {}

    for item in items:
        tags = classify_item(item, topics)
        item.tags = tags

        # 统计标签
        for tag in tags:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1

    # 输出统计
    logger.info(f"分类完成，标签分布: {dict(sorted(tag_counts.items(), key=lambda x: -x[1])[:10])}")

    return items


__all__ = ["classify_item", "classify_batch"]
