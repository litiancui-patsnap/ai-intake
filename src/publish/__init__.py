"""日报和周报发布模块。"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from ..ingest.models import Item
from ..utils.logger import get_logger

logger = get_logger("publish")


def generate_daily_report(
    items: List[Item], output_dir: str, date: datetime, config: Dict[str, Any]
) -> str:
    """生成日报 Markdown 文件。"""
    logger.info("开始生成日报，输入条目数: %s", len(items))

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    filepath = output_path / f"{date.strftime('%Y-%m-%d')}.md"

    max_items = config.get("max_items", 20)
    min_score = config.get("min_score", 60)
    must_read_max = config.get("must_read_max", 3)
    top_focus_count = config.get("top_focus_count", 3)
    markdown_config = config.get("markdown", {})
    topic_item_limit = markdown_config.get("topic_item_limit", 4)

    filtered_items = [item for item in items if item.score >= min_score]
    filtered_items = filtered_items[:max_items]

    must_read_items = [item for item in filtered_items if item.is_must_read]
    focus_items = must_read_items[:must_read_max] if must_read_items else filtered_items[:top_focus_count]
    focus_urls = {item.url for item in focus_items}
    remaining_items = [item for item in filtered_items if item.url not in focus_urls]

    items_by_topic: Dict[str, List[Item]] = defaultdict(list)
    for item in remaining_items:
        items_by_topic[_primary_topic(item)].append(item)

    md_content = _generate_daily_markdown(
        date=date,
        focus_items=focus_items,
        items_by_topic=items_by_topic,
        total_count=len(filtered_items),
        must_read_count=len(must_read_items),
        topic_item_limit=topic_item_limit,
        config=config,
    )

    filepath.write_text(md_content, encoding="utf-8")
    logger.info("日报已写入 %s", filepath)
    return str(filepath)


def _generate_daily_markdown(
    *,
    date: datetime,
    focus_items: List[Item],
    items_by_topic: Dict[str, List[Item]],
    total_count: int,
    must_read_count: int,
    topic_item_limit: int,
    config: Dict[str, Any],
) -> str:
    markdown_config = config.get("markdown", {})
    lines: List[str] = []

    lines.append(f"# AI 日报 - {date.strftime('%Y-%m-%d')}")
    lines.append("")
    est_reading_time = max(1, int(total_count * 0.3))
    lines.append(f"共筛出 {total_count} 条，必看 {must_read_count} 条，预计阅读 {est_reading_time} 分钟。")
    lines.append("")

    overview = _generate_daily_overview(focus_items, items_by_topic)
    lines.append("## 今日结论")
    lines.append("")
    lines.append(overview["summary"])
    lines.append("")
    if overview["top_topics"]:
        lines.append("重点方向：" + " | ".join(overview["top_topics"]))
        lines.append("")
    if overview["watch_points"]:
        lines.append("重点关注：")
        for point in overview["watch_points"]:
            lines.append(f"- {point}")
        lines.append("")

    lines.append("## 必看")
    lines.append("")
    if focus_items:
        for idx, item in enumerate(focus_items, 1):
            lines.extend(_format_focus_item(item, idx, markdown_config))
    else:
        lines.append("- 当前没有条目达到展示阈值。")
        lines.append("")

    if items_by_topic:
        lines.append("## 其他值得扫一眼")
        lines.append("")
        for topic, topic_items in sorted(items_by_topic.items(), key=lambda x: (-len(x[1]), x[0])):
            lines.append(f"### {topic}")
            lines.append("")
            for item in topic_items[:topic_item_limit]:
                lines.extend(_format_compact_item(item))
            lines.append("")

    if focus_items:
        lines.append("## 一句话判断")
        lines.append("")
        lines.append(_one_line_takeaway(focus_items))
        lines.append("")

    return "\n".join(lines)


def _generate_daily_overview(
    focus_items: List[Item],
    items_by_topic: Dict[str, List[Item]],
) -> Dict[str, List[str] | str]:
    topic_counts = Counter()
    for topic, items in items_by_topic.items():
        topic_counts[topic] += len(items)
    for item in focus_items:
        topic_counts[_primary_topic(item)] += 1

    top_topics = [f"{topic}（{count}）" for topic, count in topic_counts.most_common(3)]
    if focus_items:
        summary = "今天主要围绕" + " / ".join(_headline_phrase(item) for item in focus_items[:3]) + "展开。"
    else:
        summary = "今天以常规 AI 工程和产品更新为主，没有特别突出的单点突破。"

    watch_points: List[str] = []
    for item in focus_items[:3]:
        point = _watch_point(item)
        if point not in watch_points:
            watch_points.append(point)

    return {"summary": summary, "top_topics": top_topics, "watch_points": watch_points}


def _format_focus_item(item: Item, idx: int, markdown_config: Dict[str, Any]) -> List[str]:
    lines = []
    lines.append(f"### {idx}. [{item.title}]({item.url})")
    lines.append("")
    lines.append(
        f"- 来源：{item.source} | 时间：{item.published.strftime('%Y-%m-%d')} | 评分：{item.score:.0f}"
    )
    lines.append(f"- 发生了什么：{_short_summary(item, markdown_config.get('max_summary_length', 180))}")
    lines.append(f"- 为什么重要：{_why_it_matters(item)}")
    lines.append(f"- 直接结论：{_watch_point(item)}")
    lines.append(f"- 你现在可以做：{_integration_note(item)}")
    lines.append(f"- 简单 demo：{_demo_hint(item)}")
    code_demo = _code_demo(item)
    if code_demo:
        lines.append(f"- 最小代码：`{code_demo}`")

    if item.key_points:
        lines.append("- 关键点：")
        for point in item.key_points[:3]:
            lines.append(f"  - {point}")
    elif item.action and markdown_config.get("include_action", True):
        lines.append(f"- 关键点：{item.action}")

    lines.append("")
    return lines


def _format_compact_item(item: Item) -> List[str]:
    return [
        f"- [{item.title}]({item.url})",
        f"  - {item.source} | {item.published.strftime('%Y-%m-%d')} | 评分 {item.score:.0f}",
        f"  - {_short_summary(item, 120)}",
    ]


def _short_summary(item: Item, max_len: int) -> str:
    summary = item.ai_summary or item.summary or item.title
    summary = " ".join(summary.split())
    if len(summary) <= max_len:
        return summary
    return summary[: max_len - 3].rstrip() + "..."


def _primary_topic(item: Item) -> str:
    return item.tags[0] if item.tags else "其他"


def _headline_phrase(item: Item) -> str:
    text = f"{item.title} {item.ai_summary or item.summary or ''}".lower()
    if any(word in text for word in ["safety", "security", "policy", "guardrail", "teen"]):
        return "AI 安全与治理"
    if any(word in text for word in ["commerce", "shopping", "comparison", "discovery"]):
        return "商业化工作流扩展"
    if any(word in text for word in ["foundation", "investment", "fund", "community"]):
        return "生态布局与资源投入"
    if any(word in text for word in ["release", "launch", "preview", "available", "api", "sdk"]):
        return "新模型或新产品发布"
    return "重要平台更新"


def _why_it_matters(item: Item) -> str:
    text = f"{item.title} {item.ai_summary or item.summary or ''}".lower()
    if any(word in text for word in ["safety", "teen", "security", "governance", "policy"]):
        return "这类变化可能会逐步变成合规、审核或产品安全的默认基线。"
    if any(word in text for word in ["commerce", "shopping", "comparison", "product discovery"]):
        return "这说明助手正在从问答入口走向交易、推荐和转化入口。"
    if any(word in text for word in ["foundation", "investment", "fund", "community"]):
        return "这更像长期生态和战略信号，而不是立刻要改代码的工程变更。"
    if any(word in text for word in ["release", "launch", "preview", "api", "sdk"]):
        return "这会直接影响工具选型、升级计划和后续接入策略。"
    return "这条更新值得持续跟，因为它可能影响后续产品和工程判断。"


def _watch_point(item: Item) -> str:
    if item.action:
        return item.action
    text = f"{item.title} {item.ai_summary or item.summary or ''}".lower()
    if any(word in text for word in ["safety", "teen", "security", "policy"]):
        return "需要评估是否影响现有安全审核、策略配置和接入门槛。"
    if any(word in text for word in ["commerce", "shopping", "comparison", "discovery"]):
        return "暂不跟进，除非你正在做推荐、导购或交易闭环。"
    if any(word in text for word in ["foundation", "investment", "fund"]):
        return "仅记录战略信号，不需要马上投入研发资源。"
    if any(word in text for word in ["api", "sdk", "release", "launch", "preview"]):
        return "建议先评估文档、价格和升级影响，再决定是否接入生产。"
    if any(word in text for word in ["evaluation", "benchmark", "testing", "test"]):
        return "可优先评估是否纳入研发验收、回归或自动化测试。"
    return "暂不跟进，除非它直接影响现有研发流程。"


def _integration_note(item: Item) -> str:
    text = f"{item.title} {item.ai_summary or item.summary or ''} {' '.join(item.key_points)}".lower()
    conclusion = _watch_point(item)

    if "system card" in text:
        return "今天先不用做任何接入；只有当你准备升级这个模型时，再回来看它的限制、风险和不适用场景。"
    if "automation" in text or "schedule" in text or "trigger" in text:
        return "如果你现在有重复手工活，比如整理日报、周报、监控结果，就挑 1 个先自动化；没有就先跳过。"
    if "研发验收" in conclusion or "自动化测试" in conclusion or any(
        word in text for word in ["evaluation", "benchmark", "testing", "test", "system card"]
    ):
        return "今天先选 3 个你最常见的任务试跑一遍，比如写代码、改 Bug、生成测试用例；如果有 2 个明显更好，再安排小范围试用。"
    if "回归" in conclusion:
        return "把它加入你平时固定会重跑的测试题，下次模型升级时再跑一次，重点看结果有没有变差。"
    if "poc" in conclusion.lower() or any(word in text for word in ["performance", "faster", "latency"]):
        return "先试用半天到一天，只看三件事：速度有没有更快、结果有没有更好、成本有没有高太多。"
    if any(word in text for word in ["release", "launch", "api", "sdk", "gpt-", "claude", "gemini", "llama"]):
        return "先不要全量替换，只挑一个最不重要的小场景试用，比如内部工具或个人任务，确认好用再扩大。"
    if any(word in text for word in ["security", "vulnerability", "cve", "policy"]):
        return "先看你现在的权限、安全审核和日志记录会不会受影响；如果会，就优先排进本周处理。"
    return "今天先不用做事；只有当它和你正在做的开发、测试或接入直接相关时，再回来处理。"


def _demo_hint(item: Item) -> str:
    text = f"{item.title} {item.ai_summary or item.summary or ''} {' '.join(item.key_points)}".lower()

    if "gpt-" in text or "claude" in text or "gemini" in text or "llama" in text:
        return "拿同一个 Bug 描述，分别让新旧模型生成修复方案和测试用例，直接比结果。"
    if "system card" in text:
        return "升级前先看这一篇，重点找“限制”“不适用场景”“高风险用法”三部分。"
    if "automation" in text or "schedule" in text or "trigger" in text:
        return "把“每天整理 3 条 AI 新闻”这件事设成自动任务，先跑一天看是否省时间。"
    if any(word in text for word in ["evaluation", "benchmark", "testing", "test"]):
        return "选 3 道你常测的题，分别跑新旧方案，看正确率和稳定性。"
    if any(word in text for word in ["api", "sdk", "release", "launch"]):
        return "先在内部脚本里接一个最小调用，确认能跑通，再决定要不要正式接。"
    if any(word in text for word in ["security", "vulnerability", "cve", "policy"]):
        return "对照你当前权限、日志和审核流程看一遍，找出会受影响的地方。"
    return "如果这条和你手头工作无关，就先跳过，不用专门做演示。"


def _code_demo(item: Item) -> str:
    text = f"{item.title} {item.ai_summary or item.summary or ''} {' '.join(item.key_points)}".lower()

    if "gpt-" in text or "claude" in text or "gemini" in text or "llama" in text:
        return "resp = client.chat.completions.create(model='gpt-5.5', messages=[{'role':'user','content':'修复登录Bug并补3条测试用例'}])"
    if "automation" in text or "schedule" in text or "trigger" in text:
        return "python -m src.main daily"
    if any(word in text for word in ["evaluation", "benchmark", "testing", "test"]):
        return "for case in cases: print(run_new(case), run_old(case))"
    if any(word in text for word in ["api", "sdk", "release", "launch"]):
        return "client.chat.completions.create(model='gpt-5.5', messages=[{'role':'user','content':'写一个最小 FastAPI 接口'}])"
    return ""


def _one_line_takeaway(focus_items: List[Item]) -> str:
    phrases = []
    for item in focus_items[:3]:
        phrase = _headline_phrase(item)
        if phrase not in phrases:
            phrases.append(phrase)
    return "今天真正值得盯的，不是信息量，而是" + "、".join(phrases) + "。"


def generate_weekly_report(
    items: List[Item], output_dir: str, week_start: datetime, config: Dict[str, Any]
) -> str:
    """生成周报 Markdown 文件。"""
    logger.info("开始生成周报，输入条目数: %s", len(items))

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    year, week_num, _ = week_start.isocalendar()
    filepath = output_path / f"{year}-W{week_num:02d}.md"

    max_items = config.get("max_items", 120)
    min_score = config.get("min_score", 50)

    filtered_items = [item for item in items if item.score >= min_score]
    filtered_items = filtered_items[:max_items]

    md_content = _generate_weekly_markdown(week_start, filtered_items, config)
    filepath.write_text(md_content, encoding="utf-8")

    logger.info("周报已写入 %s", filepath)
    return str(filepath)


def _generate_weekly_markdown(
    week_start: datetime, items: List[Item], config: Dict[str, Any]
) -> str:
    """生成周报 Markdown 内容。"""
    lines: List[str] = []

    year, week_num, _ = week_start.isocalendar()
    lines.append(f"# AI 周报 - {year} W{week_num:02d}")
    lines.append("")

    lines.append("## 本周概览")
    lines.append("")
    lines.append(_generate_overview(items))
    lines.append("")
    lines.append("---")
    lines.append("")

    trend_count = config.get("trend_count", 5)
    trends = _extract_trends(items, trend_count)
    lines.append(f"## 本周重点趋势 Top {trend_count}")
    lines.append("")
    for idx, trend in enumerate(trends, 1):
        lines.append(f"### {idx}. {trend['title']}")
        lines.append("")
        for item in trend["items"]:
            lines.append(f"- [{item.title}]({item.url})")
        lines.append(f"- 趋势说明：{trend['description']}")
        lines.append("")

    lines.append("---")
    lines.append("")

    must_do_count = config.get("must_do_count", 3)
    must_dos = _extract_must_dos(items, must_do_count)
    lines.append(f"## 本周应关注 Top {must_do_count}")
    lines.append("")
    for idx, item in enumerate(must_dos, 1):
        lines.append(f"{idx}. **{item.action or '持续关注这条更新'}**：{item.title} - {item.source}")
    lines.append("")
    lines.append("---")
    lines.append("")

    watchlist_count = config.get("watchlist_count", 5)
    watchlist = _generate_watchlist(items, watchlist_count)
    lines.append("## 下周关注清单")
    lines.append("")
    for item in watchlist:
        lines.append(f"- [ ] {item}")
    lines.append("")

    return "\n".join(lines)


def _generate_overview(items: List[Item]) -> str:
    """生成周报总览。"""
    tag_counts = Counter()
    for item in items:
        for tag in item.tags:
            tag_counts[tag] += 1

    top_topics = [f"{topic}（{count}）" for topic, count in tag_counts.most_common(5)]
    high_score_count = len([item for item in items if item.score >= 80])
    topic_text = " | ".join(top_topics) if top_topics else "暂无明显主题集中"

    return (
        f"本周共筛出 {len(items)} 条 AI 更新，其中高分条目 {high_score_count} 条。"
        f"主要主题包括：{topic_text}。"
    )


def _extract_trends(items: List[Item], count: int) -> List[Dict[str, Any]]:
    """提取周报趋势。"""
    topic_items: Dict[str, List[Item]] = defaultdict(list)
    for item in items:
        for tag in item.tags:
            topic_items[tag].append(item)

    topic_scores = {
        topic: sum(entry.score for entry in entries)
        for topic, entries in topic_items.items()
    }
    top_topics = sorted(topic_scores.items(), key=lambda x: -x[1])[:count]

    trends = []
    for topic, _ in top_topics:
        entries = topic_items[topic]
        top_items = sorted(entries, key=lambda x: -x.score)[:3]
        trends.append(
            {
                "title": topic,
                "items": top_items,
                "description": f"{topic} 本周共有 {len(entries)} 条值得跟进的更新。",
            }
        )
    return trends


def _extract_must_dos(items: List[Item], count: int) -> List[Item]:
    """提取本周应关注条目。"""
    must_read = [item for item in items if item.is_must_read and item.action]
    must_read.sort(key=lambda x: -x.score)
    return must_read[:count]


def _generate_watchlist(items: List[Item], count: int) -> List[str]:
    """生成下周关注清单。"""
    watchlist: List[str] = []
    keywords = ["upcoming", "soon", "next", "beta", "rc", "preview", "roadmap"]

    for item in items:
        text = (item.title + " " + (item.summary or "")).lower()
        if any(keyword in text for keyword in keywords):
            watchlist.append(f"{item.source}: {item.title}")

    if len(watchlist) < count:
        high_score_items = sorted(items, key=lambda x: -x.score)
        for item in high_score_items:
            entry = f"{item.source}: {item.title}"
            if entry not in watchlist:
                watchlist.append(entry)
            if len(watchlist) >= count:
                break

    return watchlist[:count]


__all__ = ["generate_daily_report", "generate_weekly_report"]
