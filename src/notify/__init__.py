"""Notification senders for ai-intake."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from ..ingest.models import Item
from ..utils.logger import get_logger
from .infographic import generate_news_infographic

logger = get_logger("notify")


class NotificationSender:
    """Base notification sender."""

    def send(self, title: str, content: str, items: List[Item]) -> bool:
        raise NotImplementedError


class WeComBotSender(NotificationSender):
    """WeCom group bot sender."""

    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url or os.getenv("WECOM_WEBHOOK_URL")

    def send(self, title: str, content: str, items: List[Item]) -> bool:
        if not self.webhook_url:
            logger.warning("WECOM_WEBHOOK_URL is not configured")
            return False

        must_read = [item for item in items if item.is_must_read]
        high_score = [item for item in items if item.score >= 80 and not item.is_must_read]

        markdown_lines = [f"# {title}", "", content]
        if must_read:
            markdown_lines.append("")
            markdown_lines.append(f"## Must Read ({len(must_read)})")
            for item in must_read[:5]:
                markdown_lines.append(f"- **[{item.title}]({item.url})**")
                markdown_lines.append(f"  > {item.source} | {item.score:.0f}")
        if high_score:
            markdown_lines.append("")
            markdown_lines.append(f"## High Score ({len(high_score)})")
            for item in high_score[:5]:
                markdown_lines.append(f"- [{item.title}]({item.url})")
                markdown_lines.append(f"  > {item.source} | {item.score:.0f}")

        payload = {
            "msgtype": "markdown",
            "markdown": {"content": "\n".join(markdown_lines)},
        }

        try:
            response = requests.post(self.webhook_url, json=payload, timeout=10)
            response.raise_for_status()
            result = response.json()
            return result.get("errcode") == 0
        except Exception as exc:
            logger.error("Failed to send WeCom notification: %s", exc)
            return False


class ServerChanSender(NotificationSender):
    """ServerChan sender."""

    def __init__(self, sendkey: Optional[str] = None):
        self.sendkey = sendkey or os.getenv("SERVERCHAN_SENDKEY")
        self.api_url = "https://sctapi.ftqq.com/{}.send"

    def send(self, title: str, content: str, items: List[Item]) -> bool:
        if not self.sendkey:
            logger.warning("SERVERCHAN_SENDKEY is not configured")
            return False

        must_read = [item for item in items if item.is_must_read]
        high_score = [item for item in items if item.score >= 80 and not item.is_must_read]

        lines = [content]
        if must_read:
            lines.extend(["", f"### Must Read ({len(must_read)})"])
            for item in must_read[:10]:
                lines.append(f"- **[{item.title}]({item.url})**")
                lines.append(f"  - {item.source} | {item.score:.0f}")
        if high_score:
            lines.extend(["", f"### High Score ({len(high_score)})"])
            for item in high_score[:10]:
                lines.append(f"- [{item.title}]({item.url})")
                lines.append(f"  - {item.source} | {item.score:.0f}")

        try:
            response = requests.post(
                self.api_url.format(self.sendkey),
                data={"title": title, "desp": "\n".join(lines)},
                timeout=10,
            )
            response.raise_for_status()
            result = response.json()
            return result.get("code") == 0
        except Exception as exc:
            logger.error("Failed to send ServerChan notification: %s", exc)
            return False


class PushPlusSender(NotificationSender):
    """PushPlus sender."""

    def __init__(self, token: Optional[str] = None):
        self.token = token or os.getenv("PUSHPLUS_TOKEN")
        self.api_url = "http://www.pushplus.plus/send"

    def send(self, title: str, content: str, items: List[Item]) -> bool:
        if not self.token:
            logger.warning("PUSHPLUS_TOKEN is not configured")
            return False

        must_read = [item for item in items if item.is_must_read]
        high_score = [item for item in items if item.score >= 80 and not item.is_must_read]

        html = [f"<h2>{title}</h2>", f"<p>{content}</p>"]
        if must_read:
            html.append(f"<h3>Must Read ({len(must_read)})</h3><ul>")
            for item in must_read[:10]:
                html.append(
                    f'<li><a href="{item.url}"><b>{item.title}</b></a><br/>'
                    f"{item.source} | {item.score:.0f}</li>"
                )
            html.append("</ul>")
        if high_score:
            html.append(f"<h3>High Score ({len(high_score)})</h3><ul>")
            for item in high_score[:10]:
                html.append(
                    f'<li><a href="{item.url}">{item.title}</a><br/>'
                    f"{item.source} | {item.score:.0f}</li>"
                )
            html.append("</ul>")

        payload = {
            "token": self.token,
            "title": title,
            "content": "".join(html),
            "template": "html",
        }

        try:
            response = requests.post(self.api_url, json=payload, timeout=10)
            response.raise_for_status()
            result = response.json()
            return result.get("code") == 200
        except Exception as exc:
            logger.error("Failed to send PushPlus notification: %s", exc)
            return False


class FeishuBotSender(NotificationSender):
    """Feishu interactive card sender with optional local infographic upload."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.webhook_url = self.config.get("feishu_webhook_url") or os.getenv("FEISHU_WEBHOOK_URL")
        self.app_id = self.config.get("feishu_app_id") or os.getenv("FEISHU_APP_ID")
        self.app_secret = self.config.get("feishu_app_secret") or os.getenv("FEISHU_APP_SECRET")
        self.include_infographic = bool(self.config.get("feishu_include_infographic", False))
        self.image_output_dir = self.config.get("feishu_image_output_dir", "outputs/feishu")
        self.max_items = int(self.config.get("feishu_max_items", 3))

    def send(self, title: str, content: str, items: List[Item]) -> bool:
        if not self.webhook_url:
            logger.warning("FEISHU_WEBHOOK_URL is not configured")
            return False
        if not items:
            logger.warning("No items to send to Feishu")
            return False

        selected = items[: self.max_items]
        must_read_count = len([item for item in items if item.is_must_read])
        elements: list[dict[str, Any]] = []

        image_key = None
        if self.include_infographic and self.app_id and self.app_secret:
            image_key = self._generate_and_upload(selected[0])
            if image_key:
                elements.append(
                    {
                        "tag": "img",
                        "img_key": image_key,
                        "alt": {"tag": "plain_text", "content": "ai-intake daily focus"},
                        "mode": "compact_horizontal",
                        "preview": True,
                    }
                )

        elements.append(
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": (
                        f"**今日结论**\n"
                        f"{content}\n\n"
                        f"**重点关注**\n"
                        f"- 今日共筛出 **{len(items)}** 条\n"
                        f"- 必看 **{must_read_count}** 条\n"
                        f"- 飞书卡片只展示前 **{len(selected)}** 条重点"
                    ),
                },
            }
        )

        for index, item in enumerate(selected, start=1):
            summary = _short_summary(item, 110)
            tags = " / ".join(item.tags[:2]) if item.tags else "未分类"
            label = "必看" if item.is_must_read else "关注"
            item_text = (
                f"**{index}. {item.title}**  \n"
                f"`{label}` `{item.source}` `{item.published.strftime('%Y-%m-%d')}` `评分 {item.score:.0f}`\n"
                f"{summary}\n"
                f"一句话：{_watch_point(item)}\n"
                f"[查看原文]({item.url}) | 主题：{tags}"
            )
            elements.append({"tag": "div", "text": {"tag": "lark_md", "content": item_text}})
            if index < len(selected):
                elements.append({"tag": "hr"})

        card = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {"tag": "plain_text", "content": title},
                    "template": "blue",
                },
                "elements": elements,
            },
        }

        try:
            response = requests.post(self.webhook_url, json=card, timeout=20)
            response.raise_for_status()
            return response.status_code == 200
        except Exception as exc:
            logger.error("Failed to send Feishu notification: %s", exc)
            return False

    def _generate_and_upload(self, item: Item) -> Optional[str]:
        try:
            image_path = generate_news_infographic(item, self.image_output_dir)
            return self._upload_image(image_path)
        except Exception as exc:
            logger.warning("Failed to generate/upload Feishu infographic: %s", exc)
            return None

    def _upload_image(self, image_path: str) -> Optional[str]:
        token = self._get_tenant_access_token()
        if not token:
            return None

        path = Path(image_path)
        if not path.exists():
            return None

        try:
            with open(path, "rb") as file_handle:
                response = requests.post(
                    "https://open.feishu.cn/open-apis/im/v1/images",
                    headers={"Authorization": f"Bearer {token}"},
                    files={"image": (path.name, file_handle, "image/jpeg")},
                    data={"image_type": "message"},
                    timeout=20,
                )
            response.raise_for_status()
            result = response.json()
            return result.get("data", {}).get("image_key")
        except Exception as exc:
            logger.warning("Failed to upload image to Feishu: %s", exc)
            return None

    def _get_tenant_access_token(self) -> Optional[str]:
        if not self.app_id or not self.app_secret:
            return None

        payload = {"app_id": self.app_id, "app_secret": self.app_secret}
        try:
            response = requests.post(
                "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
                json=payload,
                timeout=10,
            )
            response.raise_for_status()
            result = response.json()
            if result.get("code") == 0:
                return result.get("tenant_access_token")
        except Exception as exc:
            logger.warning("Failed to get Feishu tenant token: %s", exc)
        return None


def send_notifications(
    items: List[Item],
    report_type: str = "daily",
    date: Optional[datetime] = None,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, bool]:
    """Send notifications to all configured channels."""

    if date is None:
        date = datetime.now()

    config = config or {}
    personal_use_only = bool(config.get("personal_use_only", False))
    title = (
        f"AI 日报 - {date.strftime('%Y-%m-%d')}"
        if report_type == "daily"
        else f"AI 周报 - {date.strftime('%Y-W%W')}"
    )

    must_read_count = len([item for item in items if item.is_must_read])
    focus_items = [item for item in items if item.is_must_read][:3] or items[:3]
    focus_phrases = []
    for item in focus_items:
        phrase = _headline_phrase(item)
        if phrase not in focus_phrases:
            focus_phrases.append(phrase)
    focus_text = "、".join(focus_phrases) if focus_phrases else "常规更新"
    content = (
        f"今天主要看 {focus_text}。"
        f" 建议先看前 {min(3, len(items))} 条，{must_read_count} 条进入必看。"
    )

    senders: list[tuple[str, NotificationSender]] = []
    if config.get("feishu_enabled", False) or os.getenv("FEISHU_WEBHOOK_URL"):
        senders.append(("feishu", FeishuBotSender(config)))
    if not personal_use_only:
        if config.get("wecom_enabled", False) or os.getenv("WECOM_WEBHOOK_URL"):
            senders.append(("wecom", WeComBotSender(config.get("wecom_webhook_url"))))
        if config.get("serverchan_enabled", False) or os.getenv("SERVERCHAN_SENDKEY"):
            senders.append(("serverchan", ServerChanSender(config.get("serverchan_sendkey"))))
        if config.get("pushplus_enabled", False) or os.getenv("PUSHPLUS_TOKEN"):
            senders.append(("pushplus", PushPlusSender(config.get("pushplus_token"))))

    results: Dict[str, bool] = {}
    for name, sender in senders:
        logger.info("Sending notification via %s", name)
        results[name] = sender.send(title, content, items)

    return results


def _short_summary(item: Item, max_len: int) -> str:
    summary = item.ai_summary or item.summary or item.title
    summary = " ".join(summary.split())
    if len(summary) <= max_len:
        return summary
    return summary[: max_len - 3].rstrip() + "..."


def _headline_phrase(item: Item) -> str:
    text = f"{item.title} {item.ai_summary or item.summary or ''}".lower()
    if any(word in text for word in ["safety", "security", "policy", "guardrail", "teen"]):
        return "AI 安全与治理"
    if any(word in text for word in ["commerce", "shopping", "comparison", "discovery"]):
        return "AI 商业化与产品化"
    if any(word in text for word in ["foundation", "investment", "fund", "community"]):
        return "生态布局与资源投入"
    if any(word in text for word in ["release", "launch", "preview", "available", "api", "sdk"]):
        return "模型或平台发布"
    if any(word in text for word in ["evaluation", "benchmark", "testing", "test"]):
        return "评测与测试能力"
    return "重要平台更新"


def _watch_point(item: Item) -> str:
    text = f"{item.title} {item.ai_summary or item.summary or ''}".lower()
    if any(word in text for word in ["safety", "teen", "security", "policy"]):
        return "看是否会继续变成默认接入要求或安全基线"
    if any(word in text for word in ["commerce", "shopping", "comparison", "discovery"]):
        return "看是否继续延伸到完整转化链路"
    if any(word in text for word in ["foundation", "investment", "fund"]):
        return "看后续是否落到具体项目、资助或生态合作"
    if any(word in text for word in ["api", "sdk", "release", "launch", "preview"]):
        return "看价格、文档、破坏性变更和可生产性"
    if any(word in text for word in ["evaluation", "benchmark", "testing", "test"]):
        return "看是否能直接用于研发验收、回归或自动化测试"
    return "看下一次官方更新里是否给出更明确落地方式"


__all__ = [
    "NotificationSender",
    "WeComBotSender",
    "ServerChanSender",
    "PushPlusSender",
    "FeishuBotSender",
    "send_notifications",
]
