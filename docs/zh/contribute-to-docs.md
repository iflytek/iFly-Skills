# 为文档站做贡献

本文档站基于 [VitePress](https://vitepress.dev/) 构建，位于
[`docs/`](https://github.com/iflytek/iFly-Skills/tree/main/docs) 目录。改进文档——修正错别字、
厘清某个页面、补充 FAQ 条目，或把某页翻译成新语言——是参与门槛最低、收益最高的贡献方式之一。

## 本地运行

```bash
cd docs
npm install
npm run docs:dev
```

VitePress 会打印一个本地地址（默认 <http://localhost:5173>）。保存即热更新。

复现生产构建：

```bash
npm run docs:build
npm run docs:preview
```

## 页面位置

```
docs/
├── .vitepress/
│   └── config.mts          # 站点配置：导航、侧边栏、语言
├── index.md                # 英文首页
├── guide/                  # 概览、快速开始
├── skills/                 # 技能列表
├── faq.md                  # FAQ
├── CONTRIBUTING.md
├── contribute-to-docs.md   # 本页
└── zh/                     # 简体中文镜像（相对路径一致）
    ├── index.md
    ├── guide/
    └── ...
```

每个页面底部都有 **「在 GitHub 上编辑此页」** 链接，方便一键开始。

## 国际化 (i18n)

本站采用 VitePress 标准 i18n 布局：**英文为根目录下的默认语言，每种语言在各自文件夹下镜像。**
简体中文已位于 [`docs/zh/`](https://github.com/iflytek/iFly-Skills/tree/main/docs/zh)。

要翻译某个页面，在你的语言目录下创建相同的相对路径。例如，日文版快速开始镜像英文版：

```
docs/guide/quick-start.md      →  docs/ja/guide/quick-start.md
docs/faq.md                    →  docs/ja/faq.md
```

无需一次译完所有内容——单页翻译就是很好的第一份贡献。建议优先翻译 `index`、`guide/quick-start`、`faq`。

### 注册新语言

新语言还需要在
[`docs/.vitepress/config.mts`](https://github.com/iflytek/iFly-Skills/blob/main/docs/.vitepress/config.mts)
中添加一次性的 `locales` 条目。复制现有的 `zh` 块，修改文件夹键名（`ja`、`ko`、`es`、`fr` 等）、
`label`、`lang`、`link`，并翻译 `nav` / `sidebar` 文案。如果你只想翻译 Markdown、由维护者来接好配置，
在 PR 中说明即可，我们会协助。

## 提交

1. Fork 仓库并创建分支。
2. 在 `docs/` 下完成编辑。
3. 本地构建（`npm run docs:build`）以排查错误。
4. 提交 Pull Request。CLA Assistant 机器人会引导你完成 CLA 签署。

感谢你帮助更多开发者用自己的语言使用 iFly-Skills！🙌
