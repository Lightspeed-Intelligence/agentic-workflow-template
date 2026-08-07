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


def job_block(workflow: str, job: str) -> str:
    match = re.search(rf"^  {re.escape(job)}:\n(.*?)(?=^  [A-Za-z0-9_-]+:|\Z)", workflow, re.M | re.S)
    assert match, f"job {job} not found"
    return match.group(0)


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

    # 必须捕获到下一个步骤（或 job）边界，而不是到第一个空行。YAML 块标量允许内部空行，
    # 用 `\n\n` 截断会让空行之后的内容逃过本函数的全部断言，例如追加一行把 secret 写入
    # GITHUB_ENV，或再插一次从 head 工作树读取脚本的 hook 调用。
    steps = re.findall(
        r"      - name: Run repository setup script\n(.*?)(?=^      - name: |^  [A-Za-z0-9_-]+:|\Z)",
        workflow, re.S | re.M,
    )
    assert len(steps) == 2, steps

    # 步骤级切片看不到 job 级或 workflow 级 env：那里放一个 secret 同样会被 hook 步骤继承。
    # 当前两处都没有 env，直接断言其不存在，比逐个排除更简单也更严格。
    assert not re.search(r"^env:", workflow, re.M), "workflow 级 env 会被 hook 步骤继承"
    for job in ("codex_review", "claude_review"):
        block = job_block(workflow, job)
        header = block.split("    steps:", 1)[0]
        assert not re.search(r"^    env:", header, re.M), f"{job} 不得声明 job 级 env"
    for step in steps:
        # 准备脚本不得收到任何 secret，否则它可以经 GITHUB_ENV 把凭据传给持有模型
        # 密钥的后续步骤，破坏「Agent 进程不接收 GitHub/PAT 凭据」这条不变量。
        assert "secrets." not in step, step
        # 断言完整的参数序列，而不是逐个检查「某字面量出现过」。只查存在性时，把
        # SOURCE_DIR 与 REPO_DIR 换位仍能通过——两个字面量都还在，但准备脚本会改从
        # 可被 PR 修改的 head 工作树读取，正是本扩展点的信任基础所要防的。
        assert re.search(
            r'bash "\$GITHUB_WORKSPACE/\.trusted-policy/\.github/scripts/agentic/'
            r'run-setup-hook\.sh" \\\n'
            r'\s+"\$SETUP_SCRIPT" \\\n'
            r'\s+"\$GITHUB_WORKSPACE/\.trusted-base" \\\n'
            r'\s+"\$GITHUB_WORKSPACE" \\\n'
            r'\s+"\$RUNNER_TEMP/review-prompt\.txt" \\\n'
            r'\s+review\s*$',
            step,
        ), step
        # 步骤级兜底必须挂在这个步骤上，而不是文件里任意位置。
        assert "timeout-minutes: 15" in step, step

    # 脚本必须出现在可信策略检出的 sparse-checkout 列表里。少写或写错这一行时 CI 仍然
    # 通过，但运行时找不到脚本：hook 步骤没有 continue-on-error，Agent job 会直接失败，
    # 非致命降级设计覆盖不到这种情况，fallback 也会以同样方式失败。
    assert workflow.count(
        "sparse-checkout: |\n"
        "            .claude/skills/pr-review\n"
        "            .claude/skills/github-comment\n"
        "            .github/scripts/agentic/run-setup-hook.sh\n"
    ) == 2

    # 位置必须在审查范围冻结之后：diff/commit 列表已写入 RUNNER_TEMP，准备脚本无法
    # 再影响审查哪些改动；同时仍在安装 CLI 之前，它写入的 PATH 对 Agent 有效。
    # 必须逐 job 切片：在整份 workflow 文本上用 str.index 只会命中 codex job 那一处，
    # claude fallback 的顺序实际不会被检查。
    for job, cli in (
        ("codex_review", "Install pinned Codex CLI"),
        ("claude_review", "Install pinned Claude Code CLI"),
    ):
        block = job_block(workflow, job)
        # 每个位置都独立从块首查找。若用 index(..., prepare_at) 定位 hook，搜索起点就已经
        # 排除了「hook 在 Prepare 之前」这种要防的错误，断言将永远不会失败。
        prepare_at = block.index("- name: Prepare trusted review inputs")
        hook_at = block.index("- name: Run repository setup script")
        cli_at = block.index(f"- name: {cli}")
        assert prepare_at < hook_at < cli_at, (job, cli)


def test_setup_hook_behavior() -> None:
    hook = ROOT / ".github/scripts/agentic/run-setup-hook.sh"
    run(["bash", "-n", str(hook)])

    def invoke(script_path: str, *, mode: str = "review", body: str | None = None,
               workspace: Path, extra_path: str | None = None) -> tuple[int, str]:
        source = workspace / "consumer"
        (source / ".github").mkdir(parents=True, exist_ok=True)
        if body is not None:
            target = source / script_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(body)
            # 提交脚本本身：洁净检查现在覆盖 review 模式，未跟踪的脚本文件会被算作
            # 准备脚本弄脏了工作树。真实用法中脚本来自可信 checkout，本就是已跟踪内容。
            git(source, "add", "-A")
            git(source, "commit", "-qm", f"add {script_path}")
        prompt = workspace / "prompt.txt"
        prompt.write_text("base prompt\n")
        runner_temp = workspace / "runner"
        runner_temp.mkdir(exist_ok=True)
        env = os.environ.copy()
        env["RUNNER_TEMP"] = str(runner_temp)
        if extra_path:
            env["PATH"] = f"{extra_path}:{env['PATH']}"
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

        # 提前返回的分支不得执行任何 git 命令。基线采集本身有副作用与失败模式：消费仓库
        # 若存在 .gitmodules 缺条目的 gitlink，submodule foreach 会以 128 退出，把「本仓库
        # 没声明 setup_script」变成 job 失败。用假 git 记录调用，而不是只看退出码——只看
        # 退出码时，把采集移回脚本顶部仍能通过。
        shim_dir = workspace / "shim"
        shim_dir.mkdir(exist_ok=True)
        calls = workspace / "git-calls.txt"
        shim = shim_dir / "git"
        shim.write_text(f'#!/usr/bin/env bash\nprintf "%s\\n" "$*" >> "{calls}"\nexit 0\n')
        shim.chmod(0o755)
        for script_path, body in (
            ("", None),                       # 未声明
            (".github/missing.sh", None),     # 声明但可信来源中不存在
            ("/etc/passwd", None),            # 路径校验拒绝
        ):
            calls.write_text("")
            invoke(script_path, body=body, workspace=workspace, extra_path=str(shim_dir))
            assert calls.read_text() == "", (script_path, calls.read_text())
        # 对照：真正执行脚本时必须调用 git，否则上面的断言会因为「根本没用 git」而空洞。
        calls.write_text("")
        invoke(".github/probe.sh", body="exit 0\n", workspace=workspace,
               extra_path=str(shim_dir))
        assert "status" in calls.read_text(), calls.read_text()

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
            # 只含换行的用例：上面那个值同时含 `/` 与空格，会被字符集分支拦下，因此
            # 无法单独证明换行拒绝分支存在。这两个值只违反换行规则。
            "setup.sh\nsetup.sh", "setup.sh\rsetup.sh",
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

        # 由调用方登记「workflow 自己创建的目录」。复位会用 git clean 删掉未跟踪内容，
        # 因此每次运行前都要重新预置，否则只有第一次调用能看到它们，后续用例（包括
        # review 模式那一支）实际上没有被守护。
        workflow_owned: dict[str, str] = {}

        def run_mode(name: str, mode: str) -> int:
            for path, content in workflow_owned.items():
                target = source / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content)
            # prompt 与 RUNNER_TEMP 必须落在仓库之外：真实 runner 上它们在 $RUNNER_TEMP
            # 里，放进仓库会让洁净检查把测试脚手架本身算作准备脚本的产物。
            scratch = workspace / "scratch"
            scratch.mkdir(exist_ok=True)
            prompt = scratch / "prompt.txt"
            prompt.write_text("base prompt\n")
            env = os.environ.copy()
            env["RUNNER_TEMP"] = str(scratch)
            code = run(
                ["bash", str(hook), f".github/setup-{name}.sh", str(source), str(source),
                 str(prompt), mode],
                env=env, check=False,
            ).returncode
            # 复位工作树，让每个用例从同一状态开始。
            git(source, "checkout", "-q", "--", ".")
            git(source, "clean", "-qfd")
            return code

        # 两种模式行为一致。review 模式同样不能放过残留：issue-dispatch 在 Agent 之后
        # 断言工作树完全干净，残留会让主链路与 fallback 在同一处失败；question 与
        # pr-review 则会让 Agent 基于已偏离固定 SHA 的 checkout 工作。
        for mode in ("change", "review"):
            # 被 gitignore 覆盖的产物是允许的。
            assert run_mode("ignored", mode) == 0, mode
            # 改动已跟踪文件会被拒绝。
            assert run_mode("tracked", mode) == 1, mode
            # 产生未被忽略的新文件同样被拒绝。
            assert run_mode("untracked", mode) == 1, mode

        # 回归 issue #31：pr-review 把 .trusted-base / .trusted-policy checkout 到
        # $GITHUB_WORKSPACE，又以同一目录作为 repo_dir。这些目录在准备脚本运行前就存在，
        # 属于 workflow 实现细节，不得被算作准备脚本的产物——否则只要声明 setup_script
        # 就必然失败，且报错指向错误的原因。
        workflow_owned.update({
            ".trusted-base/.github/x": "workflow-owned\n",
            ".trusted-policy/.claude/marker": "workflow-owned\n",
        })
        # 真实布局里 actions/checkout 带 path: 会在这些目录内留下嵌套 .git，porcelain 因此
        # 把整个目录折叠成一行。fixture 必须复现这一点，否则测到的是比真实情况更宽松的形态。
        for trusted in (".trusted-base", ".trusted-policy"):
            nested = source / trusted
            nested.mkdir(parents=True, exist_ok=True)
            if not (nested / ".git").exists():
                run(["git", "init", "-q"], cwd=nested)
        folded = git(source, "status", "--porcelain", "--untracked-files=all")
        assert "?? .trusted-base/\n" in folded + "\n", folded
        assert "?? .trusted-policy/\n" in folded + "\n", folded
        for mode in ("change", "review"):
            assert run_mode("ignored", mode) == 0, (mode, "trusted dirs must not be blamed")
            # 真实污染仍须被拒绝，预存的未跟踪目录不得成为普遍豁免。
            assert run_mode("tracked", mode) == 1, mode
            assert run_mode("untracked", mode) == 1, mode

        # 豁免的依据是「基线中已存在的状态条目」，不是「路径名匹配」。两个用例：
        #
        # 1) 一个 .trusted 前缀的旁路目录，证明前缀本身不构成豁免；
        # 2) 真正的 .trusted-base 目录内的已跟踪文件——按名字排除会漏掉它，这正是 issue #31
        #    提醒的副作用。该目录一旦持有索引条目就不再折叠，因此这个用例不会退化成测折叠。
        # 折叠只在目录不含索引条目时发生，因此这两个用例用一个独立仓库：上面的 fixture 已经
        # 在 .trusted-base 内建好嵌套 .git 并断言了折叠形态，无法在同一棵树里同时表达两种。
        with tempfile.TemporaryDirectory(prefix="setup-hook-named-") as named_name:
            named_ws = Path(named_name)
            named = init_repo(named_ws / "consumer")
            (named / ".github").mkdir(parents=True, exist_ok=True)
            for rel, script in (
                (".trusted-sidecar/consumer-owned.txt", "setup-trusted-tracked"),
                (".trusted-base/consumer-owned.txt", "setup-trusted-inside"),
            ):
                target = named / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("real\n")
                (named / f".github/{script}.sh").write_text(f"echo polluted >> {rel}\n")
            git(named, "add", "-A")
            git(named, "commit", "-qm", "consumer tracks files under .trusted paths")
            # 先有索引条目，再制造嵌套 .git：该目录因此不折叠，其中已跟踪文件的改动会产生
            # ` M` 行。按名字排除 .trusted-base 会漏掉它，这正是 issue #31 提醒的副作用。
            run(["git", "init", "-q"], cwd=named / ".trusted-base")
            status = git(named, "status", "--porcelain", "--untracked-files=all")
            assert "?? .trusted-base/\n" not in status + "\n", status

            def run_named(script: str, mode: str) -> int:
                scratch = named_ws / "scratch"
                scratch.mkdir(exist_ok=True)
                prompt = scratch / "prompt.txt"
                prompt.write_text("base prompt\n")
                env = os.environ.copy()
                env["RUNNER_TEMP"] = str(scratch)
                code = run(
                    ["bash", str(hook), f".github/{script}.sh", str(named), str(named),
                     str(prompt), mode],
                    env=env, check=False,
                ).returncode
                git(named, "checkout", "-q", "--", ".")
                return code

            for mode in ("change", "review"):
                assert run_named("setup-trusted-tracked", mode) == 1, (mode, "prefix no exemption")
                assert run_named("setup-trusted-inside", mode) == 1, (mode, "tracked inside must fail")


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

    # 文档不得复制可能变陈旧的 SHA 字面量。此前 pr-review-contract.md 硬编码了旧的
    # policy SHA，而唯一引用它的测试改为正则提取后，这条字面量失去了任何自动检查。
    # 用 glob 覆盖 docs/ 与 llmdoc/ 全部 Markdown，新增文件自动纳入。
    docs = [ROOT / "README.md", *sorted((ROOT / "docs").rglob("*.md"))]
    for doc in docs:
        assert not re.search(r"\b[0-9a-f]{40}\b", doc.read_text()), str(doc.relative_to(ROOT))
    for doc in sorted((ROOT / "llmdoc").rglob("*.md")):
        stale = [
            sha for sha in re.findall(r"\b[0-9a-f]{40}\b", doc.read_text())
            if sha != policy_sha
        ]
        assert not stale, (str(doc.relative_to(ROOT)), stale)

    # 准备脚本的自限时默认值被五处文档引用，必须与脚本实际值一致，否则会像 SHA 字面量
    # 一样悄悄漂移。
    hook = (ROOT / ".github/scripts/agentic/run-setup-hook.sh").read_text()
    default_timeout = re.search(r'\$\{SETUP_HOOK_TIMEOUT:-([0-9]+[smh])\}', hook)
    assert default_timeout, "run-setup-hook.sh 必须为自限时提供默认值"
    timeout_value = default_timeout.group(1)
    minutes = timeout_value.removesuffix("m")
    for doc in (
        ROOT / "README.md",
        ROOT / "llmdoc/reference/pr-review-contract.md",
        ROOT / "llmdoc/reference/workflow-contracts.md",
        ROOT / "llmdoc/architecture/pr-review-trust-boundary.md",
        ROOT / "llmdoc/architecture/workflow-orchestration.md",
    ):
        text = doc.read_text()
        assert f"{minutes}m" in text or f"{minutes}-minute" in text or f"{minutes} 分钟" in text, (
            str(doc.relative_to(ROOT)), timeout_value,
        )
        # 旧的「步骤级 15 分钟即上限」表述不得残留，否则与自限时模型矛盾。
        assert "fixed 15-minute step timeout" not in text, str(doc.relative_to(ROOT))
        assert "15-minute step, non-fatal" not in text, str(doc.relative_to(ROOT))

    # 步骤级兜底与 job 级超时的数字同样会漂移，一并与 workflow 实际值绑定。
    step_backstop = re.search(r"^        timeout-minutes: (\d+)$", workflow, re.M)
    assert step_backstop, "hook 步骤必须声明 timeout-minutes"
    job_timeout = re.search(r"^    timeout-minutes: (\d+)$", workflow, re.M)
    assert job_timeout, "reviewer job 必须声明 timeout-minutes"
    for doc in (
        ROOT / "README.md",
        ROOT / "llmdoc/reference/pr-review-contract.md",
        ROOT / "llmdoc/reference/workflow-contracts.md",
        ROOT / "llmdoc/architecture/pr-review-trust-boundary.md",
        ROOT / "llmdoc/architecture/workflow-orchestration.md",
    ):
        text = doc.read_text()
        if "timeout-minutes" in text:
            assert f"timeout-minutes: {step_backstop.group(1)}" in text, (
                str(doc.relative_to(ROOT)), step_backstop.group(1),
            )
    contract_doc = (ROOT / "llmdoc/reference/pr-review-contract.md").read_text()
    assert f"{job_timeout.group(1)} minutes" in contract_doc, job_timeout.group(1)

    policy_files = run([
        "git", "ls-tree", "-r", "--name-only", policy_sha, "--", ".claude/skills/pr-review",
    ], cwd=ROOT).stdout.splitlines()
    assert policy_files == [".claude/skills/pr-review/SKILL.md"]

    # 五个 workflow 必须共用同一个版本号。此前两个 harness 各自只读自己那几个 workflow，
    # 没有任何检查会发现 pr-review 被单独重新 pin 到另一个真实 commit（split pin）。
    # 两种键序都要覆盖：只匹配 repository 在前的写法时，调换 with: 下的键序即可绕过。
    # 这里不引入 PyYAML，因为两个 harness 目前都只依赖标准库，CI 也不安装额外依赖。
    template_repo = "repository: Lightspeed-Intelligence/agentic-workflow-template"
    all_refs: set[str] = set()
    for name in (
        "pr-review", "question", "issue-dispatch", "implement", "update-llmdoc",
    ):
        text = (ROOT / f".github/workflows/{name}.yml").read_text()
        refs = [
            *re.findall(rf"{re.escape(template_repo)}\n\s+ref: ([^\s#]+)", text),
            *re.findall(rf"ref: ([^\s#]+)\n\s+{re.escape(template_repo)}", text),
        ]
        # 每个引用模板仓库的 checkout 都必须带 ref，否则会隐式取默认分支。
        assert len(refs) == text.count(template_repo), (name, refs)
        assert refs, name
        all_refs.update(refs)
    assert all_refs == {policy_sha}, all_refs


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
