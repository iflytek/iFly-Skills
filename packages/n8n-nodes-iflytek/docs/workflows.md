# 示例工作流

本包提供三个可导入的 n8n 示例，分别演示文本处理串联、binary 文件输入和 binary 音频输出。可按所需的输入输出方式选择示例，再参照 [节点参考](nodes.md) 组合其他能力。

示例供用户手动导入和修改，节点的安装与运行不依赖导入这些文件。

## 导入与配置

安装本包并配置 Python 后，在 n8n 编辑器中选择 **Import from File**，导入安装包 `workflows/` 中的 JSON。也可从仓库下载对应文件。模板均为手动触发、未激活，未包含凭证绑定、固定执行数据或真实业务文件。

| 示例 | 用途 | 使用前配置 |
| --- | --- | --- |
| [校对与翻译](../workflows/proofread-and-translate.json) | 查看中文校对结果，在明确确认后翻译选定文本 | 为 Proofread、Translate 选择 iFlytek API 凭证；编辑 Text input |
| [票据识别](../workflows/invoice-recognition.json) | 读取图片或 PDF，输出服务字段供人工核对 | 替换 Read invoice 的文件路径或 binary 来源，选择 OCR 凭证 |
| [文本转语音](../workflows/text-to-speech.json) | 将文本合成为可下载的 MP3 | 选择合成凭证和已授权音色，编辑文本 |

校对模板首次运行的 `approvedForTranslation` 为 `false`，因此只执行校对并输出建议。审阅后，将选定文本填入 `approvedText`，把 `approvedForTranslation` 改为 `true`，再执行。第二次运行会再次调用校对，并调用翻译；模板不会自动采纳建议，也不会等待外部审批系统。

票据模板中的 `/files/invoice.jpg` 是占位路径。文件必须在实际执行节点的主机或 worker 内可读，并符合 n8n 文件访问策略。容器中可将自己的文件目录只读挂载到 `/files`；也可以替换读取节点，直接提供 `binary.data`。识别结果保留服务原始结构，金额、日期、税号等字段须核对后再存储。

语音模板的 `synthesize` 会访问讯飞服务，需要权限和额度；结果在 `binary.audio`，可从执行结果下载。`listVoices` 只是静态列表，与此模板的合成操作不同。

三个模板均可能发生服务费用，远端节点没有启用自动重试。先用少量非敏感输入验证。需要存表、通知或公网触发时，由工作流作者明确增加相应节点和权限。
