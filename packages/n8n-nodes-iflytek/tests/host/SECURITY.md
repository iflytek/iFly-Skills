# 宿主依赖安全维护

本目录提供 CI 兼容检查及 npm registry 安装验证使用的独立 n8n 宿主锁文件和安全回归，保留在源码仓库中。生产宿主由实例管理员独立安装、升级和审计。CI 中的最低版本用例用于检查节点兼容性。

## 依赖版本与安全回归

测试宿主锁定 n8n `2.40.7` 和其声明的 `n8n-workflow 2.40.1`。以下间接依赖通过版本限定的 overrides 使用修复版本，并由 `host-security.test.mjs` 检查实际安装结果及调用行为。

| 来源与影响 | 处理 | 兼容范围与验证 |
| --- | --- | --- |
| `fast-xml-parser`：AWS XML 工具链、Snowflake 的 XML 实体替换可能被绕过；[GHSA-m7jm-9gc2-mpf2](https://github.com/advisories/GHSA-m7jm-9gc2-mpf2) | `4.4.1 → 4.5.7`、`5.2.5 → 5.11.1`，分别保持原主版本 | 所有安装路径验证正常 XML 构建/解析及恶意 DOCTYPE 实体名 |
| `form-data`：Zep SDK 的 multipart 边界可预测；[GHSA-fjxv-7rqg-78g4](https://github.com/advisories/GHSA-fjxv-7rqg-78g4) | `4.0.0 → 4.0.6`，同时包含 header 参数转义修复 | 验证边界不使用 `Math.random`，字段名/文件名不能注入 CRLF header |
| `tar`：SQLite 构建助手、node-gyp、cacache 引入旧版本，解压可能耗尽资源；[GHSA-23hp-3jrh-7fpw](https://github.com/advisories/GHSA-23hp-3jrh-7fpw) | `6.2.1 → 7.5.22`；6.x 无对应修复版，需跨主版本升级 | 宿主 Node 24 满足 tar 7 的 Node ≥18 要求；验证同步提取、流式提取、filter/strip、路径越界防护、解压比例限制、实际 SQLite 助手/驱动及 cache 读写 |
| `expr-eval`：`langchain → @langchain/community 0.0.57 → expr-eval 2.0.2` 存在表达式执行漏洞；[GHSA-q9v2-7m5w-4693](https://github.com/advisories/GHSA-q9v2-7m5w-4693) | 当前宿主依赖树不包含该链，锁文件不包含 `extraneous` 条目 | 验证锁文件、Calculator 的正常运算及其依赖解析路径；Calculator 不能解析到 `expr-eval` |
| `simple-git` / `@simple-git/argv-parser`：n8n 和内置 Git 节点的命令配置、编辑器环境变量防护存在绕过；[GHSA-x6jw-m9v5-85vh](https://github.com/advisories/GHSA-x6jw-m9v5-85vh)、[GHSA-v5rq-49vh-5v5c](https://github.com/advisories/GHSA-v5rq-49vh-5v5c) | `simple-git 3.36.0 → 4.0.2`，其依赖固定为 `argv-parser 2.0.1` | 从两个消费者路径验证初始化、配置、提交、状态、日志、文件读取，以及 trailer 命令配置和 VISUAL 检测；内置 Git 功能限制见下文 |
| `shell-quote`：Daytona SDK 的 shell 参数引用允许注释后的换行恢复命令执行；[GHSA-pqg4-j6r4-53mv](https://github.com/advisories/GHSA-pqg4-j6r4-53mv) | `1.10.0 → 1.12.0` | 从 SDK 依赖路径验证普通参数往返和四种行终止符的拒绝行为 |
| `vm2`：内置 JavaScript 沙箱和 LangChain 节点依赖存在沙箱逃逸、模块解析边界绕过；[GHSA-pq68-rvw4-xp4r](https://github.com/advisories/GHSA-pq68-rvw4-xp4r)、[GHSA-5h3f-q97h-ccvc](https://github.com/advisories/GHSA-5h3f-q97h-ccvc) | `3.11.6 → 3.12.2` | 验证两个消费者的异步执行、受限模块解析、禁止 eval，以及实际 n8n JavaScriptSandbox 包装器；不将有限回归视为对所有沙箱攻击的证明 |
| `handlebars`：n8n、Express 模板引擎和 LangChain 模板依赖存在 AST 类型混淆及自有属性检查绕过，可导致 JavaScript 注入；[GHSA-8r5x-fm3f-whwj](https://github.com/advisories/GHSA-8r5x-fm3f-whwj)、[GHSA-p8wg-vrv2-v86f](https://github.com/advisories/GHSA-p8wg-vrv2-v86f) | `4.7.9 → 4.7.10`；n8n 固定依赖旧版本，因此使用版本限定的覆盖升级 | 从三个消费者路径验证正常模板、HTML 转义、合法 AST、非法 AST 拒绝及构造器访问限制，并验证 n8n 使用的 Express 模板引擎渲染 |

依赖漏洞可传播到 `@getzep/zep-cloud`、`@getzep/zep-js`、`@langchain/community` 和 `@n8n/n8n-nodes-langchain` 等父包。审计中的父包告警应沿具体依赖路径核对，同一底层漏洞可能对应多个受影响包条目。

## 无上游修复版的处理边界

`expr-eval 2.0.2` 的上述漏洞尚无上游修复版。测试宿主使用不依赖该库的 Calculator 实现，安全回归要求依赖树保持这一条件。

旧宿主或自定义集成若仍实际依赖它，应升级/移除对应集成；在完成替换前隔离该实例，禁止不可信表达式和工作流输入，不暴露相关 Webhook。只更换本节点包无法清理已有宿主中的这类依赖。以后测试宿主更新若重新引入它，安全回归和 critical 门禁必须失败，重新核对上游修复后才能发布。

tar 6.x 没有相应安全修复，当前宿主通过经过调用验证的 7.x 覆盖解决。每周复核 n8n 及这几条依赖链；上游直接采用修复版后，重新生成并审计锁文件、验证实际调用，再撤除不再需要的 override。

## Git 跨主版本覆盖的限制

`simple-git` 3.x 没有上述漏洞的修复版。n8n `2.40.7` 的内置 Git 节点通过 `.env()` 设置 `GIT_TERMINAL_PROMPT`、`GIT_ALLOW_PROTOCOL`，但没有声明 4.x 新增的 `allowEnvironment`，因此会被环境变量防护拒绝。回归明确检查这一拒绝行为；正常 Git 库操作使用临时仓库及显式允许的空配置文件完成验证，不代表内置 Git 节点或源代码管理集成已通过验收。

该宿主仅用于本包 11 个 iFLYTEK 节点的隔离验收，不用于 Git 节点或源代码管理流程，也不作为生产 n8n 安装模板。保留新版本的环境变量防护，不通过关闭防护恢复这些功能。生产实例若需要这些功能，应等待或采用已适配安全依赖的 n8n 版本并单独验证；在此之前限制不可信工作流、Git 参数与配置输入，隔离相关实例。n8n `2.42.4` 仍声明 `simple-git 3.36.0`，仅升级至该版本不足以消除此依赖风险。

## 门禁与运行边界

- PR、main 和发布复用相同生产依赖审计：节点包执行 `npm audit --omit=dev --audit-level=high`，阻止 high 和 critical；本测试宿主执行 `npm audit --omit=dev --audit-level=critical`，阻止 critical。审计服务错误均失败。
- 当前宿主从空目录正常执行 `npm ci --omit=dev` 后运行 `npm run test:security`，并检查真实 n8n、11 个节点及模板。跨主版本 override 必须同时通过这些检查。将本目录文件复制到仓库外的独立目录后安装，不在仓库中安装完整宿主。
- 审阅完整 audit 报告中的 high/moderate/low，按具体启用节点和上游修复处理。本目录回归覆盖上表列出的依赖行为；使用其他 n8n 集成时还需验证其运行条件。
- 部署管理员应按环境配置非 root、文件访问权限和 CPU/内存/PID 限制；只允许可信工作流作者，按需限制 Webhook 输入大小、网络出口及存储容量。tar 的解压比例限制不能替代磁盘配额。安装节点包的用户须自行升级并审计其宿主，不能假定获得了本测试宿主的修复。
