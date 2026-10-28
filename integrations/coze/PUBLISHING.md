# Coze 插件接入与发布

本说明适用于“云侧插件—基于已有服务创建”。由部署方在自己的工作空间导入、调试和发布；需要公共分发时，再为自己维护的服务实例申请商店上架。每个 Skill 对应一个插件，插件内包含该 Skill 的工具。

按“部署服务 → 导出插件文件 → 控制台导入并调试 → 工作空间发布 → 按需申请商店上架”的顺序操作。先完成[服务器与域名部署](./deploy/README.md)。

## 发布前准备

- 稳定的公网 HTTPS 域名、可信完整证书链、开放的端口及可访问的产物地址；插件 URL 导入后不可修改。
- 在[讯飞控制台](https://console.xfyun.cn)为启用能力开通服务及额度。服务器保存讯飞凭证，Coze 只配置该服务器的服务密钥。
- 本站工作空间和对应的 `COZE_<SITE>_BACKEND_API_KEY`；国内、国际分别配置。
- 仅启用已有运行依赖和业务权限的 Skill。GIF 需要隔离渲染环境，视频、训练及指定音色的权限须独立确认。

在仓库根目录检查部署，再导出本站实际地址对应的规范，例如国内站：

```sh
uv run --locked --project integrations/coze --python 3.13 python -B integrations/coze/scripts/check_deployment.py --site cn --all-tools
uv run --locked --project integrations/coze --python 3.13 python -B integrations/coze/scripts/export_openapi.py --site cn
```

使用其他配置文件时，为两个命令均添加 `--env-file <配置文件>`。国际站使用 `--site global`；导出的插件文件分别保存在 `integrations/coze/output/schemas/cn/` 和 `global/`。检查命令不消耗讯飞额度，真实业务结果在下面的工具调试中确认。

## 在控制台导入与配置

1. 登录目标站点，选择自己的工作空间。在国内资源库或国际 Library 中选择“+资源／+ Resource → 插件／Plugin → 导入／Import”。入口以本站实际页面为准。
2. 选择本地 JSON 文件，上传对应的 `output/schemas/<site>/<skill-id>.json`。只创建本次需要启用的 Skill 插件；不要上传使用示例域名的仓库规范。
3. 确认插件名称、描述和 URL。URL 应为自己的 HTTPS 服务地址；使用 `/coze` 等路径前缀时，工具地址也应包含该前缀。
4. 配置 **Service → Service token / API key**：位置选 **Header**，参数名填 **X-API-Key**，值填本站 `COZE_<SITE>_BACKEND_API_KEY` 的原值。密钥只在认证设置中填写。
5. 对照导出的 JSON 文件核对每个工具的输入和输出：POST 的参数放在 Body，GET 的 `job_id`／`text_id` 放在 Query。检查必填项、可选值、数组和可空字段；页面未完整识别时补齐后再调试。

官方说明：[国内导入](https://docs.coze.cn/guides_import.md)、[国际导入](https://docs.coze.com/guides/plugin_import)。一个站点导入成功不代替另一站的验证。

## 调试工具

关闭平台模拟集，使用自己有权限的最小样本。下列操作会实际使用讯飞服务及额度；训练录音需得到说话人授权。规范和[工具说明](./README.md#工具与调用)列出了完整字段。

| Skill | 调试输入／操作顺序 | 应核对的结果 |
| --- | --- | --- |
| 翻译 | `translate`：`text=Hello`、`from_lang=en`、`to_lang=cn` | `dst` 为对应中文译文 |
| 校对 | `check`：包含已知错词的短中文文本 | `checklist` 的位置和建议 |
| 票据识别 | `recognize`：脱敏 PNG／JPEG 的 `image_url` | 名称、金额等与人工标注一致 |
| 超拟人语音 | `list_voices`，再以账号可用 `vcn` 调用 `synthesize` | 音频完整、可下载和播放；列表存在不代表音色授权 |
| 图片／PDF OCR | `recognize_image`；PDF 用 `create_pdf_task → get_pdf_task` | 实际识别内容及产物；检查部分失败状态 |
| 极速转写 | `create_task → get_task` | 文本及分段与音频一致 |
| 图片理解 | `analyze`：图片 URL 和问题 | 回答完整且与图片相符 |
| 视频翻译 | `create_task → get_task`；待字幕确认阶段选择接受上游字幕后 `confirm_transcript → get_task` | 待确认时不提供字幕预览或编辑；核对状态、确认行为及最终视频 |
| 声音复刻 | `get_training_text → create_training → upload_sample → submit_training → get_training → synthesize` | 按返回文本录音；训练成功后使用本站任务的 `res_id`，下载并试听 |
| 合同审核 | `review → get_review` | 必要阶段执行，JSON／Markdown 报告可读，保留人工复核 |
| GIF | `render_html_to_gif → get_render` | GIF 尺寸／动画正确，脚本和外部资源输入被拒绝 |

文本请求可直接在调试页面填写：

```json
{"text":"Hello","from_lang":"en","to_lang":"cn"}
```

异步例子使用公开可下载的脱敏 MP3，替换示例地址：

```json
{"request_id":"transcription-demo-001","audio_url":"https://files.example.com/sample.mp3"}
```

保存返回的 `job_id`，在 `get_task` 的 Query 中填写该值，至少间隔 5 秒查询。HTTP 200 只表示任务快照；`succeeded` 才表示完成。`failed` 查看 `error_code`，`submission_unknown` 核实上游受理状态后再处理，不自动重提。

按[调用预算说明](./README.md#安装与启动)设置工作流节点超时。媒体上传／结果转存可能超过默认超时；国内工作流插件节点可按实际耗时设置到 600 秒，其他调用场景和国际站分别确认。入口代理的等待时间不能延长平台自身的超时，宜先用小样本验证。

同一操作重试须复用原 `request_id` 和完全相同的参数；新业务请求使用新标识。在工作流中只创建一次，随后用有限次数的查询／等待分支轮询，设置总时限和失败出口。声音训练及视频字幕确认是独立阶段，不能跳过前置状态。视频只有 `upstream_status` 为 `waiting_transcript_confirmation` 或 `waiting_manual_intervention_segment` 才可确认字幕；如为 `waiting_manual_intervention_refine`，须在服务商支持的审核入口处理，再继续查询。

同时验证错误服务密钥被拒绝、必填项缺失、无效文件、额度／权限不足、重复提交和过期文件的明确结果。未调试通过的工具不启用、不发布。

## 工作空间发布与更新

全部拟启用工具调试通过后，在插件详情中选择“发布／Publish”，按实际业务填写数据处理信息。在本站智能体或工作流中添加已发布工具，再执行一次代表性调用，核对参数、查询和产物取用。

部署方保存服务地址、站点、插件 ID、代码／插件版本和调试结果，便于后续更新与排查。实际账号记录和业务数据保存在自己的部署环境。

更新服务后，重新导出插件文件，在原插件中更新工具并调试、发布，再检查智能体／工作流的调用。域名或路径前缀改变时，重新创建插件并更新调用引用。回退服务版本时，使用与该版本匹配的插件配置。

## 后续申请插件商店上架

完成工作空间发布后，在本站插件商店或资源库插件页面进入上架入口，补充名称、图标、分类、用途、输入输出示例、使用条件和实际的数据处理说明，再提交审核。两站分别申请，最终结果以平台审核为准。

官方流程：[国内插件商店](https://docs.coze.cn/guides_publish_plugin_to_store.md)、[国际插件商店](https://docs.coze.com/guides/store_plugin)。更新已上架插件时，先发布插件新配置，再按商店流程提交更新。

商店插件固定调用创建时绑定的服务。部署方在 Coze 中配置后端服务密钥，并承担服务器上讯飞账号的调用费用；调用者无需填写讯飞凭证。同一插件的调用者共享已授权能力、用量上限和任务访问范围。

上架前确认服务向哪些用户开放、费用预算、讯飞额度、证书续期和持续运行安排，完成所有拟发布工具的真实调试。密钥只保存在部署配置和 Coze 认证设置中，使用说明应如实描述服务用途及数据处理方式。
