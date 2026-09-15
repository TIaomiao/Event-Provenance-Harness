# 原型实现

B 在此目录维护原型及对应测试。2026-09-08 起已有 temporal_rebase.py，负责旧L1/L2时间证据核对与共同坐标候选旁表。它不修改源文件，不直接写入临床事件表。

## B/C 对齐材料：内部草案 v0.1（2026-09-11）

`temporal_roles.bind_candidates` 只检查上游已经给出的显式角色和行链接，尚未接入 sidecar；共享协议由 A 定版。`candidate_ordinals` 是本次输入列表的零基下标，不是 sidecar 的 `token_ordinal`，也不是稳定 evidence id。

纯合成例子（同一病例、文档、页）：

```python
scope = dict(case_token="CASE-SYNTHETIC", document_token="DOC-001", page_number=1)
candidates = [scope | {"case_coordinate_day": 0}, scope | {"case_coordinate_day": 3}]
rows = [scope | dict(row_id="ROW-1", candidate_ordinals=[0], temporal_role="sampling")]
result = bind_candidates(candidates, rows)
# result[0]: lab_row_id=ROW-1, temporal_role=sampling, binding_status=explicit
# result[1]: lab_row_id=None, temporal_role=unknown, binding_status=unresolved
```

未给出角色时，即使行关联存在也保持 unresolved。document 角色原样保留，不转为 event_time；所有输出保留 api_ready=false、clinical_time_roles_validated=false。不同病例/文档/页、越界与重复关联拒绝处理；输入不修改。

待 A/C 决策：同一表头覆盖多个检验行的作用域；每个日期独立角色及角色证据定位；与 sidecar 来源哈希和 coordinate_id 对接。当前单候选只允许一个行链接，不适合表头共享日期。临床重复事件的合并/拆分和评分仍未实现。

本地合成验证：

```powershell
python -m unittest discover -s src/prototype/tests -p "test_*.py" -v
```

服务器执行使用实际生产日期源码（提取其中纯日期函数，绑定哈希）与已获准的case目录。输出必须是已存在私有目录里的新文件：

```text
python3 temporal_rebase.py --case-dir <获准的病例输出目录> --producer-source <生产ehr_pipeline.py> --output <新私有旁表JSON>
```

扩展已有病例时加 --reference-sidecar <已有v0.2及以上旁表>，固定参考文档、来源哈希与原点记录。source rules或原点来源变化会阻断；不得混用不同case_coordinate_id的数值。

默认上限30文档/250页，本轮实际26文档/187页。实际模型执行仍沿用具体授权。详见根目录ENGINEERING_PLAN.md与results/2026-09-08_temporal_recovery_report.md。
