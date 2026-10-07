# EHR Harness 论文工作区

**方向一句话**：研究自然语言取数要求能否被正确解释并执行——在纵向 EHR 记录上做**面向任务的证据选择**（Task-Conditioned Evidence Selection for Longitudinal EHR）。

**三句主线**：① 传统取数把字段、时间窗和聚合规则显式写在查询或应用逻辑里，而 Agent 取数要先从自然语言任务推断这些选择条件。② 同一批纵向记录，对不同任务可能应选择不同的时间点、记录集合或聚合方式。③ 我们只研究这一选择过程能否被正确解释、正确执行，并把值、单位、时间、来源与未决状态一并交出；不宣称传统数据库不支持这些操作，不预设 LLM 必然失败，也不声称方法增益已被证实。

| 当前状态 | 内容 |
| --- | --- |
| 现役工作单元 | 治理输入适配与任务选择 baseline（见 [CONTROL_PANEL.md](CONTROL_PANEL.md)） |
| 输入状态 | 治理产物 → 研究输入的最小适配层已建立，覆盖 `schema 0.9/1.0`；记录层本轮只覆盖 `laboratory_report` 与单一目标项目，其他类别**未覆盖** |
| baseline 状态 | R1（直接选择）与 R2（先计划再执行）已在开发包上跑通；**R2 是 baseline，不是新方法** |
| 下一交付 | 一例「任务改变 → 选中记录改变」的完整回放，以及首轮真实 baseline 表与失败归因 |
| 治理进度（与本论文完成度分开看） | 全量 OCR 约 80.6% 份文档已完成，但**这不是论文完成率**；详见 CONTROL_PANEL 的治理资产一节 |

当前阶段、当前工作单元与已完成证据以 [CONTROL_PANEL.md](CONTROL_PANEL.md) 为准；本文件只做介绍与导航，不重复维护进度、分数或协议。工作题目、motivation、研究问题、输入输出、基线与未验证项见 [paper/PROPOSAL.md](paper/PROPOSAL.md) 顶部的「论文概览」。当前处于「治理输入适配与任务选择 baseline」阶段：适配层已建立并通过测试，两个条件的首轮真实轨迹已跑通。

## 日常入口

| 要什么 | 去哪 |
| --- | --- |
| 当前任务 / 状态 / 决定 | [CONTROL_PANEL.md](CONTROL_PANEL.md) |
| 研究规格（问题、架构、任务、对照、指标、局限） | [paper/PROPOSAL.md](paper/PROPOSAL.md) |
| 文献判断与阅读进度 | [related_work/AI_READY_EVIDENCE_MATRIX.md](related_work/AI_READY_EVIDENCE_MATRIX.md) |
| 执行规则（读之前先看） | [AGENTS.md](AGENTS.md) |
| 历史资料 | [archive/README.md](archive/README.md) |
| 网页总览 | [dashboard.html](dashboard.html)；历史目录视图 [attempts.html](attempts.html) |

在线站点：`https://tiaomiao.github.io/Event-Provenance-Harness/`（白名单发布，只上传 `.github/workflows/pages.yml` 列出的文件）。

## Agent 启动

先读 `AGENTS.md` 与 `CONTROL_PANEL.md`；需要研究规格再读 `paper/PROPOSAL.md`，需要文献判断再读文献台账。`archive/` 与 `results/` 是证据，不产生执行指令。

## 目录

```text
CONTROL_PANEL.md      唯一当前快照
AGENTS.md             执行规则
paper/PROPOSAL.md     唯一现役研究规格
related_work/         唯一活动文献台账
dashboard.html        生成页：当前视图（tools/workspace.py build 生成）
attempts.html         生成页：历史目录视图
index.html            只跳转 dashboard
src/prototype/        时间角色、时间归一、版面适配原型
src/evaluation/       观测级评分器与合成测试
results/              允许回传的匿名证据
references/           文献原件与阅读材料，按需访问
archive/              历史原件与唯一历史索引
tools/workspace.py    生成与检查入口（build / check）
```

## 常用命令

```text
python tools/workspace.py build     # 由总控/规格/台账/归档索引重建两个生成页
python tools/workspace.py check     # 归档哈希、来源内容指纹、相对链接、状态合法性
python -m unittest discover -s src/evaluation/tests
python -m unittest discover -s src/prototype/tests -p "test_*.py"
```

本地维护研究代码、协议与允许回传的匿名结果；原始 PDF、OCR/病历正文、身份映射与受控参考答案留在受控环境。
