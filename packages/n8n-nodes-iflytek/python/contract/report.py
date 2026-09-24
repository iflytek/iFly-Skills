"""n8n report compatibility without modifying the original report processor."""
from processors.report_builder import ReportBuilder as SkillReportBuilder


class _UnknownConfidence:
    def __format__(self, spec):
        return '未提供；请核对原文'


class ReportBuilder(SkillReportBuilder):
    @staticmethod
    def generate_summary(result):
        # The upstream static method recursively calls itself. Supply the same
        # risk-count summary locally while reusing its Markdown report builder.
        risks = result.get('risks', [])
        parts = []
        for level, label in [('high', '发现 {} 个高风险项'), ('medium', '{} 个中风险项'), ('low', '{} 个低风险项')]:
            count = sum(risk.get('level') == level for risk in risks)
            if count:
                parts.append(label.format(count))
        if result.get('compliance_issues'):
            parts.append(f"合规性问题 {len(result['compliance_issues'])} 项")
        if result.get('human_review_required'):
            parts.append(f"需人工复核 {len(result['human_review_required'])} 项")
        return '，'.join(parts) if parts else '未发现明显风险点'

    def build_markdown(self, result):
        quality = dict(result.get('extraction_quality', {}))
        if not isinstance(quality.get('confidence'), (int, float)):
            quality['confidence'] = _UnknownConfidence()
        return super().build_markdown({**result, 'extraction_quality': quality})
