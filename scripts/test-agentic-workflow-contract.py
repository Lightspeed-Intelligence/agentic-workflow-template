#!/usr/bin/env python3
"""Offline contract tests for Codex-primary agentic workflows."""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = {
    name: ROOT / f".github/workflows/{name}.yml"
    for name in ("question", "issue-dispatch", "implement", "update-llmdoc")
}
ACTION = ROOT / ".github/actions/run-agent/action.yml"
SCRIPTS = ROOT / ".github/scripts/agentic"
CALLER = ROOT / ".github/workflows/ci.yml"


def run(
    args: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    input_text: str | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        env=env,
        input=input_text,
        text=True,
        capture_output=True,
        check=check,
    )


def git(repo: Path, *args: str) -> str:
    return run(["git", *args], cwd=repo).stdout.strip()


def job_block(workflow: str, job: str) -> str:
    match = re.search(rf"^  {re.escape(job)}:\n(.*?)(?=^  [A-Za-z0-9_-]+:|\Z)", workflow, re.M | re.S)
    assert match, f"job {job} not found"
    return match.group(0)


def embedded_run_blocks(text: str) -> list[str]:
    lines = text.splitlines()
    blocks: list[str] = []
    for index, line in enumerate(lines):
        if line.lstrip() != "run: |":
            continue
        indent = len(line) - len(line.lstrip())
        body: list[str] = []
        for candidate in lines[index + 1 :]:
            candidate_indent = len(candidate) - len(candidate.lstrip())
            if candidate.strip() and candidate_indent <= indent:
                break
            body.append(candidate[indent + 2 :] if candidate else "")
        blocks.append("\n".join(body))
    return blocks


def test_embedded_shell() -> None:
    paths = [*WORKFLOWS.values(), ACTION]
    for path in paths:
        for script in embedded_run_blocks(path.read_text()):
            sanitized = re.sub(r"\$\{\{[^\n]*?\}\}", "EXPRESSION", script)
            result = run(["bash", "-n"], input_text=sanitized, check=False)
            assert result.returncode == 0, f"{path}: {result.stderr}"
    for path in SCRIPTS.glob("*.sh"):
        run(["bash", "-n", str(path)])


def test_final_job_names() -> None:
    expected = {
        "question": "answer",
        "issue-dispatch": "dispatch",
        "implement": "implement",
        "update-llmdoc": "update",
    }
    for workflow_name, final_job in expected.items():
        text = WORKFLOWS[workflow_name].read_text()
        block = job_block(text, final_job)
        assert re.search(rf"^    name: {re.escape(final_job)}$", block, re.M)
        assert "uses: ./runtime/.github/actions/run-agent" not in block


def test_provider_and_permission_boundaries() -> None:
    caller = CALLER.read_text()
    assert "id-token: write" not in caller
    assert caller.count("OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}") == 4
    assert caller.count("OPENAI_BASE_URL: ${{ secrets.OPENAI_BASE_URL }}") == 4

    final_jobs = {
        "question": "answer",
        "issue-dispatch": "dispatch",
        "implement": "implement",
        "update-llmdoc": "update",
    }
    for name, path in WORKFLOWS.items():
        text = path.read_text()
        assert re.search(r"^      OPENAI_API_KEY:\n        required: false$", text, re.M)
        assert re.search(r"^      OPENAI_BASE_URL:\n        required: false$", text, re.M)
        assert text.count("uses: ./runtime/.github/actions/run-agent") == 2
        assert text.count("api_key: ${{ secrets.OPENAI_API_KEY || secrets.ANTHROPIC_API_KEY }}") == 1
        assert text.count("base_url: ${{ secrets.OPENAI_BASE_URL || secrets.ANTHROPIC_BASE_URL }}") == 1
        assert text.count("api_key: ${{ secrets.ANTHROPIC_API_KEY }}") == 1
        assert "github_token:" not in text
        assert "id-token:" not in text

        publisher = job_block(text, final_jobs[name])
        assert "OPENAI_API_KEY" not in publisher
        assert "ANTHROPIC_API_KEY" not in publisher
        for match in re.finditer(r"^  ([A-Za-z0-9_-]+):\n", text, re.M):
            job = match.group(1)
            block = job_block(text, job)
            if "uses: ./runtime/.github/actions/run-agent" in block:
                assert "contents: read" in block
                assert "contents: write" not in block
                assert "issues: write" not in block
                assert "pull-requests: write" not in block

    assert "issues: write" in job_block(WORKFLOWS["question"].read_text(), "answer")
    dispatch = job_block(WORKFLOWS["issue-dispatch"].read_text(), "dispatch")
    assert "issues: write" in dispatch
    assert "contents: write" not in dispatch
    for name, final in (("implement", "implement"), ("update-llmdoc", "update")):
        publisher = job_block(WORKFLOWS[name].read_text(), final)
        assert "contents: write" in publisher
        assert "pull-requests: write" in publisher


def test_fallback_and_artifact_flow() -> None:
    pure = {
        "question": ("codex_answer", "claude_answer"),
        "issue-dispatch": ("codex_analyze", "claude_analyze"),
    }
    for name, (primary, fallback) in pure.items():
        text = WORKFLOWS[name].read_text()
        fallback_block = job_block(text, fallback)
        assert f"needs.{primary}.result != 'success'" in fallback_block
        assert "result_status == \"COMPLETE\"" in text
        assert text.index(f"  {primary}:") < text.index(f"  {fallback}:")
        assert text.index(f"  {fallback}:") < text.index(f"  {'answer' if name == 'question' else 'dispatch'}:")

    for name in ("implement", "update-llmdoc"):
        text = WORKFLOWS[name].read_text()
        fallback = job_block(text, "claude_candidate")
        assert "needs.codex_candidate.result != 'success'" in fallback
        assert "needs.validate_codex.result != 'success'" in fallback
        assert "-validated-codex" in text and "-validated-claude" in text
        publisher = job_block(text, name if name == "implement" else "update")
        assert "validated-candidate" in publisher
        assert "candidate-codex" not in publisher
        assert "candidate-claude" not in publisher
        assert "publish-change.sh" in publisher


def test_issue_dispatch_is_analysis_only() -> None:
    workflow = WORKFLOWS["issue-dispatch"].read_text()
    skill = (ROOT / ".claude/skills/bug-analyze/SKILL.md").read_text()
    assert "contents: write" not in workflow
    assert "pull-requests: write" not in workflow
    assert "auto_fix_eligible" in workflow
    assert "不得编辑文件、提交、push" in skill
    assert "简单 Bug 可直接创建 PR 修复" not in skill
    assert "自动修复分支" not in skill


def test_untrusted_text_is_not_shell_source() -> None:
    forbidden = (
        "${{ github.event.issue.title }}",
        "${{ github.event.issue.body }}",
        "${{ github.event.comment.body }}",
    )
    for path in WORKFLOWS.values():
        for block in embedded_run_blocks(path.read_text()):
            assert not any(value in block for value in forbidden), (path, block)


def init_repo(path: Path) -> str:
    path.mkdir()
    run(["git", "init", "-q", "-b", "main"], cwd=path)
    git(path, "config", "user.name", "Contract Test")
    git(path, "config", "user.email", "contract@example.invalid")
    git(path, "config", "commit.gpgsign", "false")
    (path / "file.txt").write_text("base\n")
    git(path, "add", "file.txt")
    git(path, "commit", "-q", "-m", "base")
    return git(path, "rev-parse", "HEAD")


def change_result(outcome: str = "READY") -> dict[str, object]:
    return {
        "description": "candidate ready",
        "outcome": outcome,
        "commit_message": "fix: contract fixture",
        "pr_title": "Fix contract fixture",
        "pr_body": "Fixture body",
        "comment_body": "Fixture comment",
    }


def test_change_artifact_scripts() -> None:
    package = SCRIPTS / "package-change-result.sh"
    validate = SCRIPTS / "validate-change-artifact.sh"
    with tempfile.TemporaryDirectory(prefix="agentic-contract-") as tmp_name:
        root = Path(tmp_name)
        repo = root / "repo"
        runner_temp = root / "runner"
        runner_temp.mkdir()
        base = init_repo(repo)
        (repo / "file.txt").write_text("base\nchange\n")
        raw = root / "result.json"
        raw.write_text(json.dumps(change_result()))
        artifact = root / "artifact"
        run([
            str(package), str(raw), str(repo), str(artifact), base,
            "codex", "gpt-5.6-sol", "implement",
        ])
        git(repo, "reset", "-q", "--hard", base)
        env = os.environ.copy()
        env["RUNNER_TEMP"] = str(runner_temp)
        run([str(validate), str(artifact), str(repo), "implement"], env=env)
        manifest = json.loads((artifact / "manifest.json").read_text())
        assert manifest["base_sha"] == base
        assert manifest["outcome"] == "READY"
        assert manifest["changed_files"] == ["file.txt"]

        no_change_repo = root / "no-change"
        no_change_base = init_repo(no_change_repo)
        no_change_raw = root / "no-change.json"
        no_change_raw.write_text(json.dumps(change_result("NO_CHANGES")))
        no_change_artifact = root / "no-change-artifact"
        run([
            str(package), str(no_change_raw), str(no_change_repo), str(no_change_artifact),
            no_change_base, "claude", "fable-5", "implement",
        ])
        run([str(validate), str(no_change_artifact), str(no_change_repo), "implement"], env=env)
        assert not (no_change_artifact / "candidate.bundle").exists()

        docs_repo = root / "docs-repo"
        docs_base = init_repo(docs_repo)
        (docs_repo / "file.txt").write_text("invalid docs update\n")
        docs_raw = root / "docs.json"
        docs_raw.write_text(json.dumps(change_result()))
        rejected = run([
            str(package), str(docs_raw), str(docs_repo), str(root / "docs-artifact"),
            docs_base, "codex", "gpt-5.6-sol", "update-llmdoc",
        ], check=False)
        assert rejected.returncode != 0


def test_runtime_is_immutable() -> None:
    for path in WORKFLOWS.values():
        text = path.read_text()
        blocks = re.findall(
            r"repository: Lightspeed-Intelligence/agentic-workflow-template\n"
            r"\s+ref: ([^\s#]+)",
            text,
        )
        assert blocks, path
        assert all(re.fullmatch(r"[0-9a-f]{40}", ref) for ref in blocks), (path, blocks)


def main() -> None:
    test_embedded_shell()
    test_final_job_names()
    test_provider_and_permission_boundaries()
    test_fallback_and_artifact_flow()
    test_issue_dispatch_is_analysis_only()
    test_untrusted_text_is_not_shell_source()
    test_change_artifact_scripts()
    test_runtime_is_immutable()
    print("agentic workflow contract fixtures passed")


if __name__ == "__main__":
    main()
