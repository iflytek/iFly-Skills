"""
输入预处理模块
处理文件类型检测、格式识别、预处理质量评估
"""

import os
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

from utils.logger import LoggerMixin
from utils.file_utils import get_file_size, get_page_count


class InputPreprocessor(LoggerMixin):
    """
    输入预处理
    负责文件类型检测、可读性评估、预处理质量评估
    """

    # 支持的文件格式
    SUPPORTED_FORMATS = {
        "pdf": [".pdf"],
        "image": [".jpg", ".jpeg", ".png", ".bmp", ".heic"],
        "word": [".docx", ".doc"],
        "text": [".md", ".txt", ".json"]
    }

    def __init__(self):
        self.preprocess_result = {}

    def detect_type(self, file_path: str) -> Tuple[str, str]:
        """
        检测文件类型

        Args:
            file_path: 文件路径

        Returns:
            (文件类型, 提取方法)
        """
        path = Path(file_path)
        suffix = path.suffix.lower()

        # PDF
        if suffix in self.SUPPORTED_FORMATS["pdf"]:
            page_count = get_page_count(file_path)
            self.logger.info(f"PDF 文件，页数: {page_count}")
            return "pdf", "pdf_extract"

        # 图片
        elif suffix in self.SUPPORTED_FORMATS["image"]:
            return "image", "image_ocr"

        # Word
        elif suffix in self.SUPPORTED_FORMATS["word"]:
            return "word", "docx_extract"

        # 文本
        elif suffix in self.SUPPORTED_FORMATS["text"]:
            return "text", "text_read"

        else:
            return "unknown", ""

    def assess_quality(self, file_path: str) -> Dict[str, Any]:
        """
        评估输入质量

        Args:
            file_path: 文件路径

        Returns:
            质量评估结果
        """
        path = Path(file_path)
        file_size = get_file_size(file_path)

        result = {
            "filename": path.name,
            "file_size": file_size,
            "file_size_mb": round(file_size / 1024 / 1024, 2),
            "estimated_readable": True,
            "quality_concerns": []
        }

        # 文件大小检查
        if file_size < 1024:
            result["quality_concerns"].append("文件过小，可能为空或损坏")
            result["estimated_readable"] = False
        elif file_size > 50 * 1024 * 1024:
            result["quality_concerns"].append("文件较大，处理可能较慢")

        # 检查扩展名
        if path.suffix.lower() not in [
            ext for exts in self.SUPPORTED_FORMATS.values() for ext in exts
        ]:
            result["quality_concerns"].append(f"不支持的格式: {path.suffix}")
            result["estimated_readable"] = False

        self.preprocess_result = result
        return result

    def preprocess(self, file_path: str) -> Dict[str, Any]:
        """
        预处理主流程

        Args:
            file_path: 文件路径

        Returns:
            预处理结果
        """
        self.logger.info(f"预处理文件: {file_path}")

        # 类型检测
        file_type, extraction_method = self.detect_type(file_path)

        # 质量评估
        quality = self.assess_quality(file_path)

        result = {
            "file_path": file_path,
            "file_type": file_type,
            "extraction_method": extraction_method,
            "quality": quality,
            "ready_for_processing": file_type != "unknown" and quality["estimated_readable"]
        }

        self.preprocess_result = result
        return result
