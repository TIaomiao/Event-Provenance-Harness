# EHR Harness 论文工作区

研究方向：面向真实 EHR 的 Data Agent Harness，目标仍暂定 KDD 2027 Cycle 2。用户于 2026-09-11 转述师兄已确认“事件表示 + 查询 Harness”主轴；首轮实验为重复检验的值—时间—来源匹配，B/C 按研究卡中的共享口径并行推进。

## 日常入口

1. **先看总状态**：[CONTROL_PANEL](CONTROL_PANEL.md)。
2. **可视化总控**：[dashboard.html](dashboard.html)，浏览器直接打开即可。
3. **在线总控**：启用 GitHub Pages 后访问 `https://tiaomiao.github.io/Event-Provenance-Harness/`；每次推送到 `main` 会自动更新。
4. **做什么**：[论文 Proposal](paper/PROPOSAL.md) 和 [研究卡](RESEARCH_CARD.md)。
5. **做到哪里**：[实现进度](status/implementation.md)、[评测进度](status/evaluation.md)。

新开任务使用 [开场说明](archive/legacy_20260915/SESSION_PROMPTS.md)。

每个子 session 完成后，先更新自己负责的状态文件，再同步 [CONTROL_PANEL](CONTROL_PANEL.md) 和 [可视化面板](dashboard.html)；新的反例、决策和可复现证据挂到对应文档并从面板链接进入。

## 按需查阅

- 研究设计：[文献与 idea 交接](archive/legacy_20260915/RESEARCH_IDEA_HANDOFF.md)。
- 工程细节：[工程计划](archive/legacy_20260915/ENGINEERING_PLAN.md)，代码在 `src/`，验证证据在 `results/`。
- 对外沟通：[微信消息草稿](paper/2026-09-08_wechat_draft.md)。
- 当前 KDD idea：[三轮打磨后的候选版本](paper/KDD_IDEA_REVIEWED_2026-09-08.md)；日常以 [Proposal](paper/PROPOSAL.md) 为准。
- 论文与阅读卡：[论文阅读包](D:/UESTC/科研/论文/26.7-/EHR_Harness_论文阅读包)；项目内 [DataSpace 初读卡](references/READING_DATASPACE.md)供复习。
- 历史资料：[归档索引](archive/README.md)。

本地维护代码、协议和允许回传的匿名结果；Larry 保存受控数据与实验运行，zian 保存会议归档。进度以 `status/` 的更新日期和关联证据为准。
