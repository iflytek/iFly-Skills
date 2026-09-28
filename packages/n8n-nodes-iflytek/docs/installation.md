# 安装与配置

本指南供自托管 n8n 的实例管理员和工作流作者使用。安装分为 npm 节点包、Python 运行环境和 n8n 凭证三个部分。仅安装 npm 包不会自动安装 Python、浏览器或 ffmpeg。

## 环境要求

- 使用 Node.js 24 运行 n8n，准备 Python 3.10 或更高版本及独立 venv；版本选择见 [兼容范围](compatibility.md)。
- 允许 n8n 执行进程启动本地 Python，并为其提供可写的独占临时目录。
- 远端能力需要讯飞应用凭证、相应服务权限和可用额度；手绘图渲染不需要 API 凭证。
- 使用 queue mode 时，在每个实际执行工作流的进程所在环境安装相同的包和依赖。

## 安装节点包

对于 registry 中已有的发布版本，可由实例管理员在 n8n 的 **Settings → Community Nodes → Install** 中安装 `n8n-nodes-iflytek`。实例须允许安装社区节点；包的可安装状态以 registry 和实例策略为准。

也可以按 n8n 的 [社区节点手动安装说明](https://docs.n8n.io/integrations/community-nodes/installation/manual-install/) 安装。在该实例实际使用的社区节点目录中执行以下命令，将 `VERSION` 替换为已发布的版本号：

```sh
npm install --save-exact "n8n-nodes-iflytek@VERSION"
```

默认社区节点目录是运行 n8n 的用户目录下的 `.n8n/nodes`；使用自定义用户目录或容器挂载时，以实例实际配置为准。若使用维护者提供的 `.tgz` 安装包，在同一目录运行 `npm install --save-exact`，将参数替换为该文件的绝对路径。请勿将全局 npm 安装目录当作社区节点目录。

安装后，以下内容应位于 `node_modules/n8n-nodes-iflytek/`：

| 路径 | 用途 |
| --- | --- |
| `dist/` | n8n 节点、凭证和管理命令 |
| `runtime/requirements/` | Python 依赖版本锁 |
| `runtime/bridge/diagram/workflow.html` | 手绘图 HTML 模板 |
| `docs/` | 安装、兼容和运行说明 |

后续示例中的“包目录”均指这个已安装目录。普通使用不需要 checkout 仓库、编译 TypeScript 或执行源码测试。

## 配置 Python

将示例路径替换为本机实际路径。使用 n8n 服务账号创建或授权访问 venv，临时目录也必须由该账号可写。

### Linux

```sh
ifly_package_root="/absolute/path/.n8n/nodes/node_modules/n8n-nodes-iflytek"
ifly_venv="/absolute/path/iflytek-venv"
ifly_tmp="/absolute/path/iflytek-tmp"

python3 -m venv "$ifly_venv"
"$ifly_venv/bin/python" -m pip install -r "$ifly_package_root/runtime/requirements/requirements-core.lock"
"$ifly_venv/bin/python" -m pip check
mkdir -p "$ifly_tmp"

export IFLYTEK_PYTHON_EXECUTABLE="$ifly_venv/bin/python"
export IFLYTEK_TMP_ROOT="$ifly_tmp"
node "$ifly_package_root/dist/shared/preflight.js"
```

### Windows PowerShell

```powershell
$iflyPackageRoot = 'C:\path\to\.n8n\nodes\node_modules\n8n-nodes-iflytek'
$iflyVenv = 'C:\path\to\iflytek-venv'
$iflyTmp = 'C:\path\to\iflytek-tmp'

python -m venv $iflyVenv
$iflyPython = Join-Path $iflyVenv 'Scripts\python.exe'
& $iflyPython -m pip install -r (Join-Path $iflyPackageRoot 'runtime\requirements\requirements-core.lock')
& $iflyPython -m pip check
New-Item -ItemType Directory -Path $iflyTmp -Force | Out-Null

$env:IFLYTEK_PYTHON_EXECUTABLE = $iflyPython
$env:IFLYTEK_TMP_ROOT = $iflyTmp
node (Join-Path $iflyPackageRoot 'dist\shared\preflight.js')
```

上述环境变量只对当前终端及其随后启动的进程生效。请在同一环境启动 n8n；如果通过系统服务、容器或进程管理器启动，应把变量写入对应服务配置并重启实际执行进程。不要把主机路径直接填入容器，应使用容器内部可访问的路径。

预检成功表示包文件、core 依赖和本地执行链可用，不验证讯飞服务授权。预检要求依赖版本与随包锁文件一致，建议使用专用 venv，避免其他应用升级共享依赖。

## 合同文档与手绘图依赖

处理合同 PDF、DOCX 或文档图片时，在同一个 venv 安装 `runtime/requirements/requirements-full.lock`；该文件已经包含 core 依赖。将上面的 pip 命令中的 `requirements-core.lock` 替换为 `requirements-full.lock` 即可。

手绘图还需要本机安装 Chromium、Chrome 或 Edge，以及 ffmpeg。`playwright-core` 随 npm 依赖安装，但不会下载浏览器。配置两个程序的绝对路径，例如：

```sh
# Linux 示例：以实际安装路径为准
export IFLYTEK_CHROME_EXECUTABLE="/usr/bin/chromium"
export IFLYTEK_FFMPEG_EXECUTABLE="/usr/bin/ffmpeg"
```

```powershell
# Windows 示例：以实际安装路径为准
$env:IFLYTEK_CHROME_EXECUTABLE = 'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
$env:IFLYTEK_FFMPEG_EXECUTABLE = 'C:\path\to\ffmpeg.exe'
```

Linux 需使用支持 Chromium sandbox 的非 root 环境。本包不关闭浏览器 sandbox；中文渲染还需安装可用的中文字体。

当 full Python 依赖和渲染程序均已配置时，在包目录运行 `node dist/shared/preflight.js --full`。`--full` 同时检查合同依赖和渲染程序，不是仅针对合同的预检。随后用 [随包模板](../runtime/bridge/diagram/workflow.html) 执行一次 **iFlytek Animated Sketch**，确认 `binary.image` 可读取；路径检查不能替代实际渲染。

## Linux 容器中的渲染

在容器镜像中预装相同版本的节点包、Python 依赖、浏览器、ffmpeg 和字体，并使用非 root 用户。镜像内的绝对路径需要与 `IFLYTEK_*_EXECUTABLE` 配置一致；n8n 数据目录和临时目录必须可写，包和依赖可以放在只读文件系统中。

使用 `--cap-drop=ALL` 与 `--security-opt=no-new-privileges` 时，浏览器的用户命名空间沙箱仍需要相应系统调用。将随包 [Chromium seccomp 配置](chromium-seccomp.json) 复制到 Docker 宿主机，在容器启动参数中设置 `--security-opt seccomp=/absolute/path/chromium-seccomp.json`。该配置基于 [Playwright v1.61.1 的 Docker 策略](https://github.com/microsoft/playwright/blob/v1.61.1/utils/docker/seccomp_profile.json)（Apache-2.0），保留默认拒绝规则及用户命名空间调用，补充 `chroot`，让 Chromium 能在自己的命名空间中建立沙箱；内核的 capability 检查仍然有效。

应按实际工作流设置内存、CPU、进程数、共享内存和临时磁盘限制。已验证配置见 [兼容范围](compatibility.md)。所用内核或宿主安全策略必须允许非特权用户命名空间；遇到 sandbox 启动失败时检查部署策略，不要通过 `--no-sandbox`、特权容器或关闭 seccomp 来替代配置。仅本地渲染可禁用容器网络；使用讯飞远端节点的实例仍需要相应服务的出站访问。

## 配置共享凭证

在 n8n 的凭证管理中创建 **iFlytek API**，填入同一个讯飞应用的 **App ID**、**API Key**、**API Secret**，然后在各节点中选择该凭证。凭证在不同能力间复用，并不意味着应用自动拥有全部服务权限。

| 操作范围 | 必需凭证字段 |
| --- | --- |
| 翻译、校对、票据 OCR、Hyper TTS 合成、图片 OCR、极速转写、图片理解、声音克隆合成、合同审核 | App ID、API Key、API Secret |
| PDF OCR 的创建和查询 | App ID、API Secret |
| 视频翻译 | API Key、API Secret |
| 声音训练 | App ID、API Key |
| Hyper TTS `listVoices`、手绘图渲染 | 无 |

合同审核还需要星火 `generalv3.5` 及所选 OCR、图片理解、翻译服务权限。音色、模型和克隆资源的授权也需与应用匹配；本地音色列表不表示账户已获授权。

节点使用 n8n 中选定的凭证，不读取主机上预先设置的 `IFLY_*`、`XFEI_*` 或 `XFYUN_*` 作为替代凭证。保存凭证后，应使用有权限的小样本验证目标服务。

## 安装后检查

重启 n8n 后，在节点选择器中搜索 `iFlytek`。可以先运行 **iFlytek Hyper TTS → List Voices**，确认本地 Python 链路，再执行目标能力的小样本。

如果节点不可见，检查安装用户、社区节点目录、实例策略和启动日志；如果节点可见但执行失败，按 [故障排查](operations.md#故障排查) 核对错误码。并发、超时、日志和队列部署配置见 [运行与恢复](operations.md)。
