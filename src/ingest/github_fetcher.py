"""GitHub Releases采集器"""

import time
from datetime import datetime
from typing import Any, Dict, List

import requests
from dateutil import parser as date_parser

from ..utils.logger import get_logger
from .base import BaseFetcher
from .models import Item

logger = get_logger("ingest.github")


class GitHubFetcher(BaseFetcher):
    """GitHub Releases采集器"""

    API_BASE = "https://api.github.com"

    def fetch(self, source: Dict[str, Any]) -> List[Item]:
        """采集GitHub Releases

        Args:
            source: 信息源配置 (url字段应为 "owner/repo" 格式)

        Returns:
            Item列表
        """
        repo = source.get("url")
        if not repo:
            logger.error(f"信息源 {source.get('name')} 缺少仓库URL")
            return []

        # 验证格式
        if "/" not in repo or repo.count("/") != 1:
            logger.error(f"GitHub仓库格式错误 {repo}，应为 'owner/repo'")
            return []

        items = []
        last_error = None

        for attempt in range(self.max_retries):
            try:
                logger.debug(
                    f"正在采集 GitHub:{repo} (尝试 {attempt + 1}/{self.max_retries})"
                )

                # 获取最近的releases
                url = f"{self.API_BASE}/repos/{repo}/releases"
                headers = self._get_headers()

                # 如果有GitHub Token，添加到请求头
                import os

                github_token = os.getenv("GITHUB_TOKEN")
                if github_token:
                    headers["Authorization"] = f"token {github_token}"

                response = requests.get(url, headers=headers, timeout=self.timeout, params={"per_page": 10})
                response.raise_for_status()

                releases = response.json()

                # 解析releases
                for release in releases:
                    item = self._parse_release(release, source, repo)
                    if item:
                        items.append(item)

                logger.info(f"成功采集 GitHub:{repo}: {len(items)} 条")
                return items

            except requests.Timeout:
                last_error = "超时"
                logger.warning(
                    f"采集超时 GitHub:{repo} (尝试 {attempt + 1}/{self.max_retries})"
                )
            except requests.RequestException as e:
                last_error = str(e)
                if hasattr(e.response, "status_code") and e.response.status_code == 404:
                    logger.error(f"GitHub仓库不存在: {repo}")
                    break
                logger.warning(
                    f"采集失败 GitHub:{repo}: {e} (尝试 {attempt + 1}/{self.max_retries})"
                )
            except Exception as e:
                last_error = str(e)
                logger.error(f"采集异常 GitHub:{repo}: {e}")
                break

            # 重试前等待
            if attempt < self.max_retries - 1:
                time.sleep(self.retry_delay)

        if last_error:
            logger.error(
                f"采集失败 GitHub:{repo} (已重试{self.max_retries}次): {last_error}"
            )
        return items

    def _parse_release(
        self, release: Dict[str, Any], source: Dict[str, Any], repo: str
    ) -> Item:
        """解析GitHub Release

        Args:
            release: GitHub API返回的release对象
            source: 信息源配置
            repo: 仓库名称

        Returns:
            Item实例，如果解析失败返回None
        """
        try:
            # 跳过草稿
            if release.get("draft", False):
                return None

            # 提取基本信息
            url = release.get("html_url", "")
            title = release.get("name") or release.get("tag_name", "")
            if not title:
                return None

            # 完整标题
            full_title = f"{repo} - {title}"

            # 发布时间
            published_str = release.get("published_at") or release.get("created_at")
            if published_str:
                published = date_parser.parse(published_str)
            else:
                published = datetime.now()

            # 作者
            author = release.get("author", {}).get("login", "")

            # 内容
            body = release.get("body", "")

            # 提取摘要（前200字符）
            summary = body[:200] + "..." if len(body) > 200 else body

            # 检查是否为预发布
            is_prerelease = release.get("prerelease", False)
            if is_prerelease:
                full_title += " (Pre-release)"

            # 创建Item
            item = Item(
                url=url,
                title=full_title,
                published=published,
                source=source.get("name", ""),
                author=author,
                summary=summary,
                content=body[:5000] if body else None,
                raw_data={
                    "source_url": f"https://github.com/{repo}",
                    "authority_score": source.get("authority_score", 50),
                    "source_tags": source.get("tags", []),
                    "repo": repo,
                    "tag_name": release.get("tag_name"),
                    "is_prerelease": is_prerelease,
                    "release_type": "github_release",
                },
            )

            return item

        except Exception as e:
            logger.error(f"解析GitHub Release失败: {e}")
            return None
