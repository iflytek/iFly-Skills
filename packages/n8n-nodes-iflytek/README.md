# n8n-nodes-iflytek

`n8n-nodes-iflytek` 将 iFly-Skills 仓库中的可复用能力封装为自托管 n8n 社区节点。每个 Skill 对应一个节点，远端服务共享 `IflyApi` 凭证，本地手绘图渲染无需 API 凭证。节点通过 Node.js `child_process.spawn` 启动受控的 Python bridge；bridge 再加载随包分发的 Skill 脚本并返回稳定的 JSON 结果。

当前版本为 `0.0.0-dev.0`，`package.json` 仍设置为 `private: true`，用于开发和离线验收，尚未发布 npm。包元数据包含 `n8n-community-node-package` 关键字和 n8n 节点注册路径；关键字本身不代表已经发布或通过 n8n 审核。

## 已启用节点

| 节点 | 操作 | 输入 | 结果 |
| --- | --- | --- | --- |
| `IflyTranslate` | `translate` | 文本或 UTF-8 binary、源语言、目标语言 | `data.sourceText`、`translatedText`、语言字段 |
| `IflyTextProofread` | `check` | 文本或 UTF-8 binary | `data.result` 中的校对服务结果 |
| `IflyOcrInvoice` | `recognize` | 发票、收据等图片或 PDF binary | `data.result` 中的结构化识别结果 |
| `IflyHyperTts` | `synthesize` | 文本或 UTF-8 binary、音色和声音参数 | `data` 中的合成信息及 `binary.audio` MP3 |
| `IflyHyperTts` | `listVoices` | 无业务输入 | 随包静态音色常量；不访问服务端 |
| `IflyPdfImageOcr` | `recognizeImage` | 图片 binary、结果格式 | `data.result` 中的通用图片 OCR 结果 |
| `IflyPdfImageOcr` | `createPdfTask` | PDF binary 或公开 HTTP(S) URL、导出格式 | `data.taskNo`、任务状态及原始响应 |
| `IflyPdfImageOcr` | `getPdfTask` | PDF OCR `taskNo` | 当前状态及原始响应 |
| `IflyPdfImageOcr` | `getResult` | PDF OCR `taskNo` | 状态、完成标记和原始响应 |
| `IflySpeedTranscription` | `createTask` | MP3 binary、语言、口音和领域 | `data.taskId`、上传地址 |
| `IflySpeedTranscription` | `getTask` | 转写 `taskId` | 当前状态及原始响应 |
| `IflySpeedTranscription` | `getResult` | 转写 `taskId` | `data.text`、分段、状态和原始响应 |
| `IflyImageUnderstanding` | `analyze` | 图片 binary、问题和模型参数 | `data.text` |
| `IflyVideoTranslate` | `createTask` | 公开视频 HTTP(S) URL、源语言、目标语言 | `data.result` 中的任务信息 |
| `IflyVideoTranslate` | `listTasks` | 无业务输入 | `data.result` 中的任务列表 |
| `IflyVideoTranslate` | `getTask` | 视频翻译 `taskId` | `data.taskId` 及任务详情 |
| `IflyVideoTranslate` | `confirmTranscript` | 视频翻译 `taskId`、是否强制重跑 | `data.result` 中的确认结果 |
| `IflyVoicecloneTts` | `getTrainingText` | 训练文本集 ID | `data.result` 中的文本片段 |
| `IflyVoicecloneTts` | `createTraining` | 任务名称、性别、引擎和语言 | `data.result` 中的训练任务 |
| `IflyVoicecloneTts` | `uploadSample` | 训练任务 ID、音频 binary 或 URL、文本片段 | `data.result`、`data.trainingSubmitted`；binary 同时提交训练 |
| `IflyVoicecloneTts` | `submitTraining` | 训练任务 ID | `data.result` 中的提交结果 |
| `IflyVoicecloneTts` | `getTraining` | 训练任务 ID | 状态、资源 ID 和原始响应 |
| `IflyVoicecloneTts` | `synthesize` | 文本、克隆资源 ID 和声音参数 | `binary.audio` 及合成信息 |
| `IflyContractReview` | `review` | 合同文本或文档 binary、语言、审核模式与重点 | 结构化审核结果、`binary.report` Markdown 和 `binary.report2` JSON |
| `IflyAnimatedSketch` | `renderHtmlToGif` | 受限 HTML/SVG/CSS 文本或 UTF-8 binary、尺寸与动画参数 | `binary.image` GIF、尺寸和帧数 |

当前共 11 个节点、25 个操作。合同审核会编排多个客户端；手绘图节点只渲染现成 HTML，不包含自然语言生成图表操作。票据 OCR 与通用 PDF/图片 OCR 是两个独立节点，不能互相替代。

## 运行结构

```text
n8n node
  -> executeSkill
  -> PythonRunner
  -> child_process.spawn(python -I -B -u -X utf8)
  -> runtime/bridge/bridge.py
  -> fixed adapter and allow-listed Skill modules
  -> JSON response and optional binary artifacts
```

`runtime/` 在构建或打包时由包内 `python/` 适配代码和 `skills.json` 列出的原 Skill 文件生成；原文件按字节复制，不维护第二份业务脚本。bridge 只接受 `operations.json` 中登记的固定 skill/operation，丢弃 Skill 的 stdout/stderr，并将上游异常转换为固定错误码。每次调用使用独立临时目录，输入 binary 由 n8n helper 写入，输出在持久化完成后回收。

Node 负责表单、凭证与 binary 映射，bridge 负责参数校验和结果适配。合同 Skill 的服务客户端原为待实现接口；包内 `python/contract/` 补齐这些服务适配，复用原 Skill 的文本清洗、条款、风险、合规、双语检查和报告处理器，以及现有 OCR、翻译和图片理解脚本。原合同 CLI、配置和客户端接口保持原有职责。

原 Skill 源码保持不变。`python/skill_compat.py` 通过子类或调用时的局部包装处理签名、分片和流结束判定；合同报告兼容处理位于 `python/contract/report.py`。这些适配不重写原脚本文件，也不替换原模块中的函数或类。

原手绘图渲染器是直接执行的 CLI，没有可导入的函数入口。包内 `python/diagram/` 沿用其 CSS 逐帧截图与 ffmpeg 合成方式，提供独立的受限渲染入口，复用原 Skill 的字体资源。原 CLI 保持不变；n8n 调用的 Playwright、浏览器与 ffmpeg 子进程沿用临时目录和进程树取消机制。

请求协议使用版本 `1`，包含 `requestId`、`input` 和 `parameters`。成功结果包含 `ok: true`、`status: succeeded`、`data`、`artifacts` 和执行耗时；节点输出会保留 `pairedItem`。默认错误会终止当前节点，开启 n8n 的 continue-on-fail 后才会按 item 写入 `json.error`。

## 凭证与配置

在 n8n 中创建一个 **iFlytek API** 凭证（内部名 `iflyApi`），各节点按操作需要复用：

| n8n 字段 | Python 子进程变量 |
| --- | --- |
| `appId` | `IFLY_APP_ID` |
| `apiKey` | `IFLY_API_KEY` |
| `apiSecret` | `IFLY_API_SECRET` |

翻译、校对、票据 OCR、Hyper TTS、图片 OCR、极速转写、图片理解、声音克隆合成和合同审核使用完整三元组。PDF OCR 的创建和查询只需要 `appId` 与 `apiSecret`；视频翻译只需要 `apiKey` 与 `apiSecret`；声音克隆训练只需要 `appId` 与 `apiKey`。合同内部客户端复用同套凭证，但应用仍需开通星火 `generalv3.5` 及所选 OCR、图片理解、翻译服务权限。

执行层按操作注入凭证，不会将无关字段传给子进程。`listVoices` 只读取本地常量，无需凭证，也不能用来验证账户权限或真实合成能力。手绘图渲染不读取或注入 API 凭证。子进程不会继承主机中的 `XFEI_*`、`XFYUN_*`、`PYTHONPATH`、`NODE_OPTIONS` 或其他未列入白名单的变量。

管理员需要在 n8n 进程环境中配置 Python 解释器的绝对路径：

```powershell
$env:IFLYTEK_PYTHON_EXECUTABLE = 'C:\path\to\venv\Scripts\python.exe'
$env:IFLYTEK_TMP_ROOT = 'C:\path\to\existing-temp-directory' # 可选
```

Linux/macOS 使用对应的 `/absolute/venv/bin/python` 路径。原子服务使用 `python/requirements-core.lock`；使用合同 PDF/DOCX 提取时安装 `python/requirements-full.lock`（包含 core）。安装后在 npm 制品内使用对应的 `runtime/requirements/` 路径。节点执行和 npm 安装不会自动运行 pip。

手绘图还需要管理员预装 Chromium/Chrome/Edge 和 ffmpeg，并配置绝对路径：

```powershell
$env:IFLYTEK_CHROME_EXECUTABLE = 'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
$env:IFLYTEK_FFMPEG_EXECUTABLE = 'C:\path\to\ffmpeg.exe'
```

Node 使用当前 n8n 进程的解释器；`playwright-core` 作为 npm 运行依赖安装。浏览器与 ffmpeg 不随包分发，也不会自动下载。路径属于管理员配置，不是工作流输入；Linux 需运行在支持 Chromium sandbox 的非 root 环境，本包不关闭该 sandbox。

## 节点使用说明

各节点的文件输入通过 n8n binary 字段传递，不接受本地文件路径。支持文本输入的节点可使用直接文本或指定的 UTF-8 binary 字段；两者同时提供时使用直接文本。

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

合成需要已训练的 `resId`，输出支持 MP3、PCM、Speex 和 Opus，只有收到服务结束帧才返回成功。

### 合同审核

接受直接文本、UTF-8 binary，或显式选择格式的 PDF、DOCX、PNG、JPEG、BMP binary。文档上限 20 MiB，图片 OCR 上限 4 MiB；PDF 最多 8 页，以最长边不超过 1600 像素逐页栅格化后调用图片 OCR。提取的全文最多 4000 字符，超限会失败，不静默截断；长合同由调用方拆分，片段间关系需另行审查。DOCX 读取正文段落与表格，不提取页眉页脚、批注、文本框或嵌入对象。

默认图片提取方法为 OCR；显式选择 Image Understanding 时按模型推断标记，不在 OCR 失败后自动切换服务。文本经过规则检查和星火 `v3.5/chat` 审阅；可选将中文模型摘要翻译为英文。合规与双语检查属于本地规则，模型风险引用会与送审文本核对，全部结果仍需人工复核。不提供未经服务返回的识别置信度。

任一必需服务失败时返回受控错误，不自动重试；调用沿用公共层 120 秒总时限，包含逐页 OCR。JSON 结果包含规则与模型输出，Markdown/JSON 报告在 n8n binary 持久化后回收临时文件。

### 手绘图渲染

从 [受限流程图模板](python/diagram/workflow.html) 开始修改；npm 制品内同一模板位于 `runtime/bridge/diagram/workflow.html`。支持常见 HTML 文本容器、SVG 基本形状和 CSS 动画；不接受脚本、事件属性、iframe、表单、外部图片、链接或用户字体资源，也不接受 CSS URL、转义和注释。渲染器禁用页面 JavaScript、阻断外部请求，内嵌随包 Kalam 字体；中文使用主机已安装的字体回退。

输入上限 256 KiB、2000 个元素；宽度 64–1600、高度 64–1200、帧率 1–25、时长 100–5000 ms、倍率 1 或 2，总像素预算为 `ceil(时长 × 帧率 / 1000) × 宽 × 高 × 倍率² ≤ 120,000,000`。尺寸和动画时长应与 HTML 对齐；不保证任意动画天然无缝。GIF 产物上限 32 MiB。

受限格式和资源拦截不能替代生产环境的容器/系统隔离；请按部署要求限制浏览器进程的内存、CPU 和文件访问权限。

## 安装、构建与打包

开发环境需要 Node.js 24、npm、Git 和 Python 3.10 或更高版本。`n8n-workflow` peer 依赖范围为 `>=2.39.3 <3`。

```sh
cd packages/n8n-nodes-iflytek
npm ci
<venv-python> -m pip install -r python/requirements-full.lock
<venv-python> -m pip check
npm run check
npm pack --dry-run
```

`npm run build` 会清理并重新生成 `dist/`，编译凭证、节点和共享执行层，再按白名单生成 `runtime/bridge`、`runtime/skills`、依赖锁定文件和 `runtime/manifest.json`。`npm pack` 通过 `prepack` 重建后，只将 `dist/`、`runtime/`、README、LICENSE 和包元数据纳入制品；测试、源代码、构建脚本和 `node_modules/` 不进入制品。

## 测试与边界

```powershell
$env:IFLY_TEST_PYTHON = 'C:\path\to\venv\Scripts\python.exe'
npm run check
npm run typecheck
npm pack --dry-run
git diff --check
```

测试调用全部 11 个节点的实际 execute 方法，覆盖 25 个操作的分派、凭证和 binary 映射。另有真实原子 Skill 与合同适配器的传输替身测试，以及共享执行层的子进程测试，覆盖签名、业务失败码、流中断、报告、文档提取、取消、超时、临时目录回收和 runtime 清单；这些离线测试不调用收费服务。

配置 `IFLY_TEST_CHROME` 和 `IFLY_TEST_FFMPEG` 为预装程序的绝对路径，可额外执行真实 GIF 解码、渲染取消和模拟 n8n 上下文的 binary 输出测试；未配置时这些测试显式跳过。`IFLY_TEST_PYTHON` 和两个渲染测试变量仅供测试使用，不参与节点运行配置。测试 Python 需安装 full 依赖。

临时目录、tarball、`.pyc` 和测试缓存不应提交；`dist/`、`runtime/`、`node_modules/` 是可重建或开发目录，保持 Git 忽略即可。

真实 n8n 实例兼容性、服务端权限与配额、业务识别质量、发布版本管理和 npm 发布不属于当前开发包的离线测试结论。

## 许可

本包使用 Apache-2.0 许可证，详见 [LICENSE](LICENSE)。手绘图渲染适配保留上游 MIT 许可，Kalam 字体使用 SIL OFL 1.1；许可文件位于 `python/diagram/licenses/`，打包后位于 `runtime/bridge/diagram/licenses/`，字体仍来自 runtime 的原 Skill 目录。Playwright Core 使用 Apache-2.0；浏览器和 ffmpeg 由管理员按各自许可安装。
