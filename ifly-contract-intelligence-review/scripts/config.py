"""
配置管理模块
"""

import os
from typing import Optional
from dataclasses import dataclass, field


@dataclass
class Config:
    """Skill 配置类"""

    # 输出配置
    output_format: str = "markdown"
    output_dir: str = "./output"
    save_intermediate: bool = False

    # API 配置（通过环境变量或默认）
    ocr_api_endpoint: Optional[str] = field(
        default_factory=lambda: os.environ.get("OCR_API_ENDPOINT")
    )
    ocr_api_key: Optional[str] = field(
        default_factory=lambda: os.environ.get("OCR_API_KEY")
    )

    translate_api_endpoint: Optional[str] = field(
        default_factory=lambda: os.environ.get("TRANSLATE_API_ENDPOINT")
    )
    translate_api_key: Optional[str] = field(
        default_factory=lambda: os.environ.get("TRANSLATE_API_KEY")
    )

    llm_api_endpoint: Optional[str] = field(
        default_factory=lambda: os.environ.get("LLM_API_ENDPOINT")
    )
    llm_api_key: Optional[str] = field(
        default_factory=lambda: os.environ.get("LLM_API_KEY")
    )

    # 风险检测配置
    risk_threshold_high: float = 0.8
    risk_threshold_medium: float = 0.5
    risk_threshold_low: float = 0.3

    # 文本处理配置
    min_clause_length: int = 20
    max_clause_length: int = 10000

    # 日志配置
    log_level: str = field(
        default_factory=lambda: os.environ.get("LOG_LEVEL", "INFO")
    )

    def __post_init__(self):
        """初始化后处理"""
        # 确保输出目录存在
        os.makedirs(self.output_dir, exist_ok=True)
