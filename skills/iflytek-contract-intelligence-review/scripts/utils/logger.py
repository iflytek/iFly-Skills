"""
日志工具模块
"""

import logging
import sys
from typing import Optional


def get_logger(name: str, level: Optional[str] = None) -> logging.Logger:
    """
    获取日志记录器

    Args:
        name: 日志记录器名称
        level: 日志级别，默认从环境变量 LOG_LEVEL 获取

    Returns:
        配置好的日志记录器
    """
    import os

    if level is None:
        level = os.environ.get("LOG_LEVEL", "INFO")

    logger = logging.getLogger(name)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    return logger


class LoggerMixin:
    """日志混入类，用于给其他类添加日志能力"""

    @property
    def logger(self) -> logging.Logger:
        """获取当前类的日志记录器"""
        name = f"{self.__class__.__module__}.{self.__class__.__name__}"
        return get_logger(name)
