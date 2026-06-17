"""
文件工具模块
"""

import os
from pathlib import Path
from typing import Union

from errors import FileAccessError


def load_input_file(file_path: Union[str, Path]) -> str:
    """
    加载输入文件内容

    Args:
        file_path: 文件路径

    Returns:
        文件文本内容

    Raises:
        FileAccessError: 文件访问错误
    """
    path = Path(file_path)

    if not path.exists():
        raise FileAccessError(f"文件不存在: {file_path}")

    try:
        # 尝试 UTF-8 编码
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            # 尝试 GBK 编码（兼容部分中文文件）
            return path.read_text(encoding="gbk")
        except UnicodeDecodeError:
            raise FileAccessError(f"无法读取文件编码: {file_path}")


def ensure_output_dir(dir_path: Union[str, Path]) -> Path:
    """
    确保输出目录存在

    Args:
        dir_path: 目录路径

    Returns:
        Path 对象
    """
    path = Path(dir_path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_file_size(file_path: Union[str, Path]) -> int:
    """
    获取文件大小（字节）

    Args:
        file_path: 文件路径

    Returns:
        文件大小
    """
    return Path(file_path).stat().st_size


def is_supported_format(file_path: Union[str, Path]) -> bool:
    """
    检查文件格式是否支持

    Args:
        file_path: 文件路径

    Returns:
        是否支持
    """
    suffix = Path(file_path).suffix.lower()
    supported = [
        ".pdf",
        ".jpg", ".jpeg", ".png", ".bmp", ".heic",
        ".docx", ".doc",
        ".md", ".txt"
    ]
    return suffix in supported


def get_page_count(file_path: Union[str, Path]) -> int:
    """
    尝试获取 PDF 页数

    Args:
        file_path: PDF 文件路径

    Returns:
        页数，失败返回 0
    """
    try:
        import PyPDF2
        with open(file_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            return len(reader.pages)
    except Exception:
        return 0
