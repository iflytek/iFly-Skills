---
name: 🌸 HER Hack-Astron 出题
about: 面向讯飞语音、OCR、翻译、校对与多模态 Agent Skill 发布赛题
title: 'HER Hack-Astron #出题｜赛题名称'
labels: ['HER Hack-Astron']
---

> **赛题确认：** 提交后由 @FenjuFu 审核并分配正式期号。
>
> **活动标签：** 本模板自动添加 `HER Hack-Astron`。

## 命题背景

- 出题组织：{{组织名称}}
- 能力方向：{{语音识别 / 语音合成 / OCR / 翻译 / 校对 / 多模态}}
- 真实场景与目标人群：{{场景}}
- 讯飞 API / 本地能力依赖：{{能力名称，不填写真实凭据}}

## iFly-Skills 赛题方向

- 将讯飞开放能力封装成可被 Coding Agent / OpenClaw / Astron 调用的 Skill
- 串联语音 → 文本 → 校对 / 翻译 → 语音的多模态工作流
- 面向方言、会议、教育、无障碍、公益资料数字化等场景
- 改进长音频、批量 OCR、字幕、术语表和结构化结果处理
- 增加输入校验、限流重试、错误解释、脱敏和成本提示
- 为现有 Skill 补齐测试、跨平台脚本、示例和中英文文档

## Skill 契约

- 触发描述：{{Agent 何时应使用}}
- 输入 / 输出：{{类型、格式、大小限制}}
- 凭据：{{环境变量名与最小权限}}
- 失败行为：{{超时、配额、内容不支持与降级}}

## 交付与验收

- 独立 Skill 目录及完整 `SKILL.md` frontmatter / 使用说明
- 必要的 `scripts/`、`references/`、`assets/`，避免无关文件
- 使用占位环境变量，绝不提交 AppID、APISecret、Token 或用户数据
- 提供脱敏 Fixture、成功与失败测试、样例调用和期望输出
- Agent 能正确判断何时调用，输出可被后续步骤稳定消费
- 说明资费、数据传输、内容安全和隐私注意事项

## 提交与参与

- PR 标题：`[HER Hack-Astron #期号] Skill 名称 + 讯飞能力`
- PR 附兼容 Agent、测试记录、示例和安全自检
- 女性贡献者占实际 commit / `Co-authored-by:` **≥ 50%**

## 评审重点

- 场景价值与讯飞能力结合深度
- Skill 触发准确性、接口稳定性与可组合性
- 密钥、隐私、配额和失败处理
- 测试、文档与跨 Agent 复用质量

出题 / 合作 / 发奖咨询：ifly_opensource@iflytek.com
