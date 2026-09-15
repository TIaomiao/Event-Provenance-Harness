# 匿名开发事件核对表（20 条模板）

用途：承接 B 的 10–20 条匿名事件候选，供受控环境人工核对。当前只保留空模板，不含患者正文、OCR 文本、真实路径、真实日期或参考答案。

填写规则：

- `case_token`、`observation_id`、`source_locator` 只使用匿名稳定标识；定位细节留在受控环境。
- `value/unit` 只填写原文明示值；无法确认写 `unknown`，不要猜测或做单位换算。
- `date_candidates` 列出候选日期及证据 ID；`time_roles` 分开写 sampling/report/record/document/unknown，并保留 unresolved/conflicting。
- `header_scope` 记录表格、页和行作用范围证据；跨页没有续表证据时标记 unresolved。
- `source_support_status` 使用 `supported/partial/unsupported/unclear`；值、日期、角色、范围支持分别核对。
- `identity_relation` 使用 `same_copy/different_retest/unresolved/not_applicable`；不能只凭同值同日合并。
- `manual_judgment` 使用 `clear/unclear/needs_clinician/not_started`。
- 两位审核者先独立填写，再由裁决列记录结果；不让待测系统输出直接生成参考答案。

字段说明：

| 字段 | 核对内容 |
|---|---|
| value / unit | 项目原文对应的数值和单位 |
| date_candidates | 日期字面、相对日、日期证据 ID |
| time_roles | 日期的语义角色及状态 |
| header_scope | 表头作用于哪些行、页、表格 |
| source_locator | 匿名文档/页/行/bbox/evidence ID |
| source_support_status | 值、单位、日期、角色、范围是否各有支持 |
| identity_relation / identity_evidence | 副本、复测或未决及其证据 |
| manual_judgment | 明确、看不清或需临床判断 |

`REVIEW_TEMPLATE_20.csv` 提供 20 行机器可读空表。填好的参考答案必须留在受控端；冻结后记录 `reference_version`、`locked_at`、`content_digest`，独立测试病例与开发病例分开管理。评分器版本保持 `c-eval-dev-v0.1`。
