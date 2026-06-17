# iFly PDF & Image OCR

通用 OCR 技能，包含两个独立脚本：

- `scripts/image_ocr.py`：图片 OCR
- `scripts/pdf_ocr.py`：PDF OCR

这两个脚本都依赖 `requests`。

## 前置条件

```bash
pip install requests
```

环境变量按能力区分：

```bash
# 图片 OCR
export IFLY_APP_ID="your_app_id"
export IFLY_API_KEY="your_api_key"
export IFLY_API_SECRET="your_api_secret"

# PDF OCR
export IFLY_APP_ID="your_app_id"
export IFLY_API_SECRET="your_api_secret"
```

## 图片 OCR

适合对截图、扫描图、海报、表格图片做文字提取和版面保留。

```bash
# 默认同时返回 json 和 markdown 结果
python3 scripts/image_ocr.py ./image.jpg

# 只输出 markdown
python3 scripts/image_ocr.py ./image.jpg --format markdown

# 保存到文件
python3 scripts/image_ocr.py ./image.jpg -o output.txt
```

### 图片 OCR 参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `image_path` | 图片路径 | - |
| `--format` | `json`、`markdown`、`json,markdown` | `json,markdown` |
| `--output`, `-o` | 保存结果到文件 | 不保存 |

## PDF OCR

适合对 PDF 文档进行结构化识别，输出 Word、Markdown 或 JSON，并返回下载地址与分页状态。

```bash
# 默认导出 Word
python3 scripts/pdf_ocr.py ./document.pdf

# 导出 Markdown
python3 scripts/pdf_ocr.py ./document.pdf --format markdown

# 只提交任务，不轮询
python3 scripts/pdf_ocr.py ./document.pdf --no-poll

# 调整轮询时间
python3 scripts/pdf_ocr.py ./document.pdf --poll-interval 10 --max-wait 600
```

### PDF OCR 参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `pdf_path` | 本地 PDF 路径 | - |
| `--pdf-url` | 公网 PDF URL；当前 CLI 仍要求传入本地 `pdf_path` | 不传 |
| `--format` | `word`、`markdown`、`json` | `word` |
| `--no-poll` | 只返回任务号，不等待结果 | 关闭 |
| `--poll-interval` | 轮询间隔，最小 5 秒 | `5` |
| `--max-wait` | 最大等待时间（秒） | `300` |

## 限制说明

- PDF OCR 最大支持 `100` 页。
- 加密 PDF 不支持。
- `pdf_ocr.py` 当前实现里，`--pdf-url` 不是独立的 URL-only 模式，命令行仍会校验本地 `pdf_path` 是否存在。
- 图片 OCR 使用 `HMAC-SHA256` 鉴权；PDF OCR 使用 `MD5 + HMAC-SHA1` 鉴权。
- 完整文档与错误码说明见 [`SKILL.md`](./SKILL.md)。

## 参考链接

- 官方文档：https://www.xfyun.cn/doc/words/image_word_recognition/API.html
- 服务购买：https://console.xfyun.cn/services/se75ocrbm
