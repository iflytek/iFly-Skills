# 参与贡献 iFLYTEK Skills

[English](CONTRIBUTING.md) | 简体中文

感谢你一起扩展科大讯飞技能生态！新技能、问题修复、文档以及 n8n 节点改进都非常欢迎。

## 反馈问题与功能建议

- 先搜索[已有 issue](https://github.com/iflytek/iFly-Skills/issues)，没有再按对应的 [issue 模板](https://github.com/iflytek/iFly-Skills/issues/new/choose)新建。
- 报告 bug 时请写明技能名（如 `iflytek-hyper-tts`）、使用的 agent 或运行环境，以及复现步骤。请勿粘贴真实的 API key 或密钥。
- **安全漏洞请勿在公开 issue 中提交**，请按 [SECURITY.md](SECURITY.md) 私下报告。

## 仓库结构

| 路径 | 内容 |
|---|---|
| `skills/<技能名>/` | 每个技能一个目录：`SKILL.md`（frontmatter + 使用说明）、`README.md`、`_meta.json`（slug 与版本）、`scripts/`，以及可选的 `tests/`、`references/`、`assets/` |
| `tests/` | 跨技能共享的离线回归测试 |
| `packages/n8n-nodes-iflytek/` | n8n 社区节点包 `@iflytekopensource/n8n-nodes-iflytek-skills` |
| `skills.sh.json` | skills.sh 上的技能分组 |

## 新增或修改技能

1. 以现有技能（如 `skills/iflytek-hyper-tts/`）为模板。目录名、`SKILL.md` 中的 `name` 和 `_meta.json` 中的 `slug` 必须一致。
2. 凭据统一从 `IFLY_APP_ID`、`IFLY_API_KEY`、`IFLY_API_SECRET` 环境变量读取，切勿提交真实凭据。
3. 修改已发布的技能时，更新 `_meta.json` 中的 `version`。
4. 新技能需加入 `skills.sh.json` 的分组，以及 `README.md`、`README_zh.md` 的技能列表。

## 测试要求

**新功能和 bug 修复都必须附带自动化测试。**

- 测试必须能离线运行：用 mock 代替真实的 HTTP / WebSocket 调用，CI 无需任何凭据。
- 新增技能脚本或重要功能时，在 `skills/<技能名>/tests/` 或 `tests/<技能名>/` 下添加测试。
- 修复 bug 时，尽量补一个“没有修复就会失败”的回归测试。
- 确实无法自动化测试的改动，请在 PR 中说明原因和你做的手动验证。

提交 PR 前请在本地运行检查：

```bash
# Python 技能（与 Python Check 工作流一致）
pip install ruff websocket-client -r tests/iflytek_speed_transcription/requirements.txt
python -m compileall -q skills tests
ruff check --select=E9,F63,F7,F82 skills tests
python -m unittest discover -s tests -p 'test_skill_credentials.py'
python -m unittest discover -s tests/iflytek_speed_transcription -p 'test_*.py'
python -m unittest discover -s tests/iflytek_voiceclone_tts -p 'test_*.py'
python -m unittest discover -s skills/iflytek-hyper-tts/tests -p 'test_*.py'

# n8n 包
cd packages/n8n-nodes-iflytek
npm ci && npm run typecheck && npm test
```

CI 还会用 [skillcheck](https://github.com/Jetty0728/skillcheck) 和 [skill-linter](https://www.npmjs.com/package/skill-linter) 校验每个技能，并审计 n8n 包的生产依赖。

## 提交 Pull Request

1. Fork 仓库，从 `main` 创建分支（如 `feat/new-skill`）。
2. 提交信息遵循 [Conventional Commits](https://www.conventionalcommits.org/zh-hans/)，如 `feat(hyper-tts): support mp3 output`。
3. 每个提交都要签署（`git commit -s`），以确认 [Developer Certificate of Origin](https://developercertificate.org/)。
4. 向 `main` 提 PR，说明改动内容和测试方式，并确保 CI 通过。
5. 首次贡献时，CLA Assistant 机器人会请你签署贡献者许可协议。

## 许可证

提交贡献即表示你同意你的贡献以 [Apache License 2.0](LICENSE) 授权。
