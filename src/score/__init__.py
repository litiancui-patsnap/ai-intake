"""评分模块"""

import math
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List

from ..ingest.models import Item
from ..utils.logger import get_logger

logger = get_logger("score")


class Scorer:
    """评分器"""

    def __init__(self, config: Dict[str, Any], topics: List[Dict[str, Any]]):
        """初始化评分器

        Args:
            config: 评分配置（来自rules.yaml的scoring部分）
            topics: 主题配置列表
        """
        self.config = config
        self.topics = {t["name"]: t for t in topics}

        # 权重配置
        self.weights = config.get("weights", {})
        self.research_keywords = config.get("research_keywords", {})
        self.engineering_keywords = config.get("engineering_keywords", {})
        self.freshness_config = config.get("freshness", {})

    def score_item(self, item: Item, preferences: Dict[str, Any]) -> float:
        """为Item评分

        Args:
            item: 待评分的Item
            preferences: 个人偏好配置

        Returns:
            评分 (0-100)
        """
        # 计算各维度得分
        research_score = self._score_research_signal(item)
        engineering_score = self._score_engineering_signal(item)
        authority_score = self._score_authority(item)
        freshness_score = self._score_freshness(item)
        preference_score = self._score_preference(item, preferences)

        # 加权求和
        total_score = (
            research_score * self.weights.get("research_signal", 0.25)
            + engineering_score * self.weights.get("engineering_signal", 0.35)
            + authority_score * self.weights.get("authority", 0.20)
            + freshness_score * self.weights.get("freshness", 0.10)
            + preference_score * self.weights.get("preference", 0.10)
        ) * 100

        # 主题boost加权
        for tag in item.tags:
            topic = self.topics.get(tag)
            if topic:
                boost = topic.get("boost", 1.0)
                if boost != 1.0:
                    total_score *= boost

        # 限制在0-100范围内
        total_score = max(0, min(100, total_score))

        # 记录评分详解
        item.score = total_score
        item.score_breakdown = {
            "total": round(total_score, 1),
            "research_signal": round(research_score, 1),
            "engineering_signal": round(engineering_score, 1),
            "authority": round(authority_score, 1),
            "freshness": round(freshness_score, 1),
            "preference": round(preference_score, 1),
            "reasons": self._generate_reasons(
                item, research_score, engineering_score, authority_score, preference_score
            ),
        }

        return total_score

    def _score_research_signal(self, item: Item) -> float:
        """计算研究信号评分

        Args:
            item: Item

        Returns:
            评分 (0-25)
        """
        score = 0.0
        text = self._get_searchable_text(item).lower()

        # 高价值关键词 (+5分)
        for keyword in self.research_keywords.get("high_value", []):
            if keyword.lower() in text:
                score += 5
                if score >= 25:
                    return 25

        # 中等价值关键词 (+3分)
        for keyword in self.research_keywords.get("medium_value", []):
            if keyword.lower() in text:
                score += 3
                if score >= 25:
                    return 25

        # 低价值关键词 (+1分)
        for keyword in self.research_keywords.get("low_value", []):
            if keyword.lower() in text:
                score += 1
                if score >= 25:
                    return 25

        return min(score, 25)

    def _score_engineering_signal(self, item: Item) -> float:
        """计算工程信号评分

        Args:
            item: Item

        Returns:
            评分 (0-35)
        """
        score = 0.0
        text = self._get_searchable_text(item).lower()

        # 关键信号 (+7分)
        for keyword in self.engineering_keywords.get("critical", []):
            if keyword.lower() in text:
                score += 7
                if score >= 35:
                    return 35

        # 高价值信号 (+5分)
        for keyword in self.engineering_keywords.get("high_value", []):
            if keyword.lower() in text:
                score += 5
                if score >= 35:
                    return 35

        # 中等价值信号 (+3分)
        for keyword in self.engineering_keywords.get("medium_value", []):
            if keyword.lower() in text:
                score += 3
                if score >= 35:
                    return 35

        return min(score, 35)

    def _score_authority(self, item: Item) -> float:
        """计算来源权威度评分

        Args:
            item: Item

        Returns:
            评分 (0-20)
        """
        authority = item.raw_data.get("authority_score", 50)
        # 映射50-100到0-20
        return (authority - 50) * 0.4

    def _score_freshness(self, item: Item) -> float:
        """计算新鲜度评分

        Args:
            item: Item

        Returns:
            评分 (0-10)
        """
        max_score = self.freshness_config.get("max_score", 10)
        decay_hours = self.freshness_config.get("decay_hours", 48)

        now = datetime.now()

        # 处理时区问题：如果published有时区信息，移除时区使其变为naive datetime
        published = item.published
        if published.tzinfo is not None:
            published = published.replace(tzinfo=None)

        age_hours = (now - published).total_seconds() / 3600

        # 指数衰减
        score = max_score * math.exp(-age_hours / decay_hours)

        return max(0, min(max_score, score))

    def _score_preference(self, item: Item, preferences: Dict[str, Any]) -> float:
        """计算个人偏好评分

        Args:
            item: Item
            preferences: 个人偏好配置

        Returns:
            评分 (0-10)
        """
        score = 0.0
        text = self._get_searchable_text(item).lower()

        # 优先公司 (+3分)
        for vendor in preferences.get("priority_vendors", []):
            if vendor.lower() in text:
                score += 3
                break

        # 优先工具 (+2分)
        for tool in preferences.get("priority_tools", []):
            if tool.lower() in text:
                score += 2
                break

        # 优先主题 (+2分)
        priority_topics = preferences.get("priority_topics", [])
        for tag in item.tags:
            if tag in priority_topics:
                score += 2
                break

        # 低优先级主题 (-2分)
        low_priority_topics = preferences.get("low_priority_topics", [])
        for tag in item.tags:
            if tag in low_priority_topics:
                score -= 2
                break

        return max(0, min(10, score))

    def _get_searchable_text(self, item: Item) -> str:
        """获取可搜索文本

        Args:
            item: Item

        Returns:
            合并后的文本
        """
        return " ".join(
            filter(
                None,
                [
                    item.title,
                    item.summary or "",
                    item.content or "",
                ],
            )
        )

    def _generate_reasons(
        self,
        item: Item,
        research_score: float,
        engineering_score: float,
        authority_score: float,
        preference_score: float,
    ) -> List[str]:
        """生成评分理由

        Args:
            item: Item
            research_score: 研究信号评分
            engineering_score: 工程信号评分
            authority_score: 权威度评分
            preference_score: 偏好评分

        Returns:
            理由列表
        """
        reasons = []

        # 权威度
        if authority_score >= 15:
            reasons.append(f"来自高权威源: {item.source}")
        elif authority_score >= 10:
            reasons.append(f"来自中等权威源: {item.source}")

        # 工程信号
        if engineering_score >= 20:
            text_lower = self._get_searchable_text(item).lower()
            if any(kw in text_lower for kw in ["breaking", "deprecat"]):
                reasons.append("工程信号: 破坏性变更")
            elif any(kw in text_lower for kw in ["release", "launch", "available"]):
                reasons.append("工程信号: 新版本发布")
            elif any(kw in text_lower for kw in ["performance", "faster", "speedup"]):
                reasons.append("工程信号: 性能优化")
            else:
                reasons.append("工程信号: 重要更新")

        # 研究信号
        if research_score >= 15:
            text_lower = self._get_searchable_text(item).lower()
            if any(kw in text_lower for kw in ["sota", "state-of-the-art", "breakthrough"]):
                reasons.append("研究信号: 突破性成果")
            elif any(kw in text_lower for kw in ["benchmark", "evaluation"]):
                reasons.append("研究信号: 评测结果")
            else:
                reasons.append("研究信号: 新研究")

        # 主题
        if item.tags:
            top_tags = ", ".join(item.tags[:3])
            reasons.append(f"命中关注主题: {top_tags}")

        # 偏好
        if preference_score >= 5:
            reasons.append("符合个人偏好")

        return reasons


def score_batch(
    items: List[Item], config: Dict[str, Any], topics: List[Dict[str, Any]], preferences: Dict[str, Any]
) -> List[Item]:
    """批量评分

    Args:
        items: Item列表
        config: 评分配置
        topics: 主题配置列表
        preferences: 个人偏好配置

    Returns:
        评分后的Item列表（原地修改，并按分数降序排序）
    """
    logger.info(f"开始评分: {len(items)} 条数据")

    scorer = Scorer(config, topics)

    for item in items:
        scorer.score_item(item, preferences)

    # 按分数降序排序
    items.sort(key=lambda x: x.score, reverse=True)

    # 统计
    if items:
        avg_score = sum(item.score for item in items) / len(items)
        max_score = max(item.score for item in items)
        min_score = min(item.score for item in items)
        logger.info(
            f"评分完成: 平均 {avg_score:.1f}, 最高 {max_score:.1f}, 最低 {min_score:.1f}"
        )

    return items


def mark_must_read(items: List[Item], rules: List[Dict[str, str]], topics: Dict[str, Any]) -> List[Item]:
    """标记必读

    Args:
        items: Item列表
        rules: 必读规则列表
        topics: 主题配置字典

    Returns:
        标记后的Item列表（原地修改）
    """
    logger.info(f"开始标记必读: {len(items)} 条数据，{len(rules)} 条规则")

    must_read_count = 0

    for item in items:
        # 先检查主题的must_read_if_score_above规则
        for tag in item.tags:
            topic = topics.get(tag)
            if topic:
                threshold = topic.get("must_read_if_score_above")
                if threshold and item.score >= threshold:
                    item.is_must_read = True
                    logger.debug(
                        f"必读 (主题阈值): {item.title} (分数: {item.score:.1f}, 阈值: {threshold})"
                    )
                    must_read_count += 1
                    break

        # 再检查通用必读规则
        if not item.is_must_read:
            for rule in rules:
                condition = rule.get("condition", "")
                reason = rule.get("reason", "")

                if _eval_condition(condition, item):
                    item.is_must_read = True
                    logger.debug(f"必读 ({reason}): {item.title}")
                    must_read_count += 1
                    break

    logger.info(f"标记完成: {must_read_count} 条必读")

    return items


def _eval_condition(condition: str, item: Item) -> bool:
    """评估必读条件

    Args:
        condition: 条件表达式
        item: Item

    Returns:
        是否满足条件
    """
    try:
        # 定义可用的函数和变量
        context = {
            "score": item.score,
            "authority_score": item.raw_data.get("authority_score", 50),
            "source": item.source,
            "title": item.title.lower(),
            "tags": item.tags,
            "contains": lambda keyword: keyword.lower() in item.title.lower()
            or keyword.lower() in (item.summary or "").lower(),
            "source_contains": lambda keyword: keyword.lower() in item.source.lower(),
            "contains_any": lambda keywords: any(
                kw.lower() in item.title.lower() or kw.lower() in (item.summary or "").lower()
                for kw in keywords
            ),
        }

        # 安全评估
        result = eval(condition, {"__builtins__": {}}, context)
        return bool(result)

    except Exception as e:
        logger.warning(f"评估条件失败 '{condition}': {e}")
        return False


__all__ = ["Scorer", "score_batch", "mark_must_read"]
