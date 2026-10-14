# iFly-Skills Coze 服务

本目录提供一个面向 Coze 国内站和国际站的共享 HTTPS 服务，用于承载 iFly-Skills 能力。服务按站点分别配置工作空间和访问密钥；同一个后端实例可以同时服务两个站点。

服务提供 11 个 Skill、24 个工具，地址为 `/v1/skills/<skill-id>/<action>`。使用前需配置相应业务凭证及运行环境；缺少依赖的工具返回 `DEPENDENCY_UNAVAILABLE`。OpenAPI 3.0.3 文件导出与插件创建／发布工具尚未提供。

## 使用条件

- Python 3.13 或 3.14
- [uv](https://docs.astral.sh/uv/)
- 可从 Coze 访问的 HTTPS 域名（本地调试可先使用 HTTP）
- 启用能力所需的讯飞服务凭证

## 配置

复制 [.env.example](./.env.example) 为同目录的 `.env`，再填写实际值。`.env` 只保存在部署环境，不要提交到代码仓库。

| 配置项 | 说明 |
| --- | --- |
| `COZE_ENABLED_SITES` | 填写 `cn`、`global` 或 `cn,global`，明确启用的站点 |
| `COZE_<SITE>_WORKSPACE_ID` | 对应站点的工作空间 ID |
| `COZE_<SITE>_BACKEND_API_KEY` | 插件访问本服务的独立密钥，长度 32～256 个无空格 ASCII 可打印字符 |
| `COZE_<SITE>_ALLOWED_SKILLS` | 允许该站点调用的 Skill ID，使用逗号分隔 |
| `COZE_<SITE>_API_BASE_URL` | 国内使用 `https://api.coze.cn`，国际使用 `https://api.coze.com` |
| `COZE_<SITE>_API_TOKEN` | 对应站点的平台令牌，仅用于工作空间或平台管理检查 |
| `COZE_<SITE>_BACKEND_BASE_URL` | 部署后供插件访问的 HTTPS 服务地址；本地运行时可留空 |
| `IFLY_APP_ID`／`IFLY_API_KEY`／`IFLY_API_SECRET` | 原子 Skill 的讯飞业务凭证，须分别开通所需服务 |
| `IFLY_CONTRACT_APP_ID`／`IFLY_CONTRACT_API_KEY`／`IFLY_CONTRACT_API_SECRET` | 合同流程独立配置的业务凭证；用于图片 OCR、图片理解、翻译和 Spark v3.5（`generalv3.5`）审核 |
| `COZE_DATA_DIR` | 私有持久化目录；留空时使用本目录下的 `output/runtime` |
| `COZE_ARTIFACT_BASE_URL` | 可访问产物的 HTTPS 服务地址，可含反向代理路径前缀；与实际 `/v1/artifacts/...` 路由对应 |
| `COZE_RENDER_IMAGE` | 完成隔离验收后的本地渲染镜像 ID（`sha256:...`）；留空关闭 GIF 渲染 |

其中 `<SITE>` 为 `CN` 或 `GLOBAL`。两个站点的账号、工作空间、平台令牌和服务密钥分别配置，服务密钥不能复用平台令牌。后端域名可以共用，但必须能够从相应 Coze 站点访问。讯飞服务凭证只保存在服务端，不作为插件请求参数。

服务通过 `COZE_ENV_FILE` 指定配置文件，或完全使用进程环境变量；进程环境变量优先，配置变更后需要重启服务。

## 安装与启动

在仓库根目录执行：

```powershell
uv sync --locked --project integrations/coze --python 3.13
$env:COZE_ENV_FILE = (Resolve-Path integrations/coze/.env).Path
uv run --locked --project integrations/coze --python 3.13 uvicorn app.main:create_app --factory --app-dir integrations/coze --host 127.0.0.1 --port 8000 --no-access-log
```

Linux 或 macOS：

```sh
uv sync --locked --project integrations/coze --python 3.13
COZE_ENV_FILE=integrations/coze/.env uv run --locked --project integrations/coze --python 3.13 uvicorn app.main:create_app --factory --app-dir integrations/coze --host 127.0.0.1 --port 8000 --no-access-log
```

生产环境应在反向代理或托管网关后提供 HTTPS，并设置请求超时、文件大小和日志保留策略。不要把本地 HTTP 地址填入 Coze 插件配置。请保留仓库中的 `skills/` 目录，适配器从固定位置加载原始脚本及资源。

当前使用 SQLite 和本地产物存储，**每个数据目录只运行一个服务进程**，不要设置多个 Uvicorn worker。服务默认每个工作空间每分钟 60 次请求、最多 2 个同时执行的调用，实例最多 4 个；本地后台任务逐个处理，队列最多容纳 32 项。同步操作预算 60 秒，本地后台操作预算 600 秒（含排队总计最多 900 秒），部署网关与 Coze 节点的超时应与实际调用耗时匹配。

## 健康检查

访问：

```text
GET /healthz
```

正常响应为：

```json
{"status":"ok"}
```

健康检查不需要服务密钥。业务工具请求使用 `X-API-Key` 请求头：

```http
X-API-Key: <对应站点的 COZE_<SITE>_BACKEND_API_KEY>
```

服务端根据密钥绑定的站点、工作空间和允许能力进行授权，请求参数不能切换站点或工作空间。错误响应统一包含 `error.code`、`error.message`、`error.retryable` 和 `trace_id`；响应头同时返回 `X-Trace-Id`，可用于排查问题。

## Coze 接入

1. 为目标站点准备可访问的 HTTPS 服务地址，并在配置中填写对应的 `BACKEND_BASE_URL`。
2. 在对应版本提供 OpenAPI 文件后，在 Coze 中创建基于已有服务的 API 插件并导入文档。
3. 为插件工具配置 `X-API-Key` 请求头，使用目标站点的服务密钥。
4. 逐项调试工具，确认请求参数、响应字段和文件地址符合文档后再发布插件。

国内站和国际站分别使用各自的工作空间、插件记录和服务密钥。一个站点的令牌、插件 ID 或权限不能替代另一个站点的配置。

## 工具与调用

下表中的查询操作及 `list_voices` 使用 GET，其余操作使用 POST JSON。GET 的 `job_id`／`text_id` 放在查询参数中。

| Skill | 工具 | 主要输入与结果 |
| --- | --- | --- |
| `iflytek-translate` | `translate` | `text`、`from_lang`、`to_lang` → 原文、译文及语言；文本最多 4096 UTF-8 字节 |
| `iflytek-text-proofread` | `check` | `text` → `checklist`；最多 220000 字符，不自动截断 |
| `iflytek-ocr-invoice` | `recognize` | `image_url` → 结构化票据字段 |
| `iflytek-hyper-tts` | `synthesize`、`list_voices` | 文本、发音人及韵律参数 → MP3；发音人列表无需业务凭证 |
| `iflytek-pdf-image-ocr` | `recognize_image`、`create_pdf_task`、`get_pdf_task` | 图片或 PDF URL → 识别内容／任务及产物；PDF 最多 100 页 |
| `iflytek-speed-transcription` | `create_task`、`get_task` | `audio_url`（MP3）→ 文本及分段；保留上游时间值，不转换单位 |
| `iflytek-image-understanding` | `analyze` | `image_url`、`question` → 完整回答及用量 |
| `iflytek-video-translate` | `create_task`、`get_task`、`confirm_transcript` | MP4 URL、源／目标语言 → 视频任务；仅待确认阶段允许确认字幕 |
| `iflytek-voiceclone-tts` | `get_training_text`、`create_training`、`upload_sample`、`submit_training`、`get_training`、`synthesize` | 获取训练文本，创建、上传、提交、查询，成功后用本工作空间的 `res_id` 合成 MP3 |
| `iflytek-contract-intelligence-review` | `review`、`get_review` | 合同 URL → 规则和模型审核结果、Markdown／JSON 报告 |
| `animated-sketch-diagram` | `render_html_to_gif`、`get_render` | 受限 `html`、尺寸、帧率和时长 → GIF |

例如，发送翻译请求：

```http
POST /v1/skills/iflytek-translate/translate
X-API-Key: <service-key>
Content-Type: application/json

{"text":"Hello world","from_lang":"en","to_lang":"cn"}
```

创建任务和训练／字幕的阶段操作必须提供 `request_id`。同一操作重试时复用原标识与原参数；相同标识配不同参数返回 `CONFLICT`。任务受理返回 HTTP 200 和 `job_id`、`status`，不代表业务完成。保存 `job_id`，至少间隔 5 秒查询，并在工作流中设置总时限与失败分支。

任务状态包括 `queued`、`running`、`waiting_input`、`succeeded`、`partially_succeeded`、`failed`、`submission_unknown`。`ANY_FAILED` 的 PDF 保留部分失败状态。提交超时或进程中断时不会自动重新提交；`submission_unknown` 需核实上游受理情况，有上游映射的任务可以继续查询。重启后保留未开始的本地队列与已受理的上游任务，中断的调用不会自动重跑。

声音训练依次使用“创建 → 上传样本 → 提交训练 → 查询”；上传操作仅登记样本，不隐式提交训练。录音应由获授权的说话人按 `get_training_text` 返回的文本录制，上传时使用对应的 `text_id` 和 `seg_id`。当前工具不接收自定义训练文本，提供已有录音的转写不能替代所选服务端文本。合成只接受当前工作空间已成功训练的 `res_id`。

训练返回 `failure_reason=audio_text_mismatch` 时，需要按所选文本重新准备录音；格式合格或上传成功不代表训练成功。权限、额度不足等明确拒绝记录为失败；修复条件后重新发起请求时使用新的 `request_id`。

## 文件与能力限制

输入文件使用可下载的公开 HTTPS URL，不支持本地路径或直接传入 Coze `file_id`。下载校验 DNS、实际连接地址和每次重定向，阻断内网地址及环境代理；文件还须通过实际编码检查，不能只修改扩展名。图片只接收 PNG／JPEG，最多 4 MiB；PDF 最多 32 MiB；转写 MP3 和视频 MP4 最多 128 MiB。训练样本只接收单声道 WAV（16 bit）或 MP3，采样率至少 24 kHz、时长不超过 40 秒、最多 3 MiB，并须与所选训练文本一致。这些是后端接入上限，服务商限制仍需满足。

极速转写使用固定的 `language=zh_cn`、`accent=mandarin`、`domain=pro_ost_ed` 参数组合，服务自动识别中英文；英文录音也使用该组合。图片 OCR 的 `format` 可选 `json`、`markdown`、`json,markdown`，分别返回结构化 `json`、`markdown` 或两者。PDF 的已知服务商 HTTP 产物地址仅通过经验证的 HTTPS 对应地址下载，不回退到 HTTP。

音频、视频、GIF 和报告使用随机、限时 HTTPS URL，响应包含 `mime_type`、`size_bytes`、`expires_at`。**持有 URL 即可下载有效期内的产物**；应将地址作为私有数据保管。下载路由 `/v1/artifacts/...` 使用含 192 位随机熵的地址，不要求 `X-API-Key`，也不受工具调用的工作空间限流保护，便于 Coze 和上游服务拉取文件。服务记录请求追踪 ID、状态和耗时，不记录完整下载地址；没有按下载者身份审计或下载专用限流。需要限制下载流量时，可在反向代理设置连接数或速率限制，并确认不影响 Coze 和上游拉取。

输出默认保留 1 小时，供上游拉取的视频／训练样本保留 24 小时。保留期限独立于任务状态：即使任务提前失败，已转存的输入仍可通过原 URL 下载，直至过期；到期立即拒绝新下载请求，文件随后由后台自动清理。产物总容量上限 2 GiB、单文件上限 128 MiB。任务和报告记录包含业务内容，数据目录需限制访问、持久保存；任务标识的去重记录不自动删除。

合同支持 UTF-8 TXT／Markdown、DOCX（包含表格）、PDF、PNG／JPEG，不支持旧 `.doc`；最多 20 MiB、8 页 PDF，提取后最多 4000 字符，超限需先拆分。`quick`／`standard`／`deep` 沿用原 Skill 的规则范围并进行模型审核；`deep`、英文合同或 `need_translation=true` 会生成英文译文摘要，必要阶段失败即任务失败。结果区分规则检查和模型推断，模型风险必须引用原文；未测量的置信度为空，保留人工复核提示。`output_format` 可选 `markdown`、`json`、`both`。

训练适配器使用验证证书的 HTTPS，拒绝重定向；克隆合成使用验证证书的 WSS。部署前需按[声音复刻文档](https://www.xfyun.cn/doc/spark/voiceclone.html)准备录音，并核对实际账号的训练和合成权限。启用各插件前，需用部署账号确认对应服务的业务权限和调用结果。

## GIF 隔离运行环境

GIF 只支持 HTML／SVG／CSS 绘图和 CSS 动画，不接收脚本、事件处理器、外部资源或本地文件引用。上限为 256 KiB HTML、2000 个元素、1600×1200、25 fps、5 秒、2 倍缩放，并受 1.2 亿像素帧预算约束。

需要 Linux Docker 容器运行环境及支持 Dockerfile 专用忽略文件的 BuildKit 构建器。构建上下文只包含渲染代码、字体和许可证，排除凭证及本地数据。在仓库根目录构建：

```sh
docker buildx build --load -f integrations/coze/deploy/render/Dockerfile -t ifly-coze-render .
docker image inspect --format '{{.Id}}' ifly-coze-render
```

完成实际 GIF 生成、网络／文件隔离、超时回收验收后，将输出的镜像 ID 填入 `COZE_RENDER_IMAGE`。调用时固定禁用网络、只读根文件系统、非 root 用户、无宿主目录挂载，并限制 CPU、内存、进程及临时磁盘；不向容器传递业务凭证。浏览器禁用页面脚本和外部请求，操作系统隔离由容器提供。未配置时不会退回宿主机直接渲染。

## 工作空间检查

需要确认平台令牌和工作空间范围时，可运行：

```sh
uv run --locked --project integrations/coze --python 3.13 python -B integrations/coze/scripts/check_config.py --site cn --online
uv run --locked --project integrations/coze --python 3.13 python -B integrations/coze/scripts/check_config.py --site global --online
```

检查只读查询对应站点的工作空间，不创建或发布资源；令牌需要具备 `listWorkspace` 权限。检查结果不会输出令牌、完整工作空间 ID 或工作空间名称。

## 当前服务边界

平台令牌只用于平台管理检查，普通插件调用不需要将平台令牌传给本服务。接口模型已提供业务工具契约；OpenAPI 3.0.3 导出、部署后的 Coze 导入验证与插件管理操作应以对应版本实际提供的功能为准。
