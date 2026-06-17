# Contract Intelligence Review Skill

场景化合同智能审核 Workflow Skill

## 概述

本 Skill 是一个**场景编排层**，负责协调合同审核全流程，而非单一原子 API 调用。它整合了文档识别、文本提取、条款分析、风险检测、合规校对、翻译等能力，输出结构化审核报告。

## 适用场景

| 场景 | 说明 |
|------|------|
| 合同扫描件审核 | PDF 扫描件需要 OCR 识别后审核 |
| 图片合同审核 | 合同照片、截图等图片格式 |
| 文本合同审核 | Word、Markdown、TXT 等可编辑文本 |
| 双语合同审核 | 中英双语合同一致性检查 |
| 重点条款审核 | 付款、违约、续约、知识产权等专项审核 |
| 快速风险扫描 | 仅输出关键风险点 |
| 深度审核 | 完整条款分析+规范性校对+翻译摘要 |

## 目录结构

```
contract-intelligence-review/
├── SKILL.md                    # Skill 定义入口
├── README.md                   # 本文件
├── _meta.json                  # 扩展元数据（可选）
├── templates/
│   ├── review_report.md       # Markdown 报告模板
│   └── review_output.json     # JSON 输出模板
├── examples/
│   ├── sample_contract_excerpt.md   # 示例合同片段
│   └── sample_review_report.md     # 示例审核报告
├── scripts/
│   ├── main.py                # 主入口，argparse CLI
│   ├── config.py              # 配置管理
│   ├── errors.py              # 自定义异常
│   ├── clients/               # 抽象客户端层
│   │   ├── __init__.py
│   │   ├── ocr_client.py      # OCR 客户端抽象
│   │   ├── image_client.py    # 图像理解客户端抽象
│   │   ├── translate_client.py # 翻译客户端抽象
│   │   └── llm_review_client.py # LLM 审核客户端抽象
│   ├── processors/            # 业务处理器
│   │   ├── __init__.py
│   │   ├── ingest.py          # 输入预处理
│   │   ├── text_cleaner.py    # 文本清洗
│   │   ├── clause_splitter.py # 条款分段
│   │   ├── risk_detector.py   # 风险检测
│   │   ├── compliance_checker.py # 合规检查
│   │   ├── bilingual_checker.py  # 双语一致性检查
│   │   └── report_builder.py # 报告生成
│   └── utils/
│       ├── __init__.py
│       ├── file_utils.py      # 文件工具
│       ├── logger.py          # 日志工具
│       └── validation.py      # 输入验证
```

## 依赖能力说明

本 Skill 为编排层，底层能力通过抽象客户端接入：

| 能力 | 抽象接口 | 说明 |
|------|----------|------|
| OCR 识别 | `OCRClient` | 支持 PDF/图片文字提取 |
| 图像理解 | `ImageClient` | 图片内容理解（Claude Vision 等） |
| 文本翻译 | `TranslateClient` | 多语言翻译 |
| 合同审核 | `LLMReviewClient` | LLM 条款理解与风险判断 |

> **注意**：具体实现需根据实际可用的 SDK/API 注入。当前为抽象接口，保留接入任意实现的空间。

## 环境变量

| 变量名 | 必填 | 说明 |
|--------|------|------|
| `OCR_API_ENDPOINT` | 否 | OCR 服务地址 |
| `OCR_API_KEY` | 否 | OCR 服务密钥 |
| `TRANSLATE_API_ENDPOINT` | 否 | 翻译服务地址 |
| `TRANSLATE_API_KEY` | 否 | 翻译服务密钥 |
| `LLM_API_ENDPOINT` | 否 | LLM 服务地址 |
| `LLM_API_KEY` | 否 | LLM 服务密钥 |
| `LOG_LEVEL` | 否 | 日志级别，默认 INFO |

## 本地运行方式

### 安装依赖

```bash
# 创建虚拟环境（推荐）
python -m venv venv
source venv/bin/activate  # Linux/macOS
# 或 venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt
```

### 运行示例

```bash
# 基础运行
python scripts/main.py --input ./contract.pdf

# 指定审核模式
python scripts/main.py --input ./contract.pdf --review-mode deep

# 重点审查付款条款
python scripts/main.py --input ./contract.pdf --focus payment --focus liability

# 需要翻译摘要
python scripts/main.py --input ./contract.pdf --need-translation --lang en

# 输出 JSON 格式
python scripts/main.py --input ./contract.pdf --output-format json

# 保存中间结果
python scripts/main.py --input ./contract.pdf --save-intermediate --output-dir ./output
```

## 参数说明

| 参数 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `--input` | 是 | - | 输入文件路径 |
| `--input-type` | 否 | `auto` | 文件类型：`auto`, `pdf`, `image`, `text` |
| `--lang` | 否 | `zh` | 合同语言：`zh`, `en`, `bilingual` |
| `--review-mode` | 否 | `standard` | 审核模式：`quick`, `standard`, `deep` |
| `--focus` | 否 | 全部 | 重点审查项，可多次指定：`payment`, `liability`, `renewal`, `ip`, `confidentiality`, `dispute` |
| `--need-translation` | 否 | `False` | 是否需要翻译摘要 |
| `--output-format` | 否 | `markdown` | 输出格式：`markdown`, `json`, `both` |
| `--output-dir` | 否 | `./output` | 输出目录 |
| `--save-intermediate` | 否 | `False` | 是否保存中间处理结果 |

## 输出说明

### Markdown 报告结构

```markdown
# 合同智能审核报告

## 文档基本信息
- 文件名：xxx
- 页数：xx
- 语言：xx

## 输入质量评估
- OCR 识别率：xx%
- 识别不确定区域：xx 处

## 审核模式
- 审核深度：standard
- 重点关注：付款条款、违约责任

## 风险清单
### 高风险
- [风险项] [推断] 原文片段...

### 中风险
- [风险项] [建议] ...

## 规范性校对问题
- ...

## 人工复核建议
- ...
```

### JSON 输出结构

```json
{
  "document_meta": {
    "filename": "xxx",
    "page_count": xx,
    "language": "zh",
    "input_type": "pdf_scan"
  },
  "extraction_quality": {
    "ocr_confidence": 0.95,
    "uncertain_regions": [],
    "extracted_text": "..."
  },
  "clauses": [...],
  "risks": [
    {
      "category": "payment",
      "level": "high",
      "description": "...",
      "source": "推断",
      "evidence": "原文片段"
    }
  ],
  "compliance_issues": [...],
  "translation_summary": "...",
  "uncertain_items": [...],
  "human_review_required": ["..."],
  "final_summary": "..."
}
```

## 常见错误

| 错误 | 原因 | 处理方式 |
|------|------|----------|
| 文件不存在 | 输入路径错误 | 检查路径 |
| 文件格式不支持 | 格式不在支持列表 | 转换为支持格式 |
| OCR 识别失败 | 图片质量过低 | 提示人工处理 |
| 条款分段失败 | 文本结构异常 | 返回原文+风险扫描 |
| 翻译失败 | 网络或 API 问题 | 返回原文+待翻译片段 |

## 风险规则扩展

风险检测规则定义在 `scripts/processors/risk_detector.py` 中，每个风险类别包含：

- `category`: 风险类别标识
- `keywords`: 触发关键词
- `patterns`: 正则匹配模式
- `level`: 默认风险等级
- `description`: 风险描述模板
- `suggestion`: 审核建议模板

新增风险规则时，参考现有规则格式添加至对应类别。

## 条款规则扩展

条款识别规则定义在 `scripts/processors/clause_splitter.py` 中，可扩展：

- 条款标题模式
- 条款边界识别规则
- 条款主题分类器

## 模板扩展

报告模板位于 `templates/` 目录：

- `review_report.md`: Markdown 报告模板
- `review_output.json`: JSON 输出模板

修改模板后需保持变量占位符一致。

## 设计原则

1. **场景编排而非原子封装**：本 Skill 整合多个底层能力，输出完整审核结果
2. **抽象客户端**：底层能力通过接口抽象，便于替换实现
3. **不确定性显式标记**：识别质量、风险判断的不确定因素必须明确标出
4. **部分结果返回**：任一步骤失败时尽量返回可用的部分结果
5. **分级审核**：支持 quick/standard/deep 三种审核深度
6. **输入类型自适应**：自动识别文件类型并选择处理链路
