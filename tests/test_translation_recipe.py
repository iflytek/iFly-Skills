"""Offline subprocess checks for both translation/proofreading recipe examples.

Run: python -m unittest discover -s tests -p 'test_translation_recipe.py' -v
Set RECIPE_TEST_ARTIFACT_DIR to choose where evidence is retained. Each run and
case gets a fresh directory; this suite deliberately does not delete fixtures.
Only invented credentials enter the subprocess environment. The real local CLI
modules run with mocked HTTP and blocked socket/urllib transports.
"""

import ast
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[1]
FIELDS = ("APP_ID", "API_KEY", "API_SECRET")
PREFIXES = ("IFLY", "XFYUN", "XFEI", "RECIPE_TRANSLATE", "RECIPE_PROOFREAD")
CREDENTIAL_KEYS = tuple(f"{prefix}_{field}" for prefix in PREFIXES for field in FIELDS)
SCRIPTS = {
    "translate": "skills/iflytek-translate/scripts/translate.py",
    "proofread": "skills/iflytek-text-proofread/scripts/text_proofread.py",
}
SOURCE = "Release 1.2 fixes a display issue.\n"
DRAFT = "1.2 版本修复了显示问题。"
SUGGESTION = {"word": "显示", "suggest": ["界面显示"]}


def credentials(prefix, app):
    return {f"{prefix}_{field}": app if field == "APP_ID" else f"dummy-{app}-{field}"
            for field in FIELDS}


def python_example(relative):
    document = (ROOT / relative).read_text(encoding="utf-8")
    blocks = re.findall(r"```python\r?\n(.*?)\r?\n```", document, re.S)
    if len(blocks) != 1:
        raise AssertionError(f"Expected one Python example in {relative}, got {len(blocks)}")
    return blocks[0]


BOOTSTRAP = textwrap.dedent('''\
    import atexit
    import json
    import os
    from pathlib import Path
    import runpy
    import socket
    import urllib.request

    before = dict(os.environ)
    def record_environment():
        changed = sorted(key for key in set(before) | set(os.environ)
                         if before.get(key) != os.environ.get(key))
        Path("parent-environment.json").write_text(
            json.dumps({"unchanged": not changed, "changedKeys": changed}), encoding="utf-8")
    atexit.register(record_environment)
    def blocked(*args, **kwargs):
        raise AssertionError("Real network is forbidden in recipe fixtures")
    socket.socket = blocked
    urllib.request.urlopen = blocked
    runpy.run_path("run_recipe.py", run_name="__main__")
''')


WRAPPER = textwrap.dedent('''\
    import base64
    import importlib.util
    import json
    import os
    from pathlib import Path
    import socket
    import sys
    import urllib.request

    stage = STAGE
    config = json.loads(Path("fixture-config.json").read_text(encoding="utf-8"))
    mode = config.get(stage, "success")
    def record(event):
        with open("events.jsonl", "a", encoding="utf-8") as stream:
            stream.write(json.dumps(dict(stage=stage, **event), ensure_ascii=False) + "\\n")
    record({"event": "spawn", "argv": sys.argv[1:],
            "credentials": {key: os.environ[key] for key in CREDENTIAL_KEYS if key in os.environ},
            "unrelated": os.environ.get("UNRELATED_SETTING")})
    def blocked(*args, **kwargs):
        record({"event": "blocked-network"})
        raise AssertionError("Real network is forbidden in recipe fixtures")
    socket.socket = blocked
    urllib.request.urlopen = blocked
    if mode == "subprocess-error":
        raise SystemExit(23)
    if mode == "invalid-json":
        print("{invalid-json")
        raise SystemExit(0)
    if mode == "nonobject-json":
        print("[]")
        raise SystemExit(0)
    # A zero-exit nonzero translation code specifically exercises the recipe's
    # independent business-response guard; real API errors are tested separately.
    if stage == "translate" and mode == "zero-exit-business-error":
        print(json.dumps({"code": 7001, "message": "synthetic business failure"}))
        raise SystemExit(0)

    spec = importlib.util.spec_from_file_location("recipe_fixture_skill", SCRIPT_SOURCE)
    skill = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(skill)
    def fake_http(url, body, *args, **kwargs):
        if stage == "translate":
            request = json.loads(body)
            text = base64.b64decode(request["data"]["text"]).decode("utf-8")
            record({"event": "request", "app": request["common"]["app_id"],
                    "text": text, "from": request["business"]["from"],
                    "to": request["business"]["to"]})
            if mode == "api-error":
                return {"code": 7001, "message": "synthetic API error"}
            draft = "" if mode == "empty-draft" else None if mode == "invalid-draft" else DRAFT
            return {"code": 0, "data": {"result": {"from": "en", "to": "cn",
                    "trans_result": {"src": text, "dst": draft}}}}
        text = base64.b64decode(body["payload"]["text"]["text"]).decode("utf-8")
        record({"event": "request", "app": body["header"]["app_id"], "text": text})
        if mode == "api-error":
            return {"header": {"code": 7002, "message": "synthetic API error"}}
        result = {"code": 200, "data": {"checklist": config.get("suggestions", [])}}
        if mode == "business-error":
            result = {"code": 401, "msg": "synthetic business failure"}
        elif mode == "invalid-checklist":
            result["data"]["checklist"] = "not-a-list"
        elif mode == "missing-checklist":
            result["data"] = {}
        encoded = base64.b64encode(json.dumps(result).encode("utf-8")).decode("ascii")
        return {"header": {"code": 0}, "payload": {"output_result": {"text": encoded}}}
    skill._http_post = fake_http
    skill.main()
''')


class TranslationRecipeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.example = python_example("docs/recipes/translate-and-proofread.md")
        selected = os.environ.get("RECIPE_TEST_ARTIFACT_DIR")
        if selected:
            directory = Path(selected).resolve()
            directory.mkdir(parents=True, exist_ok=True)
            cls.artifacts = Path(tempfile.mkdtemp(prefix="recipe-tests-", dir=directory))
        else:
            cls.artifacts = Path(tempfile.mkdtemp(prefix="ifly-recipe-tests-"))
        cls.sequence = 0
        print(f"\nRetained recipe fixtures: {cls.artifacts}", flush=True)

    def run_recipe(self, *, env_changes=None, same_app=False, config=None,
                   source=SOURCE, existing_output=False):
        type(self).sequence += 1
        case = self.artifacts / f"{self.sequence:03d}-{self._testMethodName}"
        case.mkdir()
        (case / "run_recipe.py").write_text(self.example + "\n", encoding="utf-8")
        (case / "bootstrap.py").write_text(BOOTSTRAP, encoding="utf-8")
        (case / "fixture-config.json").write_text(json.dumps(config or {}), encoding="utf-8")
        (case / "release-notes.en.txt").write_text(source, encoding="utf-8")
        for stage, script in SCRIPTS.items():
            target = case / script
            target.parent.mkdir(parents=True)
            preamble = (f"STAGE = {stage!r}\nSCRIPT_SOURCE = {str(ROOT / script)!r}\n"
                        f"CREDENTIAL_KEYS = {CREDENTIAL_KEYS!r}\nDRAFT = {DRAFT!r}\n")
            target.write_text(preamble + WRAPPER, encoding="utf-8")
        if existing_output:
            (case / "recipe-output").mkdir()
            (case / "recipe-output/keep.txt").write_text("keep-existing-output", encoding="utf-8")

        # No ambient service credentials or tokens are copied into a fixture.
        runtime_keys = ("SystemRoot", "SYSTEMROOT", "WINDIR", "LD_LIBRARY_PATH", "DYLD_LIBRARY_PATH")
        env = {key: os.environ[key] for key in runtime_keys if key in os.environ}
        env.update({"PYTHONUTF8": "1", "PYTHONDONTWRITEBYTECODE": "1",
                    "UNRELATED_SETTING": "synthetic-keep"})
        env.update(credentials("RECIPE_TRANSLATE", "dummy-translate-app"))
        env.update(credentials("RECIPE_PROOFREAD", "dummy-translate-app" if same_app else "dummy-proofread-app"))
        for prefix in ("IFLY", "XFYUN", "XFEI"):
            env.update(credentials(prefix, f"dummy-ambient-{prefix}"))
        for key, value in (env_changes or {}).items():
            if value is None:
                env.pop(key, None)
            else:
                env[key] = value
        result = subprocess.run([sys.executable, "-X", "utf8", "bootstrap.py"], cwd=case,
                                env=env, capture_output=True, text=True, encoding="utf-8", timeout=30)
        (case / "stdout.txt").write_text(result.stdout, encoding="utf-8")
        (case / "stderr.txt").write_text(result.stderr, encoding="utf-8")
        (case / "result.json").write_text(json.dumps({"returncode": result.returncode}), encoding="utf-8")
        events = [json.loads(line) for line in (case / "events.jsonl").read_text(encoding="utf-8").splitlines()] if (case / "events.jsonl").exists() else []
        self.assertFalse([event for event in events if event["event"] == "blocked-network"], case)
        environment = json.loads((case / "parent-environment.json").read_text(encoding="utf-8"))
        self.assertTrue(environment["unchanged"], (case, environment))
        return result, case, events

    def assert_success(self, result, case, events, *, same_app=False, count=0, source=SOURCE):
        self.assertEqual(result.returncode, 0, (case, result.stderr))
        requests = [event for event in events if event["event"] == "request"]
        self.assertEqual([event["stage"] for event in requests], ["translate", "proofread"], case)
        self.assertEqual(requests[0]["app"], "dummy-translate-app")
        self.assertEqual(requests[1]["app"], "dummy-translate-app" if same_app else "dummy-proofread-app")
        self.assertEqual((requests[0]["text"], requests[0]["from"], requests[0]["to"]), (source, "en", "cn"))
        self.assertEqual(requests[1]["text"], DRAFT)
        self.assertEqual((case / "recipe-output/source.en.txt").read_text(encoding="utf-8"), source)
        self.assertEqual((case / "recipe-output/draft.zh.txt").read_text(encoding="utf-8"), DRAFT)
        for file in ("translation.json", "proofreading.json"):
            self.assertIsInstance(json.loads((case / "recipe-output" / file).read_text(encoding="utf-8")), dict)
        self.assertIn(f"{count} suggestions", result.stdout)

    def assert_stopped(self, result, case, events, *, expected_stages=()):
        self.assertNotEqual(result.returncode, 0, case)
        self.assertNotIn("suggestions saved", result.stdout)
        self.assertEqual([event["stage"] for event in events if event["event"] == "spawn"], list(expected_stages), case)

    def test_bilingual_examples_are_identical_and_parse(self):
        self.assertEqual(self.example, python_example("docs/zh/recipes/translate-and-proofread.md"))
        ast.parse(self.example)

    def test_distinct_apps_work_despite_ambient_credential_groups(self):
        self.assert_success(*self.run_recipe())

    def test_same_app_can_be_explicitly_used_for_both_stages(self):
        self.assert_success(*self.run_recipe(same_app=True), same_app=True)

    def test_child_environments_expose_only_their_own_complete_canonical_triple(self):
        result, case, events = self.run_recipe()
        self.assert_success(result, case, events)
        spawned = [event for event in events if event["event"] == "spawn"]
        self.assertEqual(len(spawned), 2)
        for event, app in zip(spawned, ("dummy-translate-app", "dummy-proofread-app")):
            self.assertEqual(event["credentials"], credentials("IFLY", app), (case, event))
            self.assertEqual(event["unrelated"], "synthetic-keep")
            self.assertEqual(event["argv"][-1], "--raw")

    def test_each_missing_or_empty_stage_field_stops_before_output_or_children(self):
        for prefix in ("RECIPE_TRANSLATE", "RECIPE_PROOFREAD"):
            for field in FIELDS:
                key = f"{prefix}_{field}"
                for value in (None, ""):
                    with self.subTest(key=key, value=value):
                        result, case, events = self.run_recipe(env_changes={key: value})
                        self.assert_stopped(result, case, events)
                        self.assertFalse((case / "recipe-output").exists(), case)
                        self.assertIn(key, result.stderr)
                        self.assertNotIn("dummy-", result.stderr + result.stdout)

    def test_unicode_source_and_suggestions_are_preserved_without_editing_draft(self):
        source = "Release notes — a café update.\n"
        result, case, events = self.run_recipe(source=source, config={"suggestions": [SUGGESTION]})
        self.assert_success(result, case, events, source=source, count=1)
        saved = json.loads((case / "recipe-output/proofreading.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["data"]["checklist"], [SUGGESTION])
        self.assertEqual((case / "recipe-output/draft.zh.txt").read_text(encoding="utf-8"), DRAFT)

    def test_empty_and_utf8_oversized_sources_stop_before_children(self):
        for source in ("", " \n\t", "a" * 4097, "汉" * 1366):
            with self.subTest(source_bytes=len(source.encode("utf-8"))):
                result, case, events = self.run_recipe(source=source)
                self.assert_stopped(result, case, events)
                self.assertFalse((case / "recipe-output").exists(), case)

    def test_source_at_4096_utf8_bytes_is_accepted(self):
        self.assert_success(*self.run_recipe(source="a" * 4096), source="a" * 4096)

    def test_existing_output_is_preserved_and_no_child_runs(self):
        result, case, events = self.run_recipe(existing_output=True)
        self.assert_stopped(result, case, events)
        self.assertEqual(list((case / "recipe-output").iterdir()), [case / "recipe-output/keep.txt"])
        self.assertEqual((case / "recipe-output/keep.txt").read_text(encoding="utf-8"), "keep-existing-output")

    def test_translation_subprocess_and_api_errors_stop_before_proofreading(self):
        for mode in ("subprocess-error", "api-error", "zero-exit-business-error"):
            with self.subTest(mode=mode):
                result, case, events = self.run_recipe(config={"translate": mode})
                self.assert_stopped(result, case, events, expected_stages=("translate",))
                self.assertTrue((case / "recipe-output/source.en.txt").exists())
                self.assertFalse((case / "recipe-output/draft.zh.txt").exists())

    def test_translation_invalid_json_or_draft_stops_before_proofreading(self):
        for mode in ("invalid-json", "nonobject-json", "empty-draft", "invalid-draft"):
            with self.subTest(mode=mode):
                result, case, events = self.run_recipe(config={"translate": mode})
                self.assert_stopped(result, case, events, expected_stages=("translate",))
                self.assertFalse((case / "recipe-output/draft.zh.txt").exists())

    def test_proofreading_failures_keep_earlier_artifacts_without_false_success(self):
        for mode in ("subprocess-error", "api-error", "business-error", "invalid-json",
                     "nonobject-json", "invalid-checklist", "missing-checklist"):
            with self.subTest(mode=mode):
                result, case, events = self.run_recipe(config={"proofread": mode})
                self.assert_stopped(result, case, events, expected_stages=("translate", "proofread"))
                self.assertEqual((case / "recipe-output/draft.zh.txt").read_text(encoding="utf-8"), DRAFT)
                self.assertEqual(json.loads((case / "recipe-output/translation.json").read_text(encoding="utf-8"))["code"], 0)


if __name__ == "__main__":
    unittest.main()
