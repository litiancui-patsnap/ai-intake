"""去重模块"""

import hashlib
from typing import Any, Dict, List
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from rapidfuzz import fuzz

from ..ingest.models import Item
from ..utils.logger import get_logger

logger = get_logger("dedup")


def normalize_url(url: str) -> str:
    """规范化URL

    移除tracking参数、统一scheme等

    Args:
        url: 原始URL

    Returns:
        规范化后的URL
    """
    try:
        parsed = urlparse(url)

        # 统一scheme为https
        scheme = "https" if parsed.scheme in ["http", "https"] else parsed.scheme

        # 移除常见的tracking参数
        tracking_params = {
            "utm_source",
            "utm_medium",
            "utm_campaign",
            "utm_term",
            "utm_content",
            "ref",
            "source",
            "fbclid",
            "gclid",
        }

        query_params = parse_qs(parsed.query)
        cleaned_params = {k: v for k, v in query_params.items() if k not in tracking_params}

        # 重新构建查询字符串
        query = urlencode(cleaned_params, doseq=True) if cleaned_params else ""

        # 移除fragment
        normalized = urlunparse((scheme, parsed.netloc, parsed.path, "", query, ""))

        return normalized.rstrip("/")
    except Exception as e:
        logger.debug(f"URL规范化失败 {url}: {e}")
        return url


def compute_content_hash(text: str) -> str:
    """计算内容哈希

    Args:
        text: 文本内容

    Returns:
        SHA256哈希值
    """
    if not text:
        return ""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def is_duplicate_url(url1: str, url2: str, threshold: float = 0.9) -> bool:
    """检查URL是否重复

    Args:
        url1: 第一个URL
        url2: 第二个URL
        threshold: 相似度阈值 (0-1)

    Returns:
        是否重复
    """
    # 先规范化
    norm_url1 = normalize_url(url1)
    norm_url2 = normalize_url(url2)

    # 完全相同
    if norm_url1 == norm_url2:
        return True

    # 计算相似度
    similarity = fuzz.ratio(norm_url1, norm_url2) / 100.0
    return similarity >= threshold


def is_duplicate_title(title1: str, title2: str, threshold: float = 0.85) -> bool:
    """检查标题是否重复

    Args:
        title1: 第一个标题
        title2: 第二个标题
        threshold: 相似度阈值 (0-1)

    Returns:
        是否重复
    """
    if not title1 or not title2:
        return False

    # 标准化标题（小写、去除空白）
    norm_title1 = " ".join(title1.lower().split())
    norm_title2 = " ".join(title2.lower().split())

    # 完全相同
    if norm_title1 == norm_title2:
        return True

    # 计算相似度
    similarity = fuzz.ratio(norm_title1, norm_title2) / 100.0
    return similarity >= threshold


def is_duplicate_content(content1: str, content2: str, threshold: float = 0.95) -> bool:
    """检查内容是否重复

    Args:
        content1: 第一个内容
        content2: 第二个内容
        threshold: 相似度阈值 (0-1)

    Returns:
        是否重复
    """
    if not content1 or not content2:
        return False

    # 先比较哈希
    hash1 = compute_content_hash(content1)
    hash2 = compute_content_hash(content2)

    if hash1 == hash2:
        return True

    # 内容相似度（仅对较短内容计算，避免性能问题）
    if len(content1) < 1000 and len(content2) < 1000:
        similarity = fuzz.ratio(content1, content2) / 100.0
        return similarity >= threshold

    return False


def deduplicate(
    items: List[Item], existing_items: List[Item] = None, config: Dict[str, Any] = None
) -> List[Item]:
    """去重

    Args:
        items: 待去重的Item列表
        existing_items: 已存在的Item列表（用于与历史数据对比）
        config: 去重配置

    Returns:
        去重后的Item列表
    """
    if config is None:
        config = {}

    url_threshold = config.get("url_similarity_threshold", 0.9)
    title_threshold = config.get("title_similarity_threshold", 0.85)
    content_threshold = config.get("content_similarity_threshold", 0.95)

    # 合并所有需要对比的items
    all_items = (existing_items or []) + items

    unique_items = []
    duplicate_count = 0

    logger.info(f"开始去重: {len(items)} 条新数据，{len(existing_items or [])} 条历史数据")

    for i, item in enumerate(items):
        is_dup = False

        # 与所有之前的items对比
        for j in range(i):
            if is_duplicate_url(item.url, items[j].url, url_threshold):
                logger.debug(f"URL重复: {item.title}")
                is_dup = True
                break
            if is_duplicate_title(item.title, items[j].title, title_threshold):
                logger.debug(f"标题重复: {item.title}")
                is_dup = True
                break
            if item.content and items[j].content:
                if is_duplicate_content(item.content, items[j].content, content_threshold):
                    logger.debug(f"内容重复: {item.title}")
                    is_dup = True
                    break

        # 与历史数据对比
        if not is_dup and existing_items:
            for existing in existing_items:
                if is_duplicate_url(item.url, existing.url, url_threshold):
                    logger.debug(f"URL与历史重复: {item.title}")
                    is_dup = True
                    break
                if is_duplicate_title(item.title, existing.title, title_threshold):
                    logger.debug(f"标题与历史重复: {item.title}")
                    is_dup = True
                    break
                if item.content and existing.content:
                    if is_duplicate_content(
                        item.content, existing.content, content_threshold
                    ):
                        logger.debug(f"内容与历史重复: {item.title}")
                        is_dup = True
                        break

        if is_dup:
            duplicate_count += 1
        else:
            unique_items.append(item)

    logger.info(f"去重完成: 保留 {len(unique_items)} 条，过滤 {duplicate_count} 条")

    return unique_items


__all__ = [
    "normalize_url",
    "compute_content_hash",
    "is_duplicate_url",
    "is_duplicate_title",
    "is_duplicate_content",
    "deduplicate",
]
