# EHR Harness 论文工作区

用户于 2026-09-05 确认：本地 PC 为论文唯一主工作区，Larry 保留数据与实验运行，zian 保留会议归档。

## 从这里开始

1. [当前上下文](CONTEXT.md)：目标、分工、现状。
2. [第一张研究卡](RESEARCH_CARD.md)：已选择重复检验与时间匹配。
3. [DataSpace 首轮阅读卡](READING_DATASPACE.md)：约 50 分钟，带着任务问题读。
4. [session 开场说明](SESSION_PROMPTS.md)：本地 A/B/C 和 DSH 的启动入口。
5. [归集与文件盘点](MIGRATION_REPORT.md)：复制范围、验证结果与远端文件数。
6. [工程补救计划](ENGINEERING_PLAN.md)：本对话的当前实现、验证与下一步。
7. [论文阅读与idea交接](RESEARCH_IDEA_HANDOFF.md)：给另一对话的研究问题与输入输出规格。

## 目录

| 位置 | 用途 |
| --- | --- |
| 根目录研究文件 | 当前有效的研究卡、上下文、讨论与分工 |
| src/prototype/ | 原型代码与对应测试，由 B 维护 |
| src/evaluation/ | 评分代码与对应测试，由 C 维护 |
| status/ | B/C 的本地匿名进度 |
| references/ | 历史文献笔记，具体事实使用前按版本核对 |
| paper/ | 后续论文正文、汇报与允许使用的图表 |
| results/ | 允许回传的匿名指标、版本清单与图表 |
| archive/ | 归集前文件快照，保留历史出处 |
| migration_manifest.json | 原始资料的 SHA-256 复制清单 |

本地 session 通过 SSH 调用 Larry 的脚本；模型菜单是否在远端正常工作不影响该组织方式。服务器使用确定版本的代码运行，匿名结果回到本地用于分析与写作。

2026-09-08 已实现独立时间候选适配器，并完成23项跨平台测试与2例真实开发样本验证。事件评分器和真实模型A/B实验仍待推进；阅读与idea由另一对话衔接。
