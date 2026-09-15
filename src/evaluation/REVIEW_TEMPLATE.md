# 开发参考事件人工核对模板（空白）

用途：下一步核对 10–20 条获准开发事件。此文件只定义字段，不包含患者信息或实际答案。填好的记录留在受控环境；不覆盖原始 PDF、OCR 或既有审核答案。

先核查允许使用的开发病例清单、文档版本与可读范围。优先原文明示字段，不根据待测系统输出选题、定值或裁定身份；10–20 条覆盖共享表头、复测、副本和时间缺失，属于开发集，不宣称分布代表性。

| 核对字段 | 填写要求 |
| --- | --- |
| reference_version / protocol_version / evaluator_version | 冻结后不可原地改写，修订单独留版本 |
| split / case_token / observation_id | 开发或独立测试分别管理，病例互斥 |
| source_version / source_digest | 锚定实际证据版本，实际映射只在受控端 |
| row / document / page / bbox | 对照原页定位，必要时复查 OCR 与原图差异 |
| item / value / unit | 盲填原文明示内容；不做临床推断 |
| time_assertions | 每条保留时间角色、坐标、日期证据、角色证据和范围证据 |
| source_support_sets | 逐字段核验支持关系；不要只确认 ID 存在 |
| identity_relation | 明示副本、明示另次采样、未决；记录关系证据 |
| literal_review | 明确 / 看不清 / 需医生判断；含糊不能默认为正确 |
| reviewer_a / reviewer_b / adjudication | 匿名审核者标记，独立核对后再展示候选和裁决 |
| included_fields / excluded_reason | 核对前预设可评分域；报告未决和排除比例 |
| locked_at / content_digest | 独立参考先冻结，再打开待测结果 |

验收：每条入评字段有独立支持证据，时间坐标可解释，疑点单列；已核对计数与待核对计数分别汇总。参考本身不清楚时记录评测资格缺口，不能扣成模型确定性错误。

独立测试：同一病例及近重复不得跨 split；答案、证据映射和逐题报告仅限评测侧。共享账号不能靠文件权限模拟角色隔离，需落实独立访问控制后再建答案。只把允许的匿名汇总带回本地。
