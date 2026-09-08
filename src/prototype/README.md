# 原型实现

B 在此目录维护原型及对应测试。2026-09-08 起已有 temporal_rebase.py，负责旧L1/L2时间证据核对与共同坐标候选旁表。它不修改源文件，不直接写入临床事件表。

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
