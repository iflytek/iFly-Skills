# Translate English release notes and proofread the Chinese draft

[中文](../zh/recipes/translate-and-proofread.md)

This recipe combines two existing skills: machine translation produces a Chinese
draft, then document proofreading returns suggestions for that draft. It keeps the
source, draft, and service responses separate so a person can review terminology,
version numbers, and suggested edits before publishing.

## Prepare

Run from the repository root with Python 3. Both scripts use the standard library.
Save a short English release note as UTF-8 `release-notes.en.txt`. The translation
service accepts at most 4,096 UTF-8 bytes per request; split longer notes at paragraph
boundaries and run each part separately. The source language is explicitly `en`,
and the target is `cn`.

Enable **machine translation** and **document proofreading** for the appropriate
applications in the [iFLYTEK console](https://console.xfyun.cn/). These commands send
the source text and translated draft to those services and use their quotas.

Both current CLI scripts read `IFLY_APP_ID`, `IFLY_API_KEY`, and
`IFLY_API_SECRET`. To use different applications without sharing credentials
between stages, configure these **recipe-specific** variables in your shell or
secret manager:

| Stage | Script | Environment variables read by this recipe |
| --- | --- | --- |
| Translate | [translate.py](../../skills/iflytek-translate/scripts/translate.py) | `RECIPE_TRANSLATE_APP_ID`, `RECIPE_TRANSLATE_API_KEY`, `RECIPE_TRANSLATE_API_SECRET` |
| Proofread | [text_proofread.py](../../skills/iflytek-text-proofread/scripts/text_proofread.py) | `RECIPE_PROOFREAD_APP_ID`, `RECIPE_PROOFREAD_API_KEY`, `RECIPE_PROOFREAD_API_SECRET` |

Set a complete, non-empty triple for each stage. If one application has both
services enabled, set the same triple for both stages. The recipe validates both
groups before starting a request, then passes only the selected triple to each
CLI as `IFLY_*`; it does not modify the parent environment. Ambient `IFLY_*`,
`XFYUN_*`, and `XFEI_*` credential values are excluded from both child environments.
The translation CLI's legacy fallback cannot separate two applications when an
unrelated `IFLY_*` group is present. Do not put credentials in the note, the
example below, or committed files.

## Run the two stages

Save the following as `run_recipe.py` in the repository root, then run
`python3 -X utf8 run_recipe.py` (Windows: `python -X utf8 run_recipe.py`).
It creates `recipe-output/` and refuses to reuse an existing directory. Move the
previous results elsewhere or choose a new output directory before another run.

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

## Review the results

| File | What to inspect |
| --- | --- |
| `source.en.txt` | The exact input for this run |
| `translation.json` | Translation response, including source/target text |
| `draft.zh.txt` | Chinese draft; check names, numbers, and intended meaning |
| `proofreading.json` | `data.checklist` entries and their context/suggestions |

An empty checklist means the service returned no suggestions. It does not establish
translation accuracy. Proofreading suggestions do not automatically modify the
draft; apply accepted changes to a separate final document. This workflow does not
preserve rich-document layout or publish the result.

If a stage fails, the script stops and keeps earlier artifacts. A directory or
draft alone is not proof that both stages succeeded. For a subprocess failure,
check that stage's credentials and service activation; for a business error,
inspect the saved JSON. Remove sensitive content before sharing diagnostics. Keep
`run_recipe.py`, input notes, and `recipe-output/` out of your commits.

For more options, see the [translation skill](../../skills/iflytek-translate/SKILL.md)
and [proofreading skill](../../skills/iflytek-text-proofread/SKILL.md).
