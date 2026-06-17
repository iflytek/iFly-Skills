"""
合规性检查模块
负责合同规范性校对，发现格式和表述问题
"""

import re
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Set
from collections import Counter

from utils.logger import LoggerMixin


@dataclass
class ComplianceIssue:
    """合规问题"""
    id: str
    type: str  # format/terminology/inconsistency/ambiguity
    severity: str  # warning/suggestion
    title: str
    description: str
    location: str  # 位置信息
    suggestion: str
    clause_id: str = ""


class ComplianceChecker(LoggerMixin):
    """
    合规性检查处理器
    检查合同格式、术语一致性、表述规范性
    """

    def __init__(self):
        self.issues = []
        self.terminology_map = {}

    def check_title_hierarchy(self, clauses: List[Dict[str, Any]]) -> List[ComplianceIssue]:
        """检查标题层级"""
        issues = []

        # 收集所有条款标题
        titles = []
        for clause in clauses:
            title = clause.get("title", "")
            if title:
                titles.append((clause.get("id", ""), title))

        # 检查是否有编号但无标题
        for clause in clauses:
            content = clause.get("content", "")
            has_number = re.search(r"第[一二三四五六七八九十百千0-9]+条", content[:50])
            has_title = clause.get("title", "")

            if has_number and not has_title:
                issues.append(ComplianceIssue(
                    id=f"title_{clause.get('id', '')}",
                    type="format",
                    severity="warning",
                    title="条款编号但无标题",
                    description="合同中存在编号但未提取到标题的条款",
                    location=f"条款 {clause.get('clause_id', '')}",
                    suggestion="建议检查条款标题提取是否完整",
                    clause_id=clause.get("id", "")
                ))

        return issues

    def check_numbering_consistency(self, clauses: List[Dict[str, Any]]) -> List[ComplianceIssue]:
        """检查编号格式一致性"""
        issues = []

        # 收集编号格式
        numbering_formats = []
        for clause in clauses:
            title = clause.get("title", "")
            # 匹配不同编号格式
            patterns = [
                (r"第[一二三四五六七八九十百千]+条", "中文条款"),
                (r"第[0-9]+条", "数字条款"),
                (r"第[0-9]+章", "数字章节"),
                (r"^\d+\.\d+", "小数编号"),
                (r"^\d+、", "顿号编号"),
                (r"^Article\s+\d+", "英文条款"),
                (r"^Section\s+\d+", "英文章节"),
            ]

            for pattern, format_name in patterns:
                if re.match(pattern, title.strip()):
                    numbering_formats.append(format_name)
                    break

        # 检查是否混用编号格式
        if numbering_formats:
            format_counts = Counter(numbering_formats)
            if len(format_counts) > 1:
                issues.append(ComplianceIssue(
                    id="numbering_mixed",
                    type="format",
                    severity="warning",
                    title="编号格式混用",
                    description=f"合同使用了多种编号格式: {', '.join(format_counts.keys())}",
                    location="全文",
                    suggestion="建议统一编号格式，便于阅读和引用",
                    clause_id=""
                ))

        return issues

    def check_terminology_consistency(
        self,
        clauses: List[Dict[str, Any]]
    ) -> List[ComplianceIssue]:
        """检查术语一致性"""
        issues = []

        # 定义需要检查一致的术语组
        term_groups = {
            "party": [["甲方", "乙方"], ["Party A", "Party B"], ["甲方/乙方", "乙方/甲方"]],
            "amount": [["人民币", "元"], ["CNY", "RMB"], ["美元", "USD"]],
            "date": [["签署", "签订"], ["生效", "生效日期"], ["终止", "解除"]],
            "currency": [["元", "圆"], ["美元", "USD", "US$"]],
        }

        # 收集文本内容
        full_text = " ".join(c.get("content", "") for c in clauses)

        for group_name, variations in term_groups.items():
            # 检查同一组术语是否混用
            found_terms = []
            for variation_group in variations:
                for term in variation_group:
                    if term in full_text:
                        found_terms.append(term)

            if len(found_terms) > 1:
                # 发现了同一概念的不同表述
                unique_terms = list(set(found_terms))
                if len(unique_terms) > 1:
                    issues.append(ComplianceIssue(
                        id=f"term_{group_name}",
                        type="inconsistency",
                        severity="warning",
                        title=f"术语不一致: {group_name}",
                        description=f"同一概念使用了多种表述: {', '.join(unique_terms)}",
                        location="全文",
                        suggestion="建议统一术语表述，避免歧义",
                        clause_id=""
                    ))

        return issues

    def check_entity_consistency(self, clauses: List[Dict[str, Any]]) -> List[ComplianceIssue]:
        """检查主体名称一致性"""
        issues = []

        # 提取主体名称
        entities = []
        for clause in clauses:
            content = clause.get("content", "") + clause.get("title", "")
            # 匹配可能的主体名称
            patterns = [
                r"甲方[：:]\s*([^\s，。,]{2,20})",
                r"乙方[：:]\s*([^\s，。,]{2,20})",
                r"丙方[：:]\s*([^\s，。,]{2,20})",
                r"委托方[：:]\s*([^\s，。,]{2,20})",
                r"受托方[：:]\s*([^\s，。,]{2,20})",
                r"([^\s，。,]{2,20})公司",
            ]

            for pattern in patterns:
                matches = re.findall(pattern, content)
                entities.extend(matches)

        if entities:
            entity_counts = Counter(entities)
            # 检查同一主体是否有多个名称
            for entity, count in entity_counts.items():
                if count > 1:
                    # 多次出现，说明可能是主体名称
                    pass  # 暂时不标记

        return issues

    def check_date_amount_consistency(
        self,
        clauses: List[Dict[str, Any]]
    ) -> List[ComplianceIssue]:
        """检查日期和金额一致性"""
        issues = []

        full_text = " ".join(c.get("content", "") for c in clauses)

        # 提取日期格式
        date_patterns = [
            r"\d{4}年\d{1,2}月\d{1,2}日",
            r"\d{4}-\d{1,2}-\d{1,2}",
            r"\d{4}/\d{1,2}/\d{1,2}",
        ]

        dates_found = []
        for pattern in date_patterns:
            dates_found.extend(re.findall(pattern, full_text))

        # 检查日期格式混用
        if len(set(dates_found)) > 1:
            formats = set()
            for pattern in date_patterns:
                if re.search(pattern, full_text):
                    formats.add(pattern)

            if len(formats) > 1:
                issues.append(ComplianceIssue(
                    id="date_format_mixed",
                    type="inconsistency",
                    severity="warning",
                    title="日期格式混用",
                    description="合同中使用了多种日期格式",
                    location="全文",
                    suggestion="建议统一日期格式",
                    clause_id=""
                ))

        return issues

    def check_ambiguity(self, clauses: List[Dict[str, Any]]) -> List[ComplianceIssue]:
        """检查语义歧义"""
        issues = []

        ambiguous_phrases = [
            (r"其他.*等", "使用'其他'、'等'等模糊表述", "suggestion"),
            (r"相关.*费用", "'相关费用'未明确范围", "suggestion"),
            (r"合理.*费用", "'合理费用'未明确标准", "suggestion"),
            (r"可能.*情况", "使用'可能'等不确定表述", "suggestion"),
            (r"视为.*认为", "'视为'类条款需明确法律后果", "warning"),
        ]

        for clause in clauses:
            content = clause.get("content", "")

            for pattern, desc, severity in ambiguous_phrases:
                if re.search(pattern, content):
                    issues.append(ComplianceIssue(
                        id=f"ambiguity_{clause.get('id', '')}_{len(issues)}",
                        type="ambiguity",
                        severity=severity,
                        title="语义可能存在歧义",
                        description=desc,
                        location=f"条款 {clause.get('clause_id', '')}",
                        suggestion="建议明确表述，避免争议",
                        clause_id=clause.get("id", "")
                    ))

        return issues

    def check_key_definitions(
        self,
        clauses: List[Dict[str, Any]]
    ) -> List[ComplianceIssue]:
        """检查关键定义是否缺失"""
        issues = []

        # 必须包含的关键定义
        required_definitions = {
            "definition": ["定义", "释义"],
            "term": ["期限", "有效期"],
            "party": ["甲方", "乙方", "双方"],
        }

        content_all = " ".join(c.get("content", "") for c in clauses)

        found_categories = set()
        for clause in clauses:
            category = clause.get("category", "")
            if category in required_definitions:
                found_categories.add(category)

        missing = set(required_definitions.keys()) - found_categories
        if missing:
            for cat in missing:
                issues.append(ComplianceIssue(
                    id=f"missing_def_{cat}",
                    type="ambiguity",
                    severity="warning",
                    title=f"缺少{cat}相关条款",
                    description=f"合同中未找到{cat}相关定义条款",
                    location="全文",
                    suggestion="建议补充相关定义条款，明确双方权利义务",
                    clause_id=""
                ))

        return issues

    def check(self, clauses: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        合规性检查主流程

        Args:
            clauses: 条款列表

        Returns:
            合规问题列表
        """
        self.logger.info("开始合规性检查...")

        self.issues = []

        # 1. 标题层级检查
        self.issues.extend(self.check_title_hierarchy(clauses))

        # 2. 编号一致性检查
        self.issues.extend(self.check_numbering_consistency(clauses))

        # 3. 术语一致性检查
        self.issues.extend(self.check_terminology_consistency(clauses))

        # 4. 主体名称一致性
        self.issues.extend(self.check_entity_consistency(clauses))

        # 5. 日期金额一致性
        self.issues.extend(self.check_date_amount_consistency(clauses))

        # 6. 语义歧义检查
        self.issues.extend(self.check_ambiguity(clauses))

        # 7. 关键定义检查
        self.issues.extend(self.check_key_definitions(clauses))

        self.logger.info(f"合规性检查完成，发现 {len(self.issues)} 个问题")
        return [issue.__dict__ for issue in self.issues]

    def get_issue_count(self) -> int:
        """获取问题数量"""
        return len(self.issues)

    def get_issues_by_type(self, issue_type: str) -> List[ComplianceIssue]:
        """按类型获取问题"""
        return [issue for issue in self.issues if issue.type == issue_type]
