# n8n 节点运行与恢复

本指南用于管理已安装的 iFlytek 节点。先完成 [安装与配置](installation.md)，再为每个实际执行进程设置容量、日志和恢复策略；版本及平台条件见 [兼容范围](compatibility.md)。以下 `node dist/shared/...` 命令均在已安装的 `n8n-nodes-iflytek` 包目录运行。

## 运行配置与就绪检查

| 管理员环境变量 | 默认值 / 范围 | 用途 |
| --- | --- | --- |
| `IFLYTEK_PYTHON_EXECUTABLE` | 必填绝对路径 | 独立 venv 的 Python |
| `IFLYTEK_TMP_ROOT` | 系统临时目录 | 生产应配置 worker 独占的本地临时目录 |
| `IFLYTEK_MAX_CONCURRENT_PROCESSES` | 2；1–16 | 同一 Node.js 进程中共享的执行槽位 |
| `IFLYTEK_MAX_QUEUED_REQUESTS` | 32；0–256 | 槽位之外允许等待的调用数，0 表示不等待 |
| `IFLYTEK_TIMEOUT_MS` | 120000；1000–600000 | 单次调用的总时限，包含排队、执行和结果持久化 |
| `IFLYTEK_LOG_EXECUTIONS` | `false`；`true` / `false` | 通过 n8n logger 输出结构化执行元信息 |
| `IFLYTEK_CHROME_EXECUTABLE` / `IFLYTEK_FFMPEG_EXECUTABLE` | 手绘图渲染及 `--full` 预检必填绝对路径 | 浏览器和 ffmpeg |

配置通过进程环境传入，工作流不提供这些字段。并发配置在每个进程第一次调用时固定，修改后重启所有执行进程。一个槽位覆盖输入落盘、子进程执行、产物持久化和临时文件回收；n8n 在获取槽位前读取的 binary 也会消耗内存，需同时限制 n8n 工作流并发和输入规模。

在已安装的 `n8n-nodes-iflytek` 目录执行：

```sh
node dist/shared/preflight.js
# 完整依赖配置增加 --full
node dist/shared/preflight.js --full
```

预检核对 Node.js 24、Python >=3.10、依赖与锁文件的精确版本、运行文件完整性、节点注册、环境配置及本地音色读取。`--full` 同时检查 full Python 依赖、浏览器/ffmpeg 路径和 Playwright Core；实际渲染仍需运行一次模板。预检不调用收费 API，不能验证服务授权。

部署时使用非 root 账号，包与 venv 只读，仅开放 n8n 数据目录和独占临时目录写权限。按工作流规模限制 CPU、内存、PID 和临时磁盘；保持时钟同步和 TLS 校验。容器内也需安装 Python 和所需系统程序，并使用容器内部路径配置运行变量。

## 日志与容量

开启日志后，`iflytek.execution` 的 `started` / `finished` 事件包含 requestId、executionId、nodeType、itemIndex、skill、operation、workerPid、active、queued、queueMs、durationMs；完成事件额外包含状态、受控错误码、可取得的退出码和 binary 字节数。耗时包含清理，排队耗时单独统计。获取输入 binary 或凭证之前的失败仍由 n8n 节点错误记录。日志写入失败不改变业务结果。

日志不包含正文、凭证、签名 URL、原始 stderr、文件路径、用户自定义节点名称或上游原始响应。不要把 requestId/executionId 当作监控指标标签。按 skill/operation/状态汇总成功率和 P95；对 `QUEUE_FULL`、超时、启动失败、清理失败、磁盘压力及持续上游错误报警。当前受控 `UPSTREAM_ERROR` 不细分服务配额与鉴权原因，需在服务控制台核对。

n8n 的执行历史与 binary 存储仍可能持有业务内容，应单独配置访问控制、成功/失败执行保存策略及保留时间。binary 字节数是资源统计，不能替代讯飞实际账单；失败、取消或丢失响应也可能已经产生费用。

总并发上限取决于所有执行进程，4 个 worker × 每进程 2 槽位最多占用 8 个槽位。账户配额须结合 n8n 执行并发和业务入口限流管理，本包不提供跨实例的全局配额服务。

## 临时目录与异常退出

正常成功、失败、取消、超时后会尝试回收该调用的 `ifly-exec-*` 目录；回收失败会报告 `CLEANUP_FAILED`。目录内的 `.ifly-owner.json` 记录所属主机、Node.js PID 和创建时间，供恢复工具判断归属。worker 被操作系统强杀时，需在维护窗口进行离线恢复。

1. 停止该临时目录所属 worker，并确认其 Python、Node、浏览器和 ffmpeg 后代均已停止。不能只依据父 PID 消失就判断子进程已停止。
2. 先预览满 24 小时的残留，再执行删除：

```sh
node dist/shared/tempRecovery.js --root /var/tmp/ifly-worker-a --min-age-hours 24
node dist/shared/tempRecovery.js --root /var/tmp/ifly-worker-a --min-age-hours 24 --apply --workers-stopped
```

工具拒绝根目录、系统临时目录本身和符号链接根路径；仅处理符合本包命名、同主机、所有者已停止且超过年龄门限的目录。活跃/未知 PID、其他主机、缺失或无效标记、近期目录与不相关内容均保留。PID 被其他进程复用时也保留，等待管理员核对。旧版本没有标记的目录需要单独核对，不做自动推断。

`--workers-stopped` 是管理员确认，工具不会停止进程，也不适合在线定时清扫。共享临时目录不能替代 worker 独占目录；容器内主机名和 PID 命名空间变化时，旧标记可能被保守保留。

## URL、训练与渲染边界

PDF/视频/声音样本和回调 URL 仅接受 HTTP(S)、80/443 端口、无用户口令及 fragment 的公开地址。适配层拒绝本地/私网/链路本地/保留地址和混合 DNS 结果，解析失败也拒绝；解析耗时受 Runner 总时限约束。

这些 URL 由上游服务后续抓取，本包不执行用户内容下载，无法固定上游稍后的 DNS 结果或控制其重定向。生产只使用管理员批准、无重定向到内网的内容域名，并落实上游抓取与部署出口控制；不能将一次 DNS 检查称为完整 SSRF 隔离。

声音训练的 token 请求固定使用 `https://avatar-hci.xfyousheng.com/aiauth/v1/token`，训练和上传请求使用 `https://opentrain.xfyousheng.com/voice_train`。包内适配校验 TLS 证书并拒绝重定向；连接或证书错误直接失败，不回退到原 Skill 的 HTTP 入口。声音克隆合成使用 TLS 校验的 WebSocket。

渲染仅接受受限 HTML/SVG/CSS，关闭页面脚本和外部请求，保留 Chromium sandbox。容器、系统资源限制和浏览器补丁管理仍需部署方落实；本包不开放任意脚本执行或自然语言生成图表接口。

## 长任务、重复费用与 worker 恢复

Create/Submit 成功后，先耐久保存业务关联键、输入摘要和上游 task ID，再进入 n8n Wait。Get 仅查询一次；由工作流设置最大轮询次数与截止时间。恢复时使用保存的 task ID 查询，避免再次调用 Create。结束本地等待或进程不代表上游任务取消。

收费操作不要启用 n8n Retry On Fail 自动重试。n8n 队列的故障重投与应用重新执行同样可能重复提交；本包的 requestId、进程内队列和临时目录不提供业务幂等。

需要跨 worker 去重时，可在独立业务 PostgreSQL 中使用 [操作记录示例](operation-ledger.sql)，由自己的工作流通过 Postgres 节点或应用服务执行。此表不会由 iFlytek 节点自动创建、读写；请勿安装到 n8n 内部数据库。

提交前以 `scope + skill + operation + operation_key` 为唯一键原子占位；只有插入成功的调用者提交上游。`scope` 区分业务或应用，`operation_key` 使用重试时不变的业务键。`request_sha256` 应从规范化输入计算，包含影响结果的参数和文件内容摘要，不存正文或密钥。重复键必须核对摘要，相同输入读取已有状态，不同输入拒绝。实际收费请求不能放在可自动重试的数据库事务里。

建议状态为 `pending_submission → submitted → succeeded/failed`。提交后响应丢失、进程中断或凭证/网络错误无法证明未提交时，进入 `submission_unknown` 并人工核对；不要按 TTL 删除占位或重新收费提交。成功取得 task ID 后再写入 submitted；过期 pending 只能转入待核对。原子占位能防止正常并发双提交，不能保证外部 API 与数据库之间恰好一次。

queue mode 使用目标 n8n 版本支持、所有 worker 可访问的 binary 存储。不能使用某台 worker 的 filesystem binary 或本包临时目录承载跨 worker 数据；大文件的对象存储能力及许可需单独核实。主进程和 worker 使用同一个凭证加密密钥、数据库和 Redis 配置。

## 升级与回滚

1. 记录当前包版本，保留可重新安装的制品、配套 Python 依赖和运行镜像；按组织要求核验来源及完整性。备份 n8n 数据、凭证加密密钥及业务提交记录。
2. 暂停新的收费提交，等待运行中调用结束并保存远端任务 ID；核对不确定提交记录。
3. 将目标版本安装到独立实例，运行预检，并检查旧工作流、多 item/表达式、binary、错误分支和 Wait 恢复。确认后将所有 worker 一起切换到同一版本。
4. 回滚恢复旧 npm 制品和配套 Python/系统依赖，不重提已完成或结果不确定的上游任务。恢复 Wait 前先确认节点版本和输出字段兼容。
5. npm 包回滚与 n8n 自身数据库迁移回滚分别处理；升级 n8n 前按官方要求验证数据库备份/恢复，不能用替换节点包代替数据库回滚。

升级和回滚都应在停止相关执行进程后进行，避免工作流执行中混用不同版本。只恢复节点包，不会自动恢复或取消上游任务；应使用已保存的 task ID 继续查询。

## 故障排查

先核对包版本、n8n/Node.js/Python 版本和节点操作。包目录下运行 `node dist/shared/preflight.js`，可先排除解释器、依赖、文件完整性和基本配置问题。

| 现象或错误码 | 检查与处理 |
| --- | --- |
| 搜索不到 iFlytek 节点 | 确认包安装在该实例的社区节点目录、实例允许加载社区节点，并在安装后重启 n8n；检查启动日志 |
| `INVALID_INPUT` | 检查文本、binary 字段、文件格式/大小、URL 和节点参数；同时检查管理员运行变量是否在规定范围内 |
| `AUTH_FAILED` | 确认节点已选中 iFlytek API 凭证且必需字段完整；不要用主机环境变量代替 n8n 凭证 |
| `PYTHON_NOT_FOUND` / `DEPENDENCY_MISSING` | 核对绝对路径、服务账号权限和 venv 锁定依赖；渲染还需浏览器及 ffmpeg |
| `RUNTIME_MISSING` / `INVALID_PROTOCOL` | 确认安装包完整，按已知版本重新安装；持续出现时提供脱敏的 requestId 和版本信息 |
| `UPSTREAM_ERROR` | 在讯飞控制台核对服务、模型、音色或资源授权及额度，并检查时钟和网络；该错误不会细分所有服务端鉴权/配额原因 |
| `QUEUE_FULL` | 检查 n8n 工作流并发、执行积压和账户限额；在资源允许时由管理员调整槽位或等待容量 |
| `PROCESS_TIMEOUT` / `EXECUTION_CANCELLED` | 已结束本地等待；异步任务可能仍在服务端运行。先用已保存 task ID 查询或人工核对，再决定后续操作 |
| `BINARY_IO` / `INVALID_ARTIFACT` / `OUTPUT_LIMIT_EXCEEDED` | 核对输入 binary 名称、产物大小、存储权限和磁盘容量；queue mode 检查共享 binary 配置 |
| `CLEANUP_FAILED` / `PROCESS_TERMINATION_FAILED` | 检查仍在运行的调用及后代进程；在维护窗口处理残留，勿对活动任务直接清扫 |

排查日志只提供受控错误信息。向 [项目 issue](https://github.com/iflytek/iFly-Skills/issues) 反馈时附上最小复现及可获得的 requestId，不公开凭证、签名 URL 或业务内容。
