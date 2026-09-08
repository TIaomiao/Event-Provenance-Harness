# 可视化面板更新协议

`dashboard.html` 是论文仓库的研究总览入口，不承载患者正文或真实参考答案。它的内容必须能从仓库内的匿名 Markdown 状态和结果文件追溯。

仓库已配置 `.github/workflows/pages.yml`：推送到 `main` 后自动部署 GitHub Pages。在线面板地址为 `https://tiaomiao.github.io/Event-Provenance-Harness/`（首次使用需在仓库 Settings → Pages 中将 Source 设为 GitHub Actions）。

## 子 session 完成一个工作单元时

1. 更新自己的 `status/`、`discussion_notes.md` 或 `results/` 文件，写清日期、协议版本、完成事项、验证证据、阻塞和下一步。
2. 在 `CONTROL_PANEL.md` 更新自己负责的 session 行、实验队列或最新事件。
3. 把同一变化压缩成一句面板语言，更新 `dashboard.html` 的对应卡片；如果是新机制、反例、师兄决策或重要边界，增加入口链接或“论文强度护栏”事件。
4. 做链接和敏感内容检查，再提交 Git。代码完成、合成测试通过、真实运行和论文结论要分别表述。

## 页面维护原则

- 页面展示“已实现 / demo only / 推测 / 待补证据”，不把候选设计写成结果。
- 数字只来自当前状态或结果文件；如果数字变化，先改证据文件，再改页面。
- 新增的有用信息必须挂到仓库中的稳定文件，不能只写在聊天或临时日志里。
- 页面可以继续保持单文件打开；若未来信息量增大，再将数据抽成 `dashboard_data.js`，由页面统一渲染。
