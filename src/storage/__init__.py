"""存储模块"""

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..ingest.models import Item
from ..utils.logger import get_logger

logger = get_logger("storage")


class Storage:
    """存储管理器"""

    def __init__(self, db_path: str = "ai-intake.db"):
        """初始化存储管理器

        Args:
            db_path: 数据库文件路径
        """
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None
        self._init_db()

    def _init_db(self):
        """初始化数据库"""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row  # 返回字典形式

        # 创建表
        self.conn.executescript(
            """
            -- 信息条目表
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                published DATETIME NOT NULL,
                source TEXT NOT NULL,
                author TEXT,
                summary TEXT,
                content TEXT,
                score REAL,
                score_breakdown TEXT,
                is_must_read BOOLEAN DEFAULT 0,
                ai_summary TEXT,
                key_points TEXT,
                action TEXT,
                raw_data TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                indexed_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            -- 主题标签表
            CREATE TABLE IF NOT EXISTS tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id INTEGER NOT NULL,
                tag TEXT NOT NULL,
                FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE CASCADE
            );

            -- 运行日志表
            CREATE TABLE IF NOT EXISTS runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_type TEXT NOT NULL,
                started_at DATETIME NOT NULL,
                finished_at DATETIME,
                items_collected INTEGER,
                items_published INTEGER,
                status TEXT,
                error_log TEXT
            );

            -- 创建索引
            CREATE INDEX IF NOT EXISTS idx_items_published ON items(published DESC);
            CREATE INDEX IF NOT EXISTS idx_items_score ON items(score DESC);
            CREATE INDEX IF NOT EXISTS idx_items_source ON items(source);
            CREATE INDEX IF NOT EXISTS idx_tags_tag ON tags(tag);
            CREATE INDEX IF NOT EXISTS idx_tags_item_id ON tags(item_id);
        """
        )

        self.conn.commit()
        logger.debug(f"数据库已初始化: {self.db_path}")

    def save_items(self, items: List[Item]) -> int:
        """保存Item列表

        Args:
            items: Item列表

        Returns:
            成功保存的数量
        """
        saved_count = 0

        for item in items:
            try:
                # 插入item
                self.conn.execute(
                    """
                    INSERT OR REPLACE INTO items
                    (url, title, published, source, author, summary, content, score, score_breakdown,
                     is_must_read, ai_summary, key_points, action, raw_data, indexed_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        item.url,
                        item.title,
                        item.published.isoformat(),
                        item.source,
                        item.author,
                        item.summary,
                        item.content,
                        item.score,
                        json.dumps(item.score_breakdown, ensure_ascii=False),
                        item.is_must_read,
                        item.ai_summary,
                        json.dumps(item.key_points, ensure_ascii=False),
                        item.action,
                        json.dumps(item.raw_data, ensure_ascii=False),
                        datetime.now().isoformat(),
                    ),
                )

                # 获取item_id
                item_id = self.conn.execute("SELECT id FROM items WHERE url = ?", (item.url,)).fetchone()[0]

                # 删除旧标签
                self.conn.execute("DELETE FROM tags WHERE item_id = ?", (item_id,))

                # 插入新标签
                for tag in item.tags:
                    self.conn.execute(
                        "INSERT INTO tags (item_id, tag) VALUES (?, ?)",
                        (item_id, tag),
                    )

                saved_count += 1

            except Exception as e:
                logger.error(f"保存Item失败 '{item.title}': {e}")

        self.conn.commit()
        logger.info(f"已保存 {saved_count}/{len(items)} 条数据")

        return saved_count

    def get_items(
        self,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        min_score: float = 0,
        tags: Optional[List[str]] = None,
        limit: Optional[int] = None,
    ) -> List[Item]:
        """查询Item列表

        Args:
            since: 开始时间
            until: 结束时间
            min_score: 最低分数
            tags: 标签过滤
            limit: 数量限制

        Returns:
            Item列表
        """
        query = "SELECT * FROM items WHERE 1=1"
        params = []

        if since:
            query += " AND published >= ?"
            params.append(since.isoformat())

        if until:
            query += " AND published <= ?"
            params.append(until.isoformat())

        if min_score > 0:
            query += " AND score >= ?"
            params.append(min_score)

        if tags:
            # 需要联表查询
            tag_placeholders = ",".join("?" * len(tags))
            query += f"""
                AND id IN (
                    SELECT item_id FROM tags WHERE tag IN ({tag_placeholders})
                )
            """
            params.extend(tags)

        query += " ORDER BY score DESC, published DESC"

        if limit:
            query += " LIMIT ?"
            params.append(limit)

        cursor = self.conn.execute(query, params)
        rows = cursor.fetchall()

        items = []
        for row in rows:
            item = self._row_to_item(row)
            if item:
                items.append(item)

        logger.debug(f"查询到 {len(items)} 条数据")

        return items

    def _row_to_item(self, row: sqlite3.Row) -> Optional[Item]:
        """将数据库行转换为Item

        Args:
            row: 数据库行

        Returns:
            Item实例
        """
        try:
            # 查询标签
            item_id = row["id"]
            tags_cursor = self.conn.execute("SELECT tag FROM tags WHERE item_id = ?", (item_id,))
            tags = [r["tag"] for r in tags_cursor.fetchall()]

            item = Item(
                url=row["url"],
                title=row["title"],
                published=datetime.fromisoformat(row["published"]),
                source=row["source"],
                author=row["author"],
                summary=row["summary"],
                content=row["content"],
                tags=tags,
                score=row["score"] or 0,
                score_breakdown=json.loads(row["score_breakdown"] or "{}"),
                is_must_read=bool(row["is_must_read"]),
                ai_summary=row["ai_summary"],
                key_points=json.loads(row["key_points"] or "[]"),
                action=row["action"],
                raw_data=json.loads(row["raw_data"] or "{}"),
            )

            return item

        except Exception as e:
            logger.error(f"转换数据库行失败: {e}")
            return None

    def export_jsonl(self, items: List[Item], output_path: str):
        """导出为JSONL格式

        Args:
            items: Item列表
            output_path: 输出文件路径
        """
        try:
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)

            with open(output_file, "w", encoding="utf-8") as f:
                for item in items:
                    f.write(json.dumps(item.to_dict(), ensure_ascii=False) + "\n")

            logger.info(f"已导出 {len(items)} 条数据到 {output_path}")

        except Exception as e:
            logger.error(f"导出JSONL失败: {e}")

    def log_run(
        self,
        run_type: str,
        started_at: datetime,
        finished_at: datetime,
        items_collected: int,
        items_published: int,
        status: str = "success",
        error_log: str = None,
    ):
        """记录运行日志

        Args:
            run_type: 运行类型 ('daily', 'weekly')
            started_at: 开始时间
            finished_at: 结束时间
            items_collected: 采集数量
            items_published: 发布数量
            status: 状态
            error_log: 错误日志
        """
        try:
            self.conn.execute(
                """
                INSERT INTO runs
                (run_type, started_at, finished_at, items_collected, items_published, status, error_log)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    run_type,
                    started_at.isoformat(),
                    finished_at.isoformat(),
                    items_collected,
                    items_published,
                    status,
                    error_log,
                ),
            )
            self.conn.commit()
            logger.debug(f"已记录运行日志: {run_type}")

        except Exception as e:
            logger.error(f"记录运行日志失败: {e}")

    def cleanup_old_data(self, days: int = 90):
        """清理旧数据

        Args:
            days: 保留天数
        """
        cutoff = datetime.now() - timedelta(days=days)

        try:
            cursor = self.conn.execute(
                "DELETE FROM items WHERE published < ?",
                (cutoff.isoformat(),),
            )
            deleted = cursor.rowcount
            self.conn.commit()

            logger.info(f"已清理 {deleted} 条 {days} 天前的数据")

        except Exception as e:
            logger.error(f"清理数据失败: {e}")

    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
            logger.debug("数据库连接已关闭")


__all__ = ["Storage"]
