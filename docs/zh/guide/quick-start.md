# 快速开始

本指南帮助你在几分钟内从零运行第一个 iFly-Skill。

## 1. 前置条件

- **Python 3**（大多数技能仅依赖标准库，无需 `pip install`）。
- 一个 **科大讯飞开放平台** 账号：<https://www.xfyun.cn/>。

## 2. 获取凭证

1. 登录 [讯飞开放平台控制台](https://console.xfyun.cn/)。
2. 创建一个应用，然后开通你需要的能力（如 *语音合成*、*通用 OCR*、*机器翻译*）。部分能力需按应用单独开通。
3. 在应用页面复制 **APPID**、**APIKey** 和 **APISecret**。

> 每项能力可能有独立的开通状态与配额。若技能返回鉴权错误，请确认对应服务已在该应用下开通。

## 3. 设置环境变量

技能从环境变量读取凭证。设置一次即可在多个技能间复用：

::: code-group

```bash [macOS / Linux]
export XFEI_APP_ID="your_app_id"
export XFEI_API_KEY="your_api_key"
export XFEI_API_SECRET="your_api_secret"
```

```powershell [Windows PowerShell]
$env:XFEI_APP_ID = "your_app_id"
$env:XFEI_API_KEY = "your_api_key"
$env:XFEI_API_SECRET = "your_api_secret"
```

:::

## 4. 获取技能

克隆仓库（或只拷贝你需要的单个技能目录）：

```bash
git clone https://github.com/iflytek/iFly-Skills.git
cd iFly-Skills
```

## 5. 运行技能

每个技能都在自己的 `SKILL.md` 中给出确切命令。通用模式如下：

```bash
cd ifly-hyper-tts          # 选择一个技能目录
cat SKILL.md               # 阅读其 API 文档与使用示例
python3 scripts/...        # 运行其中描述的脚本
```

在 [技能列表](/zh/skills/) 页浏览全部技能，并打开各技能的 `SKILL.md` 查看具体参数与示例。

## 6. 在智能体中使用

由于每个技能都是带触发描述的自包含能力包，因此可以接入支持技能的智能体运行时。`SKILL.md` 的 frontmatter
（`description`、`user_instructions`）告诉智能体何时触发，正文说明如何调用。将智能体指向技能目录，即可直接调用脚本。

## 排障

常见的凭证、配额与环境问题，请见 [FAQ](/zh/faq)。
