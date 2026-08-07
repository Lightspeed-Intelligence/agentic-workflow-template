#!/usr/bin/env python3
"""Offline contract tests for the PR-review workflow's security-critical branches."""

from __future__ import annotations

import base64
import json
import os
import re
import subprocess
import tempfile
import textwrap
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/pr-review.yml"
CALLER = ROOT / ".github/workflows/ci.yml"
PREPARE = ROOT / ".github/scripts/pr-review/prepare-review-history.sh"
README = ROOT / "README.md"
QUESTION_WORKFLOW = ROOT / ".github/workflows/question.yml"


def run(args: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None,
        input_text: str | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
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


def init_repo(repo: Path) -> Path:
    """初始化一个不继承作者签名配置的临时仓库，避免签名交互挂住测试。"""
    repo.mkdir(parents=True, exist_ok=True)
    run(["git", "init", "-q", "-b", "main"], cwd=repo)
    git(repo, "config", "user.name", "Contract Test")
    git(repo, "config", "user.email", "contract@example.invalid")
    git(repo, "config", "commit.gpgsign", "false")
    return repo


def make_repo(root: Path) -> dict[str, str]:
    repo = init_repo(root / "repo")

    tracked = repo / "tracked.txt"
    tracked.write_text("base\n")
    git(repo, "add", "tracked.txt")
    git(repo, "commit", "-q", "-m", "base")
    base = git(repo, "rev-parse", "HEAD")

    tracked.write_text("base\nprevious\n")
    git(repo, "commit", "-qam", "previous")
    previous = git(repo, "rev-parse", "HEAD")

    tracked.write_text("base\nprevious\nhead\n")
    git(repo, "commit", "-qam", "head")
    head = git(repo, "rev-parse", "HEAD")

    git(repo, "switch", "-q", "-c", "divergent", base)
    (repo / "divergent.txt").write_text("divergent\n")
    git(repo, "add", "divergent.txt")
    git(repo, "commit", "-q", "-m", "divergent")
    divergent = git(repo, "rev-parse", "HEAD")
    git(repo, "switch", "-q", "main")
    return {"repo": str(repo), "base": base, "previous": previous, "head": head, "divergent": divergent}


def state(head: str, *, critical: int = 0, important: int = 0, suggestion: int = 1,
          conclusion: str = "COMMENT") -> dict[str, object]:
    return {
        "version": 1,
        "head": head,
        "conclusion": conclusion,
        "critical_count": critical,
        "important_count": important,
        "suggestion_count": suggestion,
        "reviewer": "codex",
        "model": "gpt-5.6-sol",
    }


def marker(value: dict[str, object]) -> str:
    raw = json.dumps(value, separators=(",", ":")).encode()
    return f"<!-- pr-review-state:v1:{base64.b64encode(raw).decode()} -->"


def comment(comment_id: int, states: list[dict[str, object]] | None = None, *,
            login: str = "github-actions[bot]", user_type: str = "Bot",
            app: str | None = "github-actions", malformed: bool = False) -> dict[str, object]:
    body = "prior review\n"
    for item in states or []:
        body += marker(item) + "\n"
    if malformed:
        body += "<!-- pr-review-state:v1:not-base64! -->\n"
    return {
        "id": comment_id,
        "created_at": f"2026-01-{comment_id:02d}T00:00:00Z",
        "body": body,
        "user": {"login": login, "type": user_type},
        "performed_via_github_app": None if app is None else {"slug": app},
    }


def prepare_case(repo_info: dict[str, str], comments: list[dict[str, object]],
                 expected_mode: str, expected_reason: str) -> dict[str, object]:
    repo = Path(repo_info["repo"])
    with tempfile.TemporaryDirectory(prefix="pr-review-contract-") as tmp_name:
        tmp = Path(tmp_name)
        comments_file = tmp / "comments.json"
        comments_file.write_text(json.dumps([comments]))
        runner_temp = tmp / "runner"
        runner_temp.mkdir()
        env = os.environ.copy()
        env.update({
            "BASE_SHA": repo_info["base"],
            "HEAD_SHA": repo_info["head"],
            "RUNNER_TEMP": str(runner_temp),
            "COMMENTS_PAGES_FILE": str(comments_file),
        })
        run(["bash", str(PREPARE)], cwd=repo, env=env)
        history = json.loads((runner_temp / "review-history.json").read_text())
        assert history["mode"] == expected_mode, history
        assert history["reason"] == expected_reason, history
        if expected_mode == "incremental":
            expected_diff = git(repo, "diff", "--find-renames", f"{repo_info['previous']}..{repo_info['head']}")
        else:
            expected_diff = git(repo, "diff", "--find-renames", f"{repo_info['base']}...{repo_info['head']}")
        assert (runner_temp / "pr.diff").read_text().rstrip() == expected_diff.rstrip()
        return history


def test_history_selection(repo_info: dict[str, str]) -> None:
    previous = repo_info["previous"]
    head = repo_info["head"]
    divergent = repo_info["divergent"]

    prepare_case(repo_info, [], "full", "no_trusted_review")
    prepare_case(repo_info, [comment(1, [state(previous)], login="attacker", user_type="User", app=None)],
                 "full", "no_trusted_review")
    prepare_case(repo_info, [comment(1, [state(previous)], app="another-app")],
                 "full", "no_trusted_review")
    prepare_case(repo_info, [comment(1, malformed=True)], "full", "no_trusted_review")

    for suggestions in (1, 3):
        result = prepare_case(repo_info, [comment(1, [state(previous, suggestion=suggestions)])],
                              "incremental", "one_to_three_prior_minor_findings")
        assert result["available"] is True and result["previous"]["state"]["head"] == previous

    for kwargs in (
        {"suggestion": 0, "conclusion": "APPROVE"},
        {"suggestion": 4},
        {"critical": 1, "suggestion": 1, "conclusion": "REQUEST_CHANGES"},
        {"important": 1, "suggestion": 1, "conclusion": "REQUEST_CHANGES"},
    ):
        prepare_case(repo_info, [comment(1, [state(previous, **kwargs)])],
                     "full", "prior_review_not_small_increment")

    prepare_case(repo_info, [comment(1, [state(head)])], "full", "unusable_or_current_cutoff")
    prepare_case(repo_info, [comment(1, [state(divergent)])], "full", "unusable_or_current_cutoff")

    # The final marker in one trusted comment is publisher-controlled and wins over model prose.
    prepare_case(repo_info, [comment(1, [state(previous, suggestion=4), state(previous, suggestion=2)])],
                 "incremental", "one_to_three_prior_minor_findings")
    # Across comments, the newest valid trusted state wins.
    prepare_case(repo_info, [comment(1, [state(previous, suggestion=2)]),
                             comment(2, [state(previous, suggestion=4)])],
                 "full", "prior_review_not_small_increment")


def extract_step_run(workflow: str, name: str) -> str:
    lines = workflow.splitlines()
    target = f"      - name: {name}"
    start = lines.index(target)
    run_line = next(i for i in range(start + 1, len(lines)) if lines[i] == "        run: |")
    body: list[str] = []
    for line in lines[run_line + 1:]:
        if line and len(line) - len(line.lstrip()) <= 8:
            break
        body.append(line[10:] if line else "")
    return "\n".join(body)


def jq_accepts(program: str, value: dict[str, object]) -> bool:
    with tempfile.NamedTemporaryFile("w", suffix=".json") as handle:
        json.dump(value, handle)
        handle.flush()
        return run(["jq", "-e", program, handle.name], check=False).returncode == 0


def test_publisher_gate(workflow: str) -> None:
    body = extract_step_run(workflow, "Validate and publish review comment")
    match = re.search(r"jq -e '\n(.*?)\n\s*' \"\$REVIEW_FILE\"", body, re.S)
    assert match, "publisher jq validator not found"
    program = textwrap.dedent(match.group(1))

    valid = {
        "description": "complete",
        "review_status": "COMPLETE",
        "conclusion": "APPROVE",
        "critical_count": 0,
        "important_count": 0,
        "suggestion_count": 0,
        "comment_body": "## review",
        "reviewer": "codex",
        "model": "gpt-5.6-sol",
    }
    assert jq_accepts(program, valid)

    request_changes = valid | {
        "conclusion": "REQUEST_CHANGES", "important_count": 1,
        "reviewer": "claude", "model": "claude-opus-5",
    }
    assert jq_accepts(program, request_changes)

    invalid_values = [
        valid | {"review_status": "INCOMPLETE"},
        valid | {"suggestion_count": 1},
        valid | {"conclusion": "COMMENT", "important_count": 1},
        valid | {"conclusion": "REQUEST_CHANGES"},
        valid | {"critical_count": -1},
        valid | {"important_count": 0.5},
        valid | {"description": "bad\nsummary"},
        valid | {"comment_body": ""},
        valid | {"model": "claude-opus-5"},
    ]
    for value in invalid_values:
        assert not jq_accepts(program, value), value

    assert ".review_status == \"COMPLETE\"" in workflow
    assert "needs.codex_review.result != 'success'" in workflow
    assert "if: needs.codex_review.result == 'success'" in workflow
    assert "if: needs.claude_review.result == 'success'" in workflow
    assert body.index("STATE_B64=") < body.index("gh pr comment")
    assert "pr-review-state:v1:${STATE_B64}" in body


def test_schemas(workflow: str) -> None:
    raw_schemas = re.findall(r"<<'SCHEMA_EOF'\n(.*?)\n\s*SCHEMA_EOF", workflow, re.S)
    assert len(raw_schemas) == 2
    schemas = [json.loads(textwrap.dedent(raw)) for raw in raw_schemas]
    assert schemas[0] == schemas[1]
    schema = schemas[0]
    assert schema["additionalProperties"] is False
    assert "review_status" in schema["required"]
    assert schema["properties"]["review_status"]["enum"] == ["COMPLETE", "INCOMPLETE"]


def test_extra_allowed_tools(workflow: str) -> None:
    match = re.search(r"grep -Eq '([^']+)' <<< \"\$pattern\"", workflow)
    assert match
    pattern = match.group(1)

    def accepts(value: str) -> bool:
        if "\n" in value or "\r" in value:
            return False
        for item in value.split(","):
            if run(["grep", "-Eq", pattern], input_text=item, check=False).returncode != 0:
                return False
            tool_path = item.removeprefix("Bash(git -C ").split(" ", 1)[0]
            wrapped = f"/{tool_path}/"
            if "/../" in wrapped or "/./" in wrapped or "//" in wrapped:
                return False
        return True

    valid = [
        "Bash(git -C app diff:*)",
        "Bash(git -C app log --oneline:*)",
        "Bash(git -C .hidden/sub show:*)",
        "Bash(git -C app status:*)",
        "Bash(git -C app rev-parse HEAD:*)",
        "Bash(git -C app merge-base HEAD main:*)",
        "Bash(git -C app ls-files:*)",
    ]
    invalid = [
        "Bash(git -C app:*)", "Bash(git -C app push:*)", "Bash(git -C ../app diff:*)",
        "Bash(git -C ./app diff:*)", "Bash(git -C /app diff:*)", "Bash(rm -rf /:*)",
        "Bash(git -C app diff:*)\nBash(rm -rf /:*)", "Bash(git -C app diff;id:*)",
    ]
    assert all(accepts(value) for value in valid)
    assert not any(accepts(value) for value in invalid)


def test_setup_hook_wiring(workflow: str) -> None:
    assert workflow.count("setup_script:\n        description:") == 1
    assert workflow.count('SETUP_SCRIPT: ${{ inputs.setup_script }}') == 2
    assert workflow.count("timeout-minutes: 15") == 2

    steps = re.findall(
        r"      - name: Run repository setup script\n(.*?)\n\n", workflow, re.S,
    )
    assert len(steps) == 2, steps
    for step in steps:
        # 准备脚本不得收到任何 secret，否则它可以经 GITHUB_ENV 把凭据传给持有模型
        # 密钥的后续步骤，破坏「Agent 进程不接收 GitHub/PAT 凭据」这条不变量。
        assert "secrets." not in step, step
        # 脚本本体来自模板固定版本，而非可被 PR 修改的 head 工作树。
        assert ".trusted-policy/.github/scripts/agentic/run-setup-hook.sh" in step
        # 待执行脚本从 base commit 的稀疏检出读取。
        assert '"$GITHUB_WORKSPACE/.trusted-base"' in step
        assert step.rstrip().endswith("review")

    # 位置必须在审查范围冻结之后：diff/commit 列表已写入 RUNNER_TEMP，准备脚本无法
    # 再影响审查哪些改动；同时仍在安装 CLI 之前，它写入的 PATH 对 Agent 有效。
    for cli in ("Install pinned Codex CLI", "Install pinned Claude Code CLI"):
        prepare_at = workflow.index("- name: Prepare trusted review inputs")
        hook_at = workflow.index("- name: Run repository setup script", prepare_at)
        cli_at = workflow.index(f"- name: {cli}")
        assert prepare_at < hook_at < cli_at, cli


def test_setup_hook_behavior() -> None:
    hook = ROOT / ".github/scripts/agentic/run-setup-hook.sh"
    run(["bash", "-n", str(hook)])

    def invoke(script_path: str, *, mode: str = "review", body: str | None = None,
               workspace: Path) -> tuple[int, str]:
        source = workspace / "consumer"
        (source / ".github").mkdir(parents=True, exist_ok=True)
        if body is not None:
            target = source / script_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(body)
        prompt = workspace / "prompt.txt"
        prompt.write_text("base prompt\n")
        runner_temp = workspace / "runner"
        runner_temp.mkdir(exist_ok=True)
        env = os.environ.copy()
        env["RUNNER_TEMP"] = str(runner_temp)
        result = run(
            ["bash", str(hook), script_path, str(source), str(source), str(prompt), mode],
            env=env, check=False,
        )
        return result.returncode, prompt.read_text()

    with tempfile.TemporaryDirectory(prefix="setup-hook-") as tmp_name:
        workspace = Path(tmp_name)
        init_repo(workspace / "consumer")

        # 空输入不执行任何内容，也不改动提示词。
        code, prompt = invoke("", workspace=workspace)
        assert code == 0 and prompt == "base prompt\n"

        # 声明了路径但文件缺失：警告后继续，并向 Agent 披露未执行。
        code, prompt = invoke(".github/missing.sh", workspace=workspace)
        assert code == 0 and "未执行任何准备步骤" in prompt

        # 执行成功：披露环境已就绪。
        code, prompt = invoke(".github/ok.sh", body="exit 0\n", workspace=workspace)
        assert code == 0 and "已成功执行" in prompt

        # 执行失败不终止任务，退出码与日志末尾作为不可信数据披露。
        code, prompt = invoke(
            ".github/bad.sh", body='echo "boom detail"\nexit 7\n', workspace=workspace,
        )
        assert code == 0, prompt
        assert "退出码 7" in prompt and "boom detail" in prompt
        assert "不可信数据" in prompt

        # 路径校验：拒绝绝对路径、路径遍历、命令注入与空格。
        for bad_path in (
            "/etc/passwd", "../escape.sh", ".github/../x.sh", ".github/./x.sh",
            ".github//x.sh", "x.sh;whoami", "$(whoami).sh", "a b.sh", ".github/x.sh\nrm -rf /",
        ):
            code, prompt = invoke(bad_path, workspace=workspace)
            assert code == 1, bad_path
            assert prompt == "base prompt\n", bad_path

        # 非法 mode 是调用方错误。
        code, _ = invoke(".github/ok.sh", mode="bogus", workspace=workspace)
        assert code == 2

    # change 模式在准备脚本之后强制工作树洁净：留下的改动会被 git add -A 静默打包。
    with tempfile.TemporaryDirectory(prefix="setup-hook-change-") as tmp_name:
        workspace = Path(tmp_name)
        source = init_repo(workspace / "consumer")
        (source / ".github").mkdir(parents=True)
        (source / "tracked.txt").write_text("base\n")
        (source / ".gitignore").write_text("build/\n")

        # 三个准备脚本都必须先被跟踪并提交，否则它们自身就是工作树里的干扰噪声。
        cases = {
            "ignored": "mkdir -p build && echo out > build/artifact\n",
            "tracked": "echo polluted >> tracked.txt\n",
            "untracked": "echo new > untracked-artifact.txt\n",
        }
        for name, body in cases.items():
            (source / f".github/setup-{name}.sh").write_text(body)
        git(source, "add", "-A")
        git(source, "commit", "-qm", "base")

        def run_change(name: str) -> int:
            prompt = workspace / "prompt.txt"
            prompt.write_text("base prompt\n")
            runner_temp = workspace / "runner"
            runner_temp.mkdir(exist_ok=True)
            env = os.environ.copy()
            env["RUNNER_TEMP"] = str(runner_temp)
            code = run(
                ["bash", str(hook), f".github/setup-{name}.sh", str(source), str(source),
                 str(prompt), "change"],
                env=env, check=False,
            ).returncode
            # 复位工作树，让每个用例从同一状态开始。
            git(source, "checkout", "-q", "--", ".")
            git(source, "clean", "-qfdx")
            return code

        # 被 gitignore 覆盖的产物是允许的。
        assert run_change("ignored") == 0

        # 改动已跟踪文件会被拒绝，避免准备产物进入候选提交。
        assert run_change("tracked") == 1

        # 产生未被忽略的新文件同样被拒绝。
        assert run_change("untracked") == 1


def test_model_secret_routing(workflow: str, caller: str) -> None:
    pr_caller_match = re.search(r'^  pr-review:\n(.*)\Z', caller, re.MULTILINE | re.DOTALL)
    assert pr_caller_match, "pr-review caller job not found"
    pr_caller = pr_caller_match.group(0)
    for name in ("OPENAI_API_KEY", "OPENAI_BASE_URL"):
        assert re.search(rf'^      {name}:\n        required: false$', workflow, re.MULTILINE)
        assert pr_caller.count(f'{name}: ${{{{ secrets.{name} }}}}') == 1

    assert workflow.count(
        'OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY || secrets.ANTHROPIC_API_KEY }}'
    ) == 1
    assert workflow.count(
        'OPENAI_BASE_URL: ${{ secrets.OPENAI_BASE_URL || secrets.ANTHROPIC_BASE_URL }}'
    ) == 1
    assert 'BASE_URL="${OPENAI_BASE_URL:-https://llm.fantacy.live}"' in workflow
    assert 'OPENAI_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}' not in workflow
    assert 'BASE_URL="${ANTHROPIC_BASE_URL:-https://llm.fantacy.live}"' in workflow


def test_model_names(workflow: str, readme: str, question_workflow: str) -> None:
    assert workflow.count("--model claude-opus-5") == 1
    assert "claude-opus-4-8" not in workflow

    pr_example = re.search(r"// pr-review\n\{.*?\n\}", readme, re.DOTALL)
    question_example = re.search(r"// question\n\{.*?\n\}", readme, re.DOTALL)
    assert pr_example and '"model": "gpt-5.6-sol | claude-opus-5"' in pr_example.group(0)
    assert question_example and '"model": "gpt-5.6-sol | claude-opus-5"' in question_example.group(0)
    assert "model: claude-opus-5" in question_workflow


def test_checkout_credentials(workflow: str, caller: str) -> None:
    checkout_token = 'token: ${{ secrets.PAT_TOKEN || github.token }}'
    assert workflow.count(checkout_token) == 2
    assert workflow.count('token: ${{ github.token }}') == 4
    assert workflow.count('secrets.PAT_TOKEN') == 2
    assert workflow.count('persist-credentials: false') == 6
    assert caller.count('PAT_TOKEN: ${{ secrets.PAT_TOKEN }}') == 4


def test_trusted_policy_source(workflow: str) -> None:
    # 策略与共享运行时来自同一个模板固定版本；该版本号也被 agentic 契约测试逐字节校验。
    refs = re.findall(
        r"repository: Lightspeed-Intelligence/agentic-workflow-template\n\s+ref: ([^\s#]+)",
        workflow,
    )
    assert len(refs) == 2, refs
    assert len(set(refs)) == 1, refs
    policy_sha = refs[0]
    assert re.fullmatch(r"[0-9a-f]{40}", policy_sha), policy_sha
    assert workflow.count("path: .trusted-policy") == 2
    assert workflow.count(".trusted-policy/.claude/skills/pr-review/SKILL.md") == 2
    assert "review-sop.md" not in workflow
    assert "output-format.md" not in workflow
    assert ".trusted-base/.claude/skills/" not in workflow

    # 历史准备脚本与可选的环境准备脚本都来自 base commit 的稀疏检出。
    assert workflow.count(
        "sparse-checkout: |\n"
        "            .github/scripts/pr-review/prepare-review-history.sh\n"
        "            ${{ inputs.setup_script }}\n"
    ) == 2

    for relative in (
        ".claude/skills/pr-review/SKILL.md",
        ".claude/skills/github-comment/SKILL.md",
        ".github/scripts/agentic/run-setup-hook.sh",
    ):
        pinned = run(["git", "show", f"{policy_sha}:{relative}"], cwd=ROOT).stdout
        assert pinned == (ROOT / relative).read_text(), f"policy pin is stale for {relative}"

    policy_files = run([
        "git", "ls-tree", "-r", "--name-only", policy_sha, "--", ".claude/skills/pr-review",
    ], cwd=ROOT).stdout.splitlines()
    assert policy_files == [".claude/skills/pr-review/SKILL.md"]


def test_prepare_script_selection(workflow: str, repo_info: dict[str, str]) -> None:
    pattern = re.compile(
        r'^          prepare_script="\$GITHUB_WORKSPACE/\.trusted-base/'
        r'\.github/scripts/pr-review/prepare-review-history\.sh"\n'
        r'.*?'
        r'^          fi$',
        re.MULTILINE | re.DOTALL,
    )
    blocks = [textwrap.dedent(match.group(0)) for match in pattern.finditer(workflow)]
    assert len(blocks) == 2
    assert all('$GITHUB_WORKSPACE/.github/scripts/' not in block for block in blocks)

    with tempfile.TemporaryDirectory(prefix="pr-review-selection-") as tmp_name:
        workspace = Path(tmp_name)
        trusted = workspace / ".trusted-base/.github/scripts/pr-review/prepare-review-history.sh"
        trusted.parent.mkdir(parents=True)
        trusted.write_text('printf "%s\\n" trusted >> "$TRACE"\n')
        trace = workspace / "trace"
        runner_temp = workspace / "runner"
        runner_temp.mkdir()
        env = os.environ.copy()
        env.update({
            "BASE_SHA": repo_info["base"],
            "HEAD_SHA": repo_info["head"],
            "GITHUB_WORKSPACE": str(workspace),
            "RUNNER_TEMP": str(runner_temp),
            "TRACE": str(trace),
        })

        for block in blocks:
            run(["bash", "-c", block], cwd=Path(repo_info["repo"]), env=env)
        assert trace.read_text().splitlines() == ["trusted", "trusted"]

        trusted.unlink()
        trace.unlink()
        for block in blocks:
            run(["bash", "-c", block], cwd=Path(repo_info["repo"]), env=env)
            history = json.loads((runner_temp / "review-history.json").read_text())
            assert history == {
                "mode": "full",
                "reason": "trusted_preparation_unavailable",
                "available": False,
                "previous": None,
            }
            expected_diff = git(Path(repo_info["repo"]), "diff", "--find-renames",
                                f'{repo_info["base"]}...{repo_info["head"]}')
            assert (runner_temp / "pr.diff").read_text().rstrip() == expected_diff.rstrip()
        assert not trace.exists()


def main() -> None:
    workflow = WORKFLOW.read_text()
    caller = CALLER.read_text()
    readme = README.read_text()
    question_workflow = QUESTION_WORKFLOW.read_text()
    run(["bash", "-n", str(PREPARE)])
    with tempfile.TemporaryDirectory(prefix="pr-review-repo-") as tmp_name:
        repo_info = make_repo(Path(tmp_name))
        test_prepare_script_selection(workflow, repo_info)
        test_history_selection(repo_info)
    test_schemas(workflow)
    test_publisher_gate(workflow)
    test_extra_allowed_tools(workflow)
    test_setup_hook_wiring(workflow)
    test_setup_hook_behavior()
    test_model_secret_routing(workflow, caller)
    test_model_names(workflow, readme, question_workflow)
    test_checkout_credentials(workflow, caller)
    test_trusted_policy_source(workflow)
    print("pr-review contract fixtures passed")


if __name__ == "__main__":
    main()
