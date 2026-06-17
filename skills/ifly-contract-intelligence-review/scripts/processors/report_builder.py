"""
报告生成模块
负责生成 Markdown 和 JSON 格式的审核报告
"""

import json
from datetime import datetime
from typing import Dict, Any, List, Optional

from utils.logger import LoggerMixin


class ReportBuilder(LoggerMixin):
    """
    报告生成处理器
    生成结构化的合同审核报告
    """

    def __init__(self):
        self.template_vars = {}

    def generate_summary(self, result: Dict[str, Any]) -> str:
        """
        生成审核摘要

        Args:
            result: 完整审核结果

        Returns:
            摘要文本
        """
        risks = result.get("risks", [])
        compliance = result.get("compliance_issues", [])

        high_risks = [r for r in risks if r.get("level") == "high"]
        medium_risks = [r for r in risks if r.get("level") == "medium"]
        low_risks = [r for r in risks if r.get("level") == "low"]

        human_review = result.get("human_review_required", [])

        summary_parts = []

        # 风险统计
        if high_risks:
            summary_parts.append(f"发现 {len(high_risks)} 个高风险项")
        if medium_risks:
            summary_parts.append(f"{len(medium_risks)} 个中风险项")
        if low_risks:
            summary_parts.append(f"{len(low_risks)} 个低风险项")

        # 合规问题
        if compliance:
            summary_parts.append(f"合规性问题 {len(compliance)} 项")

        # 需人工复核
        if human_review:
            summary_parts.append(f"需人工复核 {len(human_review)} 项")

        if not summary_parts:
            return "未发现明显风险点"

        return "，".join(summary_parts)

    def build_markdown(self, result: Dict[str, Any]) -> str:
        """
        生成 Markdown 格式报告

        Args:
            result: 完整审核结果

        Returns:
            Markdown 报告文本
        """
        doc_meta = result.get("document_meta", {})
        extraction = result.get("extraction_quality", {})
        clauses = result.get("clauses", [])
        risks = result.get("risks", [])
        compliance = result.get("compliance_issues", [])
        bilingual = result.get("bilingual_issues", [])
        translation = result.get("translation_summary")
        uncertain = result.get("uncertain_items", [])
        human_review = result.get("human_review_required", [])

        lines = []

        # 标题
        lines.append("# 合同智能审核报告")
        lines.append("")
        lines.append(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")

        # 文档基本信息
        lines.append("## 文档基本信息")
        lines.append("")
        lines.append(f"- **文件名**: {doc_meta.get('filename', 'N/A')}")
        lines.append(f"- **文件类型**: {doc_meta.get('input_type', 'N/A')}")
        lines.append(f"- **提取方法**: {doc_meta.get('extraction_method', 'N/A')}")
        lines.append(f"- **语言**: {doc_meta.get('language', 'N/A')}")
        lines.append(f"- **审核模式**: {doc_meta.get('review_mode', 'N/A')}")
        focus = doc_meta.get("focus", [])
        if focus:
            lines.append(f"- **重点关注**: {', '.join(focus)}")
        lines.append("")

        # 输入质量评估
        lines.append("## 输入质量评估")
        lines.append("")
        lines.append(f"- **文本长度**: {extraction.get('text_length', 0)} 字符")
        lines.append(f"- **识别置信度**: {extraction.get('confidence', 0):.0%}")
        uncertain_regions = extraction.get("uncertain_regions", [])
        if uncertain_regions:
            lines.append(f"- **识别不确定区域**: {len(uncertain_regions)} 处")
        lines.append("")

        # 不确定性标记
        if uncertain:
            lines.append("### 不确定项")
            lines.append("")
            for item in uncertain:
                lines.append(f"- [待确认] {item}")
            lines.append("")

        # 合同结构概览
        lines.append("## 合同结构概览")
        lines.append("")
        lines.append(f"- **条款数量**: {len(clauses)}")

        # 按类别统计
        categories = {}
        for clause in clauses:
            cat = clause.get("category", "general")
            categories[cat] = categories.get(cat, 0) + 1

        if categories:
            lines.append("- **条款分类**:")
            for cat, count in sorted(categories.items()):
                lines.append(f"  - {cat}: {count}")
        lines.append("")

        # 风险清单
        if risks:
            lines.append("## 风险清单")
            lines.append("")

            # 按等级分组
            high = [r for r in risks if r.get("level") == "high"]
            medium = [r for r in risks if r.get("level") == "medium"]
            low = [r for r in risks if r.get("level") == "low"]

            if high:
                lines.append("### 高风险")
                lines.append("")
                for r in high:
                    lines.append(f"- **{r.get('title', '')}**")
                    lines.append(f"  - 类别: {r.get('category', '')}")
                    lines.append(f"  - 来源: [{r.get('source', '')}]")
                    evidence = r.get("evidence", "")
                    if evidence:
                        lines.append(f"  - 原文: 「{evidence[:100]}...」")
                    lines.append(f"  - 建议: {r.get('suggestion', '')}")
                    lines.append("")
                lines.append("")

            if medium:
                lines.append("### 中风险")
                lines.append("")
                for r in medium:
                    lines.append(f"- **{r.get('title', '')}**")
                    lines.append(f"  - 类别: {r.get('category', '')}")
                    lines.append(f"  - 来源: [{r.get('source', '')}]")
                    lines.append(f"  - 建议: {r.get('suggestion', '')}")
                lines.append("")

            if low:
                lines.append("### 低风险")
                lines.append("")
                for r in low:
                    lines.append(f"- {r.get('title', '')}")
                lines.append("")

        # 规范性校对问题
        if compliance:
            lines.append("## 规范性校对问题")
            lines.append("")
            for c in compliance:
                severity_emoji = "⚠️" if c.get("severity") == "warning" else "💡"
                lines.append(f"{severity_emoji} **{c.get('title', '')}**")
                lines.append(f"  - 类型: {c.get('type', '')}")
                lines.append(f"  - 描述: {c.get('description', '')}")
                lines.append(f"  - 建议: {c.get('suggestion', '')}")
                lines.append("")
            lines.append("")

        # 双语检查结果
        if bilingual:
            lines.append("## 双语一致性检查")
            lines.append("")
            for b in bilingual:
                lines.append(f"- **{b.get('title', '')}**")
                lines.append(f"  - 类型: {b.get('issue_type', '')}")
                lines.append(f"  - 问题: {b.get('description', '')}")
            lines.append("")

        # 翻译摘要
        if translation:
            lines.append("## 翻译摘要")
            lines.append("")
            lines.append(translation)
            lines.append("")

        # 人工复核建议
        if human_review:
            lines.append("## 人工复核建议")
            lines.append("")
            for flag in human_review:
                lines.append(f"- ⚠️ {flag}")
            lines.append("")

        # 附录：原文引用
        if clauses and len(clauses) <= 10:
            lines.append("## 附录：原文条款结构")
            lines.append("")
            for clause in clauses:
                title = clause.get("title", "(无标题)")
                lines.append(f"### {clause.get('clause_id', '')} {title}")
                content = clause.get("content", "")
                if content:
                    lines.append(f"_{content[:200]}..._")
                lines.append("")

        lines.append("---")
        lines.append("*本报告由合同智能审核 Skill 自动生成，仅供参考*")

        return "\n".join(lines)

    def build_json(self, result: Dict[str, Any]) -> str:
        """
        生成 JSON 格式输出

        Args:
            result: 完整审核结果

        Returns:
            JSON 字符串
        """
        # 确保可序列化
        output = {
            "meta": {
                "generated_at": datetime.now().isoformat(),
                "skill_version": "1.0.0",
                "skill_name": "contract-intelligence-review"
            },
            "document_meta": result.get("document_meta", {}),
            "extraction_quality": result.get("extraction_quality", {}),
            "clauses": result.get("clauses", []),
            "risks": result.get("risks", []),
            "compliance_issues": result.get("compliance_issues", []),
            "bilingual_issues": result.get("bilingual_issues", []),
            "translation_summary": result.get("translation_summary"),
            "uncertain_items": result.get("uncertain_items", []),
            "human_review_required": result.get("human_review_required", []),
            "final_summary": result.get("final_summary", "")
        }

        return json.dumps(output, ensure_ascii=False, indent=2)

    @staticmethod
    def generate_summary(result: Dict[str, Any]) -> str:
        """静态方法：生成摘要"""
        builder = ReportBuilder()
        return builder.generate_summary(result)
