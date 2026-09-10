# 英文更新说明翻译与中文草稿校对

[English](../../recipes/translate-and-proofread.md)

本配方串联两个已有技能：先用机器翻译生成中文草稿，再用公文校对获取修改建议。
原文、译文和服务响应分别保存，发布前由人工核对术语、版本号及建议的修改。

## 准备

在仓库根目录使用 Python 3 运行；两个脚本都只依赖标准库。
将一份简短的英文更新说明保存为 UTF-8 编码的 `release-notes.en.txt`。
机器翻译单次最多接收 4,096 个 UTF-8 字节；较长文本应按段落拆分，分别运行。
源语言明确设为 `en`，目标语言为 `cn`。

在[讯飞控制台](https://console.xfyun.cn/)为对应应用开通**机器翻译**和**公文校对**。
运行时会向这些服务发送原文和中文草稿，并消耗相应额度。

按各技能说明，通过当前终端或密钥管理工具设置凭证：

| 阶段 | 脚本 | 当前脚本读取的环境变量 |
| --- | --- | --- |
| 翻译 | [translate.py](../../../skills/iflytek-translate/scripts/translate.py) | `XFYUN_APP_ID`、`XFYUN_API_KEY`、`XFYUN_API_SECRET` |
| 校对 | [text_proofread.py](../../../skills/iflytek-text-proofread/scripts/text_proofread.py) | `IFLY_APP_ID`、`IFLY_API_KEY`、`IFLY_API_SECRET` |

两组变量的前缀不同，只设置其中一组不能同时配置两个阶段。请分别使用已开通对应服务的
应用凭证，不要将凭证写入更新说明、下方示例或提交到仓库的文件。

## 运行两个阶段

将下面的代码保存为仓库根目录下的 `run_recipe.py`，运行
`python3 -X utf8 run_recipe.py`（Windows：`python -X utf8 run_recipe.py`）。
脚本会创建 `recipe-output/`；目录已存在时会直接停止。再次运行前，请移动旧结果，
或在代码中选择一个新的输出目录。

```python
import json
from pathlib import Path
import subprocess
import sys

source = Path("release-notes.en.txt")
text = source.read_text(encoding="utf-8")
if not text.strip() or len(text.encode("utf-8")) > 4096:
    raise SystemExit("Use a non-empty source of at most 4096 UTF-8 bytes.")

output = Path("recipe-output")
output.mkdir()  # Fail before any API call if results already exist.
(output / "source.en.txt").write_text(text, encoding="utf-8")


def call_skill(script, *args):
    result = subprocess.run(
        [sys.executable, "-X", "utf8", script, *args, "--raw"],
        capture_output=True, text=True, encoding="utf-8", check=True,
    )
    response = json.loads(result.stdout)
    if not isinstance(response, dict):
        raise ValueError("Expected a JSON object from the skill.")
    return response


def save_json(name, response):
    (output / name).write_text(
        json.dumps(response, ensure_ascii=False, indent=2), encoding="utf-8"
    )


translated = call_skill(
    "skills/iflytek-translate/scripts/translate.py",
    "-f", str(output / "source.en.txt"), "-s", "en", "-t", "cn",
)
save_json("translation.json", translated)
if translated.get("code") != 0:
    raise SystemExit("Translation failed; inspect translation.json.")
draft = translated["data"]["result"]["trans_result"]["dst"]
if not isinstance(draft, str) or not draft.strip():
    raise SystemExit("Translation returned an empty or invalid draft.")
draft_path = output / "draft.zh.txt"
draft_path.write_text(draft, encoding="utf-8")

proofread = call_skill(
    "skills/iflytek-text-proofread/scripts/text_proofread.py",
    "-f", str(draft_path),
)
save_json("proofreading.json", proofread)
# This CLI can exit zero for a service error: inspect its JSON too.
if proofread.get("error") or proofread.get("code") != 200:
    raise SystemExit("Proofreading failed; inspect proofreading.json.")
suggestions = proofread["data"]["checklist"]
if not isinstance(suggestions, list):
    raise SystemExit("Proofreading returned an invalid checklist.")
print(f"Draft and {len(suggestions)} suggestions saved in {output.resolve()}")
```

## 核对结果

| 文件 | 核对内容 |
| --- | --- |
| `source.en.txt` | 本次运行使用的完整原文 |
| `translation.json` | 翻译服务响应，包括原文和译文 |
| `draft.zh.txt` | 中文草稿，重点核对名称、数字及原意 |
| `proofreading.json` | `data.checklist` 中的上下文与修改建议 |

空的 checklist 只表示服务没有返回建议，并不证明翻译准确。校对建议不会自动改写草稿；
请将接受的修改应用到另一份最终文档。本配方不保留富文档排版，也不会发布结果。

任一阶段失败后，脚本停止并保留已经生成的产物。目录或草稿存在不代表两个阶段均已成功。
子进程失败时，检查对应阶段的凭证和服务开通状态；业务错误则查看已保存的 JSON。
分享诊断信息前请移除敏感内容。不要将 `run_recipe.py`、输入文件和 `recipe-output/`
提交到仓库。

其他选项见[机器翻译技能](../../../skills/iflytek-translate/SKILL.md)与
[公文校对技能](../../../skills/iflytek-text-proofread/SKILL.md)。
