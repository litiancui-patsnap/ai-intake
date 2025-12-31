"""RSS/Atom Feed采集器"""

import time
from datetime import datetime
from typing import Any, Dict, List
from urllib.parse import urlparse

import feedparser
import requests
from dateutil import parser as date_parser

from ..utils.logger import get_logger
from .base import BaseFetcher
from .models import Item

logger = get_logger("ingest.rss")


class RSSFetcher(BaseFetcher):
    """RSS/Atom Feed采集器"""

    def fetch(self, source: Dict[str, Any]) -> List[Item]:
        """采集RSS/Atom Feed

        Args:
            source: 信息源配置

        Returns:
            Item列表
        """
        url = source.get("url")
        if not url:
            logger.error(f"信息源 {source.get('name')} 缺少URL")
            return []

        items = []
        last_error = None

        for attempt in range(self.max_retries):
            try:
                logger.debug(f"正在采集 {source.get('name')} (尝试 {attempt + 1}/{self.max_retries})")

                # 使用requests先获取内容，以便控制超时和重试
                response = requests.get(
                    url, headers=self._get_headers(), timeout=self.timeout
                )
                response.raise_for_status()

                # 使用feedparser解析
                feed = feedparser.parse(response.content)

                if feed.bozo:
                    logger.warning(
                        f"Feed解析警告 {source.get('name')}: {feed.get('bozo_exception')}"
                    )

                # 解析条目
                for entry in feed.entries:
                    item = self._parse_entry(entry, source)
                    if item:
                        items.append(item)

                logger.info(f"成功采集 {source.get('name')}: {len(items)} 条")
                return items

            except requests.Timeout:
                last_error = f"超时"
                logger.warning(f"采集超时 {source.get('name')} (尝试 {attempt + 1}/{self.max_retries})")
            except requests.RequestException as e:
                last_error = str(e)
                logger.warning(
                    f"采集失败 {source.get('name')}: {e} (尝试 {attempt + 1}/{self.max_retries})"
                )
            except Exception as e:
                last_error = str(e)
                logger.error(f"采集异常 {source.get('name')}: {e}")
                break  # 非网络错误不重试

            # 重试前等待
            if attempt < self.max_retries - 1:
                time.sleep(self.retry_delay)

        logger.error(f"采集失败 {source.get('name')} (已重试{self.max_retries}次): {last_error}")
        return items

    def _parse_entry(self, entry: Any, source: Dict[str, Any]) -> Item:
        """解析Feed条目

        Args:
            entry: feedparser的entry对象
            source: 信息源配置

        Returns:
            Item实例，如果解析失败返回None
        """
        try:
            # 提取URL
            url = entry.get("link", "")
            if not url:
                logger.debug("条目缺少URL，跳过")
                return None

            # 提取标题
            title = entry.get("title", "").strip()
            if not title:
                logger.debug(f"条目缺少标题: {url}")
                return None

            # 提取发布时间
            published = self._parse_date(entry)
            if not published:
                logger.debug(f"条目缺少发布时间: {url}")
                published = datetime.now()  # 使用当前时间作为fallback

            # 提取作者
            author = entry.get("author", "") or entry.get("dc_creator", "")

            # 提取摘要
            summary = entry.get("summary", "") or entry.get("description", "")
            # 清理HTML标签
            if summary:
                from bs4 import BeautifulSoup

                summary = BeautifulSoup(summary, "html.parser").get_text().strip()

            # 提取内容
            content = ""
            if hasattr(entry, "content"):
                content = entry.content[0].get("value", "")
            elif "content" in entry:
                content = entry["content"][0].get("value", "")
            else:
                content = summary

            # 清理HTML标签
            if content:
                from bs4 import BeautifulSoup

                content = BeautifulSoup(content, "html.parser").get_text().strip()

            # 创建Item
            item = Item(
                url=url,
                title=title,
                published=published,
                source=source.get("name", ""),
                author=author,
                summary=summary[:500] if summary else None,  # 限制摘要长度
                content=content[:5000] if content else None,  # 限制内容长度
                raw_data={
                    "source_url": source.get("url"),
                    "authority_score": source.get("authority_score", 50),
                    "source_tags": source.get("tags", []),
                },
            )

            return item

        except Exception as e:
            logger.error(f"解析条目失败: {e}")
            return None

    def _parse_date(self, entry: Any) -> datetime:
        """解析日期

        Args:
            entry: feedparser的entry对象

        Returns:
            datetime对象，如果解析失败返回None
        """
        # 尝试多个日期字段
        date_fields = [
            "published_parsed",
            "updated_parsed",
            "created_parsed",
            "published",
            "updated",
            "created",
        ]

        for field in date_fields:
            date_value = entry.get(field)
            if not date_value:
                continue

            try:
                # 如果是time.struct_time
                if hasattr(date_value, "tm_year"):
                    return datetime(*date_value[:6])
                # 如果是字符串
                elif isinstance(date_value, str):
                    parsed_date = date_parser.parse(date_value)
                    # 如果有时区信息，转换为naive datetime (移除时区)
                    if parsed_date.tzinfo is not None:
                        parsed_date = parsed_date.replace(tzinfo=None)
                    return parsed_date
            except Exception as e:
                logger.debug(f"解析日期失败 {field}: {e}")
                continue

        return None
