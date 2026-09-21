"""Offline regression checks for the IFLY_* credential migration.

Run with requests and websocket-client installed:
    python -m unittest discover -s tests -p 'test_skill_credentials.py'
"""

import contextlib
import importlib.util
import io
import os
from pathlib import Path
import sys
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
FIELDS = ("APP_ID", "API_KEY", "API_SECRET")
CASES = (
    ("iflytek-hyper-tts", "xfei_hyper_tts.py", "XFEI", FIELDS),
    ("iflytek-speed-transcription", "transcribe.py", "XFEI", FIELDS),
    ("iflytek-translate", "translate.py", "XFYUN", FIELDS),
    ("iflytek-ocr-invoice", "invoice.py", "XFYUN", FIELDS),
    ("iflytek-video-translate", "xfei_video_translate.py", "XFYUN", FIELDS[1:]),
)


def credentials(prefix):
    return {f"{prefix}_{name}": f"dummy-{prefix}-{name}" for name in FIELDS}


class CredentialMigrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.modules = {}
        for skill, script, _, _ in CASES:
            path = ROOT / "skills" / skill / "scripts" / script
            spec = importlib.util.spec_from_file_location(skill, path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            cls.modules[skill] = module

    def resolve(self, skill, fields, env):
        stdout, stderr = io.StringIO(), io.StringIO()
        with mock.patch.dict(os.environ, env, clear=True):
            before = dict(os.environ)
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                result = self.modules[skill].resolve_credentials(*fields)
            self.assertEqual(dict(os.environ), before)
        self.assertEqual(stdout.getvalue(), "")
        for value in env.values():
            if value:
                self.assertNotIn(value, stderr.getvalue())
        return result, stderr.getvalue()

    def test_one_canonical_set_works_for_all_migrated_skills(self):
        env = credentials("IFLY")
        for skill, _, _, fields in CASES:
            with self.subTest(skill=skill):
                result, warning = self.resolve(skill, fields, env)
                self.assertEqual(result, tuple(env[f"IFLY_{f}"] for f in fields))
                self.assertEqual(warning, "")

    def test_canonical_credentials_override_both_legacy_groups(self):
        env = {**credentials("XFEI"), **credentials("XFYUN"), **credentials("IFLY")}
        for skill, _, _, fields in CASES:
            with self.subTest(skill=skill):
                result, warning = self.resolve(skill, fields, env)
                self.assertEqual(result, tuple(env[f"IFLY_{f}"] for f in fields))
                self.assertEqual(warning, "")

    def test_partial_canonical_group_never_borrows_legacy_fields(self):
        env = {**credentials("XFEI"), **credentials("XFYUN"), "IFLY_APP_ID": "new-app"}
        for skill, _, _, fields in CASES:
            with self.subTest(skill=skill):
                result, warning = self.resolve(skill, fields, env)
                self.assertEqual(result, tuple("new-app" if f == "APP_ID" else "" for f in fields))
                self.assertEqual(warning, "")

    def test_empty_canonical_group_does_not_reactivate_legacy_credentials(self):
        env = {**credentials("XFEI"), **credentials("XFYUN"), "IFLY_API_KEY": ""}
        for skill, _, _, fields in CASES:
            with self.subTest(skill=skill):
                result, warning = self.resolve(skill, fields, env)
                self.assertEqual(result, ("",) * len(fields))
                self.assertEqual(warning, "")

    def test_each_legacy_group_remains_supported_with_one_notice(self):
        for prefix in ("XFEI", "XFYUN"):
            env = credentials(prefix)
            for skill, _, _, fields in CASES:
                with self.subTest(skill=skill, prefix=prefix):
                    result, warning = self.resolve(skill, fields, env)
                    self.assertEqual(result, tuple(env[f"{prefix}_{f}"] for f in fields))
                    self.assertEqual(len(warning.splitlines()), 1)
                    self.assertIn(prefix + "_*", warning)
                    self.assertIn("IFLY_*", warning)

    def test_both_legacy_groups_preserve_each_skills_original_precedence(self):
        env = {**credentials("XFEI"), **credentials("XFYUN")}
        for skill, _, original, fields in CASES:
            with self.subTest(skill=skill):
                result, warning = self.resolve(skill, fields, env)
                self.assertEqual(result, tuple(env[f"{original}_{f}"] for f in fields))
                self.assertIn(original + "_*", warning)

    def test_partial_legacy_group_is_not_completed_from_the_other_group(self):
        for skill, _, original, fields in CASES:
            alternative = "XFYUN" if original == "XFEI" else "XFEI"
            env = {**credentials(alternative), f"{original}_API_KEY": "old-key-only"}
            with self.subTest(skill=skill):
                result, _ = self.resolve(skill, fields, env)
                self.assertEqual(result, tuple("old-key-only" if f == "API_KEY" else "" for f in fields))

    def test_missing_credentials_are_empty_and_silent(self):
        for skill, _, _, fields in CASES:
            with self.subTest(skill=skill):
                result, warning = self.resolve(skill, fields, {})
                self.assertEqual(result, ("",) * len(fields))
                self.assertEqual(warning, "")

    def test_partial_canonical_credentials_fail_at_real_entrypoints_before_network(self):
        env = {**credentials("XFEI"), **credentials("XFYUN"), "IFLY_APP_ID": "new-app"}
        arguments = {
            "iflytek-translate": ["translate.py", "hello"],
            "iflytek-ocr-invoice": ["invoice.py", "unused.png"],
            "iflytek-video-translate": ["xfei_video_translate.py", "--action", "list_tasks"],
        }
        for skill, _, _, _ in CASES:
            module = self.modules[skill]
            if skill == "iflytek-hyper-tts":
                entry = module.get_env_credentials
            elif skill == "iflytek-speed-transcription":
                entry = module.load_config
            else:
                entry = module.main
            stdout, stderr = io.StringIO(), io.StringIO()
            with self.subTest(skill=skill), mock.patch.dict(os.environ, env, clear=True):
                with mock.patch.object(sys, "argv", arguments.get(skill, ["unused"])):
                    with mock.patch("socket.socket", side_effect=AssertionError("Network must not be used")):
                        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                            with self.assertRaises(SystemExit) as error:
                                entry()
            self.assertEqual(error.exception.code, 1)
            self.assertIn("IFLY_API_KEY", stderr.getvalue())
            self.assertEqual(stdout.getvalue(), "")
            for value in env.values():
                self.assertNotIn(value, stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
