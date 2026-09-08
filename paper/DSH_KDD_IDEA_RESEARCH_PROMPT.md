# 给本地 DSH 的 KDD idea 调研任务

必须加载 web-access skill 并遵循其公开来源核验规则。你是独立文献调研 agent，不读取患者数据，不修改代码，不把摘要级推断写成已确认事实。

目标：面向 KDD 风格的计算机论文，调研 2025–2026 公开工作，判断下面这个候选中心命题是否与近期趋势和已有工作冲突，并提出可验证的改进：

> Event identity and provenance are a missing substrate for reliable agentic analysis over real longitudinal EHR exports.

当前真实工程背景：已有肺癌 EHR 的 PDF→OCR/bbox→本地脱敏基础；已有时间候选适配器、病例级事件表、来源引用和统一模型接口；尚无真实模型 A/B、完整事件评分器和独立测试。首轮切入口是重复检验的值—时间—来源匹配，但不等于整篇论文范围。

请只返回一份研究备忘录，不修改本地文件，长度控制在 1200–1800 字，包含：

1. 最近 8–12 篇最相关的论文或官方项目（优先 arXiv 2026、KDD/顶会），每篇写题目、链接、日期/venue、问题、核心机制、评价方式，以及与本候选命题重合/不同的地方。至少覆盖 DataSpace、ClinLens、HealthFlow，以及你找到的 2–4 篇最新 agentic data / longitudinal EHR / provenance / temporal clinical IE 工作。
2. 三条趋势判断：哪些是真趋势，哪些只是包装词。特别检查 benchmark、agent harness、adaptive structuring、evidence provenance、temporal reasoning、cost-aware evaluation。
3. 对候选命题做反驳审查：最强的三条“这只是 ETL/RAG/多 Agent 拼装”的反例，什么实验能区分。
4. 在不夸大新颖性的前提下，给出一版 KDD 题目、1–2 条 motivation、3 条相互依赖且可检验的创新点。创新点必须落到具体机制或评价，不能只写“用了多 Agent”“输出了 JSON”“用了真实数据”。
5. 明确区分：论文事实 / 摘要级线索 / 你的推测 / 还缺的原文核验。若查不到 AirVx 的明确全名或链接，写“未核验”，不要猜。

最后给出：若只能完成目前工程基础和一个小型重复检验实验，论文主张应降到什么强度；若要达到完整 KDD 论文，还必须补哪三项证据。
