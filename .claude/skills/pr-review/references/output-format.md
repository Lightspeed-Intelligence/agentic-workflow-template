# PR Review Output Format

The model's final response remains the workflow-defined JSON object. Its `comment_body` field
must contain the complete GitHub PR comment body in Simplified Chinese; do not emit Markdown
outside that JSON object.

## Review Completion Status

Set the top-level `review_status` field independently from the finding conclusion:

- `COMPLETE`: the full required review was actually completed.
- `INCOMPLETE`: an environment, tool, access, or execution limitation prevented the full review,
  even if the process can still return schema-valid JSON.

Never report `COMPLETE` merely because a JSON response can be produced. An `INCOMPLETE` result is
a workflow control signal: it is not publishable and causes the isolated fallback reviewer to run.

## Conclusion Values

Use exactly one, preserving the workflow's count/conclusion contract:

- `APPROVE`: BLOCKER、MAJOR、MINOR、NIT 和开放问题均为 0。
- `REQUEST_CHANGES`: 至少存在一个 BLOCKER 或 MAJOR。
- `COMMENT`: 没有 BLOCKER/MAJOR，但存在 MINOR、NIT 或需要记录的开放问题。

## Severity

- **BLOCKER**: must fix before merge; current code can break correctness, safety, data integrity, security, or deployment.
- **MAJOR**: strongly recommended before merge; material operational, maintainability, observability, or test gap.
- **MINOR**: useful cleanup or narrow risk.
- **NIT**: small style or clarity issue worth mentioning only if it improves the patch.

结构化计数必须与正文一致：BLOCKER → `critical_count`，MAJOR →
`important_count`，MINOR/NIT → `suggestion_count`。开放问题不得伪装成已确认 finding。

## Required Structure

```markdown
## PR 审查

| 项目 | 结果 |
|------|------|
| **结论** | APPROVE / REQUEST_CHANGES / COMMENT |
| **审查范围** | `{range}` |
| **Head commit** | `{current_full_sha}` |

本次始终覆盖 workflow 提供的完整 `base...head` diff；该 SHA 仅用于固定代码链接，
不得作为后续增量审查的评论状态。

{一句话总结}

{风险分级: 低 / 中 / 高 —— 一句话说明依据}

{完整性声明: 据本轮审查，以上为本 PR 已知的全部阻塞级风险 / 仍有需作者确认的开放问题见下}

<details>
<summary><h3>历史问题复核 (仅增量审查时)</h3></summary>

- {对上一轮每个 BLOCKER/MAJOR 逐条给出: 已解决 / 仍存在 / 部分解决}
- 首次审查填「无」

</details>

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
