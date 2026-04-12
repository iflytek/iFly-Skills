"""
图像理解客户端抽象接口
用于复杂图片内容的理解（如图表、印章、手写等）
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from dataclasses import dataclass

from utils.logger import LoggerMixin


@dataclass
class ImageUnderstandingResult:
    """图像理解结果"""
    text: str
    elements: list  # 识别到的元素
    confidence: float


class BaseImageClient(ABC, LoggerMixin):
    """
    图像理解客户端抽象基类

    用于处理 OCR 无法很好处理的复杂图片场景
    """

    def __init__(self, config):
        self.config = config

    @abstractmethod
    def understand_image(self, image_path: str) -> str:
        """
        理解图片内容

        Args:
            image_path: 图片路径

        Returns:
            理解后的文本描述
        """
        pass

    @abstractmethod
    def extract_elements(self, image_path: str) -> list:
        """
        提取图片中的元素

        Args:
            image_path: 图片路径

        Returns:
            元素列表
        """
        pass


class ImageClient(BaseImageClient):
    """
    图像理解客户端默认实现（抽象接口）
    """

    def understand_image(self, image_path: str) -> str:
        """
        理解图片内容
        """
        self.logger.info(f"图像理解: {image_path}")

        if self.config.llm_api_endpoint:
            raise NotImplementedError("请注入实际的图像理解实现")
        else:
            raise NotImplementedError(
                "图像理解服务未配置。请设置 LLM_API_ENDPOINT 环境变量或实现自定义客户端"
            )

    def extract_elements(self, image_path: str) -> list:
        """
        提取图片中的元素
        """
        self.logger.info(f"图像元素提取: {image_path}")

        if self.config.llm_api_endpoint:
            raise NotImplementedError("请注入实际的图像理解实现")
        else:
            raise NotImplementedError(
                "图像理解服务未配置"
            )
