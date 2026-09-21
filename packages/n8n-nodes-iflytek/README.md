# n8n-nodes-iflytek

iFly-Skills 的自托管 n8n 社区包开发骨架，提供共享凭证定义、Skill 目录和原脚本打包工具。版本为 `0.0.0-dev.0`，保留 `private: true`；尚无已注册的业务节点，未发布 npm。

## 当前交付范围

- `credentials/IflyApi.credentials.ts`：共享 `iflyApi` 凭证，包含 App ID、API Key、API Secret；字段说明标注对应的 `IFLY_*` 变量名。从 n8n 读取凭证并注入子进程的执行入口尚未实现。
- `skills.json`：11 个 Skill 的候选节点类名、内部名、操作名和凭证类型，同时作为脚本打包白名单。清单中的名称不代表已有节点类或可执行操作。
- `scripts/stage-runtime.mjs`：复制九个原子 Skill 的 10 个 Python 脚本，生成依赖和文件校验清单。合同审核的部分 API 客户端尚未实现；手绘图尚无本包适配入口，渲染资源及浏览器/ffmpeg 依赖未打包。这两项的排除原因记录在清单中。
- `python/requirements-core.lock`：原子能力的直接、间接 Python 依赖版本锁定；不包含浏览器/ffmpeg，也不是跨平台 wheel/hash 锁。
- `tests/`：凭证加载、清单完整性、打包内容及构建失败保护测试。

`package.json` 中的 `n8n.credentials` 注册编译后的凭证类，`n8n.nodes` 为空数组。本包尚未实现 Python bridge、Runner、业务节点或 n8n 文件处理；打包的原脚本仍通过各自 CLI 调用。

清单中的 `credential` 表示该 Skill 服务调用使用的目标凭证类型，不表示鉴权已在本包接通。合同条目记录为 `iflyApi`；手绘图现有的本地 JavaScript 渲染器不读取 API 凭证，因此记录为 `null`。

## 构建与校验

在仓库内本包目录执行（需要 Git、Node.js 24 和 npm）：

```sh
npm ci
npm run check
npm pack --dry-run
npm pack --pack-destination <仓库外的已有目录>
```

`npm run build` 编译 TypeScript 并从当前仓库工作树生成 `runtime/`；`npm pack` 会先重新构建。安装后的制品包含脚本快照，无需仓库或 Git。构建工具、测试和 TypeScript 源码不进入 npm 制品。

生成目录为 `dist/`、`runtime/`，开发依赖在 `node_modules/`，均被 Git 忽略。源码、构建工具和依赖锁用于重新生成这些内容。

`runtime/manifest.json` 记录源码 HEAD、Skill 工作树是否有未提交改动、原始清单 SHA-256、逐文件 SHA-256/字节数及 Skill 目录。`sourceTreeDirty` 表示构建时 `skills/` 是否有未提交改动；为真时，HEAD 不能单独代表脚本内容，应同时核对文件校验值。用于发布的制品须从干净的固定提交构建。

## Python 依赖

Python 声明下限为 3.10。管理员在执行节点的宿主机/容器中预装依赖；npm 安装不自动调用 pip。以下示例中 `<包目录>` 可以是本地构建目录或解包后的 npm 包目录：

```sh
python -m venv <仓库外的虚拟环境目录>
<虚拟环境的Python路径> -m pip install -r <包目录>/runtime/requirements/requirements-core.lock
<虚拟环境的Python路径> -m pip check
<虚拟环境的Python路径> <包目录>/runtime/skills/iflytek-hyper-tts/scripts/xfei_hyper_tts.py --action list_voices
```

Windows 解释器位于 `Scripts/python.exe`，Linux 位于 `bin/python`。`--help` 显示 CLI 帮助；Hyper TTS 的 `--action list_voices` 只输出脚本内置的音色数据，不使用 API 凭证、不请求服务端。这些本地检查不验证 API 鉴权或语音合成。Hyper TTS 语音合成本身需要 App ID、API Key、API Secret 和相应服务权限。

## 验证与发布边界

开发依赖为 Node.js 24、TypeScript 5.9.3 和 `n8n-workflow` 2.39.3 类型。已在 Windows、Node.js 24.18.0、npm 11.16.0、Python 3.14.7 上检查构建、离线测试和 tarball。n8n 实例安装、画布加载、业务调用、Python 最低版本、Linux Docker 及跨 worker 行为尚未验证。

发布前需要实现业务节点，并完成制品安装测试、许可和兼容检查，再移除 `private` 并确定发布版本。`n8n-community-node-package` 关键词仅用于社区包识别，不代表自动安装、verified 审核通过或 n8n Cloud 兼容。
