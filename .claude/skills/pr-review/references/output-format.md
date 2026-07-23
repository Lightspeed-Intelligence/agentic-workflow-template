# PR Review Output Format

The final answer must be the GitHub PR comment body in Simplified Chinese.

## Conclusion Values

Choose by the overall merge judgment (see `references/review-sop.md`), not by a raw count of findings. Use exactly one:

- `APPROVE`: no genuine blocker. Non-blocking MINOR/NIT items, or MAJOR items that are recommendations rather than correctness/safety failures, do not by themselves prevent APPROVE. Finding nothing on a low-risk PR is a normal APPROVE.
- `REQUEST_CHANGES`: at least one genuine BLOCKER exists — code that can break correctness, safety, data integrity, security, or deployment as written. A pile of low-severity or gate-driven items does not add up to REQUEST_CHANGES when no single item is merge-blocking.
- `COMMENT`: no blocker, but there are worthwhile suggestions or unresolved questions the author should weigh.

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

{风险分级: 低 / 中 / 高 —— 一句话说明依据}

{完整性声明: 据本轮审查，以上为本 PR 已知的全部阻塞级风险 / 仍有需作者确认的开放问题见下}

<details>
<summary><h3>本轮改动引入的问题 (N)</h3></summary>

本区块放**由本轮改动引入**的问题（首次审查即整个 PR 引入的问题），按严重度降序排列。只有本区块的 BLOCKER 触发 REQUEST_CHANGES。

- **严重度**: BLOCKER
- **文件**: `{path}` [代码链接](https://github.com/{owner}/{repo}/blob/{current_full_sha}/{path}#L{start}-L{end})
- **问题**: {what is wrong}
- **验证**: {what was verified in code, 含 git blame 溯源结论}
- **影响**: {why it matters}
- **建议**: {specific fix}
- **出处**: {source name + URL, only when invoking SOP/best practice}

- **严重度**: MAJOR / MINOR / NIT
- **文件**: ...
- **问题**: ...
- **建议**: ...

</details>

<details>
<summary><h3>既存问题（非本轮引入） (N)</h3></summary>

本区块放**并非本轮改动引入、但仍然存在**的问题——经 git blame 确认其代码早于本轮增量窗口。**不阻塞本 PR 合入**，也不计入阻塞计数，但如实报告，供作者知情。每条必须带既存标识。首次审查若无此类问题填「无」。

- **严重度**: BLOCKER / MAJOR / MINOR / NIT（如实标注，但不阻塞本 PR）
- **来源**: 此问题在之前的代码中已存在，非本轮改动引入（git blame: 引入于 `{commit}`，早于审查窗口）
- **文件**: `{path}` [代码链接](https://github.com/{owner}/{repo}/blob/{current_full_sha}/{path}#L{start}-L{end})
- **问题**: {what is wrong}
- **影响**: {why it matters}
- **建议**: {specific fix}

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

## Finding Classification Rules

- Every finding goes in exactly one bucket, decided by `git blame` on the offending lines against repo history — not by which review round caught it. See the Finding Origin section in `SKILL.md`.
- **本轮改动引入**: the offending code was introduced within this round's incremental window, or older code that this round's change turns defective (interaction bug). This is the only bucket that drives the verdict and the blocking counts.
- **既存问题（非本轮引入）**: the offending code predates the window and this round did not create the defect. Report it with an explicit pre-existing note, but it never blocks this PR and is excluded from the blocking counts, regardless of severity.
- The severity counts reported to the workflow (`critical_count` / `important_count` / `suggestion_count`) count **only 本轮改动引入 findings**. Pre-existing findings are labeled in the body but not counted.
- End the comment with the single cutoff marker `审查截止: {sha}` so the next trusted round can compute its incremental window. Do not emit any version/round number.

## Empty Sections

Keep the section headers even when empty. Use `无` inside empty details blocks so downstream parsing remains stable. On a first review there is no incremental window, so the whole PR counts as 本轮改动引入 and 既存问题 is typically `无`.

## Links

All code links must use the full current commit SHA:

```text
https://github.com/{owner}/{repo}/blob/{full_sha}/{path}#L{start}-L{end}
```

Do not use branch names in code links.
