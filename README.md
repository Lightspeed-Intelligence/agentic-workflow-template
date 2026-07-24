# Agentic Workflow Template

基于 GitHub Actions 的自动化工作流模板。自动处理 Issue 分析、需求评审、代码实现、
文档维护和 PR 审查。所有 Agent workflow 都以固定版本 Codex 为主链路，技术失败时由
独立 runner 中的 Claude Code 接手；Agent 不持有 GitHub 写凭据，外部副作用由确定性
publisher 执行。

## 快速开始

### 1. 使用模板创建仓库

```bash
gh repo create my-project --template Lightspeed-Intelligence/agentic-workflow-template
```

### 2. 配置 Secrets

```bash
# 必需
gh secret set ANTHROPIC_API_KEY

# 可选 (自定义 API 端点)
gh secret set ANTHROPIC_BASE_URL

# 可选 (为 Codex 单独配置；每项未设置时回退到对应的 ANTHROPIC_* Secret)
gh secret set OPENAI_API_KEY
gh secret set OPENAI_BASE_URL

# 可选 (私有 submodule 访问)
gh secret set PAT_TOKEN

# 可选 (飞书通知)
gh secret set FEISHU_WEBHOOK_TOKEN
```

### 3. 创建调用工作流

在目标仓库 `.github/workflows/` 创建：

```yaml
# ci.yml - Issue 和 PR 事件触发
name: Agentic CI

on:
  issues:
    types: [opened]
  issue_comment:
    types: [created]
  pull_request:
    types: [opened, synchronize, reopened]

jobs:
  # Issue 创建时自动分析；不会自动修复
  issue-dispatch:
    if: github.event_name == 'issues'
    permissions:
      contents: read
      issues: write
    uses: Lightspeed-Intelligence/agentic-workflow-template/.github/workflows/issue-dispatch.yml@main
    secrets:
      ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
      ANTHROPIC_BASE_URL: ${{ secrets.ANTHROPIC_BASE_URL }}
      OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
      OPENAI_BASE_URL: ${{ secrets.OPENAI_BASE_URL }}
      PAT_TOKEN: ${{ secrets.PAT_TOKEN }}
      FEISHU_WEBHOOK_TOKEN: ${{ secrets.FEISHU_WEBHOOK_TOKEN }}

  # 评论 /impl 或 ok 时实现代码
  implement:
    if: github.event_name == 'issue_comment' && github.event.issue.pull_request == null
    permissions:
      contents: write
      issues: write
      pull-requests: write
    uses: Lightspeed-Intelligence/agentic-workflow-template/.github/workflows/implement.yml@main
    secrets:
      ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
      ANTHROPIC_BASE_URL: ${{ secrets.ANTHROPIC_BASE_URL }}
      OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
      OPENAI_BASE_URL: ${{ secrets.OPENAI_BASE_URL }}
      PAT_TOKEN: ${{ secrets.PAT_TOKEN }}
      FEISHU_WEBHOOK_TOKEN: ${{ secrets.FEISHU_WEBHOOK_TOKEN }}

  # 评论 /ask 或 /q 时回答问题
  question:
    if: github.event_name == 'issue_comment' && github.event.issue.pull_request == null
    permissions:
      contents: read
      issues: write
    uses: Lightspeed-Intelligence/agentic-workflow-template/.github/workflows/question.yml@main
    secrets:
      ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
      ANTHROPIC_BASE_URL: ${{ secrets.ANTHROPIC_BASE_URL }}
      OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
      OPENAI_BASE_URL: ${{ secrets.OPENAI_BASE_URL }}
      PAT_TOKEN: ${{ secrets.PAT_TOKEN }}
      FEISHU_WEBHOOK_TOKEN: ${{ secrets.FEISHU_WEBHOOK_TOKEN }}

  # PR 创建/更新时自动审查
  pr-review:
    if: github.event_name == 'pull_request'
    permissions:
      contents: read
      pull-requests: write
    uses: Lightspeed-Intelligence/agentic-workflow-template/.github/workflows/pr-review.yml@main
    secrets:
      ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
      ANTHROPIC_BASE_URL: ${{ secrets.ANTHROPIC_BASE_URL }}
      OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
      OPENAI_BASE_URL: ${{ secrets.OPENAI_BASE_URL }}
      PAT_TOKEN: ${{ secrets.PAT_TOKEN }}
      FEISHU_WEBHOOK_TOKEN: ${{ secrets.FEISHU_WEBHOOK_TOKEN }}
```

### 4. 配置 CLAUDE.md

在目标仓库根目录创建 `CLAUDE.md`，参考 `CLAUDE.md.example`。

## 工作流

| 工作流           | 触发条件              | 功能                                                          |
| ---------------- | --------------------- | ------------------------------------------------------------- |
| `issue-dispatch` | Issue 创建             | 只分析并分类；不修改代码或创建 PR                              |
| `implement`      | 评论 `/impl` 或 `ok`   | 生成并校验本地候选 commit，再由 publisher 创建或更新 PR        |
| `question`       | 评论 `/ask` `/q` `/?`  | 生成回答，由 publisher 幂等发布                                |
| `update-llmdoc`  | 外部 reusable caller   | 只修改 `llmdoc/`，校验候选 commit 后创建或更新 PR               |
| `pr-review`      | PR 创建/更新            | 风险分级审查；默认完整 diff，可信的 1–3 个小问题修复可走增量     |

## Skills

| Skill             | 描述     | 输出                           |
| ----------------- | -------- | ------------------------------ |
| `github-comment`  | 基础规范 | 定义评论格式、折叠、链接       |
| `bug-analyze`     | Bug 分析 | 根因定位 + 后续自动实现适用性评估 |
| `feature-review`  | 需求评审 | 成本估算 + 影响分析 (面向产品) |
| `implement`       | 代码实现 | 本地候选变更，不直接操作 GitHub |
| `update-llmdoc`   | 文档维护 | 只更新已有 `llmdoc/`            |
| `pr-review`       | PR 审查  | 高信号问题 + 风险分级全量/增量审查 |
| `answer-question` | 问题回答 | 技术咨询                       |

## 配置项

### 工作流输入

```yaml
# implement.yml
inputs:
  trigger_keywords: '["/impl", "ok", "OK"]'  # 触发关键词
  use_feishu_notify: true                     # 飞书通知

# question.yml
inputs:
  trigger_keywords: '["/ask", "/q", "/?"]'   # 触发关键词
  use_feishu_notify: true

# issue-dispatch.yml
inputs:
  use_feishu_notify: true

# update-llmdoc.yml
inputs:
  since_period: "24 hours ago"
  target_branch: dev
  use_feishu_notify: true

# pr-review.yml
inputs:
  use_feishu_notify: true
  # 可选：Claude fallback 的仓库特定只读 Git 工具模式；不得放行 git -C <path>:*。
  extra_allowed_tools: 'Bash(git -C tipsy-app diff:*),Bash(git -C tipsy-app log:*)'
```

四个 Issue/文档 workflow 与 PR 审查都优先使用 Codex + GPT-5.6-sol，进程失败、schema
失败或结构化 `INCOMPLETE` 时才启动全新 runner 中的 Claude Code + Fable-5。有效的
`BLOCKED` / `NO_CHANGES` 是业务结果，不触发 fallback。

纯回答 workflow 只跨 job 传递 JSON artifact；写代码 workflow 传递单父提交 Git bundle，
由无写权限 validator 校验后才交给 publisher。Agent 进程不接收 PAT 或 GitHub token，
checkout 凭据不持久化。只有最终 `answer`、`dispatch`、`implement`、`update` job 执行评论、
push 或创建 PR；这些名称刻意保持稳定，以兼容下游 ruleset。

PR 审查评论同样由单独的发布 job 校验结构化结果后代发。Codex 即使退出码为
0，只要结构化 `review_status` 为 `INCOMPLETE`，也会被视为软失败并触发 fallback；
自由文本中的错误字样不会被误当成运行状态。
只有核心 diff/工作树不可访问或无法完成有意义的代码审查时才应标记
`INCOMPLETE`；某个项目测试因 runner 缺少工具或版本而未运行，应记录但不会单独使审查失败。

PR 审查规范由 reusable workflow 所在的 template 仓库以固定 commit 提供；
调用方仓库无需复制 `review-sop.md` 或 `output-format.md`。调用方 base checkout
只用于获取可选的历史审查准备脚本，缺失时安全降级为完整审查。

每次 Agent 启动前，确定性准备步骤会使用 job 的只读 token 读取最新一条由
`github-actions` App 发布、且带有 publisher 生成的结构化状态标记的历史 review。
Agent 不接收该 token，也不自行查询评论。仅当前序 review 没有 BLOCKER/MAJOR、恰有
1–3 个 MINOR/NIT，且历史 head 是当前 head 的祖先时，才审查 `cutoff..head` 增量并
逐条验证旧问题；其它情况一律审查完整 `base...head`。

`extra_allowed_tools` 只接受 `git -C <安全路径>` 下的 `diff`、`log`、`show`、
`status`、`rev-parse`、`merge-base` 或 `ls-files` 模式。它用于声明 monorepo/submodule
中的额外只读工具提示；Agent 已有完整本地执行权限，因此它不构成安全边界，真正的
边界仍是 Agent job 的只读 token 和不向 Agent 进程注入 GitHub/PAT 凭据。

### Secrets

| Secret                 | 必需 | 描述                                        |
| ---------------------- | ---- | ------------------------------------------- |
| `ANTHROPIC_API_KEY`    | ✅   | Anthropic API Key                           |
| `ANTHROPIC_BASE_URL`   | ❌   | 自定义 API 端点 (代理/私有部署)             |
| `OPENAI_API_KEY`       | ❌   | Codex API Key；为空时回退到 `ANTHROPIC_API_KEY` |
| `OPENAI_BASE_URL`      | ❌   | Codex API 端点；为空时回退到 `ANTHROPIC_BASE_URL` |
| `PAT_TOKEN`            | ❌   | 私有 submodule checkout；写代码 workflow 也可仅在 publisher 使用 |
| `FEISHU_WEBHOOK_TOKEN` | ❌   | 飞书机器人 Webhook Token                    |

## 目录结构

```
.
├── .github/
│   ├── workflows/           # 可复用工作流
│   │   ├── issue-dispatch.yml
│   │   ├── implement.yml
│   │   ├── question.yml
│   │   ├── update-llmdoc.yml
│   │   └── pr-review.yml
│   └── actions/
│       ├── run-agent/       # 固定版本 Codex / Claude Code runner
│       └── feishu-notify/   # 飞书通知 Action
├── .claude/
│   └── skills/              # Claude Skills
│       ├── github-comment/  # 基础规范
│       ├── bug-analyze/
│       ├── feature-review/
│       ├── implement/
│       ├── update-llmdoc/
│       ├── pr-review/       # 入口 + references/review-sop.md、output-format.md
│       └── answer-question/
├── scripts/                 # Submodule 管理与 workflow 合同测试
│   ├── init.sh
│   ├── status.sh
│   └── update-all.sh
├── llmdoc/                  # Agent 启动上下文、架构、指南、契约与项目记忆
├── CLAUDE.md.example        # CLAUDE.md 示例
└── design.md                # 设计文档
```

## JSON 输出结构

各工作流输出 `structured_output`：

```jsonc
// issue-dispatch
{
  "description": "执行结果摘要",
  "issue_type": "bug | feature | question",
  "severity": "critical | high | medium | low | n/a",  // bug only
  "cost": "small | medium | large | extra-large | n/a", // feature only
  "auto_fix_eligible": false,
  "result_status": "COMPLETE",
  "reviewer": "codex | claude"
}

// implement
{
  "description": "实现结果摘要",
  "outcome": "READY | NO_CHANGES | BLOCKED",
  "status": "success | blocked",
  "branch_name": "agentic/issue-123",
  "pr_number": 123,
  "pr_url": "https://..."
}

// pr-review
{
  "description": "审查结论摘要",
  "review_status": "COMPLETE | INCOMPLETE",
  "conclusion": "APPROVE | REQUEST_CHANGES | COMMENT",
  "critical_count": 0,
  "important_count": 1,
  "suggestion_count": 2,
  "reviewer": "codex | claude",
  "model": "gpt-5.6-sol | fable-5"
}

// question
{
  "description": "回答内容摘要",
  "result_status": "COMPLETE",
  "reviewer": "codex | claude",
  "model": "gpt-5.6-sol | fable-5"
}
```

## Submodule 支持

对于聚合多个子项目的仓库：

1. checkout 可以使用可选 PAT 读取跨仓库私有 submodule，但不会把凭据交给 Agent。
2. Agent 可以读取各 submodule 的 `llmdoc/` 理解上下文。
3. 自动发布暂不创建跨仓库 submodule commit/PR；需要此类改动时返回 `BLOCKED`。

```bash
# 初始化
./scripts/init.sh

# 查看状态
./scripts/status.sh

# 更新所有
./scripts/update-all.sh
```

## 分支命名

- Issue 实现: `agentic/issue-{issue_number}`
- llmdoc 更新: `agentic/update-llmdoc-{target_branch}`

## 注意事项

1. **llmdoc 优先** - Agent 会先读取 `llmdoc/` 理解项目
2. **评论折叠** - 长内容使用 `<details>` 折叠
3. **可信小增量** - 只有经准备步骤认证的 1–3 个小问题修复走增量，其余全部审查完整 diff
4. **高信号** - 只标记确定的问题，避免误报
