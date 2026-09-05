# EHR 研究文献地图 v0.1

建立日期：2026-08-26  
方法来源：《AI Research Handbook》的 BFS → DFS、Seed Paper 滚雪球和文献打表法。

## 使用规则

- 这张表是研究基建，不是引用装饰。
- “已读状态”只允许：`仅见公开条目`、`读摘要`、`读原文`、`跑代码`、`完成复现`。
- 只有读过论文原文或官方代码，才能填写方法结论、实验结论和关键局限。
- 公众号、知乎和个人整理只用于发现论文，不作为实验结论的一手证据。

## 种子工作

| 工作 | 年份 / venue | 初始标签 | 可确认的公开入口 | 已读状态 | 下一步要回答 |
| --- | --- | --- | --- | --- | --- |
| M3Care: Learning with Missing Modalities in Multimodal Healthcare Data | KDD 2022 | missing modality / EHR modeling | 朱英豪公开 CV | 仅见公开条目 | 缺失模态设定、baseline、数据与指标是什么？ |
| A Comprehensive Benchmark for COVID-19 Predictive Modeling Using EHRs in Intensive Care | Patterns 2024 | benchmark / EHR prediction | 个人主页、代码 PyEHR | 仅见公开条目 | benchmark 的 split、模型范围与可复现性如何？ |
| PRISM: Mitigating EHR Data Sparsity via Learning from Missing Feature Calibrated Prototype Patient Representations | CIKM 2024 | sparsity / prototype | 朱英豪公开 CV | 仅见公开条目 | 与 PAI 的问题假设和缺失表示有何差别？ |
| EMERGE: Enhancing Multimodal EHR Predictive Modeling with Retrieval-Augmented Generation | CIKM 2024 | multimodal / RAG | 个人主页、代码 EMERGE | 仅见公开条目 | RAG 在预测中输入什么、如何防止泄漏？ |
| Learnable Prompt as Pseudo-Imputation | KDD 2025 | missingness / prompt | ACM、PAI 代码入口、公开 CV | 读二手解读 | prompt 与 backbone 如何训练，最强 baseline 和局限是什么？ |
| ColaCare | WWW 2025 | multi-agent / EHR modeling | 个人主页、代码、项目页 | 仅见公开条目 | 多 Agent 相比强单模型的增益来自哪里？ |
| MedAgentBoard | NeurIPS 2025 Datasets & Benchmarks | benchmark / medical agents | 个人主页、代码、项目页 | 仅见公开条目 | conventional methods 如何参与对比，评价任务是否接近真实工作流？ |
| HealthFlow | 公开论文与代码入口 | EHR workflow / guardrail / memory | 本地源码快照、个人主页 | 读源码框架 | 正式论文实验口径、benchmark 金标准和跨机构边界是什么？ |
| ClinicRealm | npj Digital Medicine 2026 | LLM vs conventional ML / clinical prediction | Nature 论文、代码、项目页入口 | 仅见公开条目 | 什么条件下常规模型胜过 LLM，评价是否公平？ |
| OneEHR | KDD 2026 Hands-on Tutorial | longitudinal EHR / reproducibility / toolkit | 代码与项目页入口 | 仅见公开条目 | 数据模型、纵向任务契约和 Agent-ready 具体指什么？ |

## BFS 时必须补齐的字段

| 维度 | 要记录的问题 |
| --- | --- |
| Task Definition | 输入、输出、预测时点、标签窗口是什么？ |
| Dataset Ecosystem | 数据公开性、中心、患者规模、事件类型和缺失机制是什么？ |
| Methods | 最强 baseline、关键模块、训练协议和复杂度是什么？ |
| Evaluation | 患者级 split、时间泄漏控制、metric、置信区间和统计检验是什么？ |
| Evidence | motivating figure、preliminary experiment、主实验和消融各支撑什么 Claim？ |
| Reproducibility | 代码、数据、配置、版本、运行成本和真实复现状态是什么？ |
| Groups | 哪些团队连续做这一问题，工作如何演化？ |
| Limitations | 论文自述局限、审稿争议、跨中心和临床部署边界是什么？ |
| My Judgment | 这个问题与当前 EHR 治理的真实交集是什么？是否值得做 preliminary experiment？ |

## DFS 候选顺序

1. HealthFlow：因为已有本地源码，与当前治理护栏最接近。
2. OneEHR：判断纵向 EHR toolkit 与病例级标准试卷的关系。
3. PAI + PRISM + M3Care：形成一条缺失表示方法链，而不是只读一篇热点论文。
4. ClinicRealm + PyEHR benchmark：建立“强常规 baseline 优先”的评价意识。
5. MedAgentBoard + ColaCare：研究 Agent 的增益如何被公平评估。

完成标准不是“表里有很多论文”，而是能从表中提出一个由 preliminary evidence 支撑、可用现有权限验证的问题。

