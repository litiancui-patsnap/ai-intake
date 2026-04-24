"""News search fetcher based on DuckDuckGo news results with freshness checks."""

from __future__ import annotations

import json
import re
import time
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from typing import Any, Dict, List, Optional

import requests

try:
    from ddgs import DDGS
except ImportError:  # pragma: no cover - exercised only when dependency is missing
    DDGS = None

from ..utils.logger import get_logger
from .base import BaseFetcher
from .models import Item

logger = get_logger("ingest.news_search")

HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}
NON_NEWS_PATTERNS = (
    "timeline",
    "tracker",
    "release tracker",
    "model release tracker",
    "history of",
    "retrospective",
    "roundup",
    "weekly recap",
    "weekly round-up",
    "explainer",
    "explained",
    "what is ",
    "glossary",
    "definition",
    "beginner guide",
    "tutorial",
    "complete guide",
)
EXCLUDED_URL_PATTERNS = (
    "/category/",
    "/tag/",
    "/tags/",
    "/topics/",
    "/author/",
    "/page/",
    "/archive/",
    "/search?",
    "?page=",
)
DATE_META_KEYS = {
    "article:publishedtime",
    "article:published_time",
    "og:publishedtime",
    "og:published_time",
    "datepublished",
    "datecreated",
    "pubdate",
    "publishdate",
    "publish-date",
    "article:modifiedtime",
    "article:modified_time",
    "og:updatedtime",
    "og:updated_time",
    "datemodified",
    "date",
}
JSON_LD_DATE_KEYS = (
    "datePublished",
    "dateCreated",
    "dateModified",
    "uploadDate",
    "date",
)
ARTICLE_BODY_JSON_KEYS = ("articleBody", "text", "description")
AI_SIGNAL_PATTERNS = (
    " ai ",
    "artificial intelligence",
    "model",
    "llm",
    "gpt",
    "gemini",
    "claude",
    "llama",
    "chatgpt",
    "copilot",
    "agent",
    "inference",
    "multimodal",
    "superintelligence",
    "chip",
    "gpu",
    "tpu",
    "semiconductor",
    "openai",
    "anthropic",
    "deepmind",
    "muse spark",
    "qwen",
)
MARKET_NOISE_PATTERNS = (
    "stock jumped",
    "shares jumped",
    "shares rose",
    "share price",
    "nasdaq",
    "s&p 500",
    "price target",
    "dividend",
)
PARAGRAPH_NOISE_PATTERNS = (
    "subscribe",
    "sign up",
    "newsletter",
    "advertisement",
    "all rights reserved",
    "cookie",
    "privacy policy",
    "terms of service",
)
EVENT_STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "that",
    "this",
    "after",
    "amid",
    "into",
    "over",
    "will",
    "would",
    "could",
    "their",
    "about",
    "mark",
    "ceo",
    "today",
    "latest",
    "first",
    "new",
    "its",
    "his",
    "her",
    "they",
    "them",
    "attempting",
    "spending",
    "billions",
    "says",
    "said",
}
COMPANY_ALIASES = {
    "openai": ("openai", "chatgpt", "gpt"),
    "google": ("google", "gemini", "deepmind", "alphabet"),
    "meta": ("meta", "facebook", "instagram", "whatsapp"),
    "anthropic": ("anthropic", "claude"),
    "microsoft": ("microsoft", "copilot"),
    "amazon": ("amazon", "aws"),
    "nvidia": ("nvidia",),
    "apple": ("apple", "siri"),
    "xai": ("xai", "grok"),
    "alibaba": ("alibaba", "qwen"),
}
MAX_ITEMS_PER_COMPANY = 2


def _now_utc(now: Optional[datetime] = None) -> datetime:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        return now.replace(tzinfo=timezone.utc)
    return now.astimezone(timezone.utc)


def _normalize_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _event_text(*parts: str) -> str:
    return _normalize_text(" ".join(part for part in parts if part))


def extract_company_tags(text: str) -> set[str]:
    lowered = text.lower()
    matches: set[str] = set()
    for company, aliases in COMPANY_ALIASES.items():
        if any(re.search(rf"\b{re.escape(alias)}\b", lowered) for alias in aliases):
            matches.add(company)
    return matches


def extract_event_tokens(*parts: str) -> set[str]:
    text = _event_text(*parts).lower()
    tokens = set(re.findall(r"[a-z0-9][a-z0-9.+-]{2,}", text))
    return {
        token
        for token in tokens
        if token not in EVENT_STOPWORDS and not token.isdigit()
    }


def build_search_query(base_query: str, now: Optional[datetime] = None) -> str:
    now = now or datetime.now(timezone.utc)
    cleaned = re.sub(r"\b20\d{2}\b", " ", base_query)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    suffix = f"{now.strftime('%B')} {now.year}"
    tokens: list[str] = []
    seen: set[str] = set()
    for token in f"{cleaned} {suffix}".split():
        key = token.lower()
        if key in seen:
            continue
        seen.add(key)
        tokens.append(token)
    return " ".join(tokens)


def parse_datetime_candidate(
    value: Any,
    *,
    now: Optional[datetime] = None,
) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return _normalize_datetime(value)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, timezone.utc)

    text = str(value).strip()
    if not text:
        return None

    now_utc = _now_utc(now)
    lowered = text.lower()
    if lowered in {"today", "just now"}:
        return now_utc
    if lowered == "yesterday":
        return now_utc - timedelta(days=1)

    relative_match = re.fullmatch(
        r"(?P<count>\d+)\s+(?P<unit>minute|hour|day|week)s?\s+ago",
        lowered,
    )
    if relative_match:
        count = int(relative_match.group("count"))
        unit = relative_match.group("unit")
        delta_map = {
            "minute": timedelta(minutes=count),
            "hour": timedelta(hours=count),
            "day": timedelta(days=count),
            "week": timedelta(weeks=count),
        }
        return now_utc - delta_map[unit]

    iso_like = text.replace("Z", "+00:00")
    try:
        return _normalize_datetime(datetime.fromisoformat(iso_like))
    except ValueError:
        pass

    try:
        return _normalize_datetime(parsedate_to_datetime(text))
    except (TypeError, ValueError, IndexError, OverflowError):
        pass

    for fmt in (
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%Y.%m.%d",
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
        "%b %d, %Y",
        "%B %d, %Y",
        "%d %b %Y",
    ):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue

    return None


def extract_date_from_url(url: str) -> Optional[datetime]:
    for pattern in (
        r"/(\d{4})/(\d{2})/(\d{2})/",
        r"/(\d{4})-(\d{2})-(\d{2})",
        r"(\d{4})(\d{2})(\d{2})",
    ):
        match = re.search(pattern, url)
        if not match:
            continue
        try:
            year, month, day = (int(part) for part in match.groups())
            return datetime(year, month, day, tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _parse_html_attrs(tag: str) -> dict[str, str]:
    return {
        key.lower(): value
        for key, value in re.findall(r'([:\w-]+)\s*=\s*["\']([^"\']*)["\']', tag)
    }


def _normalize_meta_key(key: str) -> str:
    return re.sub(r"[^a-z:_-]", "", key.lower())


def _iter_json_ld_dates(payload: Any, wanted_key: str) -> list[str]:
    if isinstance(payload, dict):
        matches: list[str] = []
        for key, value in payload.items():
            if key == wanted_key and isinstance(value, str):
                matches.append(value)
            matches.extend(_iter_json_ld_dates(value, wanted_key))
        return matches
    if isinstance(payload, list):
        matches: list[str] = []
        for item in payload:
            matches.extend(_iter_json_ld_dates(item, wanted_key))
        return matches
    return []


def extract_publication_date_from_html(
    html: str,
    *,
    now: Optional[datetime] = None,
) -> Optional[datetime]:
    if not html:
        return None

    for tag in re.findall(r"<meta\b[^>]*>", html, flags=re.IGNORECASE):
        attrs = _parse_html_attrs(tag)
        raw_key = attrs.get("property") or attrs.get("name") or attrs.get("itemprop")
        if not raw_key:
            continue
        if _normalize_meta_key(raw_key) not in DATE_META_KEYS:
            continue
        parsed = parse_datetime_candidate(attrs.get("content"), now=now)
        if parsed:
            return parsed

    for tag in re.findall(r"<time\b[^>]*>", html, flags=re.IGNORECASE):
        attrs = _parse_html_attrs(tag)
        parsed = parse_datetime_candidate(attrs.get("datetime"), now=now)
        if parsed:
            return parsed

    for script_content in re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        script_content = script_content.strip()
        if not script_content:
            continue
        try:
            payload = json.loads(script_content)
        except json.JSONDecodeError:
            continue

        for key in JSON_LD_DATE_KEYS:
            for candidate in _iter_json_ld_dates(payload, key):
                parsed = parse_datetime_candidate(candidate, now=now)
                if parsed:
                    return parsed

    return None


def resolve_publication_date(
    url: str,
    *,
    search_result_date: str = "",
    html: str = "",
    headers: Optional[dict[str, str]] = None,
    now: Optional[datetime] = None,
) -> Optional[datetime]:
    candidates = [
        extract_publication_date_from_html(html, now=now),
        parse_datetime_candidate(search_result_date, now=now),
        extract_date_from_url(url),
        parse_datetime_candidate((headers or {}).get("Last-Modified"), now=now),
    ]
    for candidate in candidates:
        if candidate:
            return candidate
    return None


def is_fresh_publication(
    published_at: datetime,
    *,
    now: Optional[datetime] = None,
    max_age_hours: int = 48,
) -> bool:
    now_utc = _now_utc(now)
    published_utc = _normalize_datetime(published_at)
    if published_utc > now_utc + timedelta(hours=6):
        return False
    return published_utc >= now_utc - timedelta(hours=max_age_hours)


def looks_like_ai_news(title: str, summary: str, url: str) -> bool:
    text = f" {title.lower()} {summary.lower()} {url.lower()} "
    if any(pattern in text for pattern in MARKET_NOISE_PATTERNS) and not any(
        pattern in text for pattern in AI_SIGNAL_PATTERNS
    ):
        return False
    return any(pattern in text for pattern in AI_SIGNAL_PATTERNS)


def is_low_quality_title(title: str) -> bool:
    tokens = re.findall(r"[a-zA-Z0-9]+", title.lower())
    if not tokens:
        return True
    if len(tokens) <= 2:
        return True
    if len(tokens) <= 4 and not extract_company_tags(title) and "ai" not in title.lower():
        return True
    return False


def is_duplicate_event(candidate: dict[str, str], existing_items: list[dict[str, str]]) -> bool:
    candidate_text = _event_text(
        candidate.get("title", ""),
        candidate.get("summary", ""),
        candidate.get("snippet", ""),
    )
    candidate_tokens = extract_event_tokens(candidate_text)
    candidate_companies = extract_company_tags(candidate_text)

    for existing in existing_items:
        existing_text = _event_text(
            existing.get("title", ""),
            existing.get("summary", ""),
            existing.get("snippet", ""),
        )
        existing_tokens = extract_event_tokens(existing_text)
        existing_companies = extract_company_tags(existing_text)
        overlap = candidate_tokens & existing_tokens
        if candidate_companies & existing_companies and len(overlap) >= 3:
            return True
        if len(overlap) >= 5:
            return True
    return False


def exceeds_company_limit(candidate: dict[str, str], accepted_items: list[dict[str, str]]) -> bool:
    candidate_companies = extract_company_tags(
        _event_text(candidate.get("title", ""), candidate.get("summary", ""), candidate.get("snippet", ""))
    )
    if not candidate_companies:
        return False

    company_counts = {company: 0 for company in candidate_companies}
    for item in accepted_items:
        item_companies = extract_company_tags(
            _event_text(item.get("title", ""), item.get("summary", ""), item.get("snippet", ""))
        )
        for company in candidate_companies & item_companies:
            company_counts[company] += 1

    return any(count >= MAX_ITEMS_PER_COMPANY for count in company_counts.values())


def is_candidate_article_url(url: str) -> bool:
    lowered = url.lower()
    return not any(pattern in lowered for pattern in EXCLUDED_URL_PATTERNS)


def is_evergreen_result(title: str, summary: str, url: str) -> bool:
    text = " ".join([title, summary, url]).lower()
    return any(pattern in text for pattern in NON_NEWS_PATTERNS)


def fetch_publication_context(url: str) -> tuple[str, dict[str, str]]:
    try:
        response = requests.get(
            url,
            headers=HTTP_HEADERS,
            timeout=10,
            allow_redirects=True,
        )
        if response.status_code >= 400:
            return "", {}

        content_type = response.headers.get("Content-Type", "")
        if "html" not in content_type.lower():
            return "", dict(response.headers)

        return response.text[:500000], dict(response.headers)
    except requests.RequestException:
        return "", {}


def validate_news_result(
    raw_result: dict[str, Any],
    *,
    now: Optional[datetime] = None,
    max_age_hours: int = 48,
) -> Optional[dict[str, str]]:
    title = raw_result.get("title", "").strip()
    url = raw_result.get("url") or raw_result.get("href") or ""
    summary = raw_result.get("body") or raw_result.get("snippet") or ""
    source = raw_result.get("source", "")

    if not title or not url:
        return None
    if not is_candidate_article_url(url):
        return None
    if is_low_quality_title(title):
        return None
    if not looks_like_ai_news(title, summary, url):
        return None
    if is_evergreen_result(title, summary, url):
        return None

    html, headers = fetch_publication_context(url)
    published_at = resolve_publication_date(
        url,
        search_result_date=raw_result.get("date", ""),
        html=html,
        headers=headers,
        now=now,
    )
    if not published_at:
        return None
    if not is_fresh_publication(published_at, now=now, max_age_hours=max_age_hours):
        return None

    return {
        "title": title,
        "url": url,
        "snippet": summary.strip(),
        "source": source.strip(),
        "published_at": _normalize_datetime(published_at).isoformat(),
        "html": html,
    }


def _html_fragment_to_text(fragment: str) -> str:
    text = re.sub(r"(?is)<script.*?>.*?</script>", " ", fragment)
    text = re.sub(r"(?is)<style.*?>.*?</style>", " ", text)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    return _normalize_text(unescape(text))


def _extract_json_ld_texts(payload: Any) -> list[str]:
    if isinstance(payload, dict):
        matches: list[str] = []
        for key, value in payload.items():
            if key in ARTICLE_BODY_JSON_KEYS and isinstance(value, str):
                matches.append(value)
            matches.extend(_extract_json_ld_texts(value))
        return matches
    if isinstance(payload, list):
        matches: list[str] = []
        for item in payload:
            matches.extend(_extract_json_ld_texts(item))
        return matches
    return []


def extract_article_text_from_html(html: str) -> str:
    if not html:
        return ""

    candidates: list[str] = []
    cleaned_html = re.sub(r"(?is)<script.*?>.*?</script>", " ", html)

    for script_content in re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        script_content = script_content.strip()
        if not script_content:
            continue
        try:
            payload = json.loads(script_content)
        except json.JSONDecodeError:
            continue
        for value in _extract_json_ld_texts(payload):
            normalized = _normalize_text(unescape(value))
            if len(normalized) >= 300:
                candidates.append(normalized)

    article_match = re.search(r"(?is)<article\b[^>]*>(.*?)</article>", cleaned_html)
    article_html = article_match.group(1) if article_match else cleaned_html

    paragraphs: list[str] = []
    for fragment in re.findall(r"(?is)<p\b[^>]*>(.*?)</p>", article_html):
        paragraph = _html_fragment_to_text(fragment)
        if len(paragraph) < 60:
            continue
        if any(pattern in paragraph.lower() for pattern in PARAGRAPH_NOISE_PATTERNS):
            continue
        paragraphs.append(paragraph)

    if len(paragraphs) >= 3:
        candidates.append("\n".join(paragraphs[:15]))
    elif paragraphs:
        candidates.append("\n".join(paragraphs))

    fallback_text = _html_fragment_to_text(article_html)
    if len(fallback_text) >= 500:
        candidates.append(fallback_text[:12000])

    if not candidates:
        return ""
    return max(candidates, key=len)[:12000]


class NewsSearchFetcher(BaseFetcher):
    """Fetch AI news from DuckDuckGo and validate freshness from article pages."""

    def fetch(self, source: Dict[str, Any]) -> List[Item]:
        if DDGS is None:
            raise RuntimeError("news_search requires the optional dependency 'ddgs'")

        query = source.get("query") or source.get("url")
        if not query:
            raise ValueError("news_search source requires a query")

        region = source.get("region", "us-en")
        timelimit = source.get("timelimit", "d")
        max_results = int(source.get("max_results", 5))
        max_age_hours = int(source.get("max_age_hours", 48))
        resolved_query = build_search_query(query)

        logger.info(
            "Searching news for %s (region=%s timelimit=%s max_results=%s)",
            resolved_query,
            region,
            timelimit,
            max_results,
        )

        accepted_results: list[dict[str, str]] = []
        seen_urls: set[str] = set()

        ddgs = DDGS()
        raw_results = ddgs.news(
            resolved_query,
            region=region,
            timelimit=timelimit,
            max_results=max_results * 10,
        )
        for raw_result in raw_results:
            candidate = validate_news_result(
                raw_result,
                max_age_hours=max_age_hours,
            )
            if not candidate:
                continue

            if candidate["url"] in seen_urls:
                continue
            if is_duplicate_event(candidate, accepted_results):
                continue
            if exceeds_company_limit(candidate, accepted_results):
                continue

            seen_urls.add(candidate["url"])
            accepted_results.append(candidate)
            if len(accepted_results) >= max_results:
                break
            time.sleep(0.2)

        items: List[Item] = []
        for candidate in accepted_results:
            published = parse_datetime_candidate(candidate["published_at"]) or datetime.now(timezone.utc)
            article_text = extract_article_text_from_html(candidate.get("html", ""))
            summary = candidate.get("snippet") or candidate.get("title")
            source_name = candidate.get("source") or source.get("name", "News Search")
            source_tags = list(source.get("tags", []))
            source_tags.extend(sorted(extract_company_tags(candidate["title"])))

            item = Item(
                url=candidate["url"],
                title=candidate["title"],
                published=published,
                source=source_name,
                summary=summary[:500] if summary else None,
                content=article_text[:5000] if article_text else None,
                raw_data={
                    "source_url": candidate["url"],
                    "authority_score": source.get("authority_score", 70),
                    "source_tags": sorted(set(source_tags)),
                    "search_query": resolved_query,
                    "search_region": region,
                    "search_timelimit": timelimit,
                    "published_at": candidate["published_at"],
                    "search_type": "ddgs_news",
                },
            )
            items.append(item)

        logger.info("Collected %s validated news items from search source %s", len(items), source.get("name"))
        return items
