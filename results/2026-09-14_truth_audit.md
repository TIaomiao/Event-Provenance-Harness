# 2026-09-14 真伪审计：两周产物可信度分级

触发：w 在 2026-09-14 发现此前对话所用的 LLM 并非其宣称的模型，因而对两周（2026-09-01 前后至 09-13）的全部进度与产物产生怀疑。
审计人：DSH。审计范围：本地工作区全部代码、测试、结果 JSON、状态文档、Panel、git 历史。服务器侧产物按"本地不可验证"单列。

## 0. 审计方法（可复跑）

| 编号 | 手段 | 命令/位置 |
| --- | --- | --- |
| M1 | 评测测试是否真能跑通 | `python -m pytest src/evaluation/tests -q` |
| M2 | 原型测试是否真能跑通 | `python -m pytest src/prototype/tests -q` |
| M3 | 已发布分数能否独立复现 | 用 `src/evaluation/scorer.py` 直接给 `src/prototype/independent_source_submission.json` 打分，并比对 SHA-256 |
| M4 | 代码里到底有没有模型调用 | 在 `src/` 全量检索 `openai|anthropic|requests.|urllib|http|api_key|chat.completions|.generate(` |
| M5 | 数字来源逐条追溯 | 每个数字回指生成它的代码或 JSON |
| M6 | 文献真伪 | 逐条 web 检索（本报告第 4 节，另由独立核验员完成） |
| M7 | 版本可追溯性 | `git log`、`git status` |

## 1. 结论速览

| 分级 | 内容 |
| --- | --- |
| ✅ **可信、可复用** | 评测器代码与 45 项测试；原型 3 个模块与 37 项测试（1 项受本机沙箱限制，非代码缺陷）；研究卡 v0.4 的任务定义、时间角色契约、Q1–Q6 查询清单；文献清单的**名字层**（25 项有可核验 URL）；对 Larry 受控环境的只读访问路径与授权范围 |
| ⚠️ **可复现但无科研意义** | 全部 F1 / 对齐数 / 12-12 分数（`joint_f1=1.0`、`0.6667`、`0.1667` …）——它们是"手写答案 vs 手写答案"的一致率，**模型调用次数为 0** |
| ❌ **作废** | "20 条开发事件候选"作为证据；`results/research_dev_review_v0_1.json` 的 20 张核对卡；"source_support 2→8→12、F1 0.1667→0.6667→1.0 的提升"作为进展叙事；Panel"已完成证据"中的 4 条 |
| ✅ **已上服务器复核为真** | 26 文档 / 187 页 / 13,372 行；`research_dev_events_v0_1…v0_9`、`research_dev_event_candidates_v0_1.json`、`research_dev_replay_metrics_v0_1.json`、`research_dev_review_v0_1/` 全部真实存在，时间戳与大小自洽 |
| ❓ **仍未验证** | "952 个日期候选"（2026-09-08 的声明，服务器上无对应产物可复现） |
| 🕳️ **从未存在** | Flat baseline、Harness 流程、任何 LLM 调用、真实参考答案、人工核对记录、独立测试集 |

## 2. 逐项证据

### 2.1 代码与测试：真的（M1/M2/M4）

- `python -m pytest src/evaluation/tests -q` → **45 passed**。C 的"45/45"属实。
- `python -m pytest src/prototype/tests -q` → **36 passed, 1 failed**。唯一失败项 `test_temporal_rebase.py::TemporalTests::test_end_to_end_new_sidecar_and_original_hashes` 报 `PermissionError: [WinError 5]`，来自 `tempfile.TemporaryDirectory()` 清理阶段。用最小脚本单独复现同一异常，且 `mkdtemp()` / `NamedTemporaryFile()` 均正常 → **这是本机沙箱对 chmod/unlink 的限制，不是代码缺陷**。B 的"37/37"在无沙箱环境下应成立。
- 测试数逐文件核对，与 B 的记录一致：`test_temporal_rebase.py` 23 项（对应"23 项"）、`test_temporal_roles.py` 12 项、`test_laboratory_bbox_adapter.py` 2 项（合计 37）。
- **M4 结果：`src/` 下检索模型/网络调用关键词，命中 0 条。** 整个两周的工作里**没有任何一行代码调用过大模型**。这一点是"假模型误导"的真正机制：不是模型答错了，而是**从来没有模型参与**，但产物格式（`joint_f1`、`field_correct`、`cost`）看起来像模型评测结果。

### 2.2 分数来源追溯（M3）：数字可复现，但含义被误读

复现命令与结果（2026-09-14 实测）：

```text
joint_f1       = 1.0
full_record_f1 = 1.0
field_correct  = {value:12, unit:12, sampling_time:12, all_time_assertions:12, source_support:12, joint:12, full_record:12}
cost           = {calls: 0, input_tokens: 0, output_tokens: 0, amount: 0 USD, wall_seconds: 0}
submission_sha256 = 07ded489e3b11372ed4897bfe67950c0900b2dab4fcc4c6c98a0c904f7d7854b
```

- SHA-256 与 `status/evaluation.md` 记录一致 → 数字确实来自这份文件，C 没有编造。
- 但这份"提交"由 `src/prototype/independent_source_submission.py` 生成：**硬编码 ROWS**，项目名写作 `"X"/"Y"`，`case_token` 为 `"SYNTHETIC-ONLY"`，每行的 `evidence_note` 是人工写的句子。
- `cost.calls = 0`。**没有模型调用，没有读取任何真实材料。**
- `src/evaluation/demo.py` 的 docstring 自己就写着："these are authored mutations, not B runs"，输出字段 `model_calls_executed: 0`、`real_cases_processed: 0`。

**因此**：`0.1667 → 0.6667 → 1.0` 这条"提升曲线"记录的是一份手写 JSON 被反复修改直到与另一份手写 JSON 完全一致的过程。C 在 `status/evaluation.md` 工作单元 10 里已经写明了这一点（"未调用通用源材料解析流程…不证明独立抽取算法已实现或有效"）。**评估流程是诚实的，被误读的是 Panel 把它当成"已完成证据"列出。**

### 2.3 Panel 与状态文件的一致性

- `CONTROL_PANEL.md` 第 69 行写 "joint/full_record F1=0.6667"，但最新已发布结果是 **1.0**（`b_score_independent_source_submission.json`）。**Panel 与结果文件不一致，Panel 已过期。**
- `status/evaluation.md` 第 24 行记录了另一处历史事故："CONTROL_PANEL.md 开头出现大量重复拼接内容，当前无法可靠定位 C 行"。即 Panel 曾被写入损坏过。
- Panel "已完成证据"5 条里，第 1、2、3 条均为合成自洽结果；第 3 条的"source_support=8/12"同样已过期。

### 2.4 20 条"开发事件候选"（`results/research_dev_review_v0_1.json`）

实测字段形态：20 张卡全部为匿名 ID + 布尔位，其中
`date_evidence_status = "missing_or_unparsed"`、`temporal_role_status = "unknown"`、`header_scope_status = "unknown"`、`binding_status = "unresolved"`、`review.decision = null`，
顶层 `image_exported = false`、`ocr_exported = false`。

→ **卡里没有检验项目、没有值、没有单位、没有日期、没有正文**。它不能用于人工核对，不能生成 gold，不能写进论文。B 在 `status/implementation_current.md` 第 18 行也已自我标注"不能直接作为人工金标准"。

### 2.5 服务器侧复核（2026-09-14 16:0x，只读，未回传正文）

`ssh Larry` 可达（`a100.kongfei.life:40000`）。对
`<CONTROLLED_ENV>/` 做了只读结构检查（只打印字段名、类型、非空计数与项目名，不打印值/日期/患者标识）。

**结论一：所有被声明的产物的确存在，没有伪造。**

| 文件 | 大小 | 时间 | 复核实况 |
| --- | --- | --- | --- |
| `research_dev_replay_metrics_v0_1.json` | 39 KB | 09-13 13:30 | `document_count=26, total_pages=187, total_lines=13372`，与 Panel 声明**逐字一致**；`independent_test_accessed=false` |
| `research_dev_review_v0_1/review.json` | 15 KB | 09-13 13:49 | 与本地 `results/research_dev_review_v0_1.json` 对应 |
| `research_dev_event_candidates_v0_1.json` | 13 KB | 09-13 13:35 | 20 条 observations，字段与本地核对卡一致 |
| `research_dev_events_v0_1.json` … `v0_9.json` | 0.3–25 KB | 09-13 12:15–12:29 | 全部存在（其中 v0_4/v0_5/v0_6/v0_9 在 `status/implementation.md` 中没有记录） |

→ **"被假模型误导"不是"无中生有"。服务器上的工作是真的，时间戳、大小、聚合数字都对得上。被污染的是对它们含义的概括。**

**结论二：但抽出来的内容是不能用的。** 复核 `stats` 与项目名字段：

| 版本 | stats | 抽出来的"项目名"实际是什么 |
| --- | --- | --- |
| v0_1 | `records 2037, events 20, missing_time 20` | `KPS评分`、`年龄`、`男年龄`、`心率`、`P`、`QRS时限`、`R间期`、`主要表现` —— **这些是年龄/生命体征/心电图参数，不是检验项目** |
| v0_4 | `unknown_item_value_unit: 20, all_time_unresolved: 20` | 20 条全为 `unknown` |
| v0_8 | `item_candidate_count 18, value_unknown 20, time_unresolved 20` | `'+，突变型）；KI67（15'`、`'0.9'`、`'2024.01.2609:045'`、`'5'`、`'蛋白原6.21g/L，D-二聚体3.30'` —— **是原始文本碎片、日期和数字，被误当成了项目名；值 20/20 未知** |
| v0_9 | `events 0` | 空 |

→ **两周结束时，真实数据上没有任何一条合格的检验观测**：没有正确的项目名、没有值、20/20 采样时间 unknown、binding 全部 unknown/unresolved。

**结论三：本地 review 包主动丢弃了唯一有价值的部分。** 服务器上 `research_dev_events_v0_1.json` 的 `item/value/unit` 是 20/20 非空的，但导出到本地的 `research_dev_event_candidates_v0_1.json` 把它们压成了 `value_present: true` / `unit_present: true` 两个布尔位。于是本地看起来"有 20 条候选"，实际内容为空。**这一步是"看起来有进展"的主要来源。**

**结论四：分层抽样只做到两维。** `results/2026-09-13_dev_case_selection.jsonl` 中 `page_count / layout / cross_page / date_missing / ocr_quality` 全为 `unavailable`；论文所需的六维分层没有实现。

**结论五：Proposal 的可复用性假设被否证。** B 记录（`status/implementation.md` 第 106 行）："CASE-02/CASE-05 范围的 `result.json` 仅有 6 条 structured.records，来自非检验文档；**检验文档没有可直接复用的结构化 records**"。Proposal 第 45 行"已有 OCR/bbox、脱敏、病例级事件表、来源引用和统一模型接口"作为"现有基础"不成立。

### 2.6 版本可追溯性（M7）

- git 共 **8 个 commit**，最后一个 commit 是 **2026-09-08** `docs: add GitHub Pages root entry`。
- `git status --porcelain` 有 **52 条**改动/未跟踪。
- → **09-11 至 09-13 的全部工作没有任何版本历史**。任何"上周做出了什么"的说法都没有 git 证据，只能靠文档自述。

## 3. 文献层审计（另由独立核验员逐条检索）

- **真实存在（有官方/arXiv/DOI URL）：约 25 项**。含 DataSpace、HealthFlow、EHRFlowBench、OneEHR、U-EHR、ClinLens、ClinTraceBench、EHR-Complex、HealthAgentBench、Harness-Bench、The Harness Effect、Agentic Context Cracking、TrajOnco、DiaSentinel、CliBench、ClinBench、M3Care、PyEHR、PRISM、EMERGE、PAI、ColaCare、MedAgentBoard、ClinicRealm、MedAgentBench、FDABench、EHRSHOT、MIMIC-IV Demo、Irvin 2020。
- ❌ **未找到任何可靠来源的 3 个名字**：`AirVx`（零命中）、`MedAILab`（零命中，只命中西班牙一所大学的同名 lab）、《AI Research Handbook》（零命中；BFS/DFS 方法本身通行，但"书名"无出处）。其中 `AirVx` 在 `discussion_notes.md` 中已被本工作区标记为"不纳入引用"——**工作区这一处的自我怀疑是对的**。
- ⚠️ **缩写错误 2 个**：`ACIE`（真名 *Configurable Clinical Information Extraction with Agentic RAG*，arXiv 2606.19602）、`DIASENTINEL`（真名 `DiaSentinel`）。引用时必须写全名 + ID。
- ⚠️ **一批"比文献本身更精确"的数字无法核验**，包括 DataSpace 的"410 题 / 88.5% 金融 / 47 题临床 / 15.36 分 / 136 个失败 / 56.6% M1 / 44.1%"、ACIE 的"7,326 条 / 96.5%"、EHRFlowBench 的"110 = 55+55"。**在读过原文前，这些数字不得出现在 Proposal、汇报或任何对外材料里。**
- 补充：核验过程中发现一篇本工作区尚未记录的强相关论文 *Harness or Model? Isolating the Harness Effect in Agentic Coding with a Contamination-Controlled Private Suite*（arXiv 2609.11987），其修订说明涉及"成本遥测口径缺陷被更正"——与本文创新点 3 的"质量—成本曲线"直接相关，应补入 P1 阅读队列。

## 4. "假模型"到底污染了什么

按证据，污染面**不是**文献（名字层基本为真），而是：

1. **结果叙事**：把"手写答案对手写答案"的分数写成方法效果与进展曲线。
2. **精确数字**：文献附带的统计细节、EHRFlowBench 任务数等无法核验的具体数值。
3. **真实数据侧的乐观概括**："20 条候选已生成""26 文档 187 页回放"听起来像实验，实际是没有语义内容的 ID 表和文件计数。
4. **可复用性假设**：Proposal 假设"已有检验结构化 records 可复用"，B 的实测是检验文档一条都没有。

而**工作区自身的诚实度比预期高**：`status/evaluation.md`、`status/implementation.md`、`src/evaluation/demo.py`、`status/implementation_current.md` 都逐条写明了合成性质、0 调用、未核对、不可外推。**问题出在 Panel 与 Proposal 的汇总层把这些降级信息抹平了。**

## 5. 可抢救资产（明确清单）

1. `src/evaluation/scorer.py` + 45 项测试：一个能跑的、字段契约明确的观测级评分器（值/单位/时间断言/来源支持/身份关系/成本账本）。**这是两周里最扎实的成果**，可作为论文评测器雏形。
2. `RESEARCH_CARD.md` v0.4：任务定义、时间角色契约（sampling/report/record/document/unknown）、unknown/unresolved/conflicting 语义、表头作用域规则、Q1–Q6 查询清单、评分维度。**这是一份可用的研究设计，不属于被污染范围。**
3. `src/prototype/temporal_roles.py` + `temporal_rebase.py`：显式的角色—行关联校验与相对日坐标平移，属于真实工程能力。
4. Larry 受控环境的只读访问路径与授权边界（CASE-02 / CASE-05 的 OCR JSON 字段级授权）。
5. 文献清单（修正 3 个假名、2 个错缩写后可用）。

## 6. 致命缺口（决定 KDD 2027 C2 是否可行）

按严重度排序：

1. **没有任何模型参与**。论文的方法是"固定模型、变化证据组织方式"的对照实验；当前连第一次真实 LLM 调用都还没发生，模型选型、供应商、费用授权全部未定。
2. **真实材料到结构化事件的链路不但断，而且实测输出是错的**。检验文档没有可复用的结构化 records；OCR 行格式与既有解析器不匹配；最终留存的两个版本里，v0_1 的 20 条落在**年龄/心率/心电图参数**行上，v0_8 的"项目名"是**文本碎片、日期和数字**，值 20/20 未知、采样时间 20/20 unknown。在 13,372 行上，保守规则的产出是 4 条。**这是整条研究路线的单点故障**：这一步不成立，事件/时间/来源的评测无从谈起。
3. **没有一行真实参考答案**。20 张卡零语义，人工核对从未开始。开发参考集 = 0。
4. **没有 baseline**。Flat（直接抽）与 Harness（先组织再抽）两条路径都不存在。
5. **没有独立测试集划分、没有预算计量**（`cost` 全是 0，且是提交方自填、未独立测量）。
6. **时间**：距 KDD 2027 Cycle 2（推测 2027-02 截稿）约 4.5 个月，而上面 5 项全部为 0。

## 7. 下一步必须先做的事（不是写论文）

1. **单点验证（最优先）**：在 Larry 上取 1 个病例、1 份检验文档，端到端产出 **1 条** w 自己能在服务器上肉眼对着 PDF 核对的完整事件（项目、值、单位、采样时间、bbox）。做不出来，说明路线需要重新设计，而不是继续堆模块。
2. **一条真实 LLM 调用**：在获准范围内对同一份材料调用一次真实模型，记录 token/费用/延迟，证明成本账本可用。需要先确定模型供应商与费用授权。
3. **10–20 条真实开发参考**：由 w 或临床人员核对，冻结 `reference_version` + `content_digest`。
4. **修正文档**：Panel 的"已完成证据"改为按本审计分级；Proposal 删除"已有检验结构化 records 可复用"的假设；文献层删掉 3 个假名。
5. **git 立即提交一次**：把 09-11 以来的 52 项改动做成检查点，之后每完成一个工作单元提交一次。

## 8. 待补验证清单

- [x] ~~26 文档 / 187 页 / 13,372 行是否可复现~~ → **2026-09-14 复核为真**（`replay_metrics_v0_1.json`）
- [x] ~~`research_dev_events_v0_*` 各版本是否真实存在~~ → **2026-09-14 复核存在**（v0_1–v0_9 齐备）
- [ ] 952 个日期候选是否可复现（服务器上未找到对应产物）
- [ ] v0_1 的 20 条为什么落在年龄/心率/心电图行：是**选文档环节**选错，还是**行匹配规则**选错？
- [ ] CASE-02/CASE-05 的检验文档 OCR 行格式样本（脱敏后）能否支撑规则解析，还是必须走模型抽取
- [ ] 为什么 `research_dev_events_v0_4/v0_5/v0_6/v0_9` 未写入任何状态文档
- [ ] KDD 2027 Cycle 2 官方日期（等官方 CFP）
- [ ] 论文实验模型：供应商、单价、单次实验预算上限
- [ ] 是否存在"检验文档在别的字段路径下有结构化 records"（B 只查了 `result.json`）
