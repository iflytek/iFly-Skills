"""
OCR 客户端抽象接口
用于合同扫描件和图片的文字识别
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from dataclasses import dataclass

from utils.logger import LoggerMixin


@dataclass
class OCRResult:
    """OCR 识别结果"""
    text: str
    confidence: float  # 整体置信度
    regions: list  # 识别区域详情
    page_count: int = 1


class BaseOCRClient(ABC, LoggerMixin):
    """
    OCR 客户端抽象基类

    具体实现需注入实际的 OCR 服务（如讯飞 OCR、Google Cloud Vision 等）
    """

    def __init__(self, config):
        """
        初始化 OCR 客户端

        Args:
            config: 配置对象
        """
        self.config = config

    @abstractmethod
    def extract_text(self, file_path: str) -> str:
        """
        从 PDF 文件提取文本

        Args:
            file_path: PDF 文件路径

        Returns:
            提取的文本内容
        """
        pass

    @abstractmethod
    def extract_text_from_image(self, image_path: str) -> str:
        """
        从图片提取文本

        Args:
            image_path: 图片路径

        Returns:
            提取的文本内容
        """
        pass

    def extract_with_details(self, file_path: str) -> OCRResult:
        """
        带详细信息的文本提取

        Args:
            file_path: 文件路径

        Returns:
            OCRResult 对象
        """
        # 默认实现调用基础方法
        text = self.extract_text(file_path)
        return OCRResult(
            text=text,
            confidence=0.9,
            regions=[],
            page_count=1
        )


class OCRClient(BaseOCRClient):
    """
    OCR 客户端默认实现（抽象接口）

    注意：这是抽象接口示例，实际使用时需要实现具体的后端
    当前返回 NotImplementedError，提醒使用者需要注入实际实现
    """

    def extract_text(self, file_path: str) -> str:
        """
        从 PDF 文件提取文本
        """
        self.logger.info(f"OCR 提取 PDF: {file_path}")

        # 检查是否配置了实际 API
        if self.config.ocr_api_endpoint:
            # TODO: 实现实际的 OCR API 调用
            raise NotImplementedError("请注入实际的 OCR 实现")
        else:
            # 无配置时，返回抽象接口错误
            raise NotImplementedError(
                "OCR 服务未配置。请设置 OCR_API_ENDPOINT 环境变量或实现自定义 OCR 客户端"
            )

    def extract_text_from_image(self, image_path: str) -> str:
        """
        从图片提取文本
        """
        self.logger.info(f"OCR 提取图片: {image_path}")

        if self.config.ocr_api_endpoint:
            raise NotImplementedError("请注入实际的 OCR 实现")
        else:
            raise NotImplementedError(
                "OCR 服务未配置。请设置 OCR_API_ENDPOINT 环境变量或实现自定义 OCR 客户端"
            )
