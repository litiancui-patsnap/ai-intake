"""采集模块"""

from typing import Any, Dict, List

from ..utils.logger import get_logger
from .base import BaseFetcher
from .github_fetcher import GitHubFetcher
from .models import Item
from .rss_fetcher import RSSFetcher

logger = get_logger("ingest")

# 采集器注册表
FETCHERS: Dict[str, type] = {
    "rss": RSSFetcher,
    "github": GitHubFetcher,
}


def create_fetcher(source_type: str, config: Dict[str, Any]) -> BaseFetcher:
    """创建采集器实例

    Args:
        source_type: 信息源类型 ('rss', 'github' 等)
        config: 网络配置

    Returns:
        采集器实例

    Raises:
        ValueError: 不支持的信息源类型
    """
    fetcher_class = FETCHERS.get(source_type)
    if not fetcher_class:
        raise ValueError(f"不支持的信息源类型: {source_type}")

    return fetcher_class(config)


def fetch_all(sources: List[Dict[str, Any]], config: Dict[str, Any]) -> List[Item]:
    """采集所有信息源

    Args:
        sources: 信息源列表
        config: 网络配置

    Returns:
        所有Item列表
    """
    all_items = []
    success_count = 0
    failed_count = 0

    logger.info(f"开始采集 {len(sources)} 个信息源")

    for source in sources:
        source_name = source.get("name", "未命名")
        source_type = source.get("type", "rss")

        try:
            fetcher = create_fetcher(source_type, config)
            items = fetcher.fetch(source)
            all_items.extend(items)
            success_count += 1
        except ValueError as e:
            logger.error(f"创建采集器失败 {source_name}: {e}")
            failed_count += 1
        except Exception as e:
            logger.error(f"采集失败 {source_name}: {e}")
            failed_count += 1

    logger.info(
        f"采集完成: 成功 {success_count} 个，失败 {failed_count} 个，共 {len(all_items)} 条"
    )

    return all_items


__all__ = ["Item", "BaseFetcher", "RSSFetcher", "GitHubFetcher", "create_fetcher", "fetch_all"]
