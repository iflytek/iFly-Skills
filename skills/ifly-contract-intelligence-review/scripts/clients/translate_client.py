"""
翻译客户端抽象接口
用于合同翻译和双语对照
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

from utils.logger import LoggerMixin


@dataclass
class TranslationResult:
    """翻译结果"""
    translated_text: str
    source_lang: str
    target_lang: str
    confidence: float


@dataclass
class BilingualSegment:
    """双语对照片段"""
    source_text: str
    translated_text: str
    source_lang: str
    target_lang: str
    match_confidence: float  # 匹配度


class BaseTranslateClient(ABC, LoggerMixin):
    """
    翻译客户端抽象基类
    """

    def __init__(self, config):
        self.config = config

    @abstractmethod
    def translate(self, text: str, source_lang: str, target_lang: str) -> TranslationResult:
        """
        翻译文本

        Args:
            text: 源文本
            source_lang: 源语言
            target_lang: 目标语言

        Returns:
            TranslationResult 对象
        """
        pass

    @abstractmethod
    def translate_summary(self, text: str, target_lang: str = "zh") -> str:
        """
        翻译摘要

        Args:
            text: 源文本
            target_lang: 目标语言

        Returns:
            摘要翻译文本
        """
        pass

    @abstractmethod
    def create_bilingual_segments(
        self,
        source_text: str,
        target_text: str,
        source_lang: str,
        target_lang: str
    ) -> List[BilingualSegment]:
        """
        创建双语对照片段

        Args:
            source_text: 源语文本
            target_text: 目标语文本
            source_lang: 源语言
            target_lang: 目标语言

        Returns:
            双语对照片段列表
        """
        pass


class TranslateClient(BaseTranslateClient):
    """
    翻译客户端默认实现（抽象接口）
    """

    def translate(self, text: str, source_lang: str, target_lang: str) -> TranslationResult:
        """
        翻译文本
        """
        self.logger.info(f"翻译: {source_lang} -> {target_lang}")

        if self.config.translate_api_endpoint:
            raise NotImplementedError("请注入实际的翻译实现")
        else:
            raise NotImplementedError(
                "翻译服务未配置。请设置 TRANSLATE_API_ENDPOINT 环境变量或实现自定义客户端"
            )

    def translate_summary(self, text: str, target_lang: str = "zh") -> str:
        """
        翻译摘要
        """
        self.logger.info(f"翻译摘要: {target_lang}")

        if self.config.translate_api_endpoint:
            raise NotImplementedError("请注入实际的翻译实现")
        else:
            raise NotImplementedError(
                "翻译服务未配置"
            )

    def create_bilingual_segments(
        self,
        source_text: str,
        target_text: str,
        source_lang: str,
        target_lang: str
    ) -> List[BilingualSegment]:
        """
        创建双语对照片段
        """
        self.logger.info(f"创建双语对照: {source_lang} <-> {target_lang}")

        if self.config.translate_api_endpoint:
            raise NotImplementedError("请注入实际的翻译实现")
        else:
            raise NotImplementedError(
                "翻译服务未配置"
            )
