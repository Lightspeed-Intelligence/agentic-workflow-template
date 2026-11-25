> 初版设计草稿，只作历史记录。分支命名、自动修复、审查范围等内容已经过时；
> 现行行为以 `.github/workflows/`、`.claude/skills/` 和 `llmdoc/` 为准。

### skills

1. bug-analyze 用来做深度的 bug 检查, 并且自动修复一些简单的 bug, 能够自动修复的 bug 会创建一个 PR, 分支的名称 fix/vast-github-bot/{short-description}
2. implement 根据上github issue comment 区的讨论, 实现代码, 创建 PR, 分支的名称 feat/vast-github-bot/{short-description}
3. feature-review: 像是需求评审一样, 回答问题或者回答提问(比如xxx的成本，xxx是否支持):

   > 需要注意这个 comment 是给产品看的, 所以需要注意输出的语言要更加业务向, 而不是技术向
   - 估时间
   - PRD 提问
   - 影响半径 (包括线上的功能)
   - 开发的主要难点

4. pr-review: 自动 review PR；每次覆盖完整 `base...head` diff，不查询或依赖历史评论状态，Agent 只生成评论正文，由独立发布步骤代发
5. answer-question: 如果并不是需求, 也不是 bug, 那么就回答问题, 例如回答用户咨询, 回答用户提问, 回答用户技术探讨, 最通用的模式, 方案调研的时候应该也是用这个skill
6. github-comment: 强调在 issue/ pr 中 comment 的时候要考虑可读性, 应该进行折叠
7. 在 任何情况下, 如果 impl 或者在 issue 中完成了修复, 那么应该及时关闭 issue

### github action

1. issue-dispathch: 根据 issue 的 tag, 调用不同的 skill, 例如 bug-analyze, feature-review, answer-question
2. implement: 如果用户评论 `/impl` 或者 "ok, OK, Ok, oK", 那么就调用 implement skill, 自动实现代码, 并且推送到对应仓库中
3. pr-review: 自动 review PR；每次覆盖完整 `base...head` diff，不把历史评论作为审查状态
4. question: 如果用户评论 `/ask , /question, /q , /?`, 那么就调用 question skill, 根据上下文回答问题

同时需要注意, 如果存在 submodule 的情况下, 如果改动只影响了 submodule, 那么在 commit的时候, 只需要提交 submodule 的改动, 而不是整个仓库的改动

如果存在存在多个 submodule 都修改并且 pr 的情况, 那么应该在 comment 中应该附上 PR 的链接和简易描述

需要注意 llmdoc 的读取读取, 因为有可能是聚合的 submodule 的 repo, 所以在修改某个 repo 的时候应该注意这些 submodule 的 llmdoc
