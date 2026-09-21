# n8n-nodes-iflytek

iFly-Skills 的自托管 n8n 社区包开发预览，提供共享凭证定义、Python 脚本分发和公共执行层。版本为 `0.0.0-dev.0`，保留 `private: true`。目前尚无已注册的业务节点（`n8n.nodes` 为空），未发布 npm。

## 当前能力与目录

| 目录/文件 | 职责 |
| --- | --- |
| `credentials/IflyApi.credentials.ts` | 共享 `iflyApi` 三字段凭证；API Key/Secret 为密码输入 |
| `skills.json` | 11 个 Skill 的候选节点/操作名称、凭证类型和原脚本白名单；节点类及操作的实现状态须分别查看注册表和启用清单 |
| `shared/PythonRunner.ts` | 公共执行入口：排队、独立环境、协议、文件回收 |
| `shared/processControl.ts` | `spawn`、输出限额、超时/取消终止与每 worker 共享队列 |
| `shared/executeSkill.ts` | n8n 凭证、取消信号、binary helper、item 关联与错误映射 |
| `shared/binaryFiles.ts` | 每次调用的临时文件、产物路径/大小检查和清理 |
| `shared/credentialEnv.ts`、`protocol.ts`、`errors.ts`、`operationManifest.ts` | 环境白名单、协议、固定错误信息和启用操作白名单 |
| `python/bridge.py` | 单请求 Python 入口，固定分派并复用原模块 |
| `python/operations.json` | 实际启用操作、所需凭证字段和允许的产物 MIME 类型 |
| `python/requirements-core.lock` | 九个原子能力的直接与间接依赖版本锁 |
| `scripts/stage-runtime.mjs` | 白名单复制、启用操作检查及 SHA-256 清单生成 |
| `tests/` | 包测试、真实进程测试与不进入制品的故障注入 fixture |

当前 bridge 唯一启用的操作是 `iflytek-hyper-tts/listVoices`：导入原 Hyper TTS 脚本，读取其中的 `DEFAULT_VOICE`、`FREE_VOICES` 和 `VOICE_LIST` 静态数据。读取这些本地数据不使用 API 凭证，也不请求讯飞服务端。该操作只验证 Runner → bridge → 原模块的本地执行路径，不验证服务鉴权、账户音色权限或语音合成。Hyper TTS 语音合成本身需要 App ID、API Key 和 API Secret；`synthesize` 尚未在 bridge 中启用。

九个原子 Skill 的 10 个脚本随包分发。合同审核的部分 API 客户端尚未实现，未打包为可执行操作；其清单记录的目标凭证类型为 `iflyApi`。手绘图的现有 JavaScript 渲染器不读取 API 凭证，但本包尚未提供对应 adapter，也未打包渲染资源及浏览器/ffmpeg 依赖。

`skills.json` 中的 `credential` 表示该 Skill 服务调用使用的凭证类型；每个已启用操作实际需要的字段以 `python/operations.json` 为准。节点是否在 n8n 中注册以 `package.json` 的 `n8n.nodes` 为准；脚本已打包不代表对应节点或 bridge 操作已可用。

## 安装依赖、构建与测试

需要 Node.js 24、npm、Git（仅构建时）及 Python 3.10 以上。先在包目录安装开发依赖，并在仓库外创建独立 Python 环境：

```sh
npm ci
python -m venv <venv-directory>
<venv-python> -m pip install -r python/requirements-core.lock
<venv-python> -m pip check
```

Windows 的 `<venv-python>` 为 `Scripts/python.exe`，Linux 为 `bin/python`。将测试解释器设为绝对路径，再验证：

```powershell
# Windows PowerShell
$env:IFLY_TEST_PYTHON = 'C:\path\to\venv\Scripts\python.exe'
npm run check
```

```sh
# Linux/macOS shell
IFLY_TEST_PYTHON=/absolute/venv/bin/python npm run check
```

未设置 `IFLY_TEST_PYTHON` 时，测试使用 `python` 命令解析出的解释器，仍需预装 core 依赖。测试只使用本地数据和模拟上游结果，不调用收费 API。测试临时目录位于系统临时目录并在结束后清理。

```sh
npm pack --dry-run
npm pack --pack-destination <existing-directory-outside-repository>
```

`npm run build` 编译 TypeScript，并生成 `runtime/bridge/`、`runtime/skills/`、`runtime/requirements/` 和 manifest；`npm pack` 会先重新构建。安装后的脚本快照不依赖仓库或 Git。npm 不自动运行 pip；Python 解释器与系统依赖由管理员预装。

`node_modules/` 是可复用开发依赖；`dist/`、`runtime/` 是可重建产物，均被 Git 忽略。Python 缓存与 tarball 不应进入版本库。测试 fixture、源码构建工具不进入 npm 制品；共享编译代码和 runtime 进入制品。

## 公共调用约定

`executeSkill(context, runner, itemIndex, operation)` 是供节点执行方法调用的单 item helper；接入方应按 item 顺序调用。`runner` 从管理员配置创建并复用，解释器、包路径和资源限制不作为普通工作流输入。直接离线调用示例：

```javascript
const { PythonRunner } = require('./dist/shared/PythonRunner');

async function listVoices() {
  const runner = new PythonRunner({ pythonExecutable: '/absolute/venv/bin/python' });
  return runner.run(
    { skill: 'iflytek-hyper-tts', operation: 'listVoices' },
    async (response, files) => response,
  );
}
```

Windows 使用解释器的 Windows 绝对路径。

- 请求采用协议版本 1：`requestId`、`input`、`parameters`；Runner 生成 requestId，文件通过 `input.files` 中的临时相对路径传递。`input.files` 是保留字段，调用方用 `files`/`binaryInputs` 提供 binary。
- 成功必须同时满足单个 UTF-8 JSON、匹配的版本/requestId、退出码 0 和 `ok: true`。`queued`/`running` 必须带 `data.taskId`；公共层支持该结构，长任务业务操作尚未启用。
- `run` 的消费回调收到结构化结果和有界文件 Buffer；artifact 本地路径不出现在返回 envelope。回调完成后才清理目录，因此 n8n 的 binary 存储可以先完成。adapter 的 `data` 必须只返回业务值，不放工作目录或诊断信息。
- `executeSkill` 使用 `getCredentials('iflyApi', itemIndex)`、`getExecutionCancelSignal()`、`getBinaryDataBuffer` 和 `prepareBinaryData`；输出保留 `pairedItem`。异常转换为带 itemIndex 和 requestId 的 `NodeOperationError`。节点自行遵循 n8n 的继续失败/错误分支选项，公共层不吞错。
- 只注入启用操作要求的 `IFLY_*` 字段，不继承宿主其他凭证、`PYTHONPATH`、`NODE_OPTIONS` 或代理配置。Python 以 `-I -B -u -X utf8` 启动；运行时不生成字节码缓存。管理员代理/CA 扩展尚未提供。
- 不解析 CLI 人类可读输出。bridge 在模块调用期间丢弃普通 stdout/stderr 诊断；Runner 有界读取协议、丢弃原始 stderr，并使用本地固定错误消息，避免泄露凭证、输入或异常文本。接入服务端 API 的 adapter 需将上游业务码明确映射为协议错误。

## 执行限制与清理

| 项目 | 当前实现 |
| --- | --- |
| 子进程及等待队列 | 每 Node.js worker 共享最多 2 个执行槽、32 个等待项；超出报错 |
| 超时 | 默认 120 秒，配置范围 1～600000 毫秒；覆盖排队和 Runner 调用，超时后停止子进程 |
| stdout / stderr | 默认及最大值为 8 MiB / 256 KiB，可配置更低上限 |
| stdin | 1 MiB 上限；每次调用最多 16 个输入文件和 16 个输出产物 |
| binary | 每次输入/输出各默认 32 MiB，可配置至 64 MiB；n8n 读取 helper 自身的内存限制由宿主控制 |
| 产物 | 拒绝绝对/越界路径、符号链接、硬链接、重复、空文件及超限文件；MIME 必须在操作白名单中 |
| 终止 | Windows 使用固定 `taskkill.exe /PID <数字> /T /F`；POSIX 使用独立进程组，先 TERM，250 毫秒后 KILL |
| 清理 | 正常、错误、超时、取消及 binary 存储失败均清理本次目录；清理失败明确报错 |
| 重试 | 公共层不自动重试，包括限流、未知提交结果和超时 |

回调及 n8n binary helper 的 Promise 无法被公共层强行中断；它们完成后会检查取消/超时状态并清理，不会把超时结果返回为成功。不能用这个超时替代宿主存储超时配置。

进程清理覆盖受控的 Python 子进程树。宿主崩溃、进程被外部强杀或子进程主动逃离进程组时，无法保证完成回收。浏览器渲染隔离、跨进程活动任务注册和 TTL 清扫尚未实现；公共层不会删除其他调用的临时目录。

## 验证范围与限制

实测 Windows、Node.js 24.18.0、npm 11.16.0、Python 3.14.7；TypeScript 5.9.3、`n8n-workflow` 2.39.3 和 Node 类型已锁定。n8n 接线经过类型检查和模拟执行上下文测试，尚未在 n8n 实例中验证。Linux/POSIX 终止分支、Python 最低版本和跨 worker 行为尚未实测。

公共层测试覆盖真实 Python 进程、本地静态音色读取、故障注入及仓库外制品运行。API 鉴权、语音合成、翻译、OCR 等服务调用，以及业务节点和工作流的端到端行为，不在这些离线测试的验证范围内。

`runtime/manifest.json` 记录源码 HEAD、Skill/包工作树是否有改动、清单与各 runtime 文件 SHA-256、协议版本和实际启用操作；脏工作树快照以文件 hash 为准。发布必须使用干净固定提交，完成实例验收后再移除 `private`。

`n8n-community-node-package` 关键词仅表示社区包元数据，不代表自动安装、verified 审核通过或 n8n Cloud 兼容。
