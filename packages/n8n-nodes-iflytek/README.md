# n8n-nodes-iflytek

iFly-Skills 的自托管 n8n 社区包，当前完成[实施计划](../../n8n-integration-plan.md)第 2 步：包骨架、共享凭证、节点规划清单及原脚本分发。版本为 `0.0.0-dev.0`，保留 `private: true`；尚无可执行业务节点，尚未发布 npm。

## 当前交付范围

- `credentials/IflyApi.credentials.ts`：共享 `iflyApi` 凭证，包含 App ID、API Key、API Secret；后续 Runner 将按操作注入 `IFLY_*`。凭证定义不做收费 API 探测。
- `skills.json`：11 个 Skill 的唯一节点类、内部名和计划 Operation，同时作为脚本打包白名单。清单中的操作不代表已经实现。
- `scripts/stage-runtime.mjs`：复制九个原子 Skill 的 10 个 Python 脚本，生成依赖和文件校验清单。合同真实客户端、手绘图 Python bridge 与渲染资源留到第 7 步；合同将复用同一凭证，手绘图本地 Render 无需凭证。
- `python/requirements-core.lock`：原子能力的直接、间接 Python 依赖版本锁定；不包含浏览器/ffmpeg，也不是跨平台 wheel/hash 锁。
- `tests/`：凭证加载、清单完整性、打包内容及构建失败保护测试。

`n8n.credentials` 注册编译后的凭证类，`n8n.nodes` 暂为空数组；后续每完成一个 Skill，再添加对应节点类和注册项。第 3 步负责 bridge、`child_process.spawn` Runner、错误及文件处理，第 4 步开始交付业务节点。

## 构建与校验

在仓库内本包目录执行（需要 Git、Node.js 24 和 npm）：

```sh
npm ci
npm run check
npm pack --dry-run
npm pack --pack-destination <仓库外的已有目录>
```

`npm run build` 编译 TypeScript 并从当前仓库工作树生成 `runtime/`；`npm pack` 会先重新构建。安装后的制品包含脚本快照，无需仓库或 Git。构建工具、测试和 TypeScript 源码不进入 npm 制品。

生成目录为 `dist/`、`runtime/`，开发依赖在 `node_modules/`，均已忽略；不创建空 `nodes/`、`shared/`、部署或工作流目录。新增能力时按需扩展。

`runtime/manifest.json` 记录源码 HEAD、Skill 工作树是否有未提交改动、原始清单 SHA-256、逐文件 SHA-256/字节数及计划节点映射。本地凭证改动尚未提交时，`sourceTreeDirty: true` 是预期结果，HEAD 不能单独代表脚本内容；制品以文件校验值为准。发布阶段须从干净的固定提交构建。

## Python 依赖

Python 声明下限为 3.10。管理员在执行节点的宿主机/容器中预装依赖；npm 安装不自动调用 pip。以下示例中 `<包目录>` 可以是本地构建目录或解包后的 npm 包目录：

```sh
python -m venv <仓库外的虚拟环境目录>
<虚拟环境的Python路径> -m pip install -r <包目录>/runtime/requirements/requirements-core.lock
<虚拟环境的Python路径> -m pip check
<虚拟环境的Python路径> <包目录>/runtime/skills/iflytek-hyper-tts/scripts/xfei_hyper_tts.py --action list_voices
```

Windows 解释器位于 `Scripts/python.exe`，Linux 位于 `bin/python`。`--help` 和上述本地音色列表用于无凭证离线检查；真实 API 仍需服务权限。未来 Runner 的解释器配置和凭证注入在第 3 步实现。

## 验证与发布边界

开发基线为 Node.js 24、TypeScript 5.9.3、`n8n-workflow` 2.39.3 类型（对应选定的 n8n 2.39.8 基线），实际验证环境是 Windows、Node.js 24.18.0、npm 11.16.0、Python 3.14.7。包构建、离线测试与 tarball 检查不等于 n8n 服务安装、画布加载或业务调用验收；Python 最低版本、Linux Docker、worker 和其他平台须在后续兼容测试中验证。

发布前按计划完成业务节点、制品安装测试、许可和兼容检查，再移除 `private` 并确定发布版本。`n8n-community-node-package` 关键词仅用于社区包识别，不代表自动安装、verified 审核通过或 n8n Cloud 兼容。
