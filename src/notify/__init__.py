"""通知模块 - 支持多种推送方式"""

import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests

from ..ingest.models import Item
from ..utils.logger import get_logger

logger = get_logger("notify")


class NotificationSender:
    """通知发送器基类"""

    def send(self, title: str, content: str, items: List[Item]) -> bool:
        """发送通知

        Args:
            title: 标题
            content: 内容
            items: Item列表

        Returns:
            是否发送成功
        """
        raise NotImplementedError


class WeComBotSender(NotificationSender):
    """企业微信群机器人发送器

    使用方法：
    1. 在企业微信群中添加群机器人
    2. 获取Webhook URL
    3. 设置环境变量 WECOM_WEBHOOK_URL
    """

    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url or os.getenv("WECOM_WEBHOOK_URL")

    def send(self, title: str, content: str, items: List[Item]) -> bool:
        """发送企业微信消息"""
        if not self.webhook_url:
            logger.warning("未配置企业微信Webhook URL，跳过推送")
            return False

        try:
            # 构建Markdown消息
            must_read = [item for item in items if item.is_must_read]
            high_score = [item for item in items if item.score >= 80 and not item.is_must_read]

            markdown_content = f"# {title}\n\n"

            # 必读条目
            if must_read:
                markdown_content += f"## 🔥 必读 ({len(must_read)}条)\n\n"
                for item in must_read[:5]:  # 最多显示5条
                    markdown_content += f"- **[{item.title}]({item.url})**\n"
                    markdown_content += f"  > 来源: {item.source} | 评分: {item.score:.0f}\n\n"

            # 高分条目
            if high_score:
                markdown_content += f"## ⭐ 高分推荐 ({len(high_score)}条)\n\n"
                for item in high_score[:5]:  # 最多显示5条
                    markdown_content += f"- [{item.title}]({item.url})\n"
                    markdown_content += f"  > {item.source} | {item.score:.0f}分\n\n"

            # 统计信息
            markdown_content += f"\n---\n总计 {len(items)} 条信息"

            # 发送请求
            payload = {
                "msgtype": "markdown",
                "markdown": {
                    "content": markdown_content
                }
            }

            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=10
            )
            response.raise_for_status()

            result = response.json()
            if result.get("errcode") == 0:
                logger.info("企业微信消息发送成功")
                return True
            else:
                logger.error(f"企业微信消息发送失败: {result}")
                return False

        except Exception as e:
            logger.error(f"发送企业微信消息时出错: {e}")
            return False


class ServerChanSender(NotificationSender):
    """Server酱发送器

    使用方法：
    1. 访问 https://sct.ftqq.com/ 注册
    2. 获取SendKey
    3. 设置环境变量 SERVERCHAN_SENDKEY
    """

    def __init__(self, sendkey: Optional[str] = None):
        self.sendkey = sendkey or os.getenv("SERVERCHAN_SENDKEY")
        self.api_url = "https://sctapi.ftqq.com/{}.send"

    def send(self, title: str, content: str, items: List[Item]) -> bool:
        """发送Server酱消息"""
        if not self.sendkey:
            logger.warning("未配置Server酱SendKey，跳过推送")
            return False

        try:
            # 构建消息内容
            must_read = [item for item in items if item.is_must_read]
            high_score = [item for item in items if item.score >= 80 and not item.is_must_read]

            desp = f"### 📊 统计\n\n总计 {len(items)} 条信息\n\n"

            # 必读条目
            if must_read:
                desp += f"### 🔥 必读 ({len(must_read)}条)\n\n"
                for item in must_read[:10]:
                    desp += f"- **[{item.title}]({item.url})**\n"
                    desp += f"  - 来源: {item.source} | 评分: {item.score:.0f}\n\n"

            # 高分条目
            if high_score:
                desp += f"### ⭐ 高分推荐 ({len(high_score)}条)\n\n"
                for item in high_score[:10]:
                    desp += f"- [{item.title}]({item.url})\n"
                    desp += f"  - {item.source} | {item.score:.0f}分\n\n"

            # 发送请求
            url = self.api_url.format(self.sendkey)
            payload = {
                "title": title,
                "desp": desp
            }

            response = requests.post(url, data=payload, timeout=10)
            response.raise_for_status()

            result = response.json()
            if result.get("code") == 0:
                logger.info("Server酱消息发送成功")
                return True
            else:
                logger.error(f"Server酱消息发送失败: {result}")
                return False

        except Exception as e:
            logger.error(f"发送Server酱消息时出错: {e}")
            return False


class PushPlusSender(NotificationSender):
    """PushPlus发送器

    使用方法：
    1. 访问 https://www.pushplus.plus/ 注册
    2. 获取Token
    3. 设置环境变量 PUSHPLUS_TOKEN
    """

    def __init__(self, token: Optional[str] = None):
        self.token = token or os.getenv("PUSHPLUS_TOKEN")
        self.api_url = "http://www.pushplus.plus/send"

    def send(self, title: str, content: str, items: List[Item]) -> bool:
        """发送PushPlus消息"""
        if not self.token:
            logger.warning("未配置PushPlus Token，跳过推送")
            return False

        try:
            # 构建HTML消息
            must_read = [item for item in items if item.is_must_read]
            high_score = [item for item in items if item.score >= 80 and not item.is_must_read]

            html_content = f"<h2>{title}</h2>"
            html_content += f"<p>总计 {len(items)} 条信息</p>"

            # 必读条目
            if must_read:
                html_content += f"<h3>🔥 必读 ({len(must_read)}条)</h3><ul>"
                for item in must_read[:10]:
                    html_content += f'<li><a href="{item.url}"><b>{item.title}</b></a><br/>'
                    html_content += f'来源: {item.source} | 评分: {item.score:.0f}</li>'
                html_content += "</ul>"

            # 高分条目
            if high_score:
                html_content += f"<h3>⭐ 高分推荐 ({len(high_score)}条)</h3><ul>"
                for item in high_score[:10]:
                    html_content += f'<li><a href="{item.url}">{item.title}</a><br/>'
                    html_content += f'{item.source} | {item.score:.0f}分</li>'
                html_content += "</ul>"

            # 发送请求
            payload = {
                "token": self.token,
                "title": title,
                "content": html_content,
                "template": "html"
            }

            response = requests.post(self.api_url, json=payload, timeout=10)
            response.raise_for_status()

            result = response.json()
            if result.get("code") == 200:
                logger.info("PushPlus消息发送成功")
                return True
            else:
                logger.error(f"PushPlus消息发送失败: {result}")
                return False

        except Exception as e:
            logger.error(f"发送PushPlus消息时出错: {e}")
            return False


def send_notifications(
    items: List[Item],
    report_type: str = "daily",
    date: datetime = None,
    config: Dict[str, Any] = None
) -> Dict[str, bool]:
    """发送通知到所有已配置的渠道

    Args:
        items: Item列表
        report_type: 报告类型 (daily/weekly)
        date: 日期
        config: 通知配置

    Returns:
        各渠道发送结果
    """
    if date is None:
        date = datetime.now()

    config = config or {}

    # 构建标题
    if report_type == "daily":
        title = f"AI日报 - {date.strftime('%Y-%m-%d')}"
    else:
        title = f"AI周报 - {date.strftime('%Y年第%W周')}"

    # 统计信息
    must_read_count = len([item for item in items if item.is_must_read])
    high_score_count = len([item for item in items if item.score >= 80])

    content = f"本次共采集 {len(items)} 条信息，必读 {must_read_count} 条，高分推荐 {high_score_count} 条。"

    # 初始化发送器
    senders = []

    if config.get("wecom_enabled", False) or os.getenv("WECOM_WEBHOOK_URL"):
        senders.append(("企业微信", WeComBotSender()))

    if config.get("serverchan_enabled", False) or os.getenv("SERVERCHAN_SENDKEY"):
        senders.append(("Server酱", ServerChanSender()))

    if config.get("pushplus_enabled", False) or os.getenv("PUSHPLUS_TOKEN"):
        senders.append(("PushPlus", PushPlusSender()))

    # 发送通知
    results = {}
    for name, sender in senders:
        logger.info(f"发送通知到: {name}")
        results[name] = sender.send(title, content, items)

    return results
