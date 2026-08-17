#!/usr/bin/env python3
"""Offline contract tests for optional deploy-key submodule checkout."""

from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_CHECKOUTS = {
    "issue-dispatch": 2,
    "implement": 4,
    "question": 2,
    "pr-review": 2,
    "update-llmdoc": 5,
}
CALLER = ROOT / ".github/workflows/ci.yml"

DEPLOY_KEY_SECRET = """      SUBMODULE_SSH_KEY_BASE64:
        required: false"""
DYNAMIC_SUBMODULE_MODE = (
    "submodules: ${{ secrets.SUBMODULE_SSH_KEY_BASE64 == '' && 'recursive' || 'false' }}"
)
DYNAMIC_CHECKOUT_TOKEN = (
    "token: ${{ secrets.SUBMODULE_SSH_KEY_BASE64 != '' && github.token "
    "|| secrets.PAT_TOKEN || github.token }}"
)
INIT_STEP = """- &initialize-submodules-with-deploy-key
        name: Initialize recursive submodules with deploy key"""
INIT_STEP_ALIAS = "- *initialize-submodules-with-deploy-key"
GITHUB_ED25519_HOST_KEY = (
    "github.com ssh-ed25519 "
    "AAAAC3NzaC1lZDI1NTE5AAAAIOMqqnkVzrm0SdG6UOoqKLsabgH5C9okWi0dh2l9GKJl"
)


def test_reusable_workflows_support_optional_read_only_deploy_keys() -> None:
    for name, checkout_count in WORKFLOW_CHECKOUTS.items():
        workflow = (ROOT / f".github/workflows/{name}.yml").read_text()

        assert workflow.count(DEPLOY_KEY_SECRET) == 1, name
        assert workflow.count(DYNAMIC_SUBMODULE_MODE) == checkout_count, name
        assert workflow.count(DYNAMIC_CHECKOUT_TOKEN) == checkout_count, name
        assert workflow.count(INIT_STEP) == 1, name
        assert workflow.count(INIT_STEP_ALIAS) == checkout_count - 1, name
        assert "submodules: recursive" not in workflow, name

        checkout_followups = workflow.count(
            DYNAMIC_CHECKOUT_TOKEN + "\n\n      " + INIT_STEP
        ) + workflow.count(DYNAMIC_CHECKOUT_TOKEN + "\n\n      " + INIT_STEP_ALIAS)
        assert checkout_followups == checkout_count, name

        # The key is scoped only to the deterministic checkout step. It must not
        # become workflow/job state inherited by an Agent process.
        assert workflow.count(
            "SUBMODULE_SSH_KEY_BASE64: ${{ secrets.SUBMODULE_SSH_KEY_BASE64 }}"
        ) == 1, name
        assert workflow.count('if [[ -z "$SUBMODULE_SSH_KEY_BASE64" ]]; then') == 1, name
        assert workflow.count('mktemp -d "$RUNNER_TEMP/submodule-key.XXXXXX"') == 1, name
        assert workflow.count('base64 --decode > "$key_file"') == 1, name
        assert workflow.count('chmod 600 "$key_file" "$known_hosts"') == 1, name
        assert workflow.count("trap cleanup EXIT") == 1, name
        assert workflow.count(GITHUB_ED25519_HOST_KEY) == 1, name
        assert workflow.count("StrictHostKeyChecking=yes") == 1, name
        assert workflow.count("IdentitiesOnly=yes") == 1, name
        assert workflow.count("UserKnownHostsFile=$known_hosts") == 1, name
        assert workflow.count("submodule sync --recursive") == 1, name
        assert workflow.count("submodule update --init --recursive") == 1, name
        assert workflow.count(
            "url.git@github.com:.insteadOf=https://github.com/"
        ) == 2, name


def test_checkout_paths_and_caller_contract_are_explicit() -> None:
    for name, checkout_count in WORKFLOW_CHECKOUTS.items():
        workflow = (ROOT / f".github/workflows/{name}.yml").read_text()
        expected_dir = "." if name == "pr-review" else "consumer"
        assert workflow.count(f'CONSUMER_DIR: "{expected_dir}"') == 1, name

    caller = CALLER.read_text()
    assert caller.count(
        "SUBMODULE_SSH_KEY_BASE64: ${{ secrets.SUBMODULE_SSH_KEY_BASE64 }}"
    ) == 4


def test_deploy_key_shell_is_valid_and_identical_across_workflows() -> None:
    bodies: set[str] = set()
    for name in WORKFLOW_CHECKOUTS:
        workflow = (ROOT / f".github/workflows/{name}.yml").read_text()
        step_start = workflow.index(INIT_STEP)
        body_start = workflow.index("        run: |\n", step_start) + len("        run: |\n")
        body_end = workflow.find("\n      - ", body_start)
        assert body_end != -1, name
        body = "\n".join(
            line[10:] if line.startswith("          ") else line
            for line in workflow[body_start:body_end].splitlines()
        )
        result = subprocess.run(
            ["bash", "-n"], input=body, text=True, capture_output=True, check=False
        )
        assert result.returncode == 0, (name, result.stderr)
        bodies.add(body)
    assert len(bodies) == 1, "deploy-key shell must not drift between workflows"


def test_legacy_pat_publisher_fallback_is_unchanged() -> None:
    implement = (ROOT / ".github/workflows/implement.yml").read_text()
    update_llmdoc = (ROOT / ".github/workflows/update-llmdoc.yml").read_text()

    assert "GH_TOKEN: ${{ secrets.PAT_TOKEN || github.token }}" in implement
    assert "COMMENT_TOKEN: ${{ github.token }}" in implement
    assert "GH_TOKEN: ${{ secrets.PAT_TOKEN || github.token }}" in update_llmdoc


if __name__ == "__main__":
    test_reusable_workflows_support_optional_read_only_deploy_keys()
    test_checkout_paths_and_caller_contract_are_explicit()
    test_deploy_key_shell_is_valid_and_identical_across_workflows()
    test_legacy_pat_publisher_fallback_is_unchanged()
