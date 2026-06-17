# 贡献指南

我们非常欢迎你参与贡献，共同扩展科大讯飞的技能生态！参与方式有多种——按你的时间和兴趣选择即可。

## 参与方式

| 贡献类型 | 第一步 |
|----------|--------|
| **新增技能** | 将一项讯飞能力封装为自包含的技能目录。 |
| **新增用法示例** | 展示用一个或多个现有技能解决的真实任务。 |
| **翻译文档** | 在新的语言目录（`docs/<lang>/`）下镜像一个英文页面。 |
| **扩充 FAQ** | 补充一条你当初上手时希望已经存在的问答。 |
| **报告或修复 Bug** | 提 issue，或直接发 PR 修复。 |

带有 [**good first issue** / **help wanted** 标签的 issue](https://github.com/iflytek/iFly-Skills/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22%2C%22help+wanted%22)
是最容易上手的起点。

## 新增技能

每个技能是一个自包含的顶层目录：

```
ifly-<your-skill>/
├── SKILL.md        # 必需：frontmatter（name、description、metadata）+ API 文档与用法
├── scripts/        # 可运行脚本；优先使用 Python 标准库
└── _meta.json      # 元数据
```

1. 以现有技能（如 [`ifly-translate`](https://github.com/iflytek/iFly-Skills/tree/main/ifly-translate)）为模板。
2. 写清楚 `SKILL.md`：frontmatter 的 `description` 与 `user_instructions` 决定智能体「何时」触发，
   正文记录「如何」调用。
3. **切勿提交凭证。** 从环境读取 `XFEI_APP_ID` / `XFEI_API_KEY` / `XFEI_API_SECRET`，示例中使用占位符。
4. 将你的技能加入 [技能列表](/zh/skills/) 与仓库 README 表格。

## 通用流程

1. Fork 本仓库。
2. 创建特性分支（`git checkout -b feat/new-skill`）。
3. 提交修改（`git commit -m 'feat: add awesome new skill'`）。
4. 推送分支并提交 Pull Request。

### 贡献者许可协议 (CLA)

当你提交 Pull Request 时，**CLA Assistant** 机器人会要求你签署
[贡献者许可协议](https://github.com/iflytek/iFly-Skills/blob/main/CLA.md)。按机器人提示完成即可。
CLA 签名存储在独立的远端签名仓库中，因此你的 PR 不会出现无关的签名变更。

## 改进文档

本站基于 [VitePress](https://vitepress.dev/) 构建。如何本地运行、页面位置、以及如何新增语言，
请见 [为文档站做贡献](/zh/contribute-to-docs)。

## 社区交流

欢迎加入 Astron 开源交流群（企业微信）——二维码见仓库
[README](https://github.com/iflytek/iFly-Skills#-community)。
