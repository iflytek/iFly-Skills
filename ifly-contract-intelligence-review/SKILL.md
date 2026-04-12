---
name: contract-intelligence-review
description: >
  合同智能审核 - 对合同扫描件、图片合同、双语合同进行完整审核。
  覆盖 OCR 识别、条款分析、风险检测、合规校对、翻译摘要全流程。
  适用于法务审核、采购合同审查、供应链合规检查等场景。
  关键词：合同审核、风险检测、条款分析、合规校对、contract review、risk detection。
metadata: {
  "openclaw": {
    "emoji": "📋",
    "dimensions": ["合同智能审核", "风险检测与合规校对"],
    "user_instructions": [
      "帮我审核合同", "检查合同风险", "合同合规性检查",
      "审核付款条款", "审查违约责任", "双语合同核对"
    ],
    "requires": {
      "bins": ["python3"],
      "env": ["OCR_API_ENDPOINT", "LLM_API_ENDPOINT"]
    },
    "primaryEnv": "OCR_API_ENDPOINT"
  }
}
---

# contract-intelligence-review (合同智能审核)

场景化合同智能审核 Workflow Skill。覆盖从文档识别到风险报告的完整审核流程。

## When to Use

- 用户提交合同扫描件（PDF）需要审核
- 用户提交合同照片或页面截图
- 用户提交 Word/Markdown/TXT 格式合同正文
- 用户需要审核中英双语合同的一致性
- 用户需要重点审查特定条款（付款、违约、续约、知识产权）
- 法务人员需要批量审核合同风险

## When NOT to Use

- 仅需要单个字词翻译（请使用翻译 skill）
- 仅需要语法检查（请使用校对 skill）
- 仅需要简单文本提取（请使用 OCR skill）
- 需要具有法律效力的正式法律意见书（本 skill 输出为审核参考，非法律意见）

## Prerequisites

- **Python 3.9+**
- **环境变量**（需要注入实际 OCR/LLM 实现）：
  - `OCR_API_ENDPOINT` — OCR 服务地址
  - `OCR_API_KEY` — OCR 服务密钥
  - `LLM_API_ENDPOINT` — LLM 服务地址
  - `LLM_API_KEY` — LLM 服务密钥

## Supported Inputs

- PDF 文件（扫描件或文字版）
- 图片文件（JPG/PNG/BMP/HEIC）
- Word 文档（.docx）
- Markdown 文件（.md）
- 纯文本文件（.txt）

## Usage

脚本位置：`scripts/main.py`

```bash
# 基础审核
python3 scripts/main.py --input contract.pdf

# 深度审核 + 重点条款
python3 scripts/main.py --input contract.pdf --review-mode deep --focus payment --focus liability

# 输出 JSON 格式
python3 scripts/main.py --input contract.pdf --output-format json

# 需要翻译摘要
python3 scripts/main.py --input contract.pdf --need-translation

# 保存中间结果
python3 scripts/main.py --input contract.pdf --save-intermediate --output-dir ./output
```

## Options

| Flag | Description |
|------|-------------|
| `--input` | 输入文件路径（必填） |
| `--input-type` | 文件类型：auto/pdf/image/text |
| `--lang` | 合同语言：zh/en/bilingual |
| `--review-mode` | 审核模式：quick/standard/deep |
| `--focus` | 重点审查项（可多次指定）|
| `--need-translation` | 是否需要翻译摘要 |
| `--output-format` | 输出格式：markdown/json/both |
| `--output-dir` | 输出目录 |
| `--save-intermediate` | 保存中间处理结果 |

## Workflow

1. **输入识别** — 文件类型自动检测、可读性评估
2. **内容提取** — OCR 识别 / 文本提取
3. **文本清洗** — 乱码过滤、段落重组
4. **条款分段** — 条款编号识别、标题提取
5. **风险检测** — 付款/违约/续约/知识产权/保密/争议解决
6. **合规校对** — 术语一致性、格式规范性
7. **双语检查** — 中英一致性核验
8. **报告生成** — Markdown / JSON 输出

## Risk Categories

| 类别 | 说明 |
|------|------|
| payment | 付款与结算风险 |
| liability | 违约责任风险 |
| renewal | 期限与续约风险 |
| ip | 知识产权归属风险 |
| confidentiality | 保密与数据合规风险 |
| dispute | 争议解决风险 |

## Output Format

### Markdown Report

```
# 合同智能审核报告

## 文档基本信息
- 文件名: xxx
- 审核模式: standard

## 风险清单
### 高风险
- [风险项] [推断] 原文片段...

## 人工复核建议
- ...
```

### JSON Output

```json
{
  "document_meta": {...},
  "extraction_quality": {...},
  "clauses": [...],
  "risks": [...],
  "compliance_issues": [...],
  "human_review_required": [...],
  "final_summary": "..."
}
```

## Notes

- 本 skill 为场景编排层，底层 OCR/翻译能力需通过环境变量注入
- 所有风险判断标注来源：[原文事实]/[推断]/[建议]
- 识别质量低时标记「待确认」，不虚构内容
- 本输出为通用审查建议，不构成特定法域法律意见
