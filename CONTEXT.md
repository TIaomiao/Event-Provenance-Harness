# 当前研究上下文

更新：2026-09-11。用途：统一研究定位与当前决策。所有日常状态先看 [CONTROL_PANEL](CONTROL_PANEL.md)。

## 研究定位

- 目标：利用真实 EHR 数据推进首篇计算机方向会议论文，仍暂定 KDD 2027 Cycle 2；本次用户未补充具体日期、赛道及 MICAD 备选窗口。
- 主贡献方向：2026-09-11 用户转述师兄已确认“事件表示 + 查询 Harness”；执行评测作为验证支撑。方向确认不等于方法有效性或创新性已经建立。
- 第一轮实验：重复检验的值—时间—来源匹配。任务已选，方法与评价细节见 [研究卡](RESEARCH_CARD.md)。
- 方法细节、任务覆盖和投稿安排随实验与沟通继续完善。
- 用户为大二、首次写论文。师兄提供 idea 与参考，用户推进设计和实现；解释用具体例子，逐步建立理解。

## 当前决策

- 本地是唯一研究主工作区，A/B/C 与 Windows DSH 读取同一目录；通过 SSH 执行获准的 Larry 实验。当前为 A 总控 + B/C/DSH 三个子 session。
- 复用现有 OCR/bbox、标准试卷、事件表和模型接口。首轮选择原文明示、可直接核对的事实，临床歧义按需要请教医生。
- 先用相同模型、证据和可比预算比较候选流程，分别报告质量与成本。正式方法和协议由总控 A 汇总。
- 当前优先推进 B 的时间角色/行绑定与 C 的合成评分器，按 [研究卡 v0.3](RESEARCH_CARD.md) 中共享口径 v0.1 并行工作；参考答案由人独立核对。主轴确认后可直接推进这些工作。
- 本对话承担论文 Proposal 总控：维护 [paper/PROPOSAL.md](paper/PROPOSAL.md)，吸收 DSH/其他 Codex 对话的有效结论，决定何时更新研究卡和实验协议。

## 状态与证据入口

- 工程进度：[implementation](status/implementation.md)；步骤与验证细节：[工程计划](ENGINEERING_PLAN.md)。
- 评测进度：[evaluation](status/evaluation.md)；实际指标与报告：[results](results/README.md)。
- 文献理解和候选建议：[discussion_notes](discussion_notes.md)；下一项研究设计任务：[idea 交接](RESEARCH_IDEA_HANDOFF.md)。

讨论记录保留作者当时的理解。用于方法决策或论文引用时，需核查原文；摘要检索未命中某种组合不足以确认研究缺口。
