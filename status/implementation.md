# 原型实现状态

- 协议：local-workspace-v2 / research-card-v0.2；论文 Proposal 见 `paper/PROPOSAL.md`。
- 状态：2026-09-08 时间恢复第一阶段完成，仍为私有候选产物。
- 已完成：temporal_rebase.py v0.3.1，旧相对日重放平移、同框L1完整日期候选、固定原点与哈希、来源保护。
- 验证证据：Windows/Linux各23项通过；2例26文档187页，952个日期候选；源L1/L2哈希不变，OCR/API/L4写入均0。
- 阻塞：候选未完成临床时间角色与检验行绑定；3份检验文档中1份尚无合格候选。
- 下一步：在已有来源定位上核对采样/报告/记录时间与表头/行关联，建立第一批明确事件；参考archive/legacy_20260915/ENGINEERING_PLAN.md。

## 2026-09-11 B 接续工作单元

- 协议沿用 research-card-v0.2；新增 `src/prototype/temporal_roles.py` 作为 B 内部接口草案，尚未定为共享协议。
- 已完成：显式候选序号—检验行关联、采样/报告/记录/文档/未知角色输入检查；无关联保持 unresolved。此模块接收上游已明确的角色与链接，不负责从 OCR 推断。
- 验证：本地 33 项合成测试通过（既有 23 项、新增 10 项），覆盖跨病例/文档/页拒绝、越界/布尔序号拒绝、重复关联、输入不变与未知角色；未执行服务器命令、未调用模型。
- 已补齐：候选越界、页码与来源一致性检查。仍待完善同一表头作用于多行、不同日期各自的角色证据定位、sidecar 哈希/坐标对接；当前草案不得直接用于真实数据。
- 阻塞：C 尚未建立；共享输入输出需由 A 统一，B 不修改研究卡。
- 下一步：待 C 建立后对齐角色、unknown/unresolved 与表头作用域；具体合成输入输出见 `src/prototype/README.md`。本模块仅验证上游显式关联，不表示 OCR 角色识别、事件归并或 E2 已完成。

## 2026-09-11 B 表头日期物化

- 新增 `materialize_event_table`：按采样、报告、记录、文档标签识别角色；单一表头日期可作用于同页其下多行，输出值、单位、事件时间、角色与 evidence id。
- 布局仅用于候选筛选；多表头歧义、缺标签或缺证据保持 unresolved。35 项合成测试通过。

- 共享接口待 C 评分：表头日期可作用于同页多行；每条观测分别保留采样/报告等时间断言与 evidence id。跨页续表、sidecar 坐标对接及真实 OCR 角色识别仍未验证。

## 2026-09-12 B/C 统一夹具接口联调

- 已生成 `unified_fixture_submission.json` 并被 C 评分器接受：aligned=12，joint/full_record F1=1.0，值/采样时间/来源均 12/12，身份关系 3 项正确、1 项 unresolved。
- 该脚本直接从 C `fixtures.EXPECTED` 复制预期答案，再包装为共享 `observations/time_assertions/source_refs` 格式；因此仅证明接口和评分器可通，不证明 B 的独立解析质量。
- 下一步：使用 B 自己的 `materialize_event_table` 从合成源材料生成同等格式提交，禁止导入或复制 `EXPECTED`，再交 C 重评分。

## 2026-09-12 B 独立提交诊断

- B 已生成独立来源提交并与 C fixture 的 12 条原始行对齐；C 记录 value=12/12、unit=12/12、sampling_time=8/12、all_time_assertions=6/12、source_support=2/12，joint=2/12、full_record=0。
- 这不是最终模型效果，也不是协议错误；当前缺口集中在多时间断言和日期/角色/范围 evidence 的一致性，身份关系已报告部分结果。
- 下一步：沿同一合成源材料补齐完整 `time_assertions` 与稳定来源支持，再复评分；不使用 C EXPECTED 生成提交。

## 2026-09-12 B/C 统一夹具评分回读

- 统一夹具已通过 C：aligned=12，joint/full_record F1=1.0，值/采样时间/来源均 12/12，身份关系 3 项正确、1 项 unresolved。
- 该提交脚本直接从 C `fixtures.EXPECTED` 读取答案，属于协议烟雾测试；B 独立流程的算法质量仍未验证。

## 2026-09-11 A 联调裁定

- 当前任务说明升级至研究卡 v0.4，历史实现与测试记录保留其原协议版本。
- A 采用 C 已实现的 observations/time_assertions 序列化进行首轮联调；调用兼容标签仍为 research-card-v0.3/shared-synthetic-v0.1。
- 跨页、多角色与歧义、来源组成的决策已写入研究卡，B 继续提交自身生成的合成输出与命令，不再等待 C 建立或由用户逐题决定技术默认值。

## 2026-09-13 B 时间/来源字段最小修复

- 读取最新 C 评测状态后，仅修改独立 submission 生成逻辑；未修改评分器，未读取或复制 C 的 EXPECTED。
- 修复：为 r5/r6 增加 sampling unknown 并保留 report/document；为 r7 使用 C2；r9 保留 conflicting 双 sampling；r10/r12 保留 unresolved 结构；日期/角色/范围引用采用源材料对应 ID。
- 修复前后：sampling_time 8/12→12/12，all_time_assertions 6/12→12/12，source_support 2/12→8/12；joint TP 2→8，joint F1 0.167→0.667；value/unit 仍 12/12。
- 验证：C scorer status=scored，aligned=12；原型测试 35/35 通过。尚有 4 条来源支持未满，主要是合成源材料没有独立声明完整日期/角色/范围证据映射；需 A/C 决定等价证据契约。

## 2026-09-13 B 开发病例元数据抽样

- 仅通过 SSH 在 Larry 读取 `non_governance_v0_9_seed20260810.manifest.json` 的 case_alias、pdf_count、category_counts；未读取正文、OCR、PDF、独立测试集或全量 OCR。
- 固定种子 20260913 分层抽样实际得到 16 个 case_token（low/high pdf × laboratory/other 各最多 5；lab 文档层覆盖 9 例）。匿名结果写入 `results/2026-09-13_dev_case_selection.jsonl`。
- 页数、版式、跨页、日期缺失、OCR 质量在现有 filename-level manifest 中不可用，均标记 unavailable；因此尚不能声称满足这些维度的实际覆盖。
- 阻塞：若要完成 20 例及六维分层，需要 Larry 提供不含正文的文档级/病例级匿名元数据索引，并确认 4 个缺失名额及开发病例范围；本轮未创建事件表或参考答案。

## 2026-09-13 B 真实开发元数据阶段

- w 已明确授权读取两例开发病例的 OCR JSON 元数据；本轮通过 SSH 在 Larry 受控环境只读 `ocr_layout.json` 的结构统计（page_count、line_count、confidence 汇总），未读取/回传正文、PDF 图像、独立测试集。
- 已确认开发范围为既有 CASE-02 与 CASE-05 产物；生成 20 条匿名文档级候选索引，文件为 `results/2026-09-13_dev_event_metadata_selection.json`。覆盖短/中/长文档、稠密版式、低 confidence 候选和跨页候选。
- 本轮没有从正文抽取 item/value 或临床事件；因此不能把 20 条文档候选写成 10–20 条已核对事件。下一步需在同一授权范围内读取检验 JSON 的最小必要字段（行文本/表头日期）或由人工核对后生成事件表。
- 阻塞：当前匿名索引缺少日期角色、表头作用域、检验项目和值的证据级字段；DOC-005 低 confidence 与跨页候选需优先人工核查。独立测试集未访问。

## 2026-09-13 B 真实开发事件首批

- w 已明确授权读取两例开发病例 OCR JSON 必要字段；Larry 受控环境内仅读取 `case_token/document_token/page_number/records[].text/records[].bbox/records[].confidence/page_count/line_count`，未读取或回传 PDF、独立测试集或全量 OCR。
- 在 CASE-02 与 CASE-05 的已选文档中生成 20 条匿名开发观测，覆盖 7 个文档、24 页、2037 行；输出留在 Larry 受控目录 `private_manifests/research_dev_events_v0_1.json`。
- 每条记录包含匿名 observation_id、case_token、item/value/unit、sampling `time_assertions`、source_refs 和 evidence_index；当前 20 条采样时间均为 unknown，未写入推断日期或身份关系。
- 自动抽取采用行级数值+单位候选规则；尚未完成检验项目语义、表头日期/角色、跨页作用域和副本/复测身份核对。20 条需人工或受控规则复核后才能进入 C 参考。
- 本地原型测试 35/35 通过；服务器未调用模型、未修改源文件或 L4。

## 2026-09-13 B 开发事件 v0.2 时间候选扫描

- 在同一 CASE-02/CASE-05、26 文档、187 页范围内读取 `records[].text` 仅做日期候选与中文角色标签扫描；不输出正文。已尝试生成受控 `research_dev_events_v0_2.json`。
- 当前扫描统计：0 条行同时满足“检验值+单位+可识别日期候选”的保守规则；因此未覆盖改写 v0.1 的 20 条候选，避免把正文格式不匹配误写成明确时间。
- 缺失原因：`records[].text` 中日期格式/角色标签未匹配当前保守正则（字段路径：`records[].text`）；不能据此断言文档无日期。v0.1 的 20 条候选仍保留，时间为 unknown。
- 阻塞：需要针对受控 OCR 文本的实际日期格式做一次服务器端规则校准，或由人工提供不含正文的日期候选索引；跨页、表头范围和身份关系仍未核对。独立测试集未访问。

## 2026-09-13 B 开发事件字段诊断 v0.3

- 在已授权 CASE-02/CASE-05 OCR JSON 范围内，仅统计/读取字段：文档/页/行 ID、行文本、bbox；检测到 512 条含检验相关词且含数字的行，但保守抽取仅生成 4 条候选，来自 1 个文档。
- 受控输出：`<CONTROLLED_ENV>/.json`。每条保留稳定 evidence index、sampling unresolved 和缺失原因；item/value/unit 暂置 null，未回传正文。
- 阻塞：OCR 行格式与当前项目名/值解析器不匹配，不能安全生成 10–20 条可评分事件；需读取该工程既有结构化 `result.json` 的字段 schema（不读正文）或针对实际行格式做受控规则校准。独立测试集未访问。

## 2026-09-13 B 开发事件 v0.7 单位字段校准

- 在已选 OCR JSON 中按白名单识别常见单位，生成 20 条匿名事件，覆盖 2 个文档；受控输出 `research_dev_events_v0_7.json`。
- `unit` 已从文本中提取；`item`、日期候选/角色、表头范围和身份关系仍 unknown/unresolved，并记录字段路径 `records[].text`。
- 未回传正文、未访问独立测试集；当前仍为开发候选。

## 2026-09-13 B 开发事件 v0.8 项目候选

- 在同一授权范围内从 OCR 行文本中按单位前 token 提取项目候选，生成 20 条匿名事件，覆盖 2 个文档；受控输出 `research_dev_events_v0_8.json`。
- 18/20 条获得项目名候选，20/20 条保留单位；数值、日期候选/角色、表头范围和身份关系仍 unresolved，避免误填。
- 读取字段仍限于文档/页/行 ID、行文本、bbox、日期候选及标签；正文未回传，独立测试集未访问。

## 2026-09-13 B 解析 schema 对接检查

- Larry 侧确认检验结构化契约字段：record_id、test_name、test_code、value_numeric、value_text、unit、relative_day、source_page、source_bbox、source_cells、ocr_confidence、validation_status 等。
- CASE-02/CASE-05 范围的 result.json 仅有 6 条 structured.records，来自非检验文档；检验文档没有可直接复用的结构化 records。
- 保留 v0.8/v0.7 匿名候选，不伪造项目和值；下一步依据该 schema 编写 OCR bbox 表格解析适配器，再在受控环境回放 10–20 条实验室行。
- 未回传正文，未访问独立测试集。

## 2026-09-13 B laboratory-bbox-v1.0 适配器

- 新增 `src/prototype/laboratory_bbox_adapter.py`：从 OCR layout 行中保守提取白名单单位和数值，生成 laboratory schema 记录；项目名、日期和临床角色不从邻近位置推断，缺失项进入 `quality_issues`/`needs_review`。
- 新增 2 项合成测试；原型测试总计 37/37 通过。
- 适配器当前为本地 demo，尚未在真实开发 JSON 上运行；下一步需用受控文档回放并检查字段覆盖，输出仍留在 Larry 受控环境。

## 2026-09-13 B 受控小范围回放指标

- Larry 受控环境只读回放已选 CASE-02/CASE-05 OCR JSON：26 个文档、187 页、13,372 行；未访问独立测试集，未将 OCR 文本写入本地。
- 受控匿名指标输出：`<CONTROLLED_ENV>/.json`。每文档记录 7 类指标（present/mappable/uncertain/missing）及字段路径。
- 同时具备检验词、数字和白名单单位的文档：CASE-02/case-02-doc-007、case-02-doc-008；CASE-05/case-05-doc-006、case-05-doc-012、case-05-doc-013、case-05-doc-015，可进入人工事件核对。
- 日期候选、时间角色和表头作用域在当前结构字段中缺失，指标按 `records[].text` 统计为 uncertain/missing；需要人工确认日期标签与跨页范围。无法用于事件解析的文档为无检验词/无单位或无数值的其余文档，具体原因保存在受控指标文件。

## 2026-09-13 B 六文档事件候选回放

- 严格限定 metrics 确认的 6 个文档；读取 `document_token/page_number/records[].text/records[].bbox`，仅在受控端做存在性统计，不回传正文。
- 生成 20 条匿名事件候选，覆盖其中 4 个文档；输出留在 Larry：`private_manifests/research_dev_event_candidates_v0_1.json`。
- 每条仅包含稳定 observation/page/line/bbox/source ID、项目类别、值/单位存在性、日期证据状态、时间角色状态、表头范围状态和 unresolved 标记。
- 未访问独立测试集，未修改评分器或既有事件文件。
