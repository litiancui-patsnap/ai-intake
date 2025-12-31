"""发布模块"""

from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from ..ingest.models import Item
from ..utils.logger import get_logger

logger = get_logger("publish")


def generate_daily_report(
    items: List[Item], output_dir: str, date: datetime, config: Dict[str, Any]
) -> str:
    """生成日报

    Args:
        items: Item列表
        output_dir: 输出目录
        date: 日期
        config: 输出配置

    Returns:
        输出文件路径
    """
    logger.info(f"开始生成日报: {len(items)} 条数据")

    # 创建输出目录
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # 生成文件名
    filename = f"{date.strftime('%Y-%m-%d')}.md"
    filepath = output_path / filename

    # 按配置筛选
    max_items = config.get("max_items", 40)
    min_score = config.get("min_score", 40)

    # 过滤低分
    items = [item for item in items if item.score >= min_score]

    # 限制数量
    items = items[:max_items]

    # 分组
    must_read_items = [item for item in items if item.is_must_read]
    regular_items = [item for item in items if not item.is_must_read]

    # 按主题分组
    items_by_topic = defaultdict(list)
    for item in regular_items:
        if item.tags:
            # 使用第一个标签作为主题
            items_by_topic[item.tags[0]].append(item)
        else:
            items_by_topic["其他"].append(item)

    # 生成Markdown
    md_content = _generate_daily_markdown(
        date, must_read_items, items_by_topic, len(items), config
    )

    # 写入文件
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(md_content)

    logger.info(f"日报已生成: {filepath}")

    return str(filepath)


def _generate_daily_markdown(
    date: datetime,
    must_read_items: List[Item],
    items_by_topic: Dict[str, List[Item]],
    total_count: int,
    config: Dict[str, Any],
) -> str:
    """生成日报Markdown内容

    Args:
        date: 日期
        must_read_items: 必读列表
        items_by_topic: 按主题分组的Item
        total_count: 总数
        config: 输出配置

    Returns:
        Markdown字符串
    """
    lines = []

    # Header
    lines.append(f"# AI信息日报 - {date.strftime('%Y-%m-%d')}")
    lines.append("")
    est_reading_time = total_count * 0.3  # 每条约0.3分钟
    lines.append(
        f"📊 总计: {total_count}条 | 🔥 必读: {len(must_read_items)}条 | ⏰ 预计阅读: {int(est_reading_time)}分钟"
    )
    lines.append("")
    lines.append("---")
    lines.append("")

    # Must Read Section
    if must_read_items:
        lines.append("## 🔥 必读 (Must Read)")
        lines.append("")

        for item in must_read_items:
            lines.extend(_format_item(item, config))

        lines.append("---")
        lines.append("")

    # Topic Sections
    for topic, items in sorted(items_by_topic.items(), key=lambda x: -len(x[1])):
        # 获取主题的display_name（如果有）
        lines.append(f"## 📚 {topic}")
        lines.append("")

        for item in items:
            lines.extend(_format_item(item, config))

        lines.append("")

    return "\n".join(lines)


def _format_item(item: Item, config: Dict[str, Any]) -> List[str]:
    """格式化单个Item

    Args:
        item: Item
        config: 输出配置

    Returns:
        Markdown行列表
    """
    lines = []
    markdown_config = config.get("markdown", {})

    # 标题和链接
    lines.append(f"### [{item.title}]({item.url})")

    # 元信息
    pub_date = item.published.strftime("%Y-%m-%d %H:%M")
    score_str = f"{item.score:.0f}/100"
    meta = f"- **来源**: {item.source} | **发布**: {pub_date} | **评分**: {score_str}"
    lines.append(meta)

    # 摘要
    summary = item.ai_summary or item.summary or item.title
    lines.append(f"- **摘要**: {summary}")

    # 工程师要点
    if item.key_points and markdown_config.get("include_action", True):
        lines.append("- **工程师要点**:")
        for point in item.key_points:
            lines.append(f"  - {point}")

    # 行动建议
    if item.action and markdown_config.get("include_action", True):
        lines.append(f"- **行动建议**: {item.action}")

    # 评分详解
    if markdown_config.get("include_score_breakdown", True) and item.score_breakdown:
        breakdown = item.score_breakdown
        reasons = breakdown.get("reasons", [])
        if reasons:
            reason_text = " | ".join(reasons[:3])  # 最多显示3条
            lines.append(f"- **评分详解**: {reason_text}")

    lines.append("")

    return lines


def generate_weekly_report(
    items: List[Item], output_dir: str, week_start: datetime, config: Dict[str, Any]
) -> str:
    """生成周报

    Args:
        items: Item列表（一周内的）
        output_dir: 输出目录
        week_start: 周开始日期
        config: 输出配置

    Returns:
        输出文件路径
    """
    logger.info(f"开始生成周报: {len(items)} 条数据")

    # 创建输出目录
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # 生成文件名 (ISO周号)
    year, week_num, _ = week_start.isocalendar()
    filename = f"{year}-W{week_num:02d}.md"
    filepath = output_path / filename

    # 按配置筛选
    max_items = config.get("max_items", 120)
    min_score = config.get("min_score", 50)

    # 过滤低分
    items = [item for item in items if item.score >= min_score]

    # 限制数量
    items = items[:max_items]

    # 生成Markdown
    md_content = _generate_weekly_markdown(week_start, items, config)

    # 写入文件
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(md_content)

    logger.info(f"周报已生成: {filepath}")

    return str(filepath)


def _generate_weekly_markdown(
    week_start: datetime, items: List[Item], config: Dict[str, Any]
) -> str:
    """生成周报Markdown内容

    Args:
        week_start: 周开始日期
        items: Item列表
        config: 输出配置

    Returns:
        Markdown字符串
    """
    lines = []

    year, week_num, _ = week_start.isocalendar()

    # Header
    lines.append(f"# AI信息周报 - {year} W{week_num:02d}")
    lines.append("")

    # 本周总览
    lines.append("## 本周总览")
    lines.append("")
    overview = _generate_overview(items)
    lines.append(overview)
    lines.append("")
    lines.append("---")
    lines.append("")

    # 本周趋势 Top 5
    trend_count = config.get("trend_count", 5)
    trends = _extract_trends(items, trend_count)

    lines.append(f"## 🔥 本周趋势 Top {trend_count}")
    lines.append("")

    for i, trend in enumerate(trends, 1):
        lines.append(f"### {i}. {trend['title']}")
        lines.append("")
        for item in trend["items"]:
            lines.append(f"- [{item.title}]({item.url})")
        lines.append(f"**趋势**: {trend['description']}")
        lines.append("")

    lines.append("---")
    lines.append("")

    # 本周必做 Top 3
    must_do_count = config.get("must_do_count", 3)
    must_dos = _extract_must_dos(items, must_do_count)

    lines.append(f"## ✅ 本周必做 Top {must_do_count}")
    lines.append("")

    for i, item in enumerate(must_dos, 1):
        lines.append(f"{i}. **{item.action or '关注此更新'}**: {item.title} - {item.source}")

    lines.append("")
    lines.append("---")
    lines.append("")

    # 下周关注清单
    watchlist_count = config.get("watchlist_count", 5)
    watchlist = _generate_watchlist(items, watchlist_count)

    lines.append("## 👀 下周关注清单")
    lines.append("")

    for item in watchlist:
        lines.append(f"- [ ] {item}")

    lines.append("")

    return "\n".join(lines)


def _generate_overview(items: List[Item]) -> str:
    """生成本周总览

    Args:
        items: Item列表

    Returns:
        总览文本
    """
    # 统计主题分布
    tag_counts = defaultdict(int)
    for item in items:
        for tag in item.tags:
            tag_counts[tag] += 1

    top_topics = sorted(tag_counts.items(), key=lambda x: -x[1])[:5]
    topics_text = "、".join([f"{t[0]}({t[1]}条)" for t in top_topics])

    # 统计高分条目
    high_score_count = len([item for item in items if item.score >= 80])

    overview = f"本周共采集 {len(items)} 条AI领域信息，高分条目(score≥80) {high_score_count} 条。"
    overview += f"主要主题包括: {topics_text}。"

    return overview


def _extract_trends(items: List[Item], count: int) -> List[Dict[str, Any]]:
    """提取趋势

    Args:
        items: Item列表
        count: 趋势数量

    Returns:
        趋势列表
    """
    # 按主题聚合
    topic_items = defaultdict(list)
    for item in items:
        for tag in item.tags:
            topic_items[tag].append(item)

    # 计算每个主题的总分
    topic_scores = {
        topic: sum(item.score for item in items_list)
        for topic, items_list in topic_items.items()
    }

    # Top N主题
    top_topics = sorted(topic_scores.items(), key=lambda x: -x[1])[:count]

    trends = []
    for topic, _ in top_topics:
        items_list = topic_items[topic]
        # 取该主题下最高分的3条
        top_items = sorted(items_list, key=lambda x: -x.score)[:3]

        # 生成趋势描述
        description = f"{topic}领域本周共{len(items_list)}条更新，重点关注上述进展"

        trends.append(
            {
                "title": topic,
                "items": top_items,
                "description": description,
            }
        )

    return trends


def _extract_must_dos(items: List[Item], count: int) -> List[Item]:
    """提取必做事项

    Args:
        items: Item列表
        count: 数量

    Returns:
        必做Item列表
    """
    # 优先选择must_read + 高分 + 有明确action的
    must_read = [item for item in items if item.is_must_read and item.action]

    # 按分数排序
    must_read.sort(key=lambda x: -x.score)

    return must_read[:count]


def _generate_watchlist(items: List[Item], count: int) -> List[str]:
    """生成关注清单

    Args:
        items: Item列表
        count: 数量

    Returns:
        关注清单文本列表
    """
    # 提取可能在下周有后续的事项
    watchlist = []

    keywords = ["upcoming", "soon", "next", "beta", "rc", "preview", "roadmap"]

    for item in items:
        text = (item.title + " " + (item.summary or "")).lower()
        if any(kw in text for kw in keywords):
            watchlist.append(f"{item.source}: {item.title}")

    # 如果不足，补充高分条目
    if len(watchlist) < count:
        high_score = sorted(items, key=lambda x: -x.score)
        for item in high_score:
            entry = f"{item.source}: {item.title}"
            if entry not in watchlist:
                watchlist.append(entry)
            if len(watchlist) >= count:
                break

    return watchlist[:count]


__all__ = ["generate_daily_report", "generate_weekly_report"]
