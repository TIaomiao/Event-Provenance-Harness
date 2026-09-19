# 历史资料索引

本目录是**唯一历史索引**，只作追溯用。当前安排以 [README](../README.md)、[CONTROL_PANEL](../CONTROL_PANEL.md)、[paper/PROPOSAL](../paper/PROPOSAL.md)、[related_work/AI_READY_EVIDENCE_MATRIX](../related_work/AI_READY_EVIDENCE_MATRIX.md) 为准。

**归档材料不产生执行指令。** 读之前先明确要查的事实；不按其中的「下一步」「待服务器」自动续跑。历史文件里的相对链接按它们归档前的位置理解，日期与进度以原记录时间为准。

标签含义：**【历史探索】**方向或做法已被取代，数据事实仍成立 · **【仅代码自检】**`calls = 0` 的合成自洽检查，不是模型结果 · **【待复核】**结论未验证或口径未冻结 · **【已发现具体错误】**已知有明确错误，原件保留不改写。

## 主题索引

### 一、事件身份探索（2026-09-08 ~ 09-15）

| 项 | 内容 |
| --- | --- |
| 原来解决什么 | 多份文档描述同一次检验时，值—时间—来源能否被正确绑定；重复引用与真实复测如何区分 |
| 有什么证据 | `results/2026-09-14_event_identity_finding.md`、`results/2026-09-14_event_grouping.md`、`results/2026-09-14_truth_audit.md`、`results/2026-09-14_model_event_test.md`（数据事实：DOC-013 无行级日期与编号，227 个 6 位数字串中 165 个在条码列；最小可行事件单位是**页**） |
| 目前用途 | 作为**数据事实**与接口语义来源；E1 协议本身不再作为待办。真伪审计结论（`src/` 曾无任何模型调用）仍是证据门槛的依据 |
| 原件位置 | `archive/planning/PROPOSAL_event_identity_20260914.md`（2026-09-11 版 Proposal 正文）、`archive/20260919_workspace_c14e4b2/RESEARCH_CARD.md`（研究卡 v0.4：四类时间角色契约、表头作用域规则、Q1–Q6 查询清单）、`archive/planning/2026-09-11_alignment_brief.md` |
| 标签 | 【历史探索】+【仅代码自检】（原型联调 12/12 为手写答案对手写答案） |

### 二、检验表抽取与结构真值（旧抽取 benchmark）

| 项 | 内容 |
| --- | --- |
| 原来解决什么 | 从真实扫描件抽出检验观测，并用「引用可解析率 / 值接地 / 时间接地 / 行数恢复 / 一次性完成率」衡量 |
| 有什么证据 | `results/2026-09-15_*.md`（9 份）、`results/2026-09-17_main_table.md`、`results/2026-09-17_pilot_ai_ready.md`、`results/2026-09-17_hard_questions.md`、`results/2026-09-17_main_table.md` |
| 目前用途 | **前期预实验**：作为「已有工程能力」在方法一节交代，不进新主结果位置 |
| 原件位置 | `archive/20260919_workspace_c14e4b2/paper/BENCHMARK_DESIGN_2026-09-15.md`、`.../BENCHMARK_DATASET_PROTOCOL.md`、`.../QUESTION_BANK_PILOT60.md`、`.../benchmark-main-table-report.pdf`、`.../REPORT_FOR_SENIOR_2026-09-17.html`、`archive/results_snapshot_20260915/` |
| 标签 | 【历史探索】+【待复核】（几何真值未校准；出现过 122% 的行数恢复） |

### 三、阶梯与消费者探索（2026-09-18 ~ 09-19）

| 项 | 内容 |
| --- | --- |
| 原来解决什么 | 把准备动作拆成严格超集的多层版本，逐层测量哪一层值多少；并换多个消费者模型复现方向 |
| 有什么证据 | `results/2026-09-19_ladder.md`（病例级 12 例 × 11 题 × 9 条件 × 3 次重复；队列级 16 题在两个尺度）、`results/2026-09-18_queue_level.md` |
| 目前用途 | **探索性结果**：只用来支撑「分层归因这个做法可跑通」；层数与各层地位待新问题定义确定 |
| 原件位置 | `archive/20260919_workspace_c14e4b2/paper/AI_READY_PLAN.md`（六版本与五指标口径、正向/反向协议、边界）、`.../paper/AI_READY_CLAIM_MAP.md`（研究问题与候选主张映射）、`.../related_work/EVIDENCE_CORRECTION_LOG.md` |
| 标签 | 【历史探索】+【待复核】（消费者命名均为 Gemini 系，家族独立性未证实；真实返回型号未记录） |

### 四、会议与决策（2026-09-19）

| 项 | 内容 |
| --- | --- |
| 原来解决什么 | 把 2026-09-19 会议的逐字稿、自动纪要与文字补充交叉核对成一份可引用的会后基线；区分「会议决定」与「整理者建议」 |
| 有什么证据 | 逐字稿相对时间定位（如 10:30「具体几层他们也不会关心」、19:41「实验做表一定去证实上面的一个 motivation」、27:49「AI ready 跟不 AI ready 的本质的一个点是什么」）；多份来源交叉核对 |
| 目前用途 | **事实来源**：当前有效选择已并入总控「已定选择与来源」表；需要逐字核对时查原件 |
| 原件位置 | `archive/20260919_workspace_c14e4b2/AI_READY_EHR_MEETING_BASELINE_2026-09-19.md`、`.../paper/DECISION_LOG_2026-09-19.md`（D-001~D-015，标注来源类型） |
| 标签 | 【历史探索】（会议原件不改写为会议原话之外的措辞） |

### 五、文献纠错

| 项 | 内容 |
| --- | --- |
| 原来解决什么 | 记录对抗式审查后发现的文献事实错误、越界表述与证据状态颗粒度问题 |
| 有什么证据 | 修正 1：Representation Wins 的结果方向被写反（一手来源为作者结果源文件 `paper/sections/04_results.tex`，QA 上叙述式赢、ML 上结构化赢）；修正 2：撤回「唯一空位」表述；修正 3：证据状态改为五级；修正 4：主指标与「物理上做不了」的措辞改为限定条件；修正 5：C3 从负结论改回问题；修正 6：区分会议原文与整理者建议 |
| 目前用途 | 审计链：文献台账 S1 条目保留 `correction_ref: EVIDENCE_CORRECTION_LOG#修正1`，不抹掉修正来源 |
| 原件位置 | `archive/20260919_workspace_c14e4b2/related_work/EVIDENCE_CORRECTION_LOG.md`、`.../related_work/AI_READY_EVIDENCE_MATRIX.md`（纠错前版本） |
| 标签 | 【已发现具体错误】（修正后结论以现役台账为准） |

### 六、整理快照与迁移

| 项 | 内容 |
| --- | --- |
| 原来解决什么 | 每次大规模文档收敛前先保全原件，保证可恢复、可核对 |
| 有什么证据 | 本批次 `manifest.json` 登记每份原件的原路径、归档路径、动作（copy/move）、字节数、SHA-256、来源提交、并入位置、用途与发布等级 |
| 目前用途 | 追溯与单文件恢复；不作为现役安排 |
| 原件位置 | `archive/20260919_workspace_c14e4b2/`（2026-09-19 批次，基线 `c14e4b2`）、`archive/document_cleanup_20260908_1727/`、`archive/migration/`、`archive/results_snapshot_20260915/` |
| 标签 | 【历史探索】 |

### 七、早期规划与交接包

| 项 | 内容 |
| --- | --- |
| 原来解决什么 | 项目早期的方案探索、session 开场说明与远程状态快照 |
| 有什么证据 | `archive/legacy_20260915/`（CONTEXT、ENGINEERING_PLAN、RESEARCH_IDEA_HANDOFF、SESSION_PROMPTS：描述的是「嵌套 harness」那一版方案）、`archive/context-v001/`（2026-09-05 初始交接包与远程状态快照）、`archive/planning/`（早期研究规划与会前草稿） |
| 目前用途 | 只作历史与数据事实；不要从这些文档判断现状 |
| 原件位置 | 见左列目录 |
| 标签 | 【历史探索】 |

## 恢复说明

1. 按本索引或 `manifest.json` 的 `original_path` 定位原件，复制回仓库根对应位置，并核对 `sha256`。
2. 原件字节未加任何说明横幅；解释只在本索引与 `manifest.json` 里，便于逐字节比对。
3. **归档目录里的 `AGENTS.md` 一律以 `AGENTS.md.snapshot` 命名**（`archive/context-v001/`、`archive/document_cleanup_20260908_1727/`、`archive/20260919_workspace_c14e4b2/`），避免它成为该子树自动执行的规则；恢复时改回 `AGENTS.md`。重命名前后 SHA-256 不变。
4. 归档历史里的相对链接按归档前位置理解；不要为了修链接而改动原件字节，那会让证据不可比。
5. **一个例外已登记**：`archive/20260919_workspace_c14e4b2/paper/现状.md` 在归档时按 `.local/sanitize.py` 的前三条规则替换了真实采集日期与时分秒字面量（`day_a` 2 处、`day_b` 1 处、`clock` 6 处）。该文件此前已存在于公开仓库且未被 `sanitize.py` 的检查清单覆盖；清洗只作用于归档副本，**清洗前的原件字节与 `original_sha256` 登记在仓外本地备份**。除这一条外，本批次全部条目与整理前字节逐字节一致。
