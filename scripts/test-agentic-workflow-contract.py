#!/usr/bin/env python3
"""Offline contract tests for Codex-primary agentic workflows."""

from __future__ import annotations

import json
import hashlib
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
    contract_job = job_block(caller, "pr-review-contract")
    assert "fetch-depth: 0" in contract_job
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
    assert WORKFLOWS["update-llmdoc"].read_text().count("submodules: recursive") == 5

    action = ACTION.read_text()
    install_block = action.split("    - name: Install pinned agent CLI without model credentials", 1)[1]
    install_block = install_block.split("    - name: Run pinned agent CLI", 1)[0]
    assert "inputs.api_key" not in install_block
    assert "API_KEY" not in install_block
    assert "--ignore-scripts --no-audit --no-fund" in install_block


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


def test_issue_comment_markers_are_authenticated() -> None:
    sources = [
        WORKFLOWS["question"].read_text(),
        WORKFLOWS["issue-dispatch"].read_text(),
        (SCRIPTS / "publish-change.sh").read_text(),
    ]
    for source in sources:
        assert '.user.login == \\"github-actions[bot]\\"' in source
        assert '.performed_via_github_app.slug == \\"github-actions\\"' in source
    implement = WORKFLOWS["implement"].read_text()
    publisher = (SCRIPTS / "publish-change.sh").read_text()
    assert "COMMENT_TOKEN: ${{ github.token }}" in implement
    assert 'GH_TOKEN="$COMMENT_TOKEN" gh issue comment' in publisher


def test_answer_normalizers() -> None:
    normalizer = SCRIPTS / "normalize-answer-result.sh"
    with tempfile.TemporaryDirectory(prefix="answer-normalizer-") as tmp_name:
        root = Path(tmp_name)

        def accepts(value: dict[str, object], mode: str) -> bool:
            source = root / "source.json"
            output = root / "output.json"
            source.write_text(json.dumps(value))
            return run([
                str(normalizer), str(source), str(output), "codex", "gpt-5.6-sol", mode,
            ], check=False).returncode == 0

        common = {
            "description": "complete",
            "result_status": "COMPLETE",
            "comment_body": "body",
        }
        assert accepts(common, "question")
        assert not accepts(common | {"extra": True}, "question")

        dispatch = common | {
            "issue_type": "bug",
            "severity": "high",
            "cost": "n/a",
            "auto_fix_eligible": False,
        }
        assert accepts(dispatch, "issue-dispatch")
        assert not accepts(common, "issue-dispatch")
        assert not accepts(dispatch | {"auto_fix_eligible": "false"}, "issue-dispatch")
        assert not accepts(dispatch | {"extra": True}, "issue-dispatch")


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

        dirty_no_change_repo = root / "dirty-no-change"
        dirty_no_change_base = init_repo(dirty_no_change_repo)
        (dirty_no_change_repo / "file.txt").write_text("dirty tracked\n")
        dirty_no_change_raw = root / "dirty-no-change.json"
        dirty_no_change_raw.write_text(json.dumps(change_result("NO_CHANGES")))
        assert run([
            str(package), str(dirty_no_change_raw), str(dirty_no_change_repo),
            str(root / "dirty-no-change-artifact"), dirty_no_change_base,
            "codex", "gpt-5.6-sol", "implement",
        ], check=False).returncode != 0

        git(dirty_no_change_repo, "reset", "-q", "--hard", dirty_no_change_base)
        (dirty_no_change_repo / "untracked.txt").write_text("dirty untracked\n")
        assert run([
            str(package), str(dirty_no_change_raw), str(dirty_no_change_repo),
            str(root / "untracked-no-change-artifact"), dirty_no_change_base,
            "codex", "gpt-5.6-sol", "implement",
        ], check=False).returncode != 0

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

        subrepo = root / "subrepo"
        init_repo(subrepo)

        add_repo = root / "gitlink-add"
        add_base = init_repo(add_repo)
        run([
            "git", "-c", "protocol.file.allow=always", "submodule", "add", str(subrepo), "module",
        ], cwd=add_repo)
        add_raw = root / "gitlink-add.json"
        add_raw.write_text(json.dumps(change_result()))
        add_artifact = root / "gitlink-add-artifact"
        run([
            str(package), str(add_raw), str(add_repo), str(add_artifact), add_base,
            "codex", "gpt-5.6-sol", "implement",
        ])
        assert json.loads((add_artifact / "manifest.json").read_text())["outcome"] == "BLOCKED"
        assert not (add_artifact / "candidate.bundle").exists()

        gitlink_repo = root / "gitlink-existing"
        init_repo(gitlink_repo)
        run([
            "git", "-c", "protocol.file.allow=always", "submodule", "add", str(subrepo), "module",
        ], cwd=gitlink_repo)
        git(gitlink_repo, "commit", "-q", "-am", "add gitlink")
        gitlink_base = git(gitlink_repo, "rev-parse", "HEAD")

        git(gitlink_repo / "module", "config", "user.name", "Contract Test")
        git(gitlink_repo / "module", "config", "user.email", "contract@example.invalid")
        git(gitlink_repo / "module", "config", "commit.gpgsign", "false")

        (gitlink_repo / "module/file.txt").write_text("base\ndirty\n")
        dirty_submodule_no_change = root / "dirty-submodule-no-change.json"
        dirty_submodule_no_change.write_text(json.dumps(change_result("NO_CHANGES")))
        assert run([
            str(package), str(dirty_submodule_no_change), str(gitlink_repo),
            str(root / "dirty-submodule-no-change-artifact"), gitlink_base,
            "codex", "gpt-5.6-sol", "implement",
        ], check=False).returncode != 0

        (gitlink_repo / "file.txt").write_text("base\ntop-level\n")
        dirty_raw = root / "gitlink-dirty.json"
        dirty_raw.write_text(json.dumps(change_result()))
        dirty_artifact = root / "gitlink-dirty-artifact"
        run([
            str(package), str(dirty_raw), str(gitlink_repo), str(dirty_artifact), gitlink_base,
            "codex", "gpt-5.6-sol", "implement",
        ])
        assert json.loads((dirty_artifact / "manifest.json").read_text())["outcome"] == "BLOCKED"
        assert not (dirty_artifact / "candidate.bundle").exists()

        git(gitlink_repo, "reset", "-q", "--hard", gitlink_base)
        git(gitlink_repo / "module", "reset", "-q", "--hard")
        (gitlink_repo / "module/file.txt").write_text("base\nchanged\n")
        git(gitlink_repo / "module", "commit", "-qam", "change submodule")
        modify_raw = root / "gitlink-modify.json"
        modify_raw.write_text(json.dumps(change_result()))
        modify_artifact = root / "gitlink-modify-artifact"
        run([
            str(package), str(modify_raw), str(gitlink_repo), str(modify_artifact), gitlink_base,
            "codex", "gpt-5.6-sol", "implement",
        ])
        assert json.loads((modify_artifact / "manifest.json").read_text())["outcome"] == "BLOCKED"

        git(gitlink_repo, "reset", "-q", "--hard", gitlink_base)
        git(gitlink_repo, "rm", "-q", "-f", "module")
        delete_raw = root / "gitlink-delete.json"
        delete_raw.write_text(json.dumps(change_result()))
        delete_artifact = root / "gitlink-delete-artifact"
        run([
            str(package), str(delete_raw), str(gitlink_repo), str(delete_artifact), gitlink_base,
            "codex", "gpt-5.6-sol", "implement",
        ])
        assert json.loads((delete_artifact / "manifest.json").read_text())["outcome"] == "BLOCKED"

        # Bypass the packager to prove the independent validator rejects a deletion bundle too.
        git(gitlink_repo, "reset", "-q", "--hard", gitlink_base)
        if (gitlink_repo / "module").exists():
            run(["git", "rm", "-q", "-f", "module"], cwd=gitlink_repo)
        else:
            git(gitlink_repo, "update-index", "--force-remove", "module")
        git(gitlink_repo, "commit", "-q", "-m", "delete gitlink")
        delete_candidate = git(gitlink_repo, "rev-parse", "HEAD")
        bypass = root / "gitlink-bypass"
        bypass.mkdir()
        run(["git", "bundle", "create", str(bypass / "candidate.bundle"), "HEAD", f"^{gitlink_base}"], cwd=gitlink_repo)
        bundle_sha = hashlib.sha256((bypass / "candidate.bundle").read_bytes()).hexdigest()
        changed_files = git(gitlink_repo, "diff", "--name-only", f"{gitlink_base}..{delete_candidate}").splitlines()
        bypass_result = change_result()
        bypass_result.update({"reviewer": "codex", "model": "gpt-5.6-sol"})
        (bypass / "result.json").write_text(json.dumps(bypass_result))
        (bypass / "manifest.json").write_text(json.dumps({
            "version": 1,
            "outcome": "READY",
            "base_sha": gitlink_base,
            "candidate_sha": delete_candidate,
            "bundle_sha256": bundle_sha,
            "changed_files": changed_files,
            "reviewer": "codex",
            "model": "gpt-5.6-sol",
        }))
        git(gitlink_repo, "reset", "-q", "--hard", gitlink_base)
        validator_rejected = run([
            str(validate), str(bypass), str(gitlink_repo), "implement",
        ], env=env, check=False)
        assert validator_rejected.returncode != 0

        detector = 'substr($1, 2) == "160000" || $2 == "160000"'
        assert detector in package.read_text()
        assert detector in validate.read_text()
        assert detector in (SCRIPTS / "publish-change.sh").read_text()


def test_closes_is_publisher_owned() -> None:
    skill = (ROOT / ".claude/skills/implement/SKILL.md").read_text()
    publisher = (SCRIPTS / "publish-change.sh").read_text()
    assert "publisher 会统一追加一次关闭语句" in skill
    assert "pr_body` 必须包含 `Closes" not in skill
    assert publisher.count("Closes #%s") == 1


def test_runtime_is_immutable() -> None:
    all_refs: set[str] = set()
    for path in WORKFLOWS.values():
        text = path.read_text()
        blocks = re.findall(
            r"repository: Lightspeed-Intelligence/agentic-workflow-template\n"
            r"\s+ref: ([^\s#]+)",
            text,
        )
        assert blocks, path
        assert all(re.fullmatch(r"[0-9a-f]{40}", ref) for ref in blocks), (path, blocks)
        all_refs.update(blocks)
    assert len(all_refs) == 1, all_refs

    runtime_ref = next(iter(all_refs))
    runtime_paths = [
        ".github/actions/run-agent/action.yml",
        ".github/actions/feishu-notify/action.yml",
        *[str(path.relative_to(ROOT)) for path in sorted(SCRIPTS.glob("*.sh"))],
        *[
            str(path.relative_to(ROOT))
            for path in sorted((ROOT / ".claude/skills").glob("*/SKILL.md"))
            if path.parent.name in {
                "answer-question", "bug-analyze", "feature-review", "github-comment",
                "implement", "update-llmdoc",
            }
        ],
    ]
    for relative in runtime_paths:
        pinned = run(["git", "show", f"{runtime_ref}:{relative}"], cwd=ROOT).stdout
        assert pinned == (ROOT / relative).read_text(), f"runtime pin is stale for {relative}"


def main() -> None:
    test_embedded_shell()
    test_final_job_names()
    test_provider_and_permission_boundaries()
    test_fallback_and_artifact_flow()
    test_issue_dispatch_is_analysis_only()
    test_issue_comment_markers_are_authenticated()
    test_answer_normalizers()
    test_untrusted_text_is_not_shell_source()
    test_change_artifact_scripts()
    test_closes_is_publisher_owned()
    test_runtime_is_immutable()
    print("agentic workflow contract fixtures passed")


if __name__ == "__main__":
    main()
