# EHR Harness 论文工作区

本目录是用户确认的论文唯一主工作区，适用于本地 Codex 与 Windows DSH。父级 G:/Intern/AGENTS.md 的跨任务规则继续生效。

## 称呼约定

- 在本研究项目中称呼用户为“w”。该称呼用于确认本项目规则已被读取；其他项目不自动沿用此约定。

## 工作目标

帮助大二、首次写论文的用户推进计算机方向会议论文。研究主轴为事件表示与查询 Harness；重复检验与时间匹配是首轮实验入口，方法效果和创新性依据后续证据判断。先读总控面板，再按角色读取 RESEARCH_CARD.md 与状态文件。

## 分工与文件归属

- 总控 A：研究卡、协议、文献解释、实验决策和汇报。
- 原型 B：src/prototype/ 及该目录测试，更新 status/implementation.md。
- 评测 C：src/evaluation/ 及该目录测试，更新 status/evaluation.md。
- DSH：读论文与讨论，更新 discussion_notes.md；正式协议变更由 A 汇总。
- B/C 遇到共享接口分歧，先给出合成例子和建议，由 A 统一版本。不要同时修改同一文件。

## 数据与执行

- 本地保存研究资料、开发代码、合成样例、实验配置和允许回传的匿名聚合结果。
- 原始 PDF、OCR/病历正文、身份映射及含患者内容的参考答案留在 Larry 受控环境；不要整目录同步运行产物、虚拟环境或私有状态。
- 所有 session 可以在本地工作，通过 SSH 执行获准的服务器命令，不依赖服务器 Codex 会话。
- 新研究代码在本地维护；在服务器运行前发布明确版本到独立运行目录，记录版本与配置。现有 EHR 工程继续作为服务器数据与处理基础，按需复用接口。
- 服务器操作遵守目标目录规则，不把本地研究授权扩展为全量 OCR、数据外发、服务重启或生产修改授权。
- Codex/DSH 的编程模型与论文实验模型分别配置；临床模型的供应商、数据范围和费用按实际执行授权处理。

## 验证与版本

- 参考答案需独立核对；开发样例与独立测试病例分开。报告失败、额外生成、时间关联错误和实际成本。
- 每个工作单元更新本角色状态：协议版本、完成事项、验证证据、阻塞、下一步。只写匿名摘要。
- 状态文件采用“当前快照 + 历史归档”结构：B 只更新 `status/implementation_current.md`，C 只更新 `status/evaluation_current.md`；每个快照控制在约 30–50 行，保留当前协议、最新结果、阻塞和下一步。完整工作单元记录追加到对应的 `*_history.md`，不要继续把长日志追加到旧的 `implementation.md` 或 `evaluation.md`。A 需要追溯历史时再读取归档。
- 本地 Git 管理研究代码与资料，禁止自动 push。提交前检查敏感内容与非本任务修改。
- archive/ 保存归集前快照，仅供历史追溯；当前安排以根目录文档为准。
- README.md 只维护入口，RESEARCH_CARD.md 维护首轮协议，status/ 维护角色进度，results/ 保存证据。其他文档通过链接引用状态，避免重复维护数值与阶段。
- 2026-09-15 归档：CONTEXT.md、ENGINEERING_PLAN.md、RESEARCH_IDEA_HANDOFF.md、SESSION_PROMPTS.md 描述的是"嵌套 harness"那一版方案，内容已过期，整体移入 `archive/legacy_20260915/`。当前安排以 CONTROL_PANEL.md + RESEARCH_CARD.md + paper/PROPOSAL.md 为准，不要从归档文档判断现状。
- CONTROL_PANEL.md 是日常总控面板：列出论文方向、当前实验、阅读队列、session 状态、阻塞点和下一步。所有 session 开始先读它，并在完成工作单元后更新自己负责的面板行；详细证据仍放对应状态/结果文件。
- 总控面板优先读取 `status/implementation_current.md` 和 `status/evaluation_current.md`；状态快照更新后，B/C 必须同步更新自己负责的面板行和 dashboard.html 最近事件，避免面板沿用旧状态。
- dashboard.html 是 CONTROL_PANEL.md 的本地可视化入口；面板中的数字和状态只允许来自当前 Markdown 状态/结果文件。更新研究状态时同步检查页面是否仍与总控一致。
- 子 session 的推进必须回写到可视化面板：完成工作单元后，先更新自己的 `status/` 或 `discussion_notes.md`，再同步 `CONTROL_PANEL.md` 的对应行和 `dashboard.html` 的“最近事件/状态”内容；有价值的新机制、反例或决策也要补入面板入口或关联文档，不能只留在聊天记录里。
- GITHUB_REPO_PLAN.md 记录论文仓库边界、脱敏规则和发布节奏。建议建立独立私有 GitHub 仓库，但远端未创建前不得假定已发布；任何 push、开源或邀请协作者都要先做敏感内容检查并遵守单位/医院政策。
- paper/PROPOSAL.md 是论文 Proposal 的唯一当前正文入口；本地总控对话负责吸收其他对话和 DSH 的结论，避免多个 Proposal 版本并行漂移。
- 阅读按 discussion_notes.md 的已有进展接续。references/ 是按需材料，archive/ 是历史；不默认递归载入。

解释用简体中文和具体例子；未知信息明确标注。让用户亲自理解代表错误与比较结果，工具接线交由 Codex 执行。
