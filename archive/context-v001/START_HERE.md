# EHR Harness 第一轮研究入口

交接版本：context-v001，2026-09-05。
研究状态：第一张研究卡的任务已确认：重复检验与时间匹配；字段和评分草案待 B/C 核对，尚未运行本轮实验。

## 读这几份就能接上讨论

1. CONTEXT.md：目标、已知基础与当前分工。
2. RESEARCH_CARD.md：第一轮候选任务、比较与成功标准。
3. SESSION_PROMPTS.md：按 A / B / C / DSH 选择角色。
4. READING_DATASPACE.md：第一次读论文的 50 分钟路线。

已有历史资料只按实际需要进一步读取，论文工作的当前目标以用户本次澄清和本交接为准。

## 本地与远端的联系

- 本地总控维护这份研究底稿。用户与 Codex 或 DSH 形成新结论后，总控更新版本并显式同步远端；聊天记录不会自动跨工具共享。
- Larry 的 EHR 项目内使用 research_harness_week1/context-v001/ 作为本次只读交接包；B/C 必须使用同一版本。
- B 更新 research_harness_week1/status/implementation.md，C 更新同目录 evaluation.md；只写匿名进展，禁止患者正文和原始模型输出。
- 本地总控通过 pull_status.ps1 按需拉取两份状态，存入带时间戳的 remote_status/ 子目录，再整合到本地进度。
- 本地 DSH 直接读本目录文件。discussion_notes.md 是 DSH 的提议区，总控吸收后才改变正式协议；无需将整段历史聊天导出。

这些文件提供可检查的交接。尚未创建 B/C 的 app 任务，尚未设置自动轮询或启动模型执行。
