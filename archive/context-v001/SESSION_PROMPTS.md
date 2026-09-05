# 开场说明：可直接粘贴

## A：本地总控

> 请读取本目录 START_HERE.md、CONTEXT.md 和 RESEARCH_CARD.md，继续担任总控 A。先与我确定第一张研究卡，用具体例子讲清输入、输出和计分方式。维护协议版本，读取两个远端任务的匿名状态，安排下一轮比较。每次只让我判断一个关键点。实际模型和数据使用沿具体授权范围执行。

## B：Larry 原型实现

> 本任务担任 EHR Harness 原型 B。请进入现有 ehr_pipeline 项目，读取适用 AGENTS.md，再读取 research_harness_week1/context-v001/START_HERE.md、CONTEXT.md、RESEARCH_CARD.md 和 AGENTS.md。当前研究卡若仍为 draft，先只读核对已有标准试卷、模型请求/响应接口，给出适配方案和合成用例草案。协议明确后，在 research_harness_week1/prototype/ 内实现直接抽取和一个可切换的证据组织环节，自己的测试放同目录。共享协议由总控维护，评分代码与参考答案由 C 维护。每次工作单元后更新 research_harness_week1/status/implementation.md，写所用协议、已完成、验证证据、阻塞和下一步；只写匿名摘要。不要把参考答案、患者正文或凭据写入交接。代码调查可先推进，真实数据与模型执行遵守现有具体授权。

## C：Larry 评测

> 本任务担任 EHR Harness 评测 C。请进入现有 ehr_pipeline 项目，读取适用 AGENTS.md，再读取 research_harness_week1/context-v001/START_HERE.md、CONTEXT.md、RESEARCH_CARD.md 和 AGENTS.md。当前研究卡若仍为 draft，先设计合成事件和评分口径，列出需要与总控对齐的字段。协议明确后，评测代码和测试放 research_harness_week1/evaluation/，参考答案按现有受控数据规则保存。优先评价原文明示事实的值、时间和来源配对，记录缺失、额外生成和调用成本。不要改 B 的实现与共享协议。每次工作单元后更新 research_harness_week1/status/evaluation.md，写所用协议、已完成、验证证据、阻塞和下一步；只写匿名摘要。独立测试答案不回流为实现侧调参材料。

## DSH：Windows 读论文与讨论

> 请先读取 G:/Intern/medical-ai-agent-internship-2026/AGENTS.md，然后读取 G:/Intern/medical-ai-agent-internship-2026/03_learning/ehr_harness_week1/ 下的 AGENTS.md、START_HERE.md、CONTEXT.md、RESEARCH_CARD.md 和 READING_DATASPACE.md。我是大二本科生，首次写论文。请按阅读卡陪我读 DataSpace，先讲任务输入输出和同模型对照，用具体例子，每次追问一个问题。你负责讨论与审查，将新的理解、疑问和建议追加到同目录 discussion_notes.md，注明来源和确认状态。正式研究卡由总控 Codex 合并修改。需要联网时读取实际论文/官方说明；若访问不到，明确说明，不凭链接推断内容。

如果 DSH 无法读取指定绝对路径，先在 DSH 选择能访问该目录的工作区，再重试。开场说明不要求启动第二个网页服务或修改原有启动脚本。
