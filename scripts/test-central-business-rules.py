#!/usr/bin/env python3
"""Offline integration fixtures for central rule resolution and workflow wiring."""
import base64
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
from unittest.mock import patch, MagicMock
import urllib.error

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / ".github/scripts/pr-review/central-business-rules.py"
spec = importlib.util.spec_from_file_location("central_rules", HELPER)
rules = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rules)
COMMIT = "a" * 40
CONSUMER = "example/product"
SOURCE = "example/private-rules"


class API:
    def __init__(self):
        self.calls = []
        self.manifest = {
            "schema_version": 1,
            "common": ["common.md"],
            "repositories": {CONSUMER: {"scope": "checkout", "checks": ["preserve pending"]}},
            "excluded": {"example/offline": "offline only"},
        }
        self.text = "owner facts at frozen commit"
        self.private = True
        self.full_name = SOURCE
        self.truncated = False
        self.mode = "100644"

    def files(self):
        return {"repositories.json": json.dumps(self.manifest), "common.md": self.text}

    def __call__(self, path):
        self.calls.append(path)
        if path == "repos/" + SOURCE:
            return {"private": self.private, "full_name": self.full_name}
        if path == "repos/" + SOURCE + "/commits/main":
            return COMMIT
        files = self.files()
        blobs = {hashlib.sha1(text.encode()).hexdigest(): text for text in files.values()}
        if path == "repos/" + SOURCE + "/git/trees/" + COMMIT + "?recursive=1":
            return {"truncated": self.truncated, "tree": [
                {"path": name, "mode": self.mode if name == "common.md" else "100644", "type": "blob", "sha": hashlib.sha1(text.encode()).hexdigest()}
                for name, text in files.items()
            ]}
        prefix = "repos/" + SOURCE + "/git/blobs/"
        if path.startswith(prefix):
            return {"encoding": "base64", "content": base64.b64encode(blobs[path[len(prefix):]].encode()).decode()}
        raise AssertionError("unexpected API path: " + path)


class CentralRulesTests(unittest.TestCase):
    def resolve(self, api, consumer=CONSUMER, private=True, source=SOURCE):
        return rules.resolve(source, "main", consumer, private, api)

    def test_loaded_scope_and_common_facts_use_one_immutable_commit(self):
        api = API()
        metadata, text = self.resolve(api)
        self.assertEqual(metadata["status"], "loaded")
        self.assertEqual(metadata["sha"], COMMIT)
        self.assertIn(api.text, text)
        self.assertIn("preserve pending", text)
        self.assertEqual(sum("/commits/" in path for path in api.calls), 1)
        self.assertTrue(all("/commits/" in path or "main" not in path for path in api.calls))

    def test_public_consumers_do_not_fetch_or_expose_private_facts(self):
        api = API()
        metadata, text = self.resolve(api, private=False)
        self.assertEqual(metadata["status"], "public")
        self.assertEqual(api.calls, [])
        self.assertNotIn(api.text, text)

    def test_disabled_is_explicit_and_does_not_require_credentials(self):
        api = API()
        metadata, text = self.resolve(api, source="")
        self.assertEqual(metadata["status"], "disabled")
        self.assertIn("不声称已检查业务清单", text)
        self.assertEqual(api.calls, [])

    def test_new_repository_gets_common_facts_with_unmapped_disclosure(self):
        api = API()
        metadata, text = self.resolve(api, consumer="example/new-product")
        self.assertEqual(metadata["status"], "unmapped")
        self.assertIn(api.text, text)
        self.assertIn("未登记职责", text)
        self.assertNotIn("preserve pending", text)

    def test_excluded_repository_does_not_receive_business_facts(self):
        api = API()
        metadata, text = self.resolve(api, consumer="example/offline")
        self.assertEqual(metadata["status"], "excluded")
        self.assertNotIn(api.text, text)

    def test_configured_source_errors_never_fall_back_to_generic_review(self):
        for status in (401, 403, 404, 500):
            def failed_api(path):
                raise ValueError("API status " + str(status))
            with self.subTest(status=status), self.assertRaises(ValueError):
                self.resolve(failed_api)

    def test_public_rules_source_and_incomplete_tree_are_rejected(self):
        for field, value in (("private", False), ("full_name", "other/private-rules"), ("truncated", True), ("mode", "120000"), ("mode", "160000")):
            api = API()
            setattr(api, field, value)
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                self.resolve(api)

    def test_cross_org_and_malformed_repositories_are_rejected_before_network(self):
        for source in ("other/private-rules", "../rules", "example/rules;echo", "example/rules/extra"):
            api = API()
            with self.subTest(source=source), self.assertRaises(ValueError):
                self.resolve(api, source=source)
            self.assertEqual(api.calls, [])

    def test_traversal_symlinks_missing_files_and_wrong_file_types_fail(self):
        for path in ("../common.md", "/tmp/common.md", "a/../common.md", "a//common.md", "./common.md", "missing.md", "script.py"):
            api = API()
            api.manifest["common"] = [path]
            with self.subTest(path=path), self.assertRaises(ValueError):
                self.resolve(api)

    def test_manifest_shape_scope_and_duplicate_keys_are_checked(self):
        for patch in (
            {"schema_version": True}, {"schema_version": 2}, {"common": []},
            {"common": ["common.md", "common.md"]},
            {"repositories": {CONSUMER: {"scope": "checkout", "checks": []}}},
            {"repositories": {CONSUMER: {"scope": "checkout", "checks": [42]}}},
            {"excluded": {CONSUMER: "contradictory exclusion"}},
        ):
            api = API()
            api.manifest.update(copy.deepcopy(patch))
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                self.resolve(api)
        with self.assertRaises(ValueError):
            rules.decode_json('{"scope":"first","scope":"second"}')

    def test_cli_writes_three_files_and_never_copies_token(self):
        with tempfile.TemporaryDirectory() as directory:
            env = dict(os.environ, GH_TOKEN="fixture-token-must-never-leak")
            result = subprocess.run([
                "python3", str(HELPER), "--consumer", CONSUMER, "--private", "true", "--output-dir", directory,
            ], env=env, text=True, capture_output=True, check=True)
            files = sorted(path.name for path in Path(directory).iterdir())
            self.assertEqual(files, ["context.md", "metadata.json", "provenance.md"])
            body = result.stdout + result.stderr + "".join(path.read_text() for path in Path(directory).iterdir())
            self.assertNotIn(env["GH_TOKEN"], body)
            self.assertIn("disabled", (Path(directory) / "provenance.md").read_text())

    def test_transport_sha_media_type_and_redirect_protection(self):
        response = MagicMock()
        response.read.return_value = (COMMIT + "\n").encode()
        opener = MagicMock()
        opener.open.return_value.__enter__.return_value = response
        with patch.dict(os.environ, GH_TOKEN="not-for-output"), patch.object(rules.urllib.request, "build_opener", return_value=opener) as build:
            self.assertEqual(rules.github_api("repos/example/private-rules/commits/main"), COMMIT)
            request = opener.open.call_args.args[0]
            self.assertEqual(request.get_header("Accept"), "application/vnd.github.sha")
            self.assertIsInstance(build.call_args.args[0], rules.NoRedirect)
            self.assertIsNone(build.call_args.args[0].redirect_request(request, None, 302, "moved", {}, "https://other.invalid"))

    def test_transport_http_failures_and_timeouts_are_non_success(self):
        for code in (301, 302, 401, 403, 404, 500):
            opener = MagicMock()
            opener.open.side_effect = urllib.error.HTTPError("https://api.github.com/", code, "error", {}, None)
            with self.subTest(code=code), patch.dict(os.environ, GH_TOKEN="not-for-output"), patch.object(rules.urllib.request, "build_opener", return_value=opener):
                with self.assertRaisesRegex(ValueError, "HTTP " + str(code)):
                    rules.github_api("repos/example/private-rules")
        opener.open.side_effect = TimeoutError("timeout")
        with patch.dict(os.environ, GH_TOKEN="not-for-output"), patch.object(rules.urllib.request, "build_opener", return_value=opener):
            with self.assertRaises(TimeoutError):
                rules.github_api("repos/example/private-rules")

    def test_cli_configuration_failure_writes_no_partial_artifact(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([
                "python3", str(HELPER), "--source", "other/private-rules", "--consumer", CONSUMER,
                "--private", "true", "--output-dir", directory,
            ], text=True, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("consumer organization", result.stderr)
            self.assertEqual(list(Path(directory).iterdir()), [])
            args = ["loader", "--consumer", CONSUMER, "--private", "true", "--output-dir", directory]
            with patch("sys.argv", args), patch.object(rules, "resolve", side_effect=TimeoutError()):
                with self.assertRaisesRegex(SystemExit, "TimeoutError"):
                    rules.main()
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_both_reviewers_require_and_consume_the_same_preflight_artifact(self):
        text = (ROOT / ".github/workflows/pr-review.yml").read_text()
        def job(name):
            return re.search(rf"^  {name}:\n.*?(?=^  [a-z_]+:|\Z)", text, re.M | re.S).group()
        for name in ("claude_review", "codex_review"):
            block = job(name)
            self.assertIn("business_context", block.split("runs-on:")[0])
            self.assertIn("name: review-business-context", block)
            self.assertIn('cat "$RUNNER_TEMP/business-context/context.md" >> "$RUNNER_TEMP/review-prompt.txt"', block)
            self.assertNotIn("CR_RULES_REF", block)
            self.assertNotIn("secrets.PAT_TOKEN", block.split("Prepare trusted review inputs", 1)[1])
        self.assertIn("needs.business_context.result == 'success'", job("codex_review"))
        self.assertIn('cat "$RUNNER_TEMP/business-context/provenance.md"', job("publish"))
        self.assertNotIn("business_reference", text)

    def test_rule_changes_cannot_reuse_incremental_cutoff_in_either_model(self):
        workflow = (ROOT / ".github/workflows/pr-review.yml").read_text()
        blocks = re.findall(
            r"          # Central rule updates.*?\n(.*?)\n          cat > .*?review-schema.json",
            workflow, re.S,
        )
        self.assertEqual(len(blocks), 2)
        for number, script in enumerate(blocks):
            for status, expected_mode in (("loaded", "full"), ("unmapped", "full"), ("disabled", "incremental")):
                with self.subTest(model=number, status=status), tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    def git(*args):
                        return subprocess.check_output(["git", *args], cwd=root, text=True).strip()
                    git("init", "-q")
                    git("config", "user.name", "fixture")
                    git("config", "user.email", "fixture@example.invalid")
                    git("config", "commit.gpgsign", "false")
                    (root / "code.txt").write_text("base\n")
                    git("add", ".")
                    git("commit", "-qm", "base")
                    base = git("rev-parse", "HEAD")
                    (root / "code.txt").write_text("base\nfirst change\n")
                    git("commit", "-qam", "first")
                    (root / "code.txt").write_text("base\nfirst change\nsecond change\n")
                    git("commit", "-qam", "second")
                    head = git("rev-parse", "HEAD")
                    temporary = root / "temporary"
                    (temporary / "business-context").mkdir(parents=True)
                    (temporary / "business-context/metadata.json").write_text(json.dumps({"status": status}))
                    (temporary / "review-history.json").write_text('{"mode":"incremental","reason":"old rules"}')
                    (temporary / "pr.diff").write_text("stale incremental diff")
                    (temporary / "pr-commits.txt").write_text("stale commits")
                    script = "\n".join(line[10:] if line.startswith("          ") else line for line in script.splitlines())
                    subprocess.run(["bash", "-euo", "pipefail", "-c", script], cwd=root,
                                   env=dict(os.environ, BASE_SHA=base, HEAD_SHA=head, RUNNER_TEMP=str(temporary)), check=True)
                    self.assertEqual(json.loads((temporary / "review-history.json").read_text())["mode"], expected_mode)
                    if expected_mode == "full":
                        self.assertIn("+first change", (temporary / "pr.diff").read_text())
                        self.assertIn("+second change", (temporary / "pr.diff").read_text())
                        self.assertIn(head, (temporary / "pr-commits.txt").read_text())

    def test_missing_mapping_file_cannot_use_a_local_pr_head_replacement(self):
        api = API()
        original = api.__call__
        def without_manifest(path):
            response = original(path)
            if "/git/trees/" in path:
                response["tree"] = [entry for entry in response["tree"] if entry["path"] != "repositories.json"]
            return response
        with self.assertRaises(ValueError):
            self.resolve(without_manifest)


if __name__ == "__main__":
    unittest.main()
