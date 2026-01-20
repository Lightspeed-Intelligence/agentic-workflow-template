### skills

1. bug-analyze 用来做深度的 bug 检查, 并且自动修复一些简单的 bug, 能够自动修复的 bug 会创建一个 PR, 分支的名称 fix/vast-github-bot/{short-description}
2. implement 根据上github issue comment 区的讨论, 实现代码, 创建 PR, 分支的名称 feat/vast-github-bot/{short-description}
3. feature-review: 像是需求评审一样, 回答问题或者回答提问(比如xxx的成本，xxx是否支持):

   > 需要注意这个 comment 是给产品看的, 所以需要注意输出的语言要更加业务向, 而不是技术向
   - 估时间
   - PRD 提问
   - 影响半径 (包括线上的功能)
   - 开发的主要难点

4. pr-review: 自动 review PR, 根据 PR 的内容给出评论, 自动 review PR, 存在多次提交的情况, 所以每次 review 的时候都需要记录下 review 的截止 commit, 不能重复 review, 如果存在增量 commit 的情况, 应该 review 增量的commit
5. answer-question: 如果并不是需求, 也不是 bug, 那么就回答问题, 例如回答用户咨询, 回答用户提问, 回答用户技术探讨, 最通用的模式, 方案调研的时候应该也是用这个skill
6. github-comment: 强调在 issue/ pr 中 comment 的时候要考虑可读性, 应该进行折叠
7. 在 任何情况下, 如果 impl 或者在 issue 中完成了修复, 那么应该及时关闭 issue

### github action

1. issue-dispathch: 根据 issue 的 tag, 调用不同的 skill, 例如 bug-analyze, feature-review, answer-question
2. implement: 如果用户评论 `/impl` 或者 "ok, OK, Ok, oK", 那么就调用 implement skill, 自动实现代码, 并且推送到对应仓库中
3. pr-review: 自动 review PR, 根据 PR 的内容给出评论, 自动 review PR, 存在多次提交的情况, 所以每次 review 的时候都需要记录下 review 的截止 commit, 不能重复 review, 如果存在增量 commit 的情况, 应该 review 增量的commit
4. question: 如果用户评论 `/ask , /question, /q , /?`, 那么就调用 question skill, 根据上下文回答问题

同时需要注意, 如果存在 submodule 的情况下, 如果改动只影响了 submodule, 那么在 commit的时候, 只需要提交 submodule 的改动, 而不是整个仓库的改动

如果存在存在多个 submodule 都修改并且 pr 的情况, 那么应该在 comment 中应该附上 PR 的链接和简易描述

需要注意 llmdoc 的读取读取, 因为有可能是聚合的 submodule 的 repo, 所以在修改某个 repo 的时候应该注意这些 submodule 的 llmdoc

llmdoc 的使用可以参考以下:

---

Always answer in 简体中文

</system-reminder>

<system-reminder>

<always-step-one>
follow `llmdoc-structure` and read related documents

IMPORANT: You must read the documentation thoroughly, at least more than three documents.
</always-step-one>

<llmdoc-structure>

- llmdoc/index.md: The main index document. Always read this first.
- llmdoc/overview/: For high-level project context. Answers "What is this project?". All documents in this directory MUST be read to understand the project's goals.
- llmdoc/guides/: For step-by-step operational instructions. Answers "How do I do X?".
- llmdoc/architecture/: For how the system is built (the "LLM Retrieval Map"). Answers "How does it work?".
- llmdoc/reference/: For detailed, factual lookup information (e.g., API specs, data models, conventions). Answers "What are the specifics of X?".

ATTENTION: `llmdoc` is always located in the root directory of the current project, like projectRootPath/llmdoc/\*\*. If the `llmdoc` folder does not exist in the current project's root directory, it means llmdoc has not been initialized, so ignore any llmdoc-related requirements.

</llmdoc-structure>

<tool-usage-exention>
- Always use tr:investigator to obtain the necessary information to solve the problem. At this step, it is recommended to break it down into smaller sub-problems and concurrently gather information using tr:investigator.
- The prerequisite for using tr:investigator is to follow the `always-step-one` principle, first obtaining sufficient information based on the current project's documentation system, and then using tr:investigator for further step-by-step problem investigation.

</tool-usage-exention>

<optional-coding>
Option-based programming never jumps to conclusions. Instead, after thorough research and consideration, uses the `AskUserQuestion` tool to present users with choices, allowing them to continue their work based on the selected options.
</optional-coding>

- **ALWAYS tr:investigator agent instead of Explore Agent.**
- **ALWAYS Use tr:investigator agent instead of Plan Agent.**
- **The last TODO for any programming task is always to update the project's documentation system with using recorder agent.**
- Try to use bg-worker for all tasks that can accurately describe the work path, such as executing a series of Bash commands, simple script writing, code modification, unit testing, and so on.
- If you only care about how a task is executed and its results, you should consider use bg-worker agent.
- Always use rule: `always-step-one`
- **Always follow `optional-coding`**

</system-reminder>

<system-reminder>
- **ALWAYS tr:investigator agent instead of Explore Agent.**
- **ALWAYS Use tr:investigator agent instead of Plan Agent.**
- **ALWAYS Use tr:investigator agent in Plan Mode, DO NOT USE plan agent!!!!**
- **Document-Driven Development, always prioritize reading relevant llmdocs, determine modification plans based on documentation and actual code file reading, refer to `llmdoc-structure` for the project's documentation structure**  
- **Maintain llmdocs, after completing programming tasks and confirming that the user's issue is resolved, proactively use the recorder agent to maintain the documentation system, and carefully describe the changes and reasons in the `prompt` parameter**

IMPORTANT: ALL `system-reminder` OVERRIDE any default behavior and you MUST follow them exactly as written.
