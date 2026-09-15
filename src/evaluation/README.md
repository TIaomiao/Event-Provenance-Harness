# 评测实现

C 在此目录维护评分器及对应测试。当前为 `c-eval-dev-v0.1` 合成开发自检，依据研究卡 v0.3 / 共享合成口径 v0.1。用户已确认将明确版本同步到远端 `research_harness_week1/evaluation/`，本地维护源码。

- [设计、评分口径与 A 待定清单](DESIGN.md)
- [开发参考人工核对空模板](REVIEW_TEMPLATE.md)
- `fixtures.py`：12 条手工合成原始观测、参考断言与身份关系；仅开发材料。
- `scorer.py`：独立离线评分器，标准库实现，不依赖 B。
- `demo.py`：正确、错角色、漏复测、误合并、额外输出五种人工提交的诊断。
- `tests/test_scorer.py`：来源/时间/身份/缺失/成本和异常输入验证。

在研究工作区根目录运行：

```text
python -m unittest discover -s src/evaluation/tests -v
python src/evaluation/demo.py
```

远端在 EHR 项目根目录使用 `research_harness_week1/evaluation/tests` 和对应 `demo.py` 路径。
单次评分：`python scorer.py --gold REFERENCE.json --prediction SUBMISSION.json`，仅向标准输出给匿名聚合结果；对实际参考答案必须在受控端运行。

主指标 joint 检查值/单位、采样时间与来源支持，full_record 另要求所有时间角色完整；身份误合并/误拆分分开报告。0 个真实模型运行结果。本轮未建立真实开发参考集或独立测试集；人工核对和共享序列化定版仍待完成。

真实参考答案留在受控环境。独立测试答案和逐题反馈不得回流实现侧调参；本地测试文件只含合成开发材料。
