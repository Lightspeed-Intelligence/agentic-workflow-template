# PR Review Output Format

The final answer must be the GitHub PR comment body in Simplified Chinese.

## Conclusion Values

Use exactly one:

- `APPROVE`: no merge-blocking or important issues found.
- `REQUEST_CHANGES`: at least one blocker exists, or the PR is unsafe to merge as-is.
- `COMMENT`: no blocker, but there are important suggestions or unresolved questions.

## Severity

- **BLOCKER**: must fix before merge; current code can break correctness, safety, data integrity, security, or deployment.
- **MAJOR**: strongly recommended before merge; material operational, maintainability, observability, or test gap.
- **MINOR**: useful cleanup or narrow risk.
- **NIT**: small style or clarity issue worth mentioning only if it improves the patch.

## Required Structure

```markdown
## Codex PR 审查

| 项目 | 结果 |
|------|------|
| **结论** | APPROVE / REQUEST_CHANGES / COMMENT |
| **审查范围** | `{range}` |
| **审查截止** | `{current_full_sha}` |

审查截止: {current_full_sha}

{一句话总结}

<details>
<summary><h3>阻塞问题 (N)</h3></summary>

- **严重度**: BLOCKER
- **文件**: `{path}` [代码链接](https://github.com/{owner}/{repo}/blob/{current_full_sha}/{path}#L{start}-L{end})
- **问题**: {what is wrong}
- **验证**: {what was verified in code}
- **影响**: {why it matters}
- **建议**: {specific fix}
- **出处**: {source name + URL, only when invoking SOP/best practice}

</details>

<details>
<summary><h3>重要建议 (N)</h3></summary>

- **严重度**: MAJOR
- **文件**: ...
- **问题**: ...
- **验证**: ...
- **影响**: ...
- **建议**: ...

</details>

<details>
<summary><h3>小问题 (N)</h3></summary>

- **严重度**: MINOR / NIT
- **文件**: ...
- **问题**: ...
- **建议**: ...

</details>

<details>
<summary><h3>Sources cited</h3></summary>

- {source name}: {URL}

</details>

<details>
<summary><h3>做得对的地方</h3></summary>

- {verified positive decision worth preserving}

</details>

<details>
<summary><h3>开放问题</h3></summary>

- {question that must be answered before merge, or "无"}

</details>
```

## Empty Sections

Keep the section headers even when empty. Use `无` inside empty details blocks so downstream parsing remains stable.

## Links

All code links must use the full current commit SHA:

```text
https://github.com/{owner}/{repo}/blob/{full_sha}/{path}#L{start}-L{end}
```

Do not use branch names in code links.
