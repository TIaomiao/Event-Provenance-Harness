# 评测状态

## 2026-09-13 · C 工作单元 11：匿名开发事件核对表

- 协议：research-card-v0.3/shared-synthetic-v0.1；scorer 保持 c-eval-dev-v0.1，未评分真实效果、未修改评分规则。
- 已完成：依据 B 的 20 条匿名候选范围和 `REVIEW_TEMPLATE.md`，新增 `src/evaluation/REVIEW_TEMPLATE_20.csv` 与 `REVIEW_TEMPLATE_20.md`。字段覆盖值、单位、日期候选、时间角色、表头范围、来源定位、来源支持、重复/副本关系、人工判断状态、双人核对与冻结摘要。
- 数据边界：本地仅保存 20 行空模板和匿名字段说明；B 的受控候选正文、OCR、真实路径和参考答案未读取、未复制。
- 验证证据：模板列数与字段说明一致；评分器版本/发布清单未变。当前无真实事件答案、无真实病例评分。
- 阻塞：候选的实际值、日期和来源定位需在受控环境逐条核对；人工核对完成前不能生成 gold 或报告准确率。
- 下一步：在受控端填入 10–20 条候选，双人独立核对后裁决；冻结 reference_version/content_digest，再用现有 scorer 做开发集评分。独立测试另分病例，答案不回流 B 调参。

## 2026-09-13 · C 工作单元 10：最新提交复评（HH:MM:SS）

- 协议：research-card-v0.3/shared-synthetic-v0.1；现有 c-eval-dev-v0.1。scorer.py 与 fixtures.py 的 SHA-256 均与发布清单一致，本轮未修改代码或参考答案。
- 输入：B independent_source_submission.json，9567 字节；SHA-256 为 07ded489e3b11372ed4897bfe67950c0900b2dab4fcc4c6c98a0c904f7d7854b。评分前后提交字节一致。
- 结果：protocol 兼容；aligned=12/12；value、unit、sampling_time、all_time_assertions、source_support 均为 12/12；joint/full_record TP=12、FP=0、FN=0、precision/recall/F1=1.0。漏观测、额外观测、来源对齐歧义均为 0。
- 对比上一轮：source_support 8→12（+4）；sampling_time 12→12；all_time_assertions 12→12；joint/full_record F1 0.6667→1.0（+0.3333）。
- 身份：correct=3、false_merge=0、false_split=0；missing_decision=1，未决关系仍是覆盖缺口，不能称身份全项通过。
- 成本：提交账本报告调用、失败调用、输入/输出 token、费用和墙钟时间均为 0（USD）。这是提交方填报值，未独立测量实际执行时间；零值不等同缺失，也不作为实测零耗时结论。
- 证据：完整评分及输入哈希已更新至 src/evaluation/b_score_independent_source_submission.json；上一轮结果已另存 score_previous_*.json。使用冻结版本直接评分，不以接口烟雾测试作比较基线。
- 边界：这是反复使用的合成开发输入上的复评，不能说明真实病例、未见样本或模型效果。没有重建真实金标准。
- 生成路径核查：B 脚本未导入 C EXPECTED，但以硬编码 ROWS 和逐行特殊分支构造结果，未调用通用源材料解析流程。因此本次满分证明当前提交符合合成参考，不证明独立抽取算法已实现或有效。
- 阻塞与下一步：当前观测评分无剩余错误；显式未决身份仍需后续独立版本支持。保留本版 scorer，按 REVIEW_TEMPLATE.md 在受控环境人工核对 10–20 条真实开发事件；独立测试另分病例并隔离答案。
- 面板检查：CONTROL_PANEL.md 开头出现大量重复拼接内容，当前无法可靠定位 C 行；本轮不覆盖他人面板内容，最新结果以本状态和评分 JSON 为准。

## 2026-09-11 · C 工作单元 1：合成评测开发

- 所用协议：用户本轮确认采用本地研究卡 v0.3 / shared-synthetic-v0.1；C 实现版本 c-eval-dev-v0.1。远端 context-v001 仍为旧草案，本轮未修改共享协议。
- 已完成：读取本地/远端适用规则与交接文件；编写 12 条手工合成观测、独立预期字段、评分器、45 项测试、五种人工提交的诊断；形成 A 待对齐清单及 10–20 条开发事件的空白核对模板。
- 验证证据：Windows `python -m unittest discover -s src/evaluation/tests -v`，45/45 通过；正确提交 joint TP=12，错角色 TP=11/FP=1/FN=1，漏复测 FN=1，额外输出 FP=1，误合并身份对=2。代码及设计见 `src/evaluation/`。
- 边界：以上都是评分器自身的合成开发测试，尚未运行 B 输出或模型对照；真实病例/PDF/页面处理均为 0，真实参考答案尚未创建。独立测试答案及逐题结果不回流 B。
- 阻塞：无影响合成自检的阻塞。B 实际联调前仍需 A 定版时间子字段、原始行/归并事件映射、身份关系与来源支持集；真实参考待独立人工核对。
- 下一步：同步明确版本到用户指定远端 evaluation 目录，校验哈希并运行远端测试；随后由 A/B 使用开发序列化确认接口。

当前解释：C 已完成合成评分与远端发布；真实 B 输出、真实病例、真实模型和临床参考答案仍未运行。

历史：此前状态为未启动，仅完成工作区交接，没有评分器或模型结果。

## 2026-09-11 · C 工作单元 2：远端同步与验证

- 所用协议：research-card-v0.3/shared-synthetic-v0.1；发布标识 c-eval-dev-v0.1，七个源码/测试/文档文件的 SHA-256 见 `src/evaluation/RELEASE_MANIFEST.json`。
- 已完成：8 个文件（含清单）同步到指定远端 evaluation 目录，逐文件哈希一致；原目录没有既有评测实现，未覆盖 B 文件或共享协议。五类匿名诊断保存为 `src/evaluation/synthetic_demo_results.json`。
- 验证证据：Windows 与远端评测测试各 45/45 通过；远端项目要求的 `test_ehr_pipeline` 43/43 通过；命令行有效提交与畸形 JSON 两种入口检查通过。没有新增依赖或模型调用。
- 同步复核：七个发布文件及五类诊断结果均通过跨端哈希核验；诊断产物已统一 UTF-8/LF。远端状态读回一致，旧状态独立保留。汇总见 `src/evaluation/VALIDATION.md`。
- 评分说明：正确示例 joint=12/12；错角色=11/12；漏一行产生 FN=1；多一行产生 FP=1；误合并即使字段仍 12/12，也单报 false_merge=2。不能只用字段分掩盖身份错误。
- 阻塞：B 实际提交的共享序列化、身份关系和来源等价支持集待 A 对齐；10–20 条真实开发事件待人工核对；正式独立测试还需病例隔离、答案冻结及有效角色访问控制。共享账号下 0700/0600 不等于实现侧不可访问。
- 下一步：A 查看 `src/evaluation/DESIGN.md` 的待定表，B 按定版接口交合成事件表后由 C 实际评分；随后在受控环境建立开发参考。独立测试答案和逐题错误不提供给实现侧调参。
- 状态边界：已实现合成评分器；本轮没有 B 实际效果、真实参考答案、临床准确率或真实模型 A/B 结果。推测暂无。

## 2026-09-11 · C 工作单元 3：B 合成提交接口检查

- 输入：`src/prototype/synthetic_submission.json`；只读读取，未修改 B 文件。
- 结果：`c-eval-dev-v0.1` 返回 `invalid_output`，错误码 `PREDICTION_PROTOCOL_MISMATCH`；匿名报告保存为 `src/evaluation/b_score_synthetic_submission.json`。
- 计数：参考观测 12；joint TP=0、FN=12；FP 未定义。调用成本未记录，不补零。
- 原因：B 提交使用 `schema_version/events/event_time/temporal_role/evidence`，当前 C 协议要求 `protocol/observations/time_assertions/source_refs`。两者字段语义不能安全地一一映射，未自行编写适配器或改变评分口径。
- 下一步：由 A/B 对齐输出层（原始观测行、采样/报告等多时间断言、稳定 evidence ID、身份关系和成本账本）后，C 再按冻结协议重评分。当前结果只表示接口不兼容，不表示 B 的抽取质量为零。

## 2026-09-12 · C 工作单元 4：B 第二版提交评分

- 输入：B 更新后的 `src/prototype/synthetic_submission.json`；协议字段已通过，C 评分器进入正式计分路径。
- 结果：状态 `scored`，但与当前独立合成金答案没有可对齐的稳定来源 ID：B 使用 `E-R-GLU/E-R-ALT/E-R-HGB`，金答案使用另一套独立 row ID；因此 aligned=0、joint TP=0、FN=12、FP=3、F1=0.0。该分数不能解释为 B 的抽取质量。
- 另外发现：B 仅提交 3 条观测，而当前开发金答案包含 12 条；项目和值也存在差异（例如参考中的 X/Y 与提交中的 X/Y/Z）。身份关系未提交，故 identity status=`not_reported`。
- 成本：未提供 cost，记录为 `not_recorded`，没有补零。
- 证据：评分结果保存于 `src/evaluation/b_score_synthetic_submission.json`；评分器自测仍 45/45 通过。
- 阻塞：需 B 使用与合成输入对应的稳定 evidence/row ID，或由 A 明确发布受控映射；同时明确本次提交对应哪一组开发 fixture，才能进行有意义的字段和时间评分。
- 下一步：先对齐 fixture、证据 ID 和观测覆盖范围，再重跑；在对齐前不报告质量结论，不修改 B 实现。

## 2026-09-12 · C 工作单元 5：B 独立来源提交复评分

- 输入：B 更新后的 `src/prototype/independent_source_submission.json`；协议通过，评分器成功运行。
- 结果：12/12 观测按 `r1`–`r12` 对齐；joint TP=0、FN=12、FP=12、F1=0.0。该结果不等同于抽取质量为零，因为时间引用和来源支持字段仍与独立金答案不一致。
- 字段诊断：value=11/12、unit=12/12、sampling_time=8/12、all_time_assertions=3/12、source_support=0/12；identity 正确关系 3，未决覆盖缺口 1，未报告误合并。
- 成本：未提供 cost，保持 `not_recorded`。
- 证据：结果已写入 `src/evaluation/b_score_independent_source_submission.json`；评分器测试 45/45 通过。
- 下一步：若要产生可解释的 joint 分数，B 需按同一 fixture 提供可核对的日期/角色/范围 evidence ID，或 A 发布受控等价支持映射；本轮不修改 B 文件、不回流独立答案作调参材料。

## 2026-09-12 · C 工作单元 5：统一夹具接口烟雾测试

- 输入为 B 目录下的 `unified_fixture_submission.json`，协议字段和来源集合已与 C fixture 对齐。
- 结果：aligned=12，joint/full_record F1=1.0，value/unit/sampling/source_support 均 12/12，身份关系 3 项正确、1 项 unresolved。
- 关键边界：`unified_fixture_submission.py` 直接导入 C `fixtures.EXPECTED`，结果是参考答案回包装的接口烟雾测试；不能作为 B 独立算法结果或模型效果。
- 下一步：等待 B 从自身合成解析流程生成提交，再用相同 scorer 评分；真实开发参考仍未建立。

## 2026-09-12 · C 工作单元 6：统一夹具状态解释

- 当前状态：协议联调已通；统一夹具得分只证明包装字段、稳定来源集合和评分入口可互操作。
- 质量状态：B 的独立生成路径仍未得到可解释的质量分；此前独立来源提交的 0 分主要由 fixture/来源 ID/观测覆盖不一致导致，不能直接作为抽取质量结论。
- 下一步：B 使用同一源材料独立生成完整 12 条 observations，保留 C fixture 的来源命名与覆盖映射；C 复评分并单独记录身份关系。

## 2026-09-12 · C 工作单元 7：独立提交诊断结论

- B 独立提交已成功进入评分路径并对齐 12/12 原始观测；joint=2/12，full_record=0。
- 字段诊断：value=12/12，unit=12/12，sampling_time=8/12，all_time_assertions=6/12，source_support=2/12；身份关系部分报告。
- 解释：主要是时间断言和来源支持与独立参考不一致；这不是“抽取质量为零”，也不是协议不兼容。需要在同一 fixture、同一证据 ID 和完整覆盖下修正后再测。
- 下一步：接收 B 修正版，复评分；评分器测试继续保持 45/45。

## 2026-09-12 · C 工作单元 7：B 新独立提交评分

- 输入：`src/prototype/independent_source_submission.json`，修改时间 HH:MM:SS；protocol、观测数量和来源行 ID 均通过校验，使用现有 c-eval-dev-v0.1，未修改评分规则。
- 覆盖：prediction=12、gold=12、aligned=12、missing=0、extra=0、ambiguous_source_predictions=0。
- 字段：value=12/12，unit=12/12，sampling_time=8/12，all_time_assertions=6/12，source_support=2/12，joint=2/12；joint TP=2、FP=10、FN=10、precision/recall/F1=0.1667。
- 完整记录：full_record TP=0、FP=12、FN=12、F1=0.0。identity status=reported，correct=3，false_merge=0，false_split=0，missing_decision=1。
- 成本：记录为 calls=0、failed_calls=0、input/output tokens=0、amount=0 USD、wall_seconds=0；这表示本提交未提供模型调用成本，不代表真实运行成本。
- 证据：结果保存于 `src/evaluation/b_score_independent_source_submission.json`；评分器测试 45/45 通过。
- 边界：这是合成输入评分，不是真实病例效果。当前主要缺口是来源支持引用与多时间断言仍未达到独立金答案要求；不修改 B 实现、不回流独立答案作调参材料。
- 下一步：保留 scorer 版本，使用真实开发事件核对模板建立 10–20 条受控参考记录；先核查值/单位/采样角色/来源支持，再决定是否扩展查询 Q1/Q2。

## 2026-09-13 · C 工作单元 8：B 最新独立提交错误分类

- 输入：`src/prototype/independent_source_submission.json`，修改时间 HH:MM:SS；协议兼容，观测覆盖完整，来源行 `r1`–`r12` 和身份字段可解析。
- 总分：joint TP=2、FP=10、FN=10、F1=0.1667；full_record TP=0、FP=12、FN=12、F1=0。aligned=12，漏项=0，额外观测=0。
- 分类统计：接口错误 0；值/项目错误 0；单位错误 0；sampling_time 错误 4 条（r7/r9/r10/r12）；其他时间断言错误 6 条（r5/r6/r7/r9/r10/r12）；来源支持错误 12 条；误合并 0；误拆分 0；身份未决覆盖缺口 1。
- 典型样例：r5/r6 把参考中的 sampling unknown 与 report/document 日期关系表达错；r7 将独立坐标 C2 的采样时间写成 C1；r9/r10 的未决状态没有保留参考要求的时间断言结构；r12 把无续页支持的观测写成了明确采样日期。值与单位本身保持正确。
- 成本：提交记录 calls=0、failed_calls=0、tokens=0、amount=0 USD、wall_seconds=0；这只是提交账本，不是模型运行成本测量。
- 证据：详细匿名分类及典型行见 `src/evaluation/b_error_analysis_independent_source.json`；scorer 测试 45/45 通过。此前 unified fixture 的 1.0 仅为接口烟雾测试，本结果是 B 独立生成路径评分，二者未混合。

## 2026-09-13 · C 工作单元 9：来源与时间断言修复复评

- source_support：2/12 → 8/12（+6）；sampling_time：8/12 → 12/12（+4）；all_time_assertions：6/12 → 12/12（+6）；joint F1：0.1667 → 0.6667（+0.5）。
- 当前状态：时间断言已在合成 fixture 上全部覆盖；来源支持仍有 4 条未达标。仍属合成输入复评，不是真实病例效果。
- 下一步：分析剩余 4 条 source_support 错误后，进入 10–20 条真实开发事件核对。
- 边界与下一步：这是合成输入评分，不是真实病例效果。保留现有 scorer；按 `REVIEW_TEMPLATE.md` 建立 10–20 条真实开发事件核对记录，先人工确认来源支持与时间角色，再进行受控开发评分。独立测试答案不回流 B 调参。

## 2026-09-13 · C 工作单元 9：B 最新 submission 复评分与变化

- 输入：当前 `src/prototype/independent_source_submission.json`（修改时间 HH:MM:SS）；使用现有 c-eval-dev-v0.1，未修改评分规则。评分器测试 45/45 通过。
- 覆盖与接口：protocol 兼容；prediction=12、gold=12、aligned=12、missing=0、extra=0、ambiguous=0。
- 当前结果：value=12/12、unit=12/12、sampling_time=12/12、all_time_assertions=12/12、source_support=8/12；joint TP=8、FP=4、FN=4、precision/recall/F1=0.6667；full_record TP=8、FP=4、FN=4、F1=0.6667。
- 身份关系：correct=3，false_merge=0，false_split=0，missing_decision=1；cost 仍为提交账本 calls=0、tokens=0、amount=0 USD、wall_seconds=0。
- 相比上一轮：source_support 2→8（+6）；sampling_time 8→12（+4）；all_time_assertions 6→12（+6）；joint F1 0.1667→0.6667（+0.5）。
- 边界：这是合成输入的独立 submission 评分，不是真实病例效果；结果改善只说明当前合成 fixture 上的评分项改善，不能外推临床或真实模型表现。接口烟雾测试结果未纳入本次比较。
- 证据：详细聚合结果已更新至 `src/evaluation/b_score_independent_source_submission.json`。下一步仍按 `REVIEW_TEMPLATE.md` 准备 10–20 条真实开发事件核对模板，保留 scorer 版本。
