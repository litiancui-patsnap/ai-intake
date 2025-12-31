"""摘要模块"""

import json
import re
from typing import Any, Dict, List, Optional

from ..ingest.models import Item
from ..utils.logger import get_logger

logger = get_logger("summarize")


class BaseSummarizer:
    """摘要器基类"""

    def summarize(self, item: Item) -> Dict[str, Any]:
        """生成摘要

        Args:
            item: 待摘要的Item

        Returns:
            包含summary, key_points, action的字典
        """
        raise NotImplementedError


class LLMSummarizer(BaseSummarizer):
    """LLM摘要器"""

    def __init__(self, config: Dict[str, Any]):
        """初始化LLM摘要器

        Args:
            config: LLM配置
        """
        self.config = config
        self.provider = config.get("provider", "openai")
        self.model = config.get("model", "gpt-4o-mini")
        self.max_tokens = config.get("max_tokens", 500)
        self.temperature = config.get("temperature", 0.3)
        self.timeout = config.get("timeout", 30)
        self.api_key = config.get("api_key")

        if not self.api_key:
            raise ValueError(f"缺少{self.provider} API密钥")

        # 初始化客户端
        if self.provider == "openai":
            from openai import OpenAI

            self.client = OpenAI(api_key=self.api_key, timeout=self.timeout)
        elif self.provider == "anthropic":
            from anthropic import Anthropic

            self.client = Anthropic(api_key=self.api_key, timeout=self.timeout)
        else:
            raise ValueError(f"不支持的LLM提供商: {self.provider}")

    def summarize(self, item: Item) -> Dict[str, Any]:
        """使用LLM生成摘要

        Args:
            item: Item

        Returns:
            包含summary, key_points, action的字典
        """
        try:
            # 构建prompt
            content = self._build_content(item)
            prompt = self._build_prompt(item, content)

            # 调用LLM
            if self.provider == "openai":
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                )
                result_text = response.choices[0].message.content
            elif self.provider == "anthropic":
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    messages=[{"role": "user", "content": prompt}],
                )
                result_text = response.content[0].text
            else:
                raise ValueError(f"不支持的提供商: {self.provider}")

            # 解析结果
            result = self._parse_result(result_text)
            return result

        except Exception as e:
            logger.error(f"LLM摘要生成失败: {e}")
            raise

    def _build_content(self, item: Item) -> str:
        """构建输入内容

        Args:
            item: Item

        Returns:
            内容字符串
        """
        # 优先使用content，其次summary，最后title
        if item.content and len(item.content) > 100:
            # 限制长度避免token超限
            return item.content[:3000]
        elif item.summary:
            return item.summary
        else:
            return item.title

    def _build_prompt(self, item: Item, content: str) -> str:
        """构建提示词

        Args:
            item: Item
            content: 内容

        Returns:
            提示词
        """
        return f"""你是一个资深AI工程师。请阅读以下AI领域的信息并输出：

1. 中文摘要 (100-180字，重点说明技术要点和影响)
2. 工程师要点 (3条bullet points，每条不超过30字，聚焦可操作的技术细节)
3. 行动建议 (1条，"我该做什么"或"何时关注"，不超过40字)

标题: {item.title}
来源: {item.source}
原文:
{content}

输出JSON格式:
{{
  "summary": "中文摘要...",
  "key_points": ["要点1", "要点2", "要点3"],
  "action": "行动建议"
}}

只输出JSON，不要其他内容。"""

    def _parse_result(self, result_text: str) -> Dict[str, Any]:
        """解析LLM返回结果

        Args:
            result_text: LLM返回的文本

        Returns:
            解析后的字典
        """
        try:
            # 尝试提取JSON
            json_match = re.search(r"\{.*\}", result_text, re.DOTALL)
            if json_match:
                result_text = json_match.group(0)

            result = json.loads(result_text)

            # 验证字段
            if "summary" not in result or "key_points" not in result or "action" not in result:
                raise ValueError("缺少必要字段")

            return result

        except Exception as e:
            logger.warning(f"解析LLM结果失败: {e}, 原始文本: {result_text[:200]}")
            # 返回原始文本作为摘要
            return {
                "summary": result_text[:200],
                "key_points": [],
                "action": "",
            }


class ExtractiveSummarizer(BaseSummarizer):
    """抽取式摘要器（Fallback）"""

    def summarize(self, item: Item) -> Dict[str, Any]:
        """生成抽取式摘要

        Args:
            item: Item

        Returns:
            包含summary, key_points, action的字典
        """
        # 使用现有的summary，或提取content的前200字
        if item.summary and len(item.summary) > 50:
            summary = item.summary[:200]
        elif item.content:
            summary = item.content[:200]
        else:
            summary = item.title

        # 简单的key_points提取（基于句子）
        key_points = self._extract_key_points(item)

        # 简单的action建议
        action = self._generate_action(item)

        return {
            "summary": summary,
            "key_points": key_points,
            "action": action,
        }

    def _extract_key_points(self, item: Item) -> List[str]:
        """提取关键点

        Args:
            item: Item

        Returns:
            关键点列表
        """
        text = item.content or item.summary or item.title

        # 按句子分割
        sentences = re.split(r"[。！？\n]|\.(?:\s|$)", text)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 20]

        # 简单启发式：包含关键词的句子
        keywords = ["new", "release", "improve", "faster", "better", "support", "feature", "api"]
        scored_sentences = []

        for sent in sentences[:10]:  # 只看前10句
            score = sum(1 for kw in keywords if kw.lower() in sent.lower())
            if score > 0:
                scored_sentences.append((score, sent))

        # 取top 3
        scored_sentences.sort(key=lambda x: -x[0])
        key_points = [sent[:80] + "..." if len(sent) > 80 else sent for score, sent in scored_sentences[:3]]

        return key_points if key_points else [item.title[:80]]

    def _generate_action(self, item: Item) -> str:
        """生成行动建议

        Args:
            item: Item

        Returns:
            行动建议
        """
        text = (item.title + " " + (item.summary or "")).lower()

        if "release" in text or "available" in text:
            return "关注新版本，评估升级影响"
        elif "breaking" in text or "deprecat" in text:
            return "检查代码兼容性，制定迁移计划"
        elif "security" in text or "vulnerability" in text:
            return "立即评估安全影响并更新"
        elif "performance" in text or "faster" in text:
            return "评估性能提升，考虑采用"
        else:
            return "了解新功能，评估是否适用"


def summarize_batch(items: List[Item], config: Dict[str, Any]) -> List[Item]:
    """批量生成摘要

    Args:
        items: Item列表
        config: LLM配置

    Returns:
        生成摘要后的Item列表（原地修改）
    """
    if not config.get("enabled", True):
        logger.info("LLM摘要已禁用，跳过")
        return items

    logger.info(f"开始生成摘要: {len(items)} 条数据")

    # 尝试使用LLM
    summarizer: Optional[BaseSummarizer] = None

    try:
        summarizer = LLMSummarizer(config)
        logger.info(f"使用LLM摘要器: {config.get('provider')} / {config.get('model')}")
    except Exception as e:
        logger.warning(f"初始化LLM摘要器失败: {e}")
        if config.get("fallback_to_extractive", True):
            logger.info("降级到抽取式摘要器")
            summarizer = ExtractiveSummarizer()
        else:
            logger.error("LLM摘要器不可用且未启用fallback，跳过摘要生成")
            return items

    # 批量处理
    success_count = 0
    failed_count = 0
    batch_size = config.get("batch_size", 10)

    for i in range(0, len(items), batch_size):
        batch = items[i : i + batch_size]

        for item in batch:
            try:
                result = summarizer.summarize(item)
                item.ai_summary = result.get("summary", "")
                item.key_points = result.get("key_points", [])
                item.action = result.get("action", "")
                success_count += 1
            except Exception as e:
                logger.error(f"生成摘要失败 '{item.title}': {e}")
                failed_count += 1

                # 降级到extractive
                if isinstance(summarizer, LLMSummarizer) and config.get("fallback_to_extractive", True):
                    try:
                        fallback = ExtractiveSummarizer()
                        result = fallback.summarize(item)
                        item.ai_summary = result.get("summary", "")
                        item.key_points = result.get("key_points", [])
                        item.action = result.get("action", "")
                        logger.info(f"使用fallback成功: {item.title}")
                    except Exception as e2:
                        logger.error(f"Fallback也失败: {e2}")

        # 批次间短暂休息避免rate limit
        if i + batch_size < len(items) and isinstance(summarizer, LLMSummarizer):
            import time
            time.sleep(1)

    logger.info(f"摘要生成完成: 成功 {success_count}, 失败 {failed_count}")

    return items


__all__ = ["LLMSummarizer", "ExtractiveSummarizer", "summarize_batch"]
