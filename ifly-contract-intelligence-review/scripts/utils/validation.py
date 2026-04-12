"""
输入验证模块
"""

import os
from pathlib import Path
from typing import Union

from errors import InputValidationError, UnsupportedFormatError


SUPPORTED_FORMATS = {
    ".pdf",  # PDF 文件（扫描件或文字版）
    ".jpg", ".jpeg", ".png", ".bmp", ".heic",  # 图片
    ".docx", ".doc",  # Word 文档
    ".md", ".txt",  # 文本格式
}

MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB


def validate_input_file(file_path: Union[str, Path]) -> Path:
    """
    验证输入文件

    Args:
        file_path: 文件路径

    Returns:
        Path 对象

    Raises:
        InputValidationError: 验证失败
    """
    path = Path(file_path)

    # 检查文件是否存在
    if not path.exists():
        raise InputValidationError(f"文件不存在: {file_path}")

    # 检查是否为文件
    if not path.is_file():
        raise InputValidationError(f"不是有效文件: {file_path}")

    # 检查文件大小
    file_size = path.stat().st_size
    if file_size == 0:
        raise InputValidationError(f"文件为空: {file_path}")

    if file_size > MAX_FILE_SIZE:
        raise InputValidationError(f"文件过大 ({file_size / 1024 / 1024:.1f}MB)，最大支持 {MAX_FILE_SIZE / 1024 / 1024}MB")

    # 检查文件格式
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_FORMATS:
        raise UnsupportedFormatError(
            f"不支持的文件格式: {suffix}。支持格式: {', '.join(SUPPORTED_FORMATS)}"
        )

    return path


def validate_output_dir(dir_path: Union[str, Path]) -> Path:
    """
    验证输出目录

    Args:
        dir_path: 目录路径

    Returns:
        Path 对象
    """
    path = Path(dir_path)

    # 尝试创建目录
    path.mkdir(parents=True, exist_ok=True)

    # 检查是否可写
    if not os.access(path.parent, os.W_OK):
        raise InputValidationError(f"目录不可写: {dir_path}")

    return path
