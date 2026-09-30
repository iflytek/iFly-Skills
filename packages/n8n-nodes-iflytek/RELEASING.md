# npm 发布与维护

本指南供 `@iflytekopensource/n8n-nodes-iflytek` 维护者准备、发布和验证 npm 制品，并管理版本与依赖更新。安装及运行配置见 [安装指南](docs/installation.md)。

## 发布条件

- 发布目标为 `@iflytekopensource/n8n-nodes-iflytek`，registry 为 `https://registry.npmjs.org/`，访问级别为 `public`。维护者需拥有 `iflytekopensource` 组织内创建或发布该包的权限，并满足 npm 的双因素认证要求；首次发布时由 registry 校验名称和账号权限。
- 同步 `package.json`、`package-lock.json`、包级 `CHANGELOG.md` 和用户兼容说明。稳定版使用 `X.Y.Z`，Beta 使用 `X.Y.Z-beta.N`；版本发布后不能覆盖。包级变更记录使用 `## VERSION` 标题，每个版本须有唯一且非空的章节。
- 保留 `n8n-community-node-package` 关键词，以及完整的 `n8n.nodes`、`n8n.credentials` 和随包 runtime。关键词供 npm 社区包索引使用；不等于 n8n 官方认证、编辑器已验证节点目录收录或 Cloud 支持。
- 兼容 CI、节点包及测试宿主的生产依赖审计通过。`tests/host/` 提供 CI 和 registry 安装验证所用的宿主锁文件及安全回归。

## 准备与核验制品

在干净 checkout 安装锁定依赖和 Python full 环境，执行 `npm run check`、`npm run typecheck`。Linux CI 配置实际浏览器与 ffmpeg，覆盖渲染检查。然后从包目录执行：

```sh
npm run build
npm run release:prepare -- --output /absolute/path/release
```

输出目录须位于仓库外且为空，包含 `.tgz`、`release.json`、`runtime-manifest.json`、`SHA256SUMS`、完整包级 `CHANGELOG.md` 和仅含当前版本的 `RELEASE_NOTES.md`。脚本检查版本、变更记录章节、关键词、注册路径、示例工作流、许可、允许的文件列表及 runtime 哈希，并解包复核。清单记录源码 commit、工作树状态和校验值，用于核对来源与完整性。

本地开发可追加 `--allow-dirty` 核查未提交修改；所得记录标记 `publishable: false`，不能作为正式发布输入。最终安装验证和 npm 发布使用同一 tarball，不在发布时重新打包替换。

## GitHub Actions 发布

1. 将发布代码合入 `main`，创建并推送与包版本一致的 `n8n-vVERSION` 标签。这个专用前缀不会触发仓库的 `v*` Skill 发布流程。
2. 标签触发 `n8n release`：校验 main 来源，复用兼容与安全检查，生成候选包，并从该 tarball 独立安装、执行 runtime 预检。此运行只生成 Actions 制品，不发布 npm。
3. 审核制品后，在同一标签上手动运行 workflow，设置 `publish=true`。流程重新验证，再在 `n8n-release` environment 中发布该运行生成并验证的 tarball。稳定版使用 `latest`，Beta 使用 `beta`。
4. 发布后复核 registry 版本、关键词、注册元数据、dist-tag、integrity 和 SHA-256，从 registry 精确安装到独立真实 n8n 验证，最后创建包含制品与验证报告的 GitHub release，正文使用制品中的 `RELEASE_NOTES.md`。

```sh
gh workflow run n8n-release.yml --ref n8n-vVERSION -f publish=true
```

首次发布前，仓库管理员须在 GitHub Settings → Environments 中为 `n8n-release` 配置 **Required reviewers**，并将允许部署的标签限制为 `n8n-v*`。工作流中的 `environment` 引用不会自动创建审核规则；须在设置页面确认规则已启用。普通 PR 只有读取权限。实际 CI 发布仅在 `iflytek/iFly-Skills` 的显式发布运行中执行。

CI 使用 [npm trusted publishing](https://docs.npmjs.com/trusted-publishers/) 的 OIDC 身份认证，不读取 `NPM_TOKEN`。在 npm 包设置中配置 GitHub Actions trusted publisher：组织 `iflytek`、仓库 `iFly-Skills`、workflow 文件名 `n8n-release.yml`、environment `n8n-release`，并允许直接执行 `npm publish`。工作流使用 GitHub 托管 runner、支持 OIDC 的 npm（至少 11.5.1）及 `id-token: write`，发布时生成 provenance。确认 OIDC 发布成功后，撤销不再使用的 npm 发布 token 并删除对应 GitHub secret。

若包尚未创建、无法配置 trusted publisher，先运行上述标签验证流程，审核生成的 tarball，再按下一节使用维护者账号和 2FA 首次发布同一制品。包创建后配置 trusted publisher；可在同一标签上运行 `publish=true`，流程核对已发布版本的 integrity，并完成 registry 安装验证和 GitHub release。终端首次发布不生成 GitHub Actions provenance；后续新版本通过 OIDC 发布时生成，重复运行不会为已发布版本补加 provenance。

## 维护者手动发布

使用维护者终端发布时，先核对干净源码、CI 结果和待发布制品，使用具有发布权限的 npm 账号登录并满足 2FA 要求：

```sh
npm whoami --registry https://registry.npmjs.org/
npm publish /absolute/path/release/iflytekopensource-n8n-nodes-iflytek-VERSION.tgz --access public --tag latest
npm run release:verify -- --release /absolute/path/release/release.json
```

Beta 发布将 `latest` 改为 `beta`。需要 CI provenance 时使用上述 GitHub Actions 发布方式。发布后按照 [贡献指南](CONTRIBUTING.md#真实-n8n-验证工具) 从 registry 精确安装该版本并验证，保留报告。

## 发现与失败恢复

`npm run release:verify` 核对 registry 中的包和实际下载的 tarball，并记录 `keywords:n8n-community-node-package` 搜索结果。索引可能延迟；精确包名可安装和关键词搜索已收录是两个独立结果，后者未收录时应稍后复查。安装后通过节点选择器搜索 `iFlytek`。

发布后验证失败时，先查询 registry 中的版本及 integrity。流水线仅允许复用 integrity 一致的已发布版本。GitHub release 创建失败时，在核对制品后补齐附件。若发现功能问题，发布修复版本并说明影响范围和升级方法；用户实例通过安装目标版本完成升级。

## 持续维护

用户可通过 [n8n 问题模板](../../.github/ISSUE_TEMPLATE/n8n-node.yml) 提供版本、运行方式、节点操作、脱敏错误码和最小工作流。不要索取密钥、签名 URL 或原始业务文件；凭证泄漏通过私密渠道处理并轮换凭证。

每周审阅 Dependabot 和服务接口变化。变更通过兼容与制品验证后发布，并更新包级 changelog；破坏性变化附迁移说明。保留可回退的包版本、模板和业务 task ID。回滚节点包不能撤销远端付费任务，也不能替代 n8n 数据库备份和迁移评估。

PR、main 和发布复用相同生产依赖审计：节点包使用 `--audit-level=high`，阻止 high 和 critical；独立测试宿主使用 `--audit-level=critical`。审计服务错误同样阻止发布，未达到门槛的告警仍需审阅。宿主定向升级、影响范围、临时缓解及 override 撤除条件见 [宿主依赖安全维护](tests/host/SECURITY.md)。更新锁文件后正常安装依赖，并通过安全回归及真实 n8n 检查。
