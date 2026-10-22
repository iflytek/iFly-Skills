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

两个当前 CLI 脚本都读取 `IFLY_APP_ID`、`IFLY_API_KEY` 和 `IFLY_API_SECRET`。
如需分别使用不同应用，通过当前终端或密钥管理工具设置以下**配方专用**变量：

| 阶段 | 脚本 | 本配方读取的环境变量 |
| --- | --- | --- |
| 翻译 | [translate.py](../../../skills/iflytek-translate/scripts/translate.py) | `RECIPE_TRANSLATE_APP_ID`、`RECIPE_TRANSLATE_API_KEY`、`RECIPE_TRANSLATE_API_SECRET` |
| 校对 | [text_proofread.py](../../../skills/iflytek-text-proofread/scripts/text_proofread.py) | `RECIPE_PROOFREAD_APP_ID`、`RECIPE_PROOFREAD_API_KEY`、`RECIPE_PROOFREAD_API_SECRET` |

每个阶段都必须配置完整且非空的三项凭据。如果同一个应用已开通两项服务，可为两组变量
设置同一组三项凭据。配方会在发送请求前检查两组配置，再将本阶段的三项凭据映射为
`IFLY_*` 传给对应 CLI，不修改父进程环境。两个子进程都不会继承环境中原有的
`IFLY_*`、`XFYUN_*`、`XFEI_*` 凭据，也不会收到另一个阶段的配方凭据。
翻译 CLI 的旧前缀回退无法在存在另一应用的 `IFLY_*` 时隔离两个应用。
不要将凭据写入更新说明、下方示例或提交到仓库的文件。

## 运行两个阶段

将下面的代码保存为仓库根目录下的 `run_recipe.py`，运行
`python3 -X utf8 run_recipe.py`（Windows：`python -X utf8 run_recipe.py`）。
脚本会创建 `recipe-output/`；目录已存在时会直接停止。再次运行前，请移动旧结果，
或在代码中选择一个新的输出目录。

```python
import json
import os
from pathlib import Path
import subprocess
import sys

source = Path("release-notes.en.txt")
text = source.read_text(encoding="utf-8")
if not text.strip() or len(text.encode("utf-8")) > 4096:
    raise SystemExit("Use a non-empty source of at most 4096 UTF-8 bytes.")

FIELDS = ("APP_ID", "API_KEY", "API_SECRET")
PREFIXES = ("IFLY", "XFYUN", "XFEI", "RECIPE_TRANSLATE", "RECIPE_PROOFREAD")


def stage_environment(prefix):
    values = {name: os.environ.get(prefix + "_" + name, "") for name in FIELDS}
    missing = [prefix + "_" + name for name, value in values.items() if not value]
    if missing:
        raise SystemExit("Missing recipe credentials: " + ", ".join(missing))
    env = os.environ.copy()
    for group in PREFIXES:
        for name in FIELDS:
            env.pop(group + "_" + name, None)
    env.update({"IFLY_" + name: value for name, value in values.items()})
    return env


translation_env = stage_environment("RECIPE_TRANSLATE")
proofreading_env = stage_environment("RECIPE_PROOFREAD")
output = Path("recipe-output")
output.mkdir()  # Fail before any API call if results already exist.
(output / "source.en.txt").write_text(text, encoding="utf-8")


def call_skill(script, *args, env):
    result = subprocess.run(
        [sys.executable, "-X", "utf8", script, *args, "--raw"],
        capture_output=True, text=True, encoding="utf-8", check=True, env=env,
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
    env=translation_env,
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
    env=proofreading_env,
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
