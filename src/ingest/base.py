"""采集器基类"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List

from .models import Item


class BaseFetcher(ABC):
    """采集器基类"""

    def __init__(self, config: Dict[str, Any]):
        """初始化采集器

        Args:
            config: 网络配置
        """
        self.config = config
        self.timeout = config.get("timeout", 30)
        self.max_retries = config.get("max_retries", 3)
        self.retry_delay = config.get("retry_delay", 2)
        self.user_agent = config.get(
            "user_agent", "AI-Intake/1.0 (https://github.com/yourname/ai-intake)"
        )

    @abstractmethod
    def fetch(self, source: Dict[str, Any]) -> List[Item]:
        """采集信息

        Args:
            source: 信息源配置

        Returns:
            Item列表

        Raises:
            Exception: 采集失败时抛出异常
        """
        pass

    def _get_headers(self) -> Dict[str, str]:
        """获取HTTP请求头

        Returns:
            请求头字典
        """
        return {
            "User-Agent": self.user_agent,
            "Accept": "application/xml, application/rss+xml, text/html, */*",
        }
