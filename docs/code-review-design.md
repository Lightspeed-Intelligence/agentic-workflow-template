# AI Code Review 系统是怎么跑起来的

> 写给不了解背景的同事，帮你在 10 分钟内搞清楚这套东西做了什么、怎么做的。

## 一句话说清楚

我们在 GitHub 上接了一个 AI（Claude），让它像团队成员一样自动帮忙干活：PR 提上去它自动审代码，Issue 建出来它自动分析，评论里喊一声 `/impl` 它还能直接写代码交 PR。

本文主要讲 **Code Review** 这部分。

---

## 先看效果

一个典型的流程：

```mermaid
sequenceDiagram
    participant Dev as 开发者
    participant GH as GitHub
    participant CI as GitHub Actions
    participant AI as Claude (AI)
    participant FS as 飞书群

    Dev->>GH: 提交 PR
    GH->>CI: 触发 pull_request 事件
    CI->>AI: 启动 Claude Code Action
    AI->>GH: 读取 PR diff + 代码
    AI->>AI: 按 Skill 规则审查
    AI->>GH: 发表审查评论
    AI->>CI: 返回结构化 JSON
    CI->>FS: 推送飞书通知卡片
```

你不需要 @任何人，不需要手动操作，PR 一提就自动跑。

---

## 整体架构

系统分两层：**模板仓库**（提供能力）和 **业务仓库**（使用能力）。

```mermaid
graph TB
    subgraph biz["业务仓库 (tipsy-backend 等)"]
        ci["ci.yml<br/>唯一需要的配置文件"]
        skills[".claude/skills/*<br/>AI 的工作手册"]
    end

    subgraph tpl["模板仓库 (agentic-workflow-template)"]
        subgraph wf["Reusable Workflows"]
            pr["pr-review.yml"]
            dispatch["issue-dispatch.yml"]
            impl["implement.yml"]
            q["question.yml"]
        end
        subgraph actions["Composite Actions"]
            feishu["feishu-notify/"]
        end
    end

    ci -->|"uses: ...@main<br/>远程调用"| wf

    style biz fill:#e8f4f8,stroke:#2196F3
    style tpl fill:#fff3e0,stroke:#FF9800
```

为什么这么拆？因为你不想在每个仓库里都维护一套 workflow。**模板仓库改一次，所有接入的业务仓库立刻生效。**

业务仓库只需要做两件事：
1. 放一个 `ci.yml` 当路由入口
2. 放一套 `.claude/skills/` 告诉 AI 该怎么干活

---

## 事件路由：ci.yml 做了什么

`ci.yml` 是整个系统的入口——**根据 GitHub 事件类型，分发到不同的 workflow**：

```mermaid
flowchart LR
    GH["GitHub 事件"] --> PR["pull_request<br/>opened / synchronize / reopened"]
    GH --> IS["issues<br/>opened"]
    GH --> IC["issue_comment<br/>created"]

    PR --> review["pr-review.yml<br/>自动审查代码"]
    IS --> dispatch["issue-dispatch.yml<br/>分析 Issue 类型"]
    IC --> kw{"评论内容?"}
    kw -->|"/impl 或 ok"| implement["implement.yml<br/>写代码提 PR"]
    kw -->|"/ask 或 /?"| question["question.yml<br/>回答技术问题"]

    style review fill:#c8e6c9,stroke:#4CAF50
    style dispatch fill:#e1bee7,stroke:#9C27B0
    style implement fill:#bbdefb,stroke:#2196F3
    style question fill:#fff9c4,stroke:#FFC107
```

对应的路由逻辑：

```yaml
# PR 事件 → 代码审查
pr-review:
  if: github.event_name == 'pull_request'

# Issue 新建 → 自动分析（Bug? 需求? 问题?）
issue-dispatch:
  if: github.event_name == 'issues'

# Issue 下评论 → 看关键词决定干什么
implement:
  if: github.event_name == 'issue_comment'  # 匹配 /impl, ok 等
question:
  if: github.event_name == 'issue_comment'  # 匹配 /ask, /? 等
```

---

## Code Review 的详细流程

这是本文重点。当一个非 Draft 的 PR 被 opened / synchronize / reopened 时，审查流程启动：

```mermaid
flowchart TD
    A["Step 1: Checkout<br/>拉取完整代码 (fetch-depth: 0)<br/>包括 submodule，用 PAT_TOKEN 跨仓库"]
    B["Step 2: Claude Code Action<br/>核心步骤，启动 AI 审查"]
    C["Step 3: 输出到 GitHub Step Summary<br/>JSON 写到 Action 日志页"]
    D["Step 4: 解析结果，映射通知状态<br/>APPROVE → 绿 / REQUEST_CHANGES → 红 / COMMENT → 蓝"]
    E["Step 5: 飞书通知<br/>发卡片到群里，带颜色和 PR 链接"]

    A --> B --> C --> D --> E

    style B fill:#fff3e0,stroke:#FF9800,stroke-width:2px
```

其中 **Step 2** 是 AI 实际干活的地方，内部逻辑如下：

```mermaid
flowchart TD
    start["接收 PR 信息<br/>(编号、标题、作者)"]
    load["加载 pr-review Skill<br/>(.claude/skills/pr-review/SKILL.md)"]
    check["gh pr view --comments<br/>查找历史审查评论"]
    found{"找到<br/>审查截止: sha ?"}
    full["首次审查<br/>gh pr diff (全量)"]
    incr["增量审查<br/>git diff {sha}..HEAD"]
    review["逐文件审查代码<br/>标记高信号问题"]
    comment["gh pr comment<br/>发表审查评论<br/>(嵌入本次截止 SHA)"]
    json["返回结构化 JSON"]

    start --> load --> check --> found
    found -->|"没找到"| full
    found -->|"找到了"| incr
    full --> review
    incr --> review
    review --> comment --> json

    style found fill:#fff9c4,stroke:#FFC107
    style review fill:#c8e6c9,stroke:#4CAF50
```

Claude 可以使用的工具有严格的白名单：

| 工具 | 用途 | 权限性质 |
|------|------|----------|
| `gh pr comment` | 发表 PR 评论 | 写（仅评论） |
| `gh pr diff` / `gh pr view` | 查看 PR 信息 | 只读 |
| `Read` / `Glob` / `Grep` | 读取仓库代码 | 只读 |
| `Task` / `Skill` | 调用子能力 | 内部 |

注意：**没给 Write 和 Edit 权限**——审查时 AI 只能看、不能改你的代码。

---

## 增量审查是怎么实现的

这个设计比较巧妙，值得单独讲。

**问题**：一个 PR 可能连续 push 好几次，你不希望每次都从头审一遍。

**方案**：用 PR 评论当"状态存储"——每次审查完在评论里记录一个 commit SHA，下次只 diff 这个 SHA 之后的新改动。

```mermaid
sequenceDiagram
    participant Dev as 开发者
    participant AI as Claude

    Note over Dev,AI: 第一次 push
    Dev->>AI: PR opened / synchronize
    AI->>AI: 没找到历史审查记录 → 全量审查
    AI-->>Dev: 评论: "审查截止: aaa111"

    Note over Dev,AI: 第二次 push
    Dev->>AI: PR synchronize
    AI->>AI: 找到 "审查截止: aaa111"
    AI->>AI: git diff aaa111..HEAD (只看新改动)
    AI-->>Dev: 评论: "审查截止: bbb222"

    Note over Dev,AI: 第三次 push
    Dev->>AI: PR synchronize
    AI->>AI: 找到 "审查截止: bbb222"
    AI->>AI: git diff bbb222..HEAD
    AI-->>Dev: 评论: "审查截止: ccc333"
```

没有额外的数据库、没有外部存储，就靠 PR 评论里的一行文本实现了状态跟踪。简单但有效。

另外，`use_sticky_comment: true` 这个配置保证 Claude 在同一个 PR 里只维护一条评论（更新而非新建），PR 的评论区不会被刷屏。

---

## Skill 系统：AI 的"工作手册"

Claude 不是裸跑的，它的行为受 `.claude/skills/` 目录下的 Markdown 文件约束。你可以把 Skill 理解成给 AI 写的 SOP（标准作业流程）。

```mermaid
graph TD
    base["github-comment/SKILL.md<br/>基础规范：语言、格式、链接"]

    pr["pr-review/SKILL.md<br/>审查规则 + 输出模板"]
    bug["bug-analyze/SKILL.md<br/>Bug 分析规则"]
    feat["feature-review/SKILL.md<br/>需求评审规则"]
    impl["implement/SKILL.md<br/>代码实现规则"]
    qa["answer-question/SKILL.md<br/>通用问答规则"]

    base --> pr
    base --> bug
    base --> feat
    base --> impl
    base --> qa

    style base fill:#e8eaf6,stroke:#3F51B5,stroke-width:2px
```

以 `pr-review` Skill 为例，它规定了几件事：

**该标记的（高信号问题）：**
- 语法错误、类型错误、缺少 import
- 不管输入是什么都一定会出错的逻辑 bug
- 违反了某个明确规范（且能引用该规范）

**不该标记的（误报来源）：**
- PR 改动前就存在的老问题
- "有可能出问题"但需要特定条件才会触发的
- 主观的"我觉得这样写更好"
- Linter 已经能抓的

一句话原则：**拿不准就别标。误报一多，大家就不看了。**

输出模板也是固定的——三级问题用折叠块展示：

```mermaid
graph LR
    R["🔴 阻塞问题<br/>不改不能合"] --> O["🟠 重要建议<br/>强烈建议改"] --> G["🟢 小问题<br/>改不改都行"]

    style R fill:#ffcdd2,stroke:#f44336
    style O fill:#ffe0b2,stroke:#FF9800
    style G fill:#c8e6c9,stroke:#4CAF50
```

---

## 结构化输出：JSON 驱动下游

Claude 的审查结果不只是一段评论文本，还有一份结构化 JSON：

```json
{
  "conclusion": "APPROVE",
  "description": "代码良好，发现2个小问题",
  "critical_count": 0,
  "important_count": 1,
  "suggestion_count": 2
}
```

这个 JSON 通过 `--json-schema` 参数在调用时约束，Claude 必须按格式输出。有了结构化数据，后续的通知和状态判断都能自动处理，不用去解析自然语言。

```mermaid
flowchart LR
    AI["Claude 输出 JSON"] --> summary["GitHub Step Summary<br/>(给人看的日志)"]
    AI --> jq["shell 脚本 jq 解析"]
    jq --> color["conclusion → 卡片颜色"]
    jq --> desc["description → 卡片正文"]
    jq --> count["*_count → 问题统计"]
    color --> feishu["飞书群通知"]
    desc --> feishu
    count --> feishu

    style AI fill:#fff3e0,stroke:#FF9800
    style feishu fill:#c8e6c9,stroke:#4CAF50
```

---

## 飞书通知

飞书通知用一个 Composite Action（`feishu-notify`）封装，所有 workflow 共用。它干的事很简单——根据状态拼一张飞书卡片 JSON，curl 发到 Webhook：

```mermaid
flowchart LR
    input["输入:<br/>title / description<br/>link_url / status"]
    color{"status?"}
    green["✅ success → 绿色"]
    red["❌ error → 红色"]
    orange["⚠️ warning → 橙色"]
    blue["ℹ️ info → 蓝色"]
    card["拼飞书卡片 JSON"]
    send["curl POST → 飞书 Webhook"]

    input --> color
    color --> green --> card
    color --> red --> card
    color --> orange --> card
    color --> blue --> card
    card --> send

    style green fill:#c8e6c9,stroke:#4CAF50
    style red fill:#ffcdd2,stroke:#f44336
    style orange fill:#ffe0b2,stroke:#FF9800
    style blue fill:#bbdefb,stroke:#2196F3
```

---

## 权限和安全

```mermaid
graph TD
    subgraph tokens["Token 分工"]
        gt["GITHUB_TOKEN (自动)<br/>当前仓库范围内的默认操作"]
        pat["PAT_TOKEN (手动配置)<br/>跨仓库 checkout + 推送代码"]
        ak["ANTHROPIC_API_KEY<br/>调用 Claude API"]
        fw["FEISHU_WEBHOOK_TOKEN<br/>发飞书通知"]
    end

    subgraph review_perm["Code Review 时 Claude 的权限"]
        read["✅ 读代码 (Read/Glob/Grep)"]
        ghpr["✅ 操作 PR (comment/diff/view)"]
        write["❌ 写文件 (Write/Edit)"]
        push["❌ 推送代码 (git push)"]
    end

    style write fill:#ffcdd2,stroke:#f44336
    style push fill:#ffcdd2,stroke:#f44336
    style read fill:#c8e6c9,stroke:#4CAF50
    style ghpr fill:#c8e6c9,stroke:#4CAF50
```

**审查时 AI 是只读的**，不可能意外改动你的代码。

---

## 新仓库接入清单

给一个新仓库接入这套能力，只需要三步：

```mermaid
flowchart TD
    A["1️⃣ 配置 Secrets<br/>GitHub 仓库 Settings → Secrets<br/>添加 ANTHROPIC_API_KEY / PAT_TOKEN 等"]
    B["2️⃣ 添加 ci.yml<br/>复制到 .github/workflows/<br/>改一下远程引用路径即可"]
    C["3️⃣ 复制 Skills<br/>将 .claude/skills/ 目录放到仓库根目录<br/>AI 运行时需要读这些工作手册"]
    D["🎉 完成<br/>不需要装任何依赖<br/>不需要改项目代码<br/>纯配置，PR 一提就自动审查"]

    A --> B --> C --> D

    style D fill:#c8e6c9,stroke:#4CAF50,stroke-width:2px
```

---

## 不只是 Code Review

虽然本文聚焦 Code Review，但同一套架构还支撑了其他几个能力：

```mermaid
flowchart TD
    subgraph issue_created["Issue 被创建"]
        ic_event["issues: opened"]
        ic_dispatch["issue-dispatch.yml"]
        ic_event --> ic_dispatch
        ic_dispatch --> bug["🐛 bug-analyze<br/>分析根因、评估严重程度<br/>简单 bug 直接提修复 PR"]
        ic_dispatch --> feat["📋 feature-review<br/>评估业务价值、预估成本<br/>列出技术风险和待澄清问题"]
        ic_dispatch --> ans1["💬 answer-question<br/>当一般咨询处理"]
    end

    subgraph issue_comment["Issue 下有人评论"]
        comment_event["issue_comment: created"]
        comment_event --> impl_kw{"/impl 或 ok"}
        comment_event --> ask_kw{"/ask 或 /?"}
        impl_kw --> impl["⚡ implement<br/>读 Issue 讨论，写代码，提 PR"]
        ask_kw --> ans2["💬 answer-question<br/>基于代码库回答问题"]
    end

    subgraph pr_event["PR 被创建或更新"]
        pr_trigger["pull_request:<br/>opened / synchronize / reopened"]
        pr_trigger --> review["🔍 pr-review<br/>自动审查代码质量"]
    end

    style review fill:#c8e6c9,stroke:#4CAF50,stroke-width:2px
    style bug fill:#ffcdd2,stroke:#f44336
    style feat fill:#e1bee7,stroke:#9C27B0
    style impl fill:#bbdefb,stroke:#2196F3
```

---

## 总结

几个关键的设计决策：

- **模板仓库 + Reusable Workflow** — 改一处，全局生效，多仓库接入成本极低
- **Skill = Markdown SOP** — AI 的行为规则以 Markdown 定义，任何人都能读懂和修改
- **评论里存状态** — 增量审查不需要外部存储，靠 commit SHA 串联上下文
- **结构化输出** — JSON Schema 让 AI 的结果可编程，驱动通知和统计
- **最小权限** — 审查时 AI 只能读、不能写，避免意外修改
- **高信号策略** — 宁可漏报也不误报，维护团队对自动审查的信任
