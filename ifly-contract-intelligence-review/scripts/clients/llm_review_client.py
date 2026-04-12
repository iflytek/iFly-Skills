"""
LLM 合同审核客户端抽象接口
用于条款理解、风险判断和专业审核建议
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

from utils.logger import LoggerMixin


@dataclass
class ReviewResult:
    """审核结果"""
    summary: str
    key_clauses: List[Dict]  # 关键条款
    risks: List[Dict]  # 风险项
    suggestions: List[str]  # 建议
    confidence: float


@dataclass
class ClauseAnalysis:
    """条款分析结果"""
    clause_id: str
    title: str
    content: str
    category: str  # 条款类别
    importance: str  # high/medium/low
    issues: List[str]  # 发现的问题


class BaseLLMReviewClient(ABC, LoggerMixin):
    """
    LLM 审核客户端抽象基类
    """

    def __init__(self, config):
        self.config = config

    @abstractmethod
    def review_contract(
        self,
        text: str,
        review_mode: str,
        focus_areas: List[str]
    ) -> ReviewResult:
        """
        合同审核

        Args:
            text: 合同文本
            review_mode: 审核模式 quick/standard/deep
            focus_areas: 重点审核领域

        Returns:
            ReviewResult 对象
        """
        pass

    @abstractmethod
    def analyze_clause(
        self,
        clause_text: str,
        clause_title: str,
        category: str
    ) -> ClauseAnalysis:
        """
        单个条款分析

        Args:
            clause_text: 条款文本
            clause_title: 条款标题
            category: 条款类别

        Returns:
            ClauseAnalysis 对象
        """
        pass

    @abstractmethod
    def generate_summary(
        self,
        text: str,
        max_length: int
    ) -> str:
        """
        生成摘要

        Args:
            text: 文本内容
            max_length: 最大长度

        Returns:
            摘要文本
        """
        pass


class LLMReviewClient(BaseLLMReviewClient):
    """
    LLM 合同审核客户端默认实现（抽象接口）
    """

    def review_contract(
        self,
        text: str,
        review_mode: str,
        focus_areas: List[str]
    ) -> ReviewResult:
        """
        合同审核
        """
        self.logger.info(f"合同审核: mode={review_mode}, focus={focus_areas}")

        if self.config.llm_api_endpoint:
            raise NotImplementedError("请注入实际的 LLM 审核实现")
        else:
            raise NotImplementedError(
                "LLM 审核服务未配置。请设置 LLM_API_ENDPOINT 环境变量或实现自定义客户端"
            )

    def analyze_clause(
        self,
        clause_text: str,
        clause_title: str,
        category: str
    ) -> ClauseAnalysis:
        """
        单个条款分析
        """
        self.logger.info(f"条款分析: {clause_title}")

        if self.config.llm_api_endpoint:
            raise NotImplementedError("请注入实际的 LLM 审核实现")
        else:
            raise NotImplementedError(
                "LLM 审核服务未配置"
            )

    def generate_summary(
        self,
        text: str,
        max_length: int
    ) -> str:
        """
        生成摘要
        """
        self.logger.info(f"生成摘要: max_length={max_length}")

        if self.config.llm_api_endpoint:
            raise NotImplementedError("请注入实际的 LLM 审核实现")
        else:
            raise NotImplementedError(
                "LLM 审核服务未配置"
            )
