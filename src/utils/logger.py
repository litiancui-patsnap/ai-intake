"""日志工具"""

import logging
import sys
from typing import Optional


class ColoredFormatter(logging.Formatter):
    """带颜色的日志格式化器"""

    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def format(self, record):
        log_color = self.COLORS.get(record.levelname, self.RESET)
        record.levelname = f"{log_color}{record.levelname:8s}{self.RESET}"
        return super().format(record)


def setup_logger(name: str = "ai-intake", level: int = logging.INFO) -> logging.Logger:
    """设置日志记录器

    Args:
        name: 日志记录器名称
        level: 日志级别

    Returns:
        配置好的日志记录器
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # 避免重复添加handler
    if logger.handlers:
        return logger

    # 控制台handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)

    # 格式化器
    formatter = ColoredFormatter(
        "[%(asctime)s] %(levelname)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
    console_handler.setFormatter(formatter)

    logger.addHandler(console_handler)

    return logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """获取日志记录器

    Args:
        name: 子模块名称，如 'ingest', 'score' 等

    Returns:
        日志记录器
    """
    if name:
        return logging.getLogger(f"ai-intake.{name}")
    return logging.getLogger("ai-intake")
