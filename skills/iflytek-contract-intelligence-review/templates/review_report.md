# 合同智能审核报告

**生成时间**: {{generated_time}}

---

## 文档基本信息

- **文件名**: {{filename}}
- **文件类型**: {{input_type}}
- **提取方法**: {{extraction_method}}
- **语言**: {{language}}
- **审核模式**: {{review_mode}}
{{#if focus}}
- **重点关注**: {{focus}}{{/if}}

---

## 输入质量评估

- **文本长度**: {{text_length}} 字符
- **识别置信度**: {{confidence}}
{{#if uncertain_regions}}
- **识别不确定区域**: {{uncertain_regions}} 处{{/if}}

---

{{#if uncertain_items}}
### 不确定项

{{#each uncertain_items}}
- [待确认] {{this}}
{{/each}}

---{{/if}}

## 合同结构概览

- **条款数量**: {{clause_count}}

{{#if categories}}
- **条款分类**:
{{#each categories}}
  - {{@key}}: {{this}}
{{/each}}{{/if}}

---

## 风险清单

{{#if risks}}
### 高风险

{{#each high_risks}}
- **{{title}}**
  - 类别: {{category}}
  - 来源: [{{source}}]
  - 原文: 「{{evidence}}」
  - 建议: {{suggestion}}

{{/each}}

### 中风险

{{#each medium_risks}}
- **{{title}}**
  - 类别: {{category}}
  - 来源: [{{source}}]
  - 建议: {{suggestion}}

{{/each}}

### 低风险

{{#each low_risks}}
- {{title}}

{{/each}}
{{else}}
未发现明显风险点
{{/if}}

---

## 规范性校对问题

{{#if compliance_issues}}
{{#each compliance_issues}}
{{#ifEqual severity "warning"}}⚠️{{else}}💡{{/ifEqual}} **{{title}}**
  - 类型: {{type}}
  - 描述: {{description}}
  - 建议: {{suggestion}}

{{/each}}
{{else}}
未发现规范性校对问题
{{/if}}

---

{{#if bilingual_issues}}
## 双语一致性检查

{{#each bilingual_issues}}
- **{{title}}**
  - 类型: {{issue_type}}
  - 问题: {{description}}

{{/each}}

---{{/if}}

{{#if translation_summary}}
## 翻译摘要

{{translation_summary}}

---{{/if}}

{{#if human_review_required}}
## 人工复核建议

{{#each human_review_required}}
- ⚠️ {{this}}
{{/each}}

---{{/if}}

## 附录：原文条款结构

{{#each clauses}}
### {{clause_id}} {{title}}

_{{content}}_


{{/each}}

---

*本报告由合同智能审核 Skill 自动生成，仅供参考*
*以下为通用合同风险审查建议，不构成特定法域法律意见*
