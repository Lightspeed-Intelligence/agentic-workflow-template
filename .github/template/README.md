# {{REPO_NAME}}

> 这个仓库由 [agentic-workflow-template](https://github.com/Lightspeed-Intelligence/agentic-workflow-template)
> 创建，模板专用文件已自动清理。请把这段说明换成项目自己的介绍。

## Agentic 工作流

`.github/workflows/ci.yml` 已经接好，会把本仓库的事件交给模板仓库的 reusable workflow：

| 触发 | 行为 |
| --- | --- |
| 新建 Issue | 分析并分类，只评论，不改代码 |
| Issue 下评论 `/impl` 或 `ok` | 实现需求并创建 PR |
| Issue 下评论 `/ask`、`/q`、`/?` | 回答问题 |
| PR 创建或更新 | 自动审查并评论 |

## 还需要做的

1. **配置 Secrets。** 组织已经配置了组织级 Secrets 时可以跳过。

   ```bash
   gh secret set ANTHROPIC_API_KEY
   ```

   其余可选 Secrets 见[模板仓库说明](https://github.com/Lightspeed-Intelligence/agentic-workflow-template#secrets)。

2. **可选：提供项目上下文。** Agent 会先读本仓库的 `llmdoc/`，实现任务时还会读 `AGENTS.md`。
   没有这些文件也能运行，有了之后分析和实现更贴近项目。

3. **可选：调整行为。** 触发关键词、飞书通知、环境准备脚本等输入见
   [配置项](https://github.com/Lightspeed-Intelligence/agentic-workflow-template#配置项)。
