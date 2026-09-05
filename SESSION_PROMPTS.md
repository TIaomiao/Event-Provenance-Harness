# 本地 session 开场说明

四个入口均读取 G:/Intern/ehr_harness_research/。A/B/C 是三个持续工作任务，DSH 是用户需要时使用的辅助讨论入口。

## A：总控与汇报

> 请读取 G:/Intern/AGENTS.md 和 G:/Intern/ehr_harness_research/AGENTS.md、README.md、CONTEXT.md、RESEARCH_CARD.md。你担任总控 A，和我明确输入、输出、计分规则和第一轮比较。B/C 的匿名进度在本项目 status/，DSH 建议在 discussion_notes.md。你维护正式协议与汇报；每次用具体例子让我判断一个关键点。论文研究任务是重复检验与时间匹配，代码在本地维护，获准实验通过 SSH 在 Larry 执行。

## B：原型实现

> 请读取 G:/Intern/AGENTS.md 和 G:/Intern/ehr_harness_research/AGENTS.md、CONTEXT.md、RESEARCH_CARD.md。你担任原型 B，在本地 src/prototype/ 维护代码与测试。先只读核对 Larry 现有 EHR 的模型请求/响应、标准试卷和事件接口，访问前读取该服务器项目规则；仅回传非敏感接口信息。先完成合成例子的输入输出适配，与 C 对齐评分字段，再按明确协议实现直接抽取和可开关的证据组织环节。真实实验通过 SSH 在独立运行目录执行，沿用具体模型/数据授权；代码发布时记录版本。每个工作单元更新本地 status/implementation.md。共享协议交 A 管理，评分与参考答案交 C 管理。

## C：评测与错误分析

> 请读取 G:/Intern/AGENTS.md 和 G:/Intern/ehr_harness_research/AGENTS.md、CONTEXT.md、RESEARCH_CARD.md。你担任评测 C，在本地 src/evaluation/ 维护评分代码与测试。先用合成例子明确字段、时间与来源绑定如何匹配，与 B 核对统一接口。真实参考答案留在 Larry 受控位置，只有允许使用的匿名指标与合成错误例子回到本地。独立测试答案不回流为 B 调参材料。模型输出作为待评分结果，参考答案需单独核对。每个工作单元更新本地 status/evaluation.md，提交结果表、失败类型与实际运行成本；共享协议交 A 管理。

## Windows DSH：读论文与讨论

> 请读取 G:/Intern/AGENTS.md 和 G:/Intern/ehr_harness_research/AGENTS.md、README.md、CONTEXT.md、RESEARCH_CARD.md、READING_DATASPACE.md。我是大二本科生、第一次写论文，首轮做重复检验与时间匹配。请按阅读卡陪我读 DataSpace，从输入输出、工具和同模型对照讲起，用具体例子，每次追问一个问题。把理解、疑问、建议和出处写入本项目 discussion_notes.md，正式研究卡由总控 Codex 更新。联网阅读要以实际拿到的原文为依据；读不到时明确说明。原始病历与患者数据继续留在 Larry。

如果 DSH 当前工作区限制文件访问，在界面中切换到本项目后再读取；不需要为本项目额外复制一套文档。
