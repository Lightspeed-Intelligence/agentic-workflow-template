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

## Finding 来源（代码溯源）

每条 finding 除严重度外，还须标注「来源」，用 `git blame` 判定问题代码的实际出处。这是与
「历史问题复核」正交的另一维度：历史复核比较的是「上一轮 review vs 本轮」（时间、跨轮、依赖 workflow 历史），
来源比较的是「本轮改动 vs 更早的代码」（代码溯源、无状态、每轮含首轮都能判）。

- **本轮改动引入**: 问题代码行由本轮审查范围内的 commit 写入（落在 workflow 提供的审查范围 diff 内）；或本轮改动使原本正确的旧代码变为缺陷的交互型问题（此时虽 blame 指向旧代码，但缺陷由本轮造成，归此类）。判定带语义，不是纯机械 blame。
- **既存(非本轮引入)**: 问题代码早于本轮审查范围，且本轮改动并未使其变坏——纯粹是本 PR 恰好触及/依赖/放大了这段旧代码时才报（遵循 review-sop 的 Finding Discipline，不拖入与本 PR 完全无关的祖传问题）。

来源**不改变**严重度、阻塞判定和计数：既存问题按其真实严重度照常计入 `critical_count` /
`important_count` / `suggestion_count`，照常参与结论（BLOCKER/MAJOR 仍触发 REQUEST_CHANGES）。
「来源」只是让作者一眼看清哪些是本次改出来的、哪些是本次撞上的旧债，不降低任何问题的处理级别。

## Required Structure

```markdown
## PR 审查

| 项目 | 结果 |
|------|------|
| **结论** | APPROVE / REQUEST_CHANGES / COMMENT |
| **审查模式** | full / incremental |
| **审查范围** | `{range}` |
| **Head commit** | `{current_full_sha}` |

严格使用 workflow 提供的审查模式和范围；cutoff 与历史状态由 workflow 的确定性步骤认证，
reviewer 不自行从评论推断。Head SHA 仅用于固定当前树和代码链接。

{一句话总结}

{风险分级: 低 / 中 / 高 —— 一句话说明依据}

{完整性声明: 据本轮审查，以上为本 PR 已知的全部阻塞级风险 / 仍有需作者确认的开放问题见下}

<details>
<summary><h3>历史问题复核</h3></summary>

- {对上一轮每个 finding 逐条给出: 已解决 / 仍存在 / 部分解决；增量模式必须填写}
- 没有可信历史 review 时填「无」

</details>

<details>
<summary><h3>阻塞问题 (N)</h3></summary>

- **严重度**: BLOCKER
- **来源**: 本轮改动引入 / 既存(非本轮引入)
- **文件**: `{path}` [代码链接](https://github.com/{owner}/{repo}/blob/{current_full_sha}/{path}#L{start}-L{end})
- **问题**: {what is wrong}
- **验证**: {what was verified in code, 含 git blame 溯源依据}
- **影响**: {why it matters}
- **建议**: {specific fix}
- **出处**: {source name + URL, only when invoking SOP/best practice}

</details>

<details>
<summary><h3>重要建议 (N)</h3></summary>

- **严重度**: MAJOR
- **来源**: 本轮改动引入 / 既存(非本轮引入)
- **文件**: ...
- **问题**: ...
- **验证**: ...
- **影响**: ...
- **建议**: ...

</details>

<details>
<summary><h3>小问题 (N)</h3></summary>

- **严重度**: MINOR / NIT
- **来源**: 本轮改动引入 / 既存(非本轮引入)
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
