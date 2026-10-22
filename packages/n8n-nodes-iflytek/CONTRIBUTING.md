# n8n 节点开发与验证

本文件面向修改本包源码的贡献者，保留在仓库中，不进入 npm 制品。安装包用户请从 [README](README.md) 开始。

npm 制品、版本标签、发布权限及维护流程见 [发布维护指南](RELEASING.md)。

## 本地开发

从完整的 iFly-Skills 仓库 checkout 工作；构建需要读取仓库内的原 Skill 文件。准备 Node.js 24、npm、Git 和 Python 3.10 或更高版本，在独立 venv 安装 full 依赖：

```sh
cd packages/n8n-nodes-iflytek
npm ci
# 使用 venv 中的 Python 执行
python -m pip install -r python/requirements-full.lock
python -m pip check
npm run build
npm run typecheck
```

`nodes/` 负责表单、item、凭证和 binary 映射；`shared/` 负责进程、协议、文件生命周期及 n8n 接口；`python/` 提供包内适配。优先在封装层解决兼容问题，避免为平台接入修改原 Skill 的行为。

`npm run build` 编译 `dist/`，按 `skills.json` 和固定文件清单生成 `runtime/`。原 Skill 资源按字节复制；`runtime/manifest.json` 记录文件完整性和来源。请修改源文件后重建，不直接编辑生成目录。

源码目录为 `packages/n8n-nodes-iflytek/`，npm 包名为 `@iflytekopensource/n8n-nodes-iflytek-skills`。n8n 从 `package.json` 的 `n8n.nodes` 和 `n8n.credentials` 加载编译后的 CommonJS 文件；本包不提供通用 JavaScript 库入口。工作流节点类型使用完整包名，例如 `@iflytekopensource/n8n-nodes-iflytek-skills.iflyTranslate`。

## 回归与打包

将 `IFLY_TEST_PYTHON` 设置为安装了 full 依赖的解释器绝对路径，然后执行：

```sh
npm test
npm run typecheck
npm pack --dry-run
git diff --check
```

`npm run check` 会先构建再运行测试。配置 `IFLY_TEST_CHROME` 和 `IFLY_TEST_FFMPEG` 后，测试会使用实际浏览器与 ffmpeg；未配置时相应测试显式跳过。这些变量仅供测试，安装包的运行变量见 [安装指南](docs/installation.md)。

测试包括全部节点的 execute 映射、传输替身、凭证隔离、协议、取消、超时、产物和清理行为，不使用真实账户。收费 API 验证须另行选择获授权的样本和预算，不把模拟结果记作服务验收。

打包后核对 `package.json` 的 `files`：用户文档、编译结果和运行资源应完整；测试、贡献指南、缓存和临时制品不进入 npm 包。README 与 docs 中的相对链接必须指向实际随包文件。CI 配置位于仓库 `.github/workflows/n8n-check.yml`。

## 真实 n8n 验证工具

先打包，并在仓库外的独立社区节点目录中安装 tarball；n8n 主机使用另一个独立目录。以下命令从本包源码目录执行，路径需替换为实际值。基础设施脚本要求 Linux/WSL，Python 依赖应与候选制品一致。

```sh
node scripts/n8n-acceptance.mjs \
  --n8n-root /test/host/node_modules/n8n --community-root /test/community \
  --python /test/venv/bin/python --report /test/compatibility.json

node scripts/acceptance.mjs --package /test/community/node_modules/@iflytekopensource/n8n-nodes-iflytek-skills \
  --python /test/venv/bin/python --samples 100 --report /test/load.json

node scripts/n8n-load-acceptance.mjs \
  --n8n-root /test/host/node_modules/n8n --community-root /test/community \
  --python /test/venv/bin/python --samples 100 --render-samples 10 \
  --chrome /absolute/path/chromium --ffmpeg /absolute/path/ffmpeg \
  --report /test/n8n-load.json

node scripts/n8n-queue-acceptance.mjs \
  --n8n-root /test/host/node_modules/n8n --community-root /test/community \
  --python /test/venv/bin/python --postgres-bin /usr/lib/postgresql/14/bin \
  --postgres-share /usr/share/postgresql/14 --redis /usr/bin/redis-server \
  --report /test/queue.json

node scripts/n8n-rollback.mjs --n8n-root /test/host/node_modules/n8n \
  --baseline-community /test/baseline --candidate-community /test/candidate \
  --python /test/venv/bin/python --report /test/rollback.json
```

这些工具调用本地 `listVoices`、可选的 HTML 渲染和受控错误输入，不调用收费 API。跨 worker 的 task ID 与响应丢失为模拟数据。`acceptance.mjs` 测量本地 Runner；`n8n-load-acceptance.mjs` 通过实际生产 Webhook 测量单进程 n8n 在并发 1/2/4 下的端到端耗时、进程内存、Python 数量和临时磁盘占用，并检查执行持久化、GIF 下载/解码及残留。后者仅在同时提供 `--chrome` 和 `--ffmpeg` 时执行渲染负载，每组另有一次不计入负载统计的预热。结果用于建立环境基线，不代表收费服务、queue mode 或生产容量承诺。回滚工具只替换节点包，不执行 n8n 数据库版本迁移。

n8n 工具创建独立临时账号、数据目录和本地端口，结束后清理自己启动的实例；宿主安装、venv、下载缓存和报告由调用方管理。queue 工具还需本机 PostgreSQL、Redis 二进制及其系统库，使用独立业务库加载 `docs/operation-ledger.sql`。
