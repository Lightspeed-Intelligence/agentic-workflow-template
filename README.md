# Agentic Workflow Template

基于 Claude Code Action 的 GitHub 自动化工作流模板。自动处理 Issue 分析、需求评审、Bug 修复、代码实现和 PR 审查。

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
    types: [opened, labeled]
  issue_comment:
    types: [created]
  pull_request:
    types: [opened, synchronize, reopened]

# 必须授予 reusable workflow 所需的权限
permissions:
  contents: write
  issues: write
  pull-requests: write
  id-token: write

jobs:
  # Issue 创建/打标签时自动分析
  issue-dispatch:
    if: github.event_name == 'issues'
    uses: Lightspeed-Intelligence/agentic-workflow-template/.github/workflows/issue-dispatch.yml@main
    secrets:
      ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
      ANTHROPIC_BASE_URL: ${{ secrets.ANTHROPIC_BASE_URL }}
      PAT_TOKEN: ${{ secrets.PAT_TOKEN }}
      FEISHU_WEBHOOK_TOKEN: ${{ secrets.FEISHU_WEBHOOK_TOKEN }}

  # 评论 /impl 或 ok 时实现代码
  implement:
    if: github.event_name == 'issue_comment' && github.event.issue.pull_request == null
    uses: Lightspeed-Intelligence/agentic-workflow-template/.github/workflows/implement.yml@main
    secrets:
      ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
      ANTHROPIC_BASE_URL: ${{ secrets.ANTHROPIC_BASE_URL }}
      PAT_TOKEN: ${{ secrets.PAT_TOKEN }}
      FEISHU_WEBHOOK_TOKEN: ${{ secrets.FEISHU_WEBHOOK_TOKEN }}

  # 评论 /ask 或 /q 时回答问题
  question:
    if: github.event_name == 'issue_comment' && github.event.issue.pull_request == null
    uses: Lightspeed-Intelligence/agentic-workflow-template/.github/workflows/question.yml@main
    secrets:
      ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
      ANTHROPIC_BASE_URL: ${{ secrets.ANTHROPIC_BASE_URL }}
      PAT_TOKEN: ${{ secrets.PAT_TOKEN }}
      FEISHU_WEBHOOK_TOKEN: ${{ secrets.FEISHU_WEBHOOK_TOKEN }}

  # PR 创建/更新时自动审查
  pr-review:
    if: github.event_name == 'pull_request'
    uses: Lightspeed-Intelligence/agentic-workflow-template/.github/workflows/pr-review.yml@main
    secrets:
      ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
      ANTHROPIC_BASE_URL: ${{ secrets.ANTHROPIC_BASE_URL }}
      PAT_TOKEN: ${{ secrets.PAT_TOKEN }}
      FEISHU_WEBHOOK_TOKEN: ${{ secrets.FEISHU_WEBHOOK_TOKEN }}
```

### 4. 配置 CLAUDE.md

在目标仓库根目录创建 `CLAUDE.md`，参考 `CLAUDE.md.example`。

## 工作流

| 工作流           | 触发条件              | 功能                                                          |
| ---------------- | --------------------- | ------------------------------------------------------------- |
| `issue-dispatch` | Issue 创建/打标签     | 根据标签分发到 bug-analyze / feature-review / answer-question |
| `implement`      | 评论 `/impl` 或 `ok`  | 实现代码并创建 PR                                             |
| `question`       | 评论 `/ask` `/q` `/?` | 回答技术问题                                                  |
| `pr-review`      | PR 创建/更新          | 代码审查，支持增量审查                                        |

## Skills

| Skill             | 描述     | 输出                           |
| ----------------- | -------- | ------------------------------ |
| `github-comment`  | 基础规范 | 定义评论格式、折叠、链接       |
| `bug-analyze`     | Bug 分析 | 根因定位 + 自动修复 (简单 bug) |
| `feature-review`  | 需求评审 | 成本估算 + 影响分析 (面向产品) |
| `implement`       | 代码实现 | 创建分支 + PR                  |
| `pr-review`       | PR 审查  | 高信号问题 + 增量审查          |
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

# issue-dispatch.yml / pr-review.yml
inputs:
  use_feishu_notify: true
```

### Secrets

| Secret                 | 必需 | 描述                                        |
| ---------------------- | ---- | ------------------------------------------- |
| `ANTHROPIC_API_KEY`    | ✅   | Anthropic API Key                           |
| `ANTHROPIC_BASE_URL`   | ❌   | 自定义 API 端点 (代理/私有部署)             |
| `PAT_TOKEN`            | ❌   | Personal Access Token (私有 submodule 访问) |
| `FEISHU_WEBHOOK_TOKEN` | ❌   | 飞书机器人 Webhook Token                    |

## 目录结构

```
.
├── .github/
│   ├── workflows/           # 可复用工作流
│   │   ├── issue-dispatch.yml
│   │   ├── implement.yml
│   │   ├── question.yml
│   │   └── pr-review.yml
│   └── actions/
│       └── feishu-notify/   # 飞书通知 Action
├── .claude/
│   └── skills/              # Claude Skills
│       ├── github-comment/  # 基础规范
│       ├── bug-analyze/
│       ├── feature-review/
│       ├── implement/
│       ├── pr-review/
│       └── answer-question/
├── scripts/                 # Submodule 管理脚本
│   ├── init.sh
│   ├── status.sh
│   └── update-all.sh
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
  "cost": "small | medium | large | extra-large | n/a" // feature only
}

// implement
{
  "description": "实现结果摘要",
  "status": "success | failed | blocked",
  "branch_name": "feat/vast-github-bot/xxx",
  "pr_number": 123,
  "pr_url": "https://..."
}

// pr-review
{
  "description": "审查结论摘要",
  "conclusion": "APPROVE | REQUEST_CHANGES | COMMENT",
  "critical_count": 0,
  "important_count": 1,
  "suggestion_count": 2
}

// question
{
  "description": "回答内容摘要"
}
```

## Submodule 支持

对于聚合多个子项目的仓库：

1. 改动只影响 submodule → 只在 submodule 内提交
2. 影响多个 submodule → 每个独立 PR，评论汇总链接
3. 读取各 submodule 的 `llmdoc/` 理解上下文

```bash
# 初始化
./scripts/init.sh

# 查看状态
./scripts/status.sh

# 更新所有
./scripts/update-all.sh
```

## 分支命名

- 功能: `feat/vast-github-bot/{short-description}`
- 修复: `fix/vast-github-bot/{short-description}`

## 注意事项

1. **llmdoc 优先** - Agent 会先读取 `llmdoc/` 理解项目
2. **评论折叠** - 长内容使用 `<details>` 折叠
3. **增量审查** - PR 审查会记录 commit SHA，支持增量
4. **高信号** - 只标记确定的问题，避免误报
