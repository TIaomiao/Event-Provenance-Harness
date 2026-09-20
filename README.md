# EHR Harness 论文工作区

**方向一句话**：把扫描病历中的处理能力组织成可调用、可核验、可复用的系统（Harness），由 Agent 编排调用，并验证它对后续 AI 使用的帮助。

当前阶段是**用户首轮阅读与研究反馈**：四篇精选文献的原文与阅读卡已备好，等 w 亲自读、填四问并整理成给师兄的两页反馈。工作题目、motivation、研究问题、待验证主张与候选贡献见研究规格顶部的「论文概览」。

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
