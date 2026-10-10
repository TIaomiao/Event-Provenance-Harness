# AI-Ready 相关工作对照表（唯一活动文献台账）

本文件是**唯一活动文献台账**。它回答的问题是：别人怎么定义 AI-ready、怎么设对照、怎么证明收益——先看清这件事，再决定我们怎么做。现役研究规格见 [paper/PROPOSAL.md](../paper/PROPOSAL.md)，当前状态见 [CONTROL_PANEL.md](../CONTROL_PANEL.md)。

两个分区：**精选阅读**（决定我们差异怎么写的关键篇目）与**扩展检索**（本轮扫到的相邻工作）。每篇按同样的问题填：为谁准备 / 用于什么任务 → 原数据有什么问题、做了哪些准备 → 对照是什么 → 下游任务 · 指标 · 正确性依据 → 结果支持什么、哪些只是宣称 → 适合与不适合我们的地方。

**两条进度分开记**：「DSH 核验状态」是本研究 Agent 逐篇核对到什么程度；「用户阅读状态」是 w 本人的阅读回执。**只看摘要不算完成**，摘要级条目不得引用任何数字或机制细节。

## 精选阅读

| # | 论文（标识符 · 链接） | 材料类型与核对范围 | 为谁准备 / 什么任务 | 准备动作 | 对照 | 下游任务 · 指标 · 正确性依据 | 结果支持什么 / 哪些只是宣称 | 适合我们 / 不适合我们 | DSH 核验状态 | 用户阅读状态 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| S1 | **Representation Wins on QA, Not on ML**（[Zenodo 20292792](https://zenodo.org/records/20292792)；作者结果源文件 [`04_results.tex`](https://raw.githubusercontent.com/TJmetrichealth/FHIR_RAG_TEST/main/paper/sections/04_results.tex)） | 作者结果源文件（§Overall Accuracy 表 1、§Feature-Extraction Arm 的 AUC 表） | 给检索 / 问答与分析用；配对比较两种表示（合成 FHIR、13,800 题、qwen3-32b） | 同一批数据的三种系统：A 叙述式 RAG / B 结构化朴素 / C 结构化资源感知 | **配对设计**：同一批题、同一答题模型、同一提示模板，只换表示与检索 | QA 用 exact-match；ML 用合成依从性分类 AUC | **QA：A 40.6% > B 35.3% > C 33.4%（叙述赢，A−B=+5.27pp，McNemar p<0.001）；ML：FS-Structured AUC 0.997 > FS-Narrative 0.846（结构化赢）。** 另有：无检索基线 N=25.2%；检索归因增益 A +15.4pp / B +10.1pp / C +8.2pp；成本/正确答案 A \$0.00085 / B \$0.00432 / C \$0.00149；输出预算 512→1024 只提升结构化系统（B +3.8pp、C +5.1pp），叙述系统 0.0pp；错误分类：推理截断（预算）44–58%、时间锚失败 30→10%、**N/A 误用 8%→22%** | ✅ **与我们最接近的工作**：配对设计、检索归因分解、成本/正确答案、预算敏感性都该直接学；❌ 输入是**合成** FHIR，任务限于依从性指标，不是医院扫描件 | **方法与结果已核**（2026-09-19） | 未记录 |
| S2 | **FHIRBench**（`10.64898/2026.07.14.26358020`，[medRxiv](https://www.medrxiv.org/content/10.64898/2026.07.14.26358020v1.full.pdf)）；**注意与 S6 的 FHIR-AgentBench 是两篇不同论文** | 元数据 + 摘要；**全文本轮获取受阻** | 给 LLM 用；在 FHIR 记录上答临床问题 | 原数据**已经是结构化 FHIR**；准备动作 = 序列化格式选择 | 不同序列化格式互为对照 | 4 模型 × 3 任务 × 100 个合成 bundle；指标 = 任务准确率 + token | 支持「紧凑格式更好、格式选择影响可用性」；**不支持**任何关于真实扫描件的结论 | ✅ 与我们的「格式统一」动作直接可比；❌ 输入是合成的、已结构化，没有版面 / 印章 / 页码污染 | **摘要已核；全文不可得**（本轮获取受阻，不得当成已复核） | 未记录 |
| S3 | **HoloBench**（`arXiv:2410.11996`，[链接](https://arxiv.org/abs/2410.11996)） | 原文部分已核（要点段） | 长上下文聚合 | 与数据准备无关；研究上下文长度对聚合的影响 | 不同上下文长度 | 聚合准确率 | 支持「**聚合随规模退化、max/min 抗退化**」——**我们已复现同一现象，不得声称新发现** | ✅ 直接约束我们队列级结论的表述；❌ 与「数据准备」不同层 | 原文部分已核 | 未记录 |
| S4 | **Infherno**（`arXiv:2507.12261`；发表版 [EACL 2026 System Demonstrations pp.163–174](https://aclanthology.org/2026.eacl-demo.13/)） | **全文已取得**（arXiv 版与 EACL 发表版，各 12 页，本地落盘；两版正文基本一致） | 把自由文本临床记录变成 FHIR 资源集合，交付一个 FHIR Bundle | 不是让模型一次写整份 JSON，而是 ReAct Agent：调术语工具查编码 → 执行 Python 代码用 `fhir.resources` 构造对象 → 接收报错并自我修复 | 与人工参考标注比；与 6 个 LLM 横比；与「模块化流水线 / 指令微调 + 约束解码」做定性对比 | 两个实验：`MedicationStatement.medication` 的 P/R/F1（人工归类 TP/FP/FN）；合成数据上逐项人工比对，区分主要项 / 次要项 | 支持「Agent 调工具 + 跑代码 + 用报错驱动重试，能把文本变成合法 FHIR」；**它的校验回路是「结构合法性」回路，不是「语义正确性」回路**——值对不对仍靠事后人工比对 | ✅ 可学「模型组织语义 + 程序负责合法性与报错 + 用报错驱动重试」的分工；❌ 规模只有 10+10 份文档、单标注者、只覆盖 3 类资源，评的是「是否合法 / 一致」而非「是否方便下游使用」 | **方法与结果已核**（全文已取得；数字逐字核对自 Table 1） | 卡片已备，四问答案栏待 w 填写 |
| S5 | **From Medical Records to AI-Ready Datasets**（`10.3390/jcm15166297`；PMID 42652700；[MDPI](https://www.mdpi.com/2077-0383/15/16/6297)） | **全文已取得**（Europe PMC 官方全文 XML；MDPI 官网 PDF 被 Cloudflare 拦截未取得；补充材料 Table S1 / Table 4 已取得并转录） | 给临床研究者；产出「这份数据到底准备好没有」的判定与文档 | 人工整理：任务与人群定义、单位分析、数据字典、测量时点、重复测量口径、缺失原因编码、清单与评分 | **没有做对照实验**；只在 Discussion 里与 TRIPOD+AI / FAIR / OMOP / OHDSI 做定位上的区分 | 判断依据是「定义是否被清楚记录」，不是实验；0–2 分 × 10 领域 = 总分 0–20，四档区间（0–7 / 8–12 / 13–16 / 17–20），另有 9 条一票否决 | 作者**自陈**它是「结构化、专家知情的提案，而不是经共识形成或经实证验证的测量工具」（§2.2、§5），阈值未经实证校准（§4.3），§4.6 那个 14/20 的工作示例是**假想的** | ✅ 提供「AI-ready 是个等级」的合法性，以及「重复测量口径必须在抽取前定好」这条可直接借用的论证；❌ 没有任何 Agent 实验、没有抽取正确率，**收益是主张的而不是测出来的**——正是我们要补的位置 | **方法与结果已核**（全文已取得；引用可定位到章节与补充材料） | 卡片已备，四问答案栏待 w 填写 |
| S6 | **FHIR-AgentBench**（`arXiv:2509.19319v2`；PMLR 297 / ML4H 2025）——全名 *Benchmarking LLM Agents for Realistic Interoperable EHR Question Answering* | **全文已取得**（19 页 PDF + 带页码标记的提取文本） | 把 2,931 条真实临床问题建在 HL7 FHIR 上，做成「检索与作答分开计分」的 Agent 评测集 | 为每题准备 ground-truth 的 FHIR 资源 ID 集合与标准答案；Agent 先取资源、再作答 | 三轴对照：检索策略 × 单轮/多轮 × 是否用代码，共 5 种架构；其中两种架构下横比 4 个模型 | 检索 Precision / Recall 与 Answer Correctness 分开；AC 由 LLM evaluator（o4-mini）判定，500 样本人工复核 97% 一致；所有模型统一 32k 上下文 | §5.1：表现最好的多轮架构下各模型 AC 都落在 44–50%，作者据此认为**架构与任务难度比基座模型的选择更是瓶颈**；§5.2 把失败分成「检索失败」与「取到资源后的解读失败（Interpretation Gap）」，后者的原文措辞是 *"even when all correct resources are retrieved"* | ✅ 可借任务构造流程（从已有需求反推 → 在原始库上重跑 → 迭代校验 → 保留「答案为空的题」）与「检索 / 作答分离计分」；❌ 金标准只到**资源 ID 级**（不区分同一资源内的观测身份与时间角色），且**不含多患者 / 队列级题目**（§6 列为 future work） | **方法与结果已核**（全文已取得；所有数字逐个从原文核对） | 卡片已备，四问答案栏待 w 填写 |
| S7 | **HealthFlow**（[npj Digital Medicine 2026](https://www.nature.com/articles/s41746-026-03097-0_reference.pdf)；`arXiv:2508.02621`） | **全文本地已有**（27 页）；本轮为**定向读**，未通读全篇 | 自动化 EHR 分析；输入是**已发布、已去标识、已有 schema 的数据集**（TJH + MIMIC-IV Public Demo），在沙箱工作区里以文件形态交给 Agent | 任务画像依赖 **schema-derived tags**（患者标识列、时间字段、目标变量、队列列）与风险标签；工具按画像预先提供 | 与多个通用 / 生物医学 Agent 框架比；组件渐进消融；另做换模型 / 换执行器的敏感性分析 | EHRFlowBench 用 1–5 分 LLM 评审（报告渲染成 PDF 与参考解答 PDF 对比，缺工件记 0）；MedAgentBoard 用二元成功率；另加 12 位专家 240 次盲选偏好 | 支持「换模型只造成小幅波动，而加架构组件带来明显提升」；**它不承担最上游的数据准备**——原文未说明 PDF / OCR / 脱敏 / 多源合并这一段 | ✅ 可把「下游需要什么输入」当作准备层的验收标准；❌ 记忆跨任务累积而基线每题独立、**公平性口径不对等**；主指标是模型评审分而非二元全对；论文 100 题与本地代码快照 110 题的口径需统一 | **方法与结果已核（定向）**；引用均可按行号在提取文本里定位 | 卡片已备，四问答案栏待 w 填写 |

**修正引用**：S1 的结果方向曾在本表被写反，修正过程与一手定位见归档原件 `archive/20260919_workspace_c14e4b2/related_work/EVIDENCE_CORRECTION_LOG.md` 的**修正 1**（`correction_ref: EVIDENCE_CORRECTION_LOG#修正1`）。本表保留该引用以维持审计链。

## 当前候选相关工作

本节只服务当前「面向任务的纵向 EHR 证据选择」选题判别。它不把用户重点阅读变成整张表的必读清单；用户阅读状态与 DSH 核验状态分开记录。新近 arXiv 条目按预印本处理，未核到正式录用信息就不写成已录用。**阅读口径已改为 abstract-first**：先记录「用户摘要已读」（背景、问题、方法、结果、对我们的启发各一两句），再单独记录「技术原文核验范围」；不因未读全文就否定第一轮阅读。本节四篇为**相邻参照**，不据「输入不同」宣布创新空白。

| 用途 | 论文（官方出处/版本） | 发表状态与核验范围 | 已核到的相关机制 | 对当前实验设计的影响 | 用户阅读状态 |
| --- | --- | --- | --- | --- | --- |
| 相邻参照 | **TIMER: temporal instruction modeling and evaluation for longitudinal clinical records**（`10.1038/s41746-025-01965-9`；npj Digital Medicine 2025, vol 8 art. 577；PMC12475073 / PMID 41006898；预印本 [arXiv:2503.04176](https://arxiv.org/abs/2503.04176)） | 已正式发表；出版社页、DOI、卷期与摘要已核。评测名以发表版 **`TIMER-Eval`** 为准（预印本 v1 称 `TIMER-Bench`，训练集称 `TIMER-Instruct`） | 把每条指令—回答绑定到时间轴上的规范时间点；按 Recency-Focused / Edge-Focused / Uniformly-Distributed 重采样，显式做证据归属；报告训练/测试时间分布匹配可使结果变化 +1.2%～+6.5%；并量化 MedAlign 的近期偏置（55.3% 的问题落在时间轴最后 25%） | 我们的 Q1/Q2/Q3 锚点与窗口必须显式给出并**报告任务集自身的时间分布**，否则「答对」可能只是近期偏置；锚点由数据派生这一点要在报告里说明 | 摘要已读（待用户确认）；技术原文未核 |
| 相邻参照 | **MedAlign: A Clinician-Generated Dataset for Instruction Following with Electronic Medical Records**（`10.1609/aaai.v38i20.30205`；AAAI-24, vol 38 no 20, pp. 22021–22030；预印本 [arXiv:2308.14089](https://arxiv.org/abs/2308.14089)） | 已正式发表；AAAI 卷期、页码与 DOI 已核。**未核到 NeurIPS 版本**，不得写成 NeurIPS | 983 条临床医生撰写的自然语言指令、303 条参考回答、276 份纵向 EHR；6 个通用 LLM 的临床准确度/质量排序对比自动 NLG 指标；错误率 35%（GPT-4）～68%（MPT-7B-Instruct）；GPT-4 在 32k→2k 上下文下准确率下降 8.3% | 上下文长度与「选哪些记录」会直接改变准确率，支持本选题的动机；但其输入是**已结构化 EHR + 指令跟随**，与我们「扫描 PDF 上游 + 取数选择输出」不同，不能直接当我们的基线数字 | 摘要已读（待用户确认）；技术原文未核 |
| 相邻参照 | **TimeR4: Time-aware Retrieval-Augmented Large Language Models for Temporal Knowledge Graph Question Answering**（`10.18653/v1/2024.emnlp-main.394`；[EMNLP 2024 Main](https://aclanthology.org/2024.emnlp-main.394/), pp. 6942–6952） | 已正式发表；ACL Anthology 与 DOI 已核。**领域是时序知识图谱问答，不是医疗/EHR 研究**；两个 TKGQA 数据集名称未从官方元数据核到 | Retrieve-Rewrite-Retrieve-Rerank 框架：先用图谱背景知识重写问题、把时间约束显式化，再做时间感知的检索与重排（对比式时间感知学习微调检索器）；报告相对提升 47.8% 与 22.5% | 「先把自然语言里的时间约束外化成显式条件，再检索」**已是既有做法**；因此 R2（plan then execute）是标准模式而非我们的创新点，汇报时不得包装成新方法 | 摘要已读（待用户确认）；技术原文未核 |
| 相邻参照 | **EHR-RAG: Bridging Long-Horizon Structured Electronic Health Records and Large Language Models via Enhanced Retrieval-Augmented Generation**（[arXiv:2601.21340v1](https://arxiv.org/abs/2601.21340)，2026-01-29 提交，cs.AI） | **预印本，未正式发表**；arXiv 页面与提交日期已核。**核验纠错**：此前怀疑该 arXiv 编号不存在，实际存在且正是 EHR-RAG，该怀疑被推翻 | 长程结构化 EHR 的 RAG：事件与时间感知的混合检索、自适应迭代检索、双路径证据检索与推理（事实 + 反事实）；摘要称在四个长程 EHR 预测任务上平均超过最强 LLM 基线 +10.76% Macro-F1；数据集名称未从摘要核到 | 与我们的「取数选择」相邻但输出不同（它产出预测/推理结论，我们产出选中记录集合与未决状态）；其时间感知检索与本选题的时序条件解释同源，写作时作为相邻工作引用，不据输入差异宣布空白 | 摘要已读（待用户确认）；技术原文未核 |
| 用户重点 | **DocETL: Agentic Query Rewriting and Evaluation for Complex Document Processing**（[arXiv:2410.12189 v3](https://arxiv.org/abs/2410.12189)，2025-04-01 修订；[docetl.org](https://docetl.org/)） | arXiv v3；官方摘要与版本信息已核；未把它标为正式录用 | 声明式文档处理流水线、面向 LLM 局限的 rewrite directives、Agent 引导的计划评估与验证提示；摘要称在四类非结构化文档任务上优于精心设计基线 | B1/B1-V 的搜索与自检、B2 的固定准备、未来 B3 的有限补查都要把“计划/验证成本”和“证据是否新增”分开记录；不能把 Agent 编排本身当贡献 | 待读 |
| 用户重点 | **Sufficient Context: A New Lens on Retrieval Augmented Generation Systems**（[arXiv:2411.06037 v3](https://arxiv.org/abs/2411.06037)，2025-04-22 修订） | arXiv v3；官方标题、版本和摘要已核；全文机制尚未复核；未核到正式录用信息 | 区分“检索到的上下文被模型利用失败”和“检索上下文本身不足以回答”；提出 sufficient context 视角 | B1-V 的判分必须分开检索/证据范围不足、关联失败和解释失败；任务 C 的 `insufficient` 不能和错误确定混为一类 | 待读 |
| 直接近邻 | **EHR-RobustGym: Benchmarking and Training Agents for Robust Clinical Reasoning**（[arXiv:2609.39371 v1](https://arxiv.org/abs/2609.39371)，2026-09-30 提交） | 新预印本；官方摘要、提交日期和 v1 已核；未核到录用信息；不得写成已录用 | 在 MIMIC-IV 上构造 clean/noise 对，区分 record/value/query noise，提供 SQL/Python 交互和 outcome verification，并报告噪声下鲁棒性与 pass^k 一致性 | 直接提醒我们把“证据错接”定义成可扰动/可观测的错误类型，并记录重复运行一致性；其结构化 MIMIC 输入与真实扫描 PDF 上游不同 | 待读 |
| 直接近邻 | **CliniCARE-Bench: Clinical Calibrated Audit of Medical Reasoning in EHR**（[arXiv:2608.07796 v1](https://arxiv.org/abs/2608.07796)，2026-08-07 提交） | 新预印本；官方摘要、提交日期和 v1 已核；未核到录用信息；不得写成已录用 | 四态 verdict（含缺资料与医学歧义）、证据 grounding、过程遵循、校准弃答、可回放轨迹；摘要称使用真实患者派生 MIMIC-IV 案例与临床校准 | 当前任务 C 的 `supported/contradicted/insufficient` 要保留缺资料态；主表增加过程/证据错误和不当确定回答；其数据已结构化且有临床校准，不能直接作为扫描准备基线 | 待读 |
| 决定性问题 | **EHRSQL: A Practical Text-to-SQL Benchmark for Electronic Health Records**（[arXiv:2301.07695](https://arxiv.org/abs/2301.07695)；NeurIPS 2022 Datasets and Benchmarks；GitHub [glee4810/EHRSQL](https://github.com/glee4810/EHRSQL)） | 已正式发表；**本篇由 DSH 直接读取原文页面核对**（正文 §3.1.2、Table 1、Table 3、§4.2） | 三类时间过滤器 `[time_filter_global]` / `[time_filter_within]` / **`[time_filter_exact]`**，后者原文定义为「指到一个确切时间，例如 *last* measurement」，其 **Option** 是「从过滤后的事件中选出一个确切事件（**first / last**）」；时间按表达类型（absolute/relative/mixed）／单位（年到就诊、ICU 访次）／区间类型（since/until/in）系统分类；**24,411** 个问答对、MIMIC-III + eICU、平均 13.5 表、**93.2%** 的查询用到至少一列时间；题目由 **222 名医院工作人员**在**未见 schema** 的情况下提出；含**不可答问题**；评测为 `F1_ans` + `F1_exe`（执行准确率） | **推翻我们原来的独立性假设**：「从自然语言推断该取哪个时间点（first/last/窗口）」**不是空白**，2022 年就已被系统标注并评测。因此**不得**再把这句写成新问题；必须把 EHRSQL 当**对照与来源**。真正的差别在输入（结构化库 vs 扫描病历）与评分对象（最终答案执行准确率 vs 选中记录集合） | 待读（本行为 DSH 核验） |
| 古典定位 | **Knowledge-based temporal abstraction in clinical domains**（[DOI 10.1016/0933-3657(95)00036-4](https://doi.org/10.1016/0933-3657(95)00036-4)；*Artif Intell Med* 1996;8(3):267–298；PMID 8830925）；综述 **Temporal abstraction in intelligent clinical data analysis: a survey**（[DOI 10.1016/j.artmed.2006.08.002](https://doi.org/10.1016/j.artmed.2006.08.002)）；**A framework for distributed mediation of temporal-abstraction queries to clinical databases**（[DOI 10.1016/j.artmed.2004.07.009](https://doi.org/10.1016/j.artmed.2004.07.009)） | 均正式发表；**只核到摘要与元数据级**——Shahar 1996 全文付费墙，5 个子任务的描述取自 Europe PMC 索引摘要；**未核到**常被引用的 1997 *Artificial Intelligence* 同名论文记录 | KBTA 把原始时间戳值提升为区间概念（LOW/HIGH、INCREASING）；**相关时间窗是查询的输入参数或知识库条目**，不是从任务推断的；IDAN/ALMA 中介的是**形式化**时间查询 | **不能声称**「把时序值抽象成区间／按窗口取数」是新的；同时它给出一个有用的对照：**当年也是「窗口由人给」**，我们的问题是「窗口由模型推断」 | 未读 |
| 建模定位 | **GRU-D**（[DOI 10.1038/s41598-018-24271-9](https://doi.org/10.1038/s41598-018-24271-9)）；**BEHRT**（[DOI 10.1038/s41598-020-62922-y](https://doi.org/10.1038/s41598-020-62922-y)） | 均正式发表；核到摘要与元数据级 | 时间作为**衰减信号**（GRU-D）或**位置/就诊嵌入**（BEHRT）；窗口是**预先固定的预处理超参**，不随任务变化 | 说明「不规则采样与缺失处理」也已解决；我们的时间角色（采集 vs 报告）与「未决」不是这些工作的关注点 | 未读 |

**时序选择问题的独立性判定（2026-10-08，DSH 核验，分两段）**：<br>**第一段——任务不新**：原以为「让 LLM 在多个时间点里选对那一个」是空白，**核查后推翻**；EHRSQL 的 `[time_filter_exact]` 已把 first/last（附录 Table 8 给出 first / second / second to last / last 四种 SQL 写法）列为标注类别并整体评测，且 93.2% 的查询涉及时间列。<br>**第二段——测量是空的**：EHRSQL **从不单独报告** first/last 这类题目的准确率（全文只有聚合 `F1_ans`/`F1_exe`；附录 H.2 对时间表达式只有定性举例、无数字；无谓词消融），其 H.1 更明确把错误归因于 **schema linking 失败**而非时间谓词；后续的 EHRSQL 2024 共享任务（ClinicalNLP 2024，DOI 10.18653/v1/2024.clinicalnlp-1.62，改报可靠性分数 `RS(c)`）同样**未按时间类型分别报数**。<br>**残余可辩护的位置共五处**：① **时间选择谓词的错误分布从未被单独测量**（模型在 first/last/Nth/窗口上各错多少、错在解释还是执行，无人回答）；② 输入是**真实扫描病历**，记录在表格重建之前不成立（实测：逐行抽取器值+单位完整 0 条，跨行重建 2,303 条明确记录）；③ **评分粒度**——「给选中集合打分」**也已有人做**：FHIR-AgentBench（ML4H 2025，[arXiv:2509.19319](https://arxiv.org/abs/2509.19319)）按 `true_fhir_ids` 打 retrieval P/R/F1，但粒度**只到 FHIR 资源 ID**、无「观测 ID + 显式时间点」一级，且其 judge 声明**忽略单位、日期可忽略时间与时区差异**（单位错与时刻错在答案指标里不扣分）；④ **采集时间 vs 报告时间**作为标注轴未被系统处理（TIMER 的金标准含时间证据但只用文本指标评回答；EHR-RAG 是方法论文非基准）；⑤ 「条件被声明 vs 必须推断」这条边界几乎没有被系统测量。据此，题目应改写为「真实扫描病历上的记录层 + 观测级时间点与时间角色的集合评分 + 按题型分报的时间谓词错误分布」，并把 EHRSQL 作为**主要对照基准**、FHIR-AgentBench 作为**可复用的集合评分骨架**（需关掉其单位/时刻宽松判定）。**未核线索**：BRIE（[arXiv:2609.30205](https://arxiv.org/abs/2609.30205)，预印本）是否已给带时间点的证据集合打分；TrustSQL（[arXiv:2403.15879](https://arxiv.org/abs/2403.15879)）同行评审状态未核实。

阅读视图见 [temporal_selection_related_work.html](temporal_selection_related_work.html)。

**当前设计吸收**：DocETL 约束计划改写与验证成本；Sufficient Context 约束证据不足与利用失败的区分；EHR-RobustGym 约束噪声类型与重复一致性；CliniCARE-Bench 约束多态弃答、证据 grounding 和轨迹可回放；**EHRSQL 约束我们把「时间条件推断」当既有工作、并作为主要对照基准**。上述是设计影响，不是对这些论文结果的复现。

## 阅读卡

w 本人的第一轮阅读卡**已经备好**，是仓库外的本地阅读包 `26.7-/EHR_Harness_论文阅读包/04_Agent数据准备与评测/`：

- `00_阅读总目录与顺序.md`：读什么、读哪里、读到什么算完。
- `01_AI-Ready数据集_阅读卡.md`、`02_Infherno_阅读卡.md`、`03_FHIR-AgentBench_阅读卡.md`、`04_HealthFlow定向_阅读卡.md`：逐节原文定位、术语解释、关键段落中译。
- `01b_AI-Ready清单与评分标准_原文转录.md`：补充材料 Table S1 / Table 4 的原文转录。
- `05_交师兄两页反馈_模板.md`：读完之后要交的两页。

四篇原文**已全部取得并落盘**（Infherno 与 FHIR-AgentBench 为 PDF，AI-Ready 为 Europe PMC 官方全文，HealthFlow 27 页），**不需要再获取一遍**。

每篇只要求 w 亲自回答四问，答案栏在卡片里**留空给本人写**——DSH 已读不等于 w 已读。

| 卡 | 论文 | 1. 它把什么输入变成什么输出 | 2. 它与什么方法比 | 3. 它依据什么判断更好或更差 | 4. 哪点适合我们 / 哪点不能直接搬 | 原文定位（DSH 已核） |
| --- | --- | --- | --- | --- | --- | --- |
| 卡 1 | **JCM AI-Ready 指南**（S5） | 日常诊疗记录 / 本地数据集 → 数据的**定义与文档**（不是模型，也不是结构化数据本身） | **没有对照实验**；只在 Discussion 与 TRIPOD+AI / FAIR / OMOP / OHDSI 做定位区分 | 「定义是否被清楚记录」；0–20 分 + 9 条一票否决；作者自陈阈值未经实证校准 | 可搬：时点子句、「重复测量口径必须抽取前定好」、缺失原因编码、把「混时点」设为否决级；不可搬：它没有任何 Agent 实验，也没把「准备好」与「下游变好」连起来 | §1、§2.1–2.2、§3.3、§3.4、§3.9、§4.3–4.4、§4.6、§5 |
| 卡 2 | **Infherno**（S4） | 自由文本临床记录 → 一个 FHIR Bundle | 人工参考标注；6 个 LLM；与模块化流水线 / 指令微调 + 约束解码定性对比 | 两个实验：`MedicationStatement.medication` 的 P/R/F1（人工归类）；合成数据逐项人工比对 | 可学「模型组织语义 + 程序负责合法性与报错 + 用报错驱动重试」；不可搬：规模 10+10、单标注者、3 类资源、评「是否合法」而非「是否方便下游使用」 | §1、§2、§3、§4、§5、Limitations |
| 卡 3 | **FHIR-AgentBench**（S6） | 自然语言临床问题 + 一个患者的 FHIR 数据 → **取回的资源集合 + 最终答案**（分开计分） | 检索策略 × 单轮/多轮 × 是否用代码，共 5 种架构；其中两种下横比 4 个模型 | 检索 P/R 与 Answer Correctness 分开；AC 由 LLM evaluator 判定、500 样本人工复核 97% 一致；统一 32k 上下文 | 可借：任务构造流程、「检索 / 作答分离计分」、错误分「检索失败 / 解读失败」；不可搬：金标准只到资源 ID 级、不含多患者题 | §1、§3、§4.1–4.2、§5.1、§5.2、§6 |
| 卡 4（定向） | **HealthFlow**（S7） | 已发布已去标识数据集 + 一条分析任务 → 代码 / 统计结果 / 报告工件 + 结构化裁决 | 多个通用 / 生物医学 Agent 框架；组件渐进消融；换模型 / 换执行器敏感性 | EHRFlowBench 的 1–5 分 LLM 评审；MedAgentBoard 二元成功率；12 位专家 240 次盲选 | 可借：把「下游需要什么输入」当准备层的验收标准；注意它记忆跨任务累积、基线每题独立，公平性口径不对等 | §4.1、§4.2、§4.5、§2.2 |

**用户阅读状态（截至 2026-09-20）**：四篇的卡片与原文都已备好，w **尚未填写四问**——不得记为已读，也不得把 DSH 的核验等级当成 w 的阅读进度。

**读法提醒**：卡 1 与卡 2 说明「准备」这一段的两种主流做法（人工量表 / 自动合成），两者都**不测「准备之后 AI 是否更好用」**——这正是我们要接的那一段。卡 3 与 S2 的 FHIRBench 是**两篇不同论文**，引用时按标题和标识符分开写。

## 扩展检索

| # | 论文（标识符 · 链接） | 材料类型与核对范围 | 为谁准备 / 什么任务 | 准备动作 | 对照 | 结果支持什么 / 哪些只是宣称 | 适合我们 / 不适合我们 | DSH 核验状态 | 用户阅读状态 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| E1 | **An actionable framework for AI-ready data**（[Wiley AAAI](https://onlinelibrary.wiley.com/doi/10.1002/aaai.70054)） | 元数据 | 通用（不限医疗）；组织级数据就绪框架 | 组织治理层面（元数据、质量、流程） | 框架对比，非实验 | 宣称框架可操作；不能支持任务级收益 | ⚠️ 说明「AI-ready」在**通用数据治理**里已被定义过，必须引用 | 线索已定位 | 未记录 |
| E2 | **Data Readiness for Scientific AI at Scale**（`arXiv:2507.23018`，[链接](https://ar5iv.labs.arxiv.org/html/2507.23018)） | 元数据 | 科学数据（非医疗专属） | 数据就绪度分级 | 分级框架 | 宣称分级可指导准备程度 | ⚠️ 与「分层」思路同源，我们的分层不能自称首创，必须说明差异（我们是**任务度量驱动**而非治理分级） | 线索已定位 | 未记录 |
| E3 | **AI Data Readiness and Model Sharing（AIRDW）**（[Drexel CCI 报告](https://mrc.cci.drexel.edu/wp-content/uploads/2024/05/AIRDW_2_5_Purushotham.pdf)） | 元数据 | 健康与气候科学；数据共享与就绪 | 就绪度维度划分 | 研讨报告 | 宣称维度清单 | ⚠️ 同上，引用即可 | 线索已定位 | 未记录 |
| E4 | **Agentic AI Workflow for Cancer Diagnosis/Staging Curation**（[Tempus](https://www.tempus.com/publications/an-agentic-ai-workflow-for-automated-high-fidelity-curation-of-cancer-diagnosis-and-staging-from-unstructured-patient-records/)） | **会议展示摘要**（不得冒充已读完整论文） | 真实非结构化病历 → 癌症诊断/分期结构化 | agent 工作流 + 人工审核 | 与人工审核对照 | 支持「agent 在真实病历上可做到高保真」；**这是抽取质量，不是数据准备程度的归因** | ✅ 真实数据 + agent 准备 + 人工对照，是我们该学的实验形态；❌ 不做「准备程度值多少」的分解 | 摘要已核 | 未记录 |
| E5 | **SLIDERS**（`arXiv:2604.22294`，[链接](https://arxiv.org/abs/2604.22294)） | 摘要 + 元数据 | 6~11M token 上的结构化抽取与编码对账 | 长上下文抽取 | 抽取 / 对账基线 | 支持「长上下文抽取已有系统级工作」 | ⚠️ 我们只做度量层，不做系统 | 摘要已核 | 未记录 |
| E6 | **SHIELD**（`arXiv:2605.03301`，[链接](https://export.arxiv.org/pdf/2605.03301)） | 摘要 + 元数据 | 企业级**去标识化**数据集与蒸馏小模型 | 隐私：去标识化 | 不同去标识化方法 | 支持「准备动作里隐私是一等公民」 | ✅ 提醒我们：真实病历的「准备」里包含**合规动作**——它已列为所有条件的共同前提（Proposal §十），不是可关闭的一层 | 摘要已核 | 未记录 |
| E7 | **BioXArena**（`arXiv:2605.15766`，[链接](https://ui.adsabs.harvard.edu/abs/2026arXiv260515766L/abstract)） | 元数据 | 多模态生物医学 ML 任务的 agent 评测 | 基准组织 | 多任务对照 | 支持「benchmark 已是成熟形态」 | ⚠️ 与我们不同层，引用以说明评测生态 | 线索已定位 | 未记录 |
| E8 | **MIMIC-IV + LM 基准**（[ACL CL4Health 2024](https://preview.aclanthology.org/proper-vol2-ingestion/2024.cl4health-1.23.pdf)） | 摘要 + 元数据 | 语言模型做 EHR 任务 | 数据已是结构化表 | 模型间对照 | 支持「EHR + LLM 有标准做法」 | ⚠️ 假定库已存在；正好说明我们研究的**是它前面那一段** | 摘要已核 | 未记录 |
| E9 | **NYUTron**（[Nature 2023, PMC10338337](https://pmc.ncbi.nlm.nih.gov/articles/instance/10338337/bin/41586_2023_6160_MOESM1_ESM.pdf)） | 摘要 + 元数据 | 医院内临床文本模型部署 | 院内自由文本；训练数据构建 | 与既有风险模型对照 | 支持「文本准备投入能换临床收益」 | ✅ 提供「准备值多少」的另一种度量传统（临床效用）；❌ 不是给现成 agent 用 | 摘要已核 | 未记录 |
| E10 | **agent 在数据仓库上的观察**（`10.64898/2026.09.02.26362008`，[medRxiv](https://www.medrxiv.org/content/10.64898/2026.09.02.26362008v1.full.pdf)） | 元数据 | agent 在数据仓库上做分析 | 研究 agent 能看到多少仓库 | 可见范围不同 | 支持「**agent 能看到多少数据决定它的表现**」 | ✅ 与我们「给消费者看什么版本」同一类变量 | 线索已定位 | 未记录 |

## 证据状态定义

每个结论必须能追到这一级。

| 状态 | 含义 | 允许的用法 |
| --- | --- | --- |
| **方法与结果已核** | 读到方法与结果的具体位置（表号 / 章节 / 源文件），数字可引用 | 可以引用数字，并给出版本与位置 |
| **原文部分已核** | 读了摘要 + 方法或结果的若干段 | 只能说该论文「做了 X」，不得引用数字细节 |
| **摘要已核** | 只读到摘要 / 元数据 | **不得引用任何数字或机制细节**，只能作为检索线索 |
| **线索已定位** | 只有链接与标题 | 不得写进论文正文 |
| **全文不可得** | 尝试获取失败 | 如实标注，不阻塞其他工作 |

**当前达到「方法与结果已核」的是 S1、S4、S5、S6 与 S7（定向）。** S2（FHIRBench）的全文本轮仍未取得，不得当成已复核；S3（HoloBench）是原文部分已核。

## 检索边界与待核缺口

下面三条是**检索覆盖内的待核缺口，不是结论**。

1. **「AI-ready」这个词已被占了三层**：通用数据治理框架（E1/E2/E3 的分级与维度）、临床人工量表（S5 的 0–2 级）、序列化 / 表示实验（S2/S1）。我们不能自称提出这个词，也不能只做其中任何一层。
2. **在本轮检索范围内**（关键词 + 近一年 + 若干相邻概念），现有工作的对象多为「已是结构化或合成的输入」（S2/S1/E8）或「抽取 / 合成质量」（S4/E4）或「人工量表」（S5）。**「从真实医院扫描件起、把每个准备动作的作用分开量」这一组合，本轮检索未命中同形工作**——这是待核缺口，不是「证明无人研究」。下一轮必须补：相邻概念（data readiness / clinical NLP preprocessing / 信息抽取评估）、**前后向引文追踪**、以及不止近一年的时间窗。
3. **三个必须避开的坑**：
   - HoloBench（S3）已占「聚合随规模退化、max/min 抗退化」——我们的队列级观察要写成复现与延伸。
   - S1 已给出「表示选择对 QA 与 ML 影响相反」的强证据——不能笼统写「结构化更好用」，必须**分任务类型**说，并解释与它的差别（它比「结构化→叙述」，我们比「扫描件→可用数据」）。
   - S1 还给出「检索归因」与「预算敏感性」两件现成工具（无检索基线、token 预算扫描）——我们已把它们列入待做；若不采用需说明理由。

## 下一步

1. **等 w 亲自读并填四问**：四篇卡片与原文都已备好，四问的答案栏留空给本人写；DSH 已核不等于 w 已读，不得代填，也不得记为已读。
2. **DSH 侧核对池**：FHIRBench 全文获取 → HoloBench → #4/#5/#6/#13/#16 的方法与结果。原文拿不到就标清楚，不写未经核实的结果。
3. **补检索**：按上面第 2 条列出的三个面补扫，新篇目按同样的问题入表。
4. **交给师兄**：四篇阅读结论 + 本表 + 两页反馈，请他一起分析。
5. **不许做的事**：不要为了让我们的曲线「看起来被支持」而挑着引用；已被占的位置（S3、S1）要主动写进正文。
