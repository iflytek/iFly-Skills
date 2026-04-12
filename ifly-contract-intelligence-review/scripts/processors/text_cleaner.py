"""
文本清洗模块
负责去除乱码、段落重组、文本标准化
"""

import re
from typing import List, Dict, Any

from utils.logger import LoggerMixin


class TextCleaner(LoggerMixin):
    """
    文本清洗处理器
    清理合同文本中的噪音，标准化格式
    """

    # 常见乱码模式
    GARBAGE_PATTERNS = [
        r'[\x00-\x08\x0b-\x0c\x0e-\x1f]',  # 控制字符
        r'[\ufffd]',  # Unicode 替换字符
        r'□+',  # 方框占位符
        r'▢+',  # 方框占位符变体
        r'[\u3000]+',  # 全角空格
    ]

    # 需要保留的特殊字符
    PRESERVE_CHARS = r'[\w\u4e00-\u9fff\u3400-\u4dbf.,;:!?()（）【】《》""''「」‖\-–—·]'

    def __init__(self):
        self.clean_stats = {
            "garbage_removed": 0,
            "whitespace_normalized": 0,
            "lines_processed": 0
        }

    def remove_garbage(self, text: str) -> str:
        """去除乱码和无效字符"""
        result = text

        for pattern in self.GARBAGE_PATTERNS:
            matches = len(re.findall(pattern, result))
            self.clean_stats["garbage_removed"] += matches
            result = re.sub(pattern, '', result)

        return result

    def normalize_whitespace(self, text: str) -> str:
        """标准化空白字符"""
        # 多个空格/换行合并为一个
        result = re.sub(r'[ \t]+', ' ', text)
        result = re.sub(r'\n\s*\n', '\n\n', result)

        self.clean_stats["whitespace_normalized"] = 1
        return result

    def remove_page_breaks(self, text: str) -> str:
        """移除分页符"""
        # 常见分页符
        result = re.sub(r'(?<=\n)={3,50}(?=\n)', '', text)
        result = re.sub(r'(?<=\n)-{3,50}(?=\n)', '', text)
        result = re.sub(r'第\s*\d+\s*页', '', result)
        result = re.sub(r'Page\s+\d+', '', result, flags=re.IGNORECASE)

        return result

    def fix_common_ocr_errors(self, text: str) -> str:
        """修复常见 OCR 错误"""
        result = text

        # 常见易错字符替换（基于上下文）
        replacements = [
            # 数字混淆
            (r'0(?=[a-zA-Z])', 'O'),  # 0O -> OO
            (r'l(?=[0-9])', '1'),  # l1 -> 11
            (r'O(?=[0-9])', '0'),  # O0 -> 00

            # 中文标点修复
            (r'。([^\n])', r'。\n\1'),  # 句号后换行
            (r'；([^\n])', r'；\n\1'),  # 分号后换行

            # 常见连续字符
            (r'_{10,}', ''),  # 长下划线
            (r'-{10,}', ''),  # 长横线
        ]

        for pattern, replacement in replacements:
            result = re.sub(pattern, replacement, result)

        return result

    def split_into_sentences(self, text: str) -> List[str]:
        """将文本拆分为句子"""
        # 基于常见句末标点分割
        sentence_end = r'[。！？；\n]'
        sentences = re.split(sentence_end, text)

        # 过滤空句子
        return [s.strip() for s in sentences if s.strip()]

    def clean(self, text: str) -> str:
        """
        文本清洗主流程

        Args:
            text: 原始文本

        Returns:
            清洗后的文本
        """
        self.logger.info("开始文本清洗...")
        self.clean_stats = {"garbage_removed": 0, "whitespace_normalized": 0, "lines_processed": 0}

        result = text

        # 1. 移除乱码
        result = self.remove_garbage(result)

        # 2. 移除分页符
        result = self.remove_page_breaks(result)

        # 3. 修复 OCR 错误
        result = self.fix_common_ocr_errors(result)

        # 4. 标准化空白
        result = self.normalize_whitespace(result)

        self.logger.info(
            f"文本清洗完成: 移除乱码 {self.clean_stats['garbage_removed']} 处, "
            f"文本长度 {len(result)}"
        )

        return result

    def get_stats(self) -> Dict[str, Any]:
        """获取清洗统计"""
        return self.clean_stats
