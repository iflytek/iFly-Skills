# n8n-nodes-iflytek

`n8n-nodes-iflytek` 为自托管 n8n 提供 iFLYTEK Skills 节点，支持语音转写与合成、声音克隆、票据和 PDF/图片 OCR、文本和视频翻译、中文校对、图片理解、合同审核及 HTML 手绘图渲染。

远端服务使用共享的 **iFlytek API** 凭证。本地手绘图渲染和静态音色列表不需要 API 凭证；实际语音合成仍需要服务授权。

## 快速开始

1. 准备允许运行 Python 子进程的自托管 n8n、Node.js 24 和 Python 3.10 或更高版本。已验证的版本与平台见 [兼容范围](docs/compatibility.md)。
2. 按 [安装与配置](docs/installation.md) 安装本包及 Python 依赖，设置解释器路径，运行预检并重启 n8n。
3. 在 n8n 中创建 **iFlytek API** 凭证，填写同一讯飞应用的 **App ID**、**API Key** 和 **API Secret**。应用需开通所选服务，并有可用额度。
4. 在节点选择器中搜索 `iFlytek`，选择能力和操作，将其连接到工作流。

第一个工作流可使用 **Manual Trigger → iFlytek Translate**：选择凭证，在 **Text** 填入“欢迎使用 iFLYTEK Skills”，将 **Source Language** 设置为 `cn`、**Target Language** 设置为 `en`，执行后从 `data.translatedText` 读取译文。下游节点可使用表达式 `{{ $json.data.translatedText }}`。这个示例会调用翻译服务，按应用的服务套餐计费。

## 节点与操作

| 节点 | 操作 | 输入 | 结果 |
| --- | --- | --- | --- |
| `iFlytek Translate` | `translate` | 文本或 UTF-8 binary、源语言、目标语言 | `data.sourceText`、`data.translatedText`、语言字段 |
| `iFlytek Text Proofread` | `check` | 文本或 UTF-8 binary | `data.result` 中的校对服务结果 |
| `iFlytek Invoice OCR` | `recognize` | 发票、收据等图片或 PDF binary | `data.result` 中的结构化识别结果 |
| `iFlytek Hyper TTS` | `synthesize` | 文本或 UTF-8 binary、音色和声音参数 | `data` 中的合成信息及 `binary.audio` MP3 |
| `iFlytek Hyper TTS` | `listVoices` | 无业务输入 | 随包静态音色常量；不访问服务端 |
| `iFlytek PDF and Image OCR` | `recognizeImage` | 图片 binary、结果格式 | `data.result` 中的通用图片 OCR 结果 |
| `iFlytek PDF and Image OCR` | `createPdfTask` | PDF binary 或公开 HTTP(S) URL、导出格式 | `data.taskNo`、任务状态及原始响应 |
| `iFlytek PDF and Image OCR` | `getPdfTask` | PDF OCR `taskNo` | 当前状态及原始响应 |
| `iFlytek PDF and Image OCR` | `getResult` | PDF OCR `taskNo` | 状态、完成标记和原始响应 |
| `iFlytek Speed Transcription` | `createTask` | MP3 binary、语言、口音和领域 | `data.taskId`、上传地址 |
| `iFlytek Speed Transcription` | `getTask` | 转写 `taskId` | 当前状态及原始响应 |
| `iFlytek Speed Transcription` | `getResult` | 转写 `taskId` | `data.text`、分段、状态和原始响应 |
| `iFlytek Image Understanding` | `analyze` | 图片 binary、问题和模型参数 | `data.text` |
| `iFlytek Video Translate` | `createTask` | 公开视频 HTTP(S) URL、源语言、目标语言 | `data.result` 中的任务信息 |
| `iFlytek Video Translate` | `listTasks` | 无业务输入 | `data.result` 中的任务列表 |
| `iFlytek Video Translate` | `getTask` | 视频翻译 `taskId` | `data.taskId` 及任务详情 |
| `iFlytek Video Translate` | `confirmTranscript` | 视频翻译 `taskId`、是否强制重跑 | `data.result` 中的确认结果 |
| `iFlytek Voice Clone TTS` | `getTrainingText` | 训练文本集 ID | `data.result` 中的文本片段 |
| `iFlytek Voice Clone TTS` | `createTraining` | 任务名称、性别、引擎和语言 | `data.result` 中的训练任务 |
| `iFlytek Voice Clone TTS` | `uploadSample` | 训练任务 ID、音频 binary 或 URL、文本片段 | `data.result`、`data.trainingSubmitted`；binary 同时提交训练 |
| `iFlytek Voice Clone TTS` | `submitTraining` | 训练任务 ID | `data.result` 中的提交结果 |
| `iFlytek Voice Clone TTS` | `getTraining` | 训练任务 ID | 状态、资源 ID 和原始响应 |
| `iFlytek Voice Clone TTS` | `synthesize` | 文本、克隆资源 ID 和声音参数 | `binary.audio` 及合成信息 |
| `iFlytek Contract Review` | `review` | 合同文本或文档 binary、语言、审核模式与重点 | 结构化审核结果、`binary.report` Markdown 和 `binary.report2` JSON |
| `iFlytek Animated Sketch` | `renderHtmlToGif` | 受限 HTML/SVG/CSS 文本或 UTF-8 binary、尺寸与动画参数 | `binary.image` GIF、尺寸和帧数 |

当前共 11 个节点、25 个操作。合同审核会编排多个客户端；手绘图节点只渲染现成 HTML，不包含自然语言生成图表操作。票据 OCR 与通用 PDF/图片 OCR 是两个独立节点，不能互相替代。

## 输入、结果与错误处理

文件通过 n8n 的 binary 字段传入。例如上游文件位于 `binary.data` 时，在 **Input Binary Field** 填写 `data`，无需填写本地文件路径。支持文本输入的节点优先使用 **Text**；只有 Text 为空时才读取指定的 UTF-8 binary 字段。

每个输入 item 对应一个输出 item，并保留 n8n 的 item 关联。业务结果位于 `json.data`；音频、图像和报告位于上表所列的 binary 字段，可继续交给上传、保存或发送文件的节点。文件完成 n8n 持久化后，本包会清理调用临时目录，工作流应使用 binary 字段传递文件。

JSON 输出同时包含 `ok`、`status`、`requestId` 和 `meta.durationMs`。外层 `ok: true`、`status: succeeded` 表示本次节点调用成功；创建远端任务后的完成状态仍需根据 `data` 中的服务结果判断。保存创建操作返回的 task ID，再通过 Wait 和查询节点等待任务完成，详见 [长任务与恢复](docs/operations.md#长任务重复费用与-worker-恢复)。

默认情况下，错误会停止节点。选择节点设置中的 **On Error → Continue (using regular output)** 后，item 级错误会通过 `json.error` 返回，下游应先判断是否存在此字段；解释器等公共配置错误仍可能直接停止整个节点。错误码的处理方式见 [故障排查](docs/operations.md#故障排查)。收费提交不要直接开启 **Retry On Fail**，以免重复提交产生费用。

## 节点使用说明

远端文件和回调 URL 只接受 HTTP(S)、80/443 端口及解析为公开 IP 的地址，不接受内网地址、URL 用户口令或 fragment。上游服务负责后续抓取；其重定向和 DNS 变化仍需服务方控制，生产应使用管理员批准的内容域名。

### 文本翻译

接受文本、源语言和目标语言，返回译文及语言信息；源语言和目标语言分别通过 `fromLanguage`、`toLanguage` 指定。

### 文本校对

接受中文文本，在 `data.result` 中返回校对结果。服务返回业务失败码时映射为节点错误。

### 票据识别

接受发票、收据等图片或 PDF binary，在 `data.result` 中返回票据识别结果。

### Hyper TTS 语音合成

接受文本、音色和声音参数，合成输出默认写入 `binary.audio`，文件名为 `speech.mp3`。只有收到服务结束帧才返回成功，结果不包含随后被清理的临时文件路径。

`listVoices` 只读取随包的静态音色常量，不调用合成服务；实际语音合成仍需配置凭证并具备对应服务权限。

### PDF 与图片 OCR

图片识别接受图片 binary；PDF 创建任务接受 PDF binary 或公开 HTTP(S) URL，填写 URL 后忽略 binary 字段。

`getPdfTask` 与 `getResult` 都查询 PDF 任务状态。完成状态为 `FINISH` 或 `ANY_FAILED` 时返回完成标记；下载地址由服务响应提供，节点不会自动下载结果文件。

### 极速转写

创建任务接受 MP3 binary，可指定语言、口音和领域。创建后通过返回的 `taskId` 查询状态或获取转写文本与分段结果。

### 图片理解

接受图片 binary 和问题，支持 `general`/`imagev3`、`temperature` `(0, 1]` 和 `maxTokens` `1..8192`。只有收到服务结束帧才返回文本结果，原始 WebSocket 帧不会暴露给 n8n。

### 视频翻译

使用公开视频 HTTP(S) URL 创建任务，不在节点内上传本地视频；支持列出任务和按 `taskId` 查询详情。`confirmTranscript` 单独执行确认，并通过 `forceRerun` 明确控制后续重跑，不自动重试任务提交。

### 声音克隆

训练支持获取训练文本、创建任务、上传样本、提交和查询状态。样本填写公开 URL 后忽略 binary，仅添加音频，需要再执行 `submitTraining`。binary 上传会同时提交训练：必须开启节点中的确认选项，输入不得超过 3 MiB，随后执行 `getTraining`，不要重复提交。`data.trainingSubmitted` 标明本次是否已提交；音频时长、采样率和内容还需满足服务要求。训练业务失败码映射为节点错误。

`createTraining` 返回的任务 ID 位于 `data.result.data`，后续操作的 Task ID 应直接引用该值（例如 `={{ $json.data.result.data }}`），保留完整字符串，不转换为数字。已有工作流中的安全整数 ID 仍兼容。

合成需要已训练的 `resId`，输出支持 MP3、PCM、Speex 和 Opus，只有收到服务结束帧才返回成功。

声音训练使用 HTTPS token/训练入口，校验服务端证书并拒绝重定向，不回退到 HTTP。声音克隆合成使用 TLS WebSocket。训练次数、合成额度和音色资源权限需分别开通，详见 [服务与平台限制](docs/compatibility.md)。

### 合同审核

接受直接文本、UTF-8 binary，或显式选择格式的 PDF、DOCX、PNG、JPEG、BMP binary。文档上限 20 MiB，图片 OCR 上限 4 MiB；PDF 最多 8 页，以最长边不超过 1600 像素逐页栅格化后调用图片 OCR。提取的全文最多 4000 字符，超限会失败，不静默截断；长合同由调用方拆分，片段间关系需另行审查。DOCX 读取正文段落与表格，不提取页眉页脚、批注、文本框或嵌入对象。

默认图片提取方法为 OCR；显式选择 Image Understanding 时按模型推断标记，不在 OCR 失败后自动切换服务。文本经过规则检查和星火 `v3.5/chat` 审阅；可选将中文模型摘要翻译为英文。合规与双语检查属于本地规则，模型风险引用会与送审文本核对，全部结果仍需人工复核。不提供未经服务返回的识别置信度。

任一必需服务失败时返回受控错误，不自动重试；调用沿用公共层总时限（默认 120 秒，管理员可调整），包含逐页 OCR。JSON 结果包含规则与模型输出，Markdown/JSON 报告在 n8n binary 持久化后回收临时文件。

### 手绘图渲染

从安装包内的 [受限流程图模板](runtime/bridge/diagram/workflow.html) 开始修改，将 HTML 文本传给节点。支持常见 HTML 文本容器、SVG 基本形状和 CSS 动画；不接受脚本、事件属性、iframe、表单、外部图片、链接或用户字体资源，也不接受 CSS URL、转义和注释。渲染器禁用页面 JavaScript、阻断外部请求，内嵌随包 Kalam 字体；中文使用主机已安装的字体回退。

输入上限 256 KiB、2000 个元素；宽度 64–1600、高度 64–1200、帧率 1–25、时长 100–5000 ms、倍率 1 或 2，总像素预算为 `ceil(时长 × 帧率 / 1000) × 宽 × 高 × 倍率² ≤ 120,000,000`。尺寸和动画时长应与 HTML 对齐；不保证任意动画天然无缝。GIF 产物上限 32 MiB。

受限格式和资源拦截不能替代生产环境的容器/系统隔离；请按部署要求限制浏览器进程的内存、CPU 和文件访问权限。

## 文档与问题反馈

- [安装与配置](docs/installation.md)：安装包、Python 依赖、共享凭证和手绘图运行环境。
- [兼容范围](docs/compatibility.md)：n8n、Python、平台及服务能力的适用条件。
- [运行与恢复](docs/operations.md)：并发、日志、错误处理、任务恢复和升级回滚。
- [问题反馈](https://github.com/iflytek/iFly-Skills/issues)：请提供包版本、n8n/Node.js/Python 版本、操作系统、节点/操作、错误码及可获得的 requestId，并附不含敏感信息的最小复现。不要提交密钥、签名 URL 或业务文件原文。

需要修改节点或参与开发时，参阅仓库中的 [贡献指南](https://github.com/iflytek/iFly-Skills/blob/main/packages/n8n-nodes-iflytek/CONTRIBUTING.md)。

## 许可

本包使用 Apache-2.0 许可证，详见 [LICENSE](LICENSE)。手绘图渲染适配保留 [MIT 许可](runtime/bridge/diagram/licenses/animated-sketch-diagram-MIT.txt)，Kalam 字体使用 [SIL OFL 1.1](runtime/bridge/diagram/licenses/Kalam-OFL.txt)。Playwright Core 使用 Apache-2.0；浏览器和 ffmpeg 由管理员按各自许可安装。
