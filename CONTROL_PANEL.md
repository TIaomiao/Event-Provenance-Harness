# EHR Harness 总控面板

更新时间：2026-09-08（Asia/Shanghai）。维护人：本地 Proposal 总控对话 A。

所有 Codex 对话和 Windows DSH 先读本文件。完成工作单元后更新自己负责的行和“最新事件”；详细证据放对应文件。本项目共 4 个逻辑 session，A 同时就是 Proposal 对话，不再另设第五个总控。

可视化入口：[dashboard.html](dashboard.html)；在线入口（启用 GitHub Pages 后）：`https://tiaomiao.github.io/Event-Provenance-Harness/`。GitHub 仓库边界与后续发布节奏见 [GITHUB_REPO_PLAN.md](GITHUB_REPO_PLAN.md)。

## 当前一句话

目标是 KDD 风格计算机会议论文；候选主轴是“事件身份与来源作为纵向 EHR Agent 的数据基座”；首轮实验 E1 是重复检验的值—时间—来源匹配。整篇论文主轴仍待师兄确认。

## 论文定位（与 `paper/PROPOSAL.md` 对齐）

- **当前题目**：Event-Provenance Harness: Query-Conditioned Structuring for Verifiable Analytics over Real-World Longitudinal EHRs。
- **中心命题**：真实纵向 EHR 的难点不是把 PDF 转成 JSON，而是把分散、重复、冲突且时间含义不同的证据组织成带事件身份和来源的可验证记录。
- **Motivation**：值抽取正确并不代表事件关系正确；重复引用、真实复测、采样/报告/记录/文档时间和来源支持必须被单独表达与评估。
- **三项候选创新**：事件身份与时间—来源层、查询驱动且不确定性感知的事件物化、执行锚定的 EHR Harness 与 evaluator。
- **强度边界**：这些仍是候选研究设计；真实模型 A/B、独立评价集、效果和跨任务泛化尚未建立。

## Session 状态

| Session | 入口 | 当前职责 | 状态 | 下一步 |
| --- | --- | --- | --- | --- |
| A 总控 / Proposal | 当前对话，本地 `paper/PROPOSAL.md` | 研究定位、协议版本、跨 session 汇总、师兄汇报 | 进行中 | 维护本面板与 Proposal，决定协议变更 |
| B 原型实现 | 本地 `src/prototype/`，通过 SSH 在 Larry 执行 | 时间角色、事件身份和 Harness 原型 | E1 输入适配部分完成 | 继续日期角色与检验行关联 |
| C 评测 | 本地 `src/evaluation/`，通过 SSH 使用受控答案 | 评分器、参考集、错误与成本 | 尚未启动 | 先写合成评分器和边界例子 |
| DSH 文献讨论 | Windows DSH，本地工作区 | 读论文、核对趋势、提出机制建议 | 已完成 DataSpace 与一轮 KDD 相关调研 | 补最近邻全文位置，更新讨论行 |

## 论文阅读队列

| 优先级 | 材料 | 状态 | 下一步产出 |
| --- | --- | --- | --- |
| P0 | DataSpace | 首轮阅读完成，部分设置已复核 | 写出可复用评分和公平对照规则 |
| P0 | HealthFlow | 已有论文与阅读卡 | 提炼计划/执行/评估边界 |
| P0 | ClinLens、HealthAgentBench、EHR-Complex | 已核验摘要/API | 选 2 篇读全文，核对与 E1 的真正重合 |
| P1 | Agentic Context Cracking、Harness-Bench、The Harness Effect | 已核验摘要/API | 比较查询物化、预算和 Harness 效应 |
| P1 | ACIE、ClinTraceBench、TrajOnco、EHR 文档不一致检测 | 已核验摘要/API | 补事件、时间、来源和冲突评测差异 |
| P2 | APOLLO、PAI | 已有本地 PDF | 等主轴确定后按需阅读 |
| 待核 | AirVx、OneEHR、U-EHR | DSH 线索未完成一手核验 | 向师兄索取全名或链接 |

## 实验队列

| 编号 | 实验 | 目的 | 状态 | 依赖 |
| --- | --- | --- | --- | --- |
| E0 | 合成事件与评分器 | 固定值/时间/来源/副本/冲突口径 | 待 C 开始 | 研究卡 v0.2 |
| E1 | 重复检验值—时间—来源匹配 | 首轮验证事件身份机制 | 输入适配部分完成 | E0、日期角色与行绑定 |
| E2 | 查询驱动事件物化 | 测质量—成本和跨任务复用 | 待定 | E1 机制成立 |
| E3 | 主实验与消融 | 判断收益来自哪个环节 | 待定 | 独立参考集和固定预算 |
| E4 | 分层稳健性 | 长度、重复、时间歧义、OCR 质量 | 待定 | E3 |

## 当前阻塞点

1. 时间候选还没有完成采样/报告/记录角色和检验行绑定。
2. 评测器与独立参考集尚未建立，当前不能报告模型效果。
3. 论文主轴和“多时序、模型层、protocol”的具体含义待师兄确认。
4. KDD 目标届次与投稿时间待核对；KDD 2026 公开投稿周期已结束。

## 已完成证据

- 时间候选适配器 v0.3.1：Windows/Linux 各 23 项合成测试，两例开发样本，26 文档/187 页，952 个候选；源文件未修改，未调用外部模型。
- DataSpace、ClinLens、HealthFlow 等公开论文/项目已建立初步对照；正式差异仍需最近邻全文核验。
- Proposal 候选已收敛为事件身份层、查询驱动物化和执行评测三点；效果与新颖性尚未证实。

## 数据优势与边界

- inventory 记录约 39,560 个病例目录、462,789 份 PDF；这是文件系统规模，不能直接等同独立患者数、事件数或科研可用样本数。
- 可区分度来自原始医院 PDF 的版式/OCR/bbox、跨文档重复与真实复测、时间角色混杂和来源可回溯；不是“数据多”或“用了多 Agent”本身。
- 主要对照数据源：MIMIC/EHRSHOT/UKB 结构化 EHR、MedAgentBench FHIR/虚拟 EHR、DataSpace/FDABench 渲染 benchmark，以及 HealthFlow/ClinLens/ClinTraceBench/EHR-Complex 的纵向 Agent 任务。
- 需要补的可公开统计：独立患者数、文档/事件数、时间跨度、重复率、时间歧义率、OCR 质量分层和可评价病例数。

## 本周最小完成标准

- 用户能用三分钟讲清 Proposal 的一句话主张、E1 任务和一个反驳例子。
- C 有合成评分器草案；B 有日期角色/检验行关联的接口建议。
- 面板更新一次 B/C 状态，保留一项需要师兄决定的问题。

## 用户学习动作

- 每篇论文只记输入、输出、机制、评价四项；优先读 DataSpace、HealthFlow、ClinLens/ClinTraceBench 的方法与 evaluator。
- 每读一项机制，写一个纯合成事件例子；再让 Codex/DSH 解释代码如何实现和评分。
- 每周口头复述一次：一句主张、一个反例、一项实验、一个待师兄判断的问题。

## 面板更新规则

- A 更新论文定位、协议版本、实验/阅读队列和师兄决策。
- B 只更新 B 行和 `status/implementation.md`；C 只更新 C 行和 `status/evaluation.md`；DSH 更新 DSH 行和 `discussion_notes.md`。
- 不把代码完成写成实验完成，不把合成结果写成真实数据结果；新增结论带日期和来源。
- 患者正文、真实参考答案、凭据和原始模型响应不进入面板。
- 面板和 GitHub 规划只展示匿名摘要；当前建议建立独立私有仓库，先完成脱敏检查和 E0/B 接口，再创建远端。
