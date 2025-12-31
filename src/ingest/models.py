"""数据模型"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class Item:
    """信息条目数据模型"""

    url: str
    title: str
    published: datetime
    source: str
    author: Optional[str] = None
    summary: Optional[str] = None
    content: Optional[str] = None
    raw_data: Dict[str, Any] = field(default_factory=dict)

    # 处理后添加的字段
    tags: List[str] = field(default_factory=list)
    score: float = 0.0
    score_breakdown: Dict[str, Any] = field(default_factory=dict)
    is_must_read: bool = False
    ai_summary: Optional[str] = None
    key_points: List[str] = field(default_factory=list)
    action: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典

        Returns:
            字典表示
        """
        return {
            "url": self.url,
            "title": self.title,
            "published": self.published.isoformat(),
            "source": self.source,
            "author": self.author,
            "summary": self.summary,
            "content": self.content,
            "tags": self.tags,
            "score": self.score,
            "score_breakdown": self.score_breakdown,
            "is_must_read": self.is_must_read,
            "ai_summary": self.ai_summary,
            "key_points": self.key_points,
            "action": self.action,
            "raw_data": self.raw_data,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Item":
        """从字典创建Item实例

        Args:
            data: 字典数据

        Returns:
            Item实例
        """
        # 解析日期
        if isinstance(data.get("published"), str):
            data["published"] = datetime.fromisoformat(data["published"])

        return cls(**data)
