"""
双语一致性检查模块
负责中英双语合同的一致性核对
"""

import re
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple

from utils.logger import LoggerMixin


@dataclass
class BilingualIssue:
    """双语不一致问题"""
    id: str
    clause_id: str
    issue_type: str  # missing_translation/semantic_deviation/format_inconsistency
    severity: str  # high/medium/low
    title: str
    source_text: str
    target_text: Optional[str]
    description: str
    suggestion: str


class BilingualChecker(LoggerMixin):
    """
    双语一致性检查处理器
    检查中英双语合同的关键条款一致性
    """

    def __init__(self):
        self.issues = []
        self.segments = []

    def align_clauses(
        self,
        source_clauses: List[Dict[str, Any]],
        target_clauses: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        对齐双语条款

        Args:
            source_clauses: 源语言条款
            target_clauses: 目标语言条款

        Returns:
            对齐的条款对列表
        """
        aligned = []

        # 基于标题或编号进行匹配
        for src in source_clauses:
            src_title = src.get("title", "")
            src_id = src.get("id", "")

            # 尝试找到对应的目标条款
            matched = None
            for tgt in target_clauses:
                tgt_title = tgt.get("title", "")

                # 提取编号
                src_num = self._extract_number(src_title)
                tgt_num = self._extract_number(tgt_title)

                if src_num and tgt_num and src_num == tgt_num:
                    matched = tgt
                    break

                # 模糊匹配
                if src_title and tgt_title:
                    # 检查关键词重叠
                    src_keywords = set(self._extract_keywords(src_title))
                    tgt_keywords = set(self._extract_keywords(tgt_title))
                    if src_keywords & tgt_keywords:  # 有交集
                        matched = tgt
                        break

            aligned.append({
                "source": src,
                "target": matched,
                "aligned": matched is not None
            })

        return aligned

    def _extract_number(self, text: str) -> Optional[str]:
        """提取条款编号"""
        patterns = [
            r"第[一二三四五六七八九十百千0-9]+条",
            r"第[0-9]+条",
            r"^\d+\.",
            r"^\d+、",
            r"Article\s+\d+",
            r"Section\s+\d+",
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(0)

        return None

    def _extract_keywords(self, text: str) -> List[str]:
        """提取关键词"""
        # 简单实现，提取连续的中文或英文词
        chinese = re.findall(r"[\u4e00-\u9fff]{2,}", text)
        english = re.findall(r"[a-zA-Z]{3,}", text)
        return chinese + english

    def check_semantic_deviation(
        self,
        source_text: str,
        target_text: str
    ) -> Tuple[bool, str]:
        """
        检查语义偏差

        Args:
            source_text: 源语文本
            target_text: 目标语文本

        Returns:
            (是否有偏差, 描述)
        """
        # 这是一个简化实现
        # 实际应该使用更复杂的语义匹配算法

        # 检查关键数字是否一致
        src_numbers = re.findall(r"\d+", source_text)
        tgt_numbers = re.findall(r"\d+", target_text)

        if src_numbers and tgt_numbers:
            src_nums_set = set(src_numbers)
            tgt_nums_set = set(tgt_numbers)
            if src_nums_set != tgt_nums_set:
                return True, f"数字不一致: 原文 {src_numbers}, 译文 {tgt_numbers}"

        # 检查关键日期是否一致
        src_dates = re.findall(r"\d{4}[-/年]\d+[-/月]\d+", source_text)
        tgt_dates = re.findall(r"\d{4}[-/]\d+[-/]\d+", target_text)

        if src_dates and tgt_dates:
            if src_dates != tgt_dates:
                return True, f"日期不一致"

        return False, ""

    def check_missing_translation(
        self,
        source_clauses: List[Dict[str, Any]],
        aligned_clauses: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        检查缺失翻译

        Args:
            source_clauses: 源语言条款
            aligned_clauses: 对齐的条款

        Returns:
            缺失翻译的条款列表
        """
        missing = []

        for aligned in aligned_clauses:
            if not aligned["aligned"]:
                source = aligned["source"]
                missing.append({
                    "clause_id": source.get("id", ""),
                    "title": source.get("title", ""),
                    "has_source": True,
                    "has_target": False,
                    "reason": "未找到对应翻译"
                })

        return missing

    def check_format_consistency(
        self,
        source_clauses: List[Dict[str, Any]],
        target_clauses: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        检查格式一致性

        Args:
            source_clauses: 源语言条款
            target_clauses: 目标语言条款

        Returns:
            格式不一致项
        """
        issues = []

        # 检查条款数量是否一致
        if len(source_clauses) != len(target_clauses):
            issues.append({
                "type": "count_mismatch",
                "description": f"条款数量不一致: 源文 {len(source_clauses)}, 译文 {len(target_clauses)}",
                "severity": "high"
            })

        return issues

    def check(
        self,
        source_clauses: Optional[List[Dict[str, Any]]] = None,
        target_clauses: Optional[List[Dict[str, Any]]] = None,
        bilingual_text: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        双语检查主流程

        Args:
            source_clauses: 源语言条款列表
            target_clauses: 目标语言条款列表
            bilingual_text: 双语文本（直接传入时使用）

        Returns:
            双语问题列表
        """
        self.logger.info("开始双语一致性检查...")
        self.issues = []

        # 如果传入的是双语文本，需要先拆分
        if bilingual_text and not source_clauses:
            # TODO: 实现双语文本拆分
            pass

        if source_clauses and target_clauses:
            # 1. 对齐条款
            aligned = self.align_clauses(source_clauses, target_clauses)

            # 2. 检查缺失翻译
            missing = self.check_missing_translation(source_clauses, aligned)
            for m in missing:
                self.issues.append({
                    "id": f"missing_{m['clause_id']}",
                    "clause_id": m["clause_id"],
                    "issue_type": "missing_translation",
                    "severity": "high",
                    "title": m.get("title", ""),
                    "source_text": m.get("title", ""),
                    "target_text": None,
                    "description": m.get("reason", "未找到对应翻译"),
                    "suggestion": "需人工补充翻译"
                })

            # 3. 检查语义偏差
            for aligned_item in aligned:
                if aligned_item["aligned"]:
                    src = aligned_item["source"]["content"]
                    tgt = aligned_item["target"]["content"]

                    has_deviation, desc = self.check_semantic_deviation(src, tgt)
                    if has_deviation:
                        self.issues.append({
                            "id": f"deviation_{aligned_item['source']['id']}",
                            "clause_id": aligned_item["source"]["id"],
                            "issue_type": "semantic_deviation",
                            "severity": "medium",
                            "title": aligned_item["source"].get("title", ""),
                            "source_text": src[:200],
                            "target_text": tgt[:200],
                            "description": desc,
                            "suggestion": "需人工核对语义一致性"
                        })

            # 4. 检查格式一致性
            format_issues = self.check_format_consistency(source_clauses, target_clauses)
            for fi in format_issues:
                self.issues.append({
                    "id": f"format_{fi['type']}",
                    "clause_id": "",
                    "issue_type": "format_inconsistency",
                    "severity": fi.get("severity", "low"),
                    "title": "",
                    "source_text": "",
                    "target_text": "",
                    "description": fi.get("description", ""),
                    "suggestion": "建议统一格式"
                })

        self.logger.info(f"双语检查完成，发现 {len(self.issues)} 个问题")
        return self.issues

    def get_issue_count(self) -> int:
        """获取问题数量"""
        return len(self.issues)
