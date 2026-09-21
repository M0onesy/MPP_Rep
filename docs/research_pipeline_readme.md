# Research Pipeline README

本目录记录本次已经跑通的 Python 研究原型。它不是官方 JKMP 全量复现。

## 运行顺序

1. `python mainProj/scripts/raw_data_inventory.py --raw-dir mainProj/data/raw --output mainProj/docs/raw_data_inventory_report.md`
2. `python mainProj/scripts/markit_coverage.py --input mainProj/data/raw/American Equities.csv --rebuild`
3. `python mainProj/scripts/build_crsp_panel.py --rebuild`
4. `python mainProj/scripts/run_m0_m3_prototype.py`
5. `python mainProj/scripts/make_research_reports.py`
6. `python mainProj/scripts/make_presentation_visuals.py`
7. `python mainProj/scripts/raw_data_dictionary_report.py --no-hash`
8. `python mainProj/scripts/project_structure_report.py`

## 主要输出

- `mainProj/data/prod/markit_coverage.csv`：Markit 字段年度/月度覆盖率。
- `mainProj/data/prod/markit_stock_monthly.parquet`：Markit 股票-月费用摘要，覆盖 2002–2026。
- `mainProj/data/prod/crsp_monthly_panel.parquet`：CRSP 普通股月度面板，含 Markit 匹配、费用、价量信号和宇宙选择。
- `mainProj/data/prod/prototype_weights.parquet` 与 `prototype_monthly_metrics.csv`：M0–M3 原型权重和月度结果。
- `mainProj/data/prod/prototype_sensitivity.csv`：M2/M3 一维敏感性实际重跑汇总，覆盖交易成本、费率缩放、目标样本数、样本口径和多头出借收入开关。
- `mainProj/reports/figures/markit/` 与 `mainProj/reports/figures/prototype/`：组会可用图表。
- `mainProj/reports/figures/presentation/`：面向组会汇报的结论型可视化图表。
- `mainProj/docs/raw_data_dictionary_and_reproduction_status.md`：原始文件字段字典、复现状态和全部图表解读。
- `mainProj/docs/project_structure_report.md`：目录职责、规范输出、测试输出和文件放置规则。
- `二阶段/05_组会可视化图表说明.md`：图表展示顺序、讲稿要点与导师可能追问。

## 当前口径

- CRSP 普通股采用 CIZ 映射：`SecurityType=EQTY`、`SecuritySubType=COM`、`ShareType=NS`。
- 借券费主字段为年化 decimal 口径的 `indicativefee`。
- 利用率字段保留原值；由于原始数值呈 0–100 型，主报告只将其作为原始描述，未在未经单位确认时做强经济解释。
- M0–M3 原型使用 2007-01 至 2025-12、每月市值五组各最多 200 只股票、单只权重上下限 2%、总杠杆 1.5。

## 组会可视化包

`make_presentation_visuals.py` 只读取现有 `prod` 结果，不重跑 Markit、CRSP 或 M0–M3 主流程。当前生成 11 张 PNG：

1. `fig01_coverage_heatmap.png`：数据覆盖总览。
2. `fig02_sample_timeline.png`：Markit/CRSP 共同样本规模时间线。
3. `fig03_fee_timeseries_annotated.png`：借券费时间序列强化版。
4. `fig04_key_year_fee_distributions.png`：关键年份横截面分布。
5. `fig05_fee_by_size_group.png`：市值分组借券费梯度。
6. `fig06_variance_persistence.png`：费率变异度分解与持续性。
7. `fig07_crsp_markit_funnel.png`：CRSP-Markit 匹配漏斗。
8. `fig11_m0_m3_method_flow.png`：M0-M3 原型设计流程图。
9. `fig08_m0_m3_dashboard.png`：M0-M3 原型结果仪表板。
10. `fig09_m2_m3_core_comparison.png`：M2 vs M3 核心比较。
11. `fig10_sensitivity_panel.png`：M2/M3 敏感性分析面板。

`reports/figures/prototype_test*` 是历史或短样本测试图，不进入主结果；完整图表清单、数据来源和解释边界见
`mainProj/docs/raw_data_dictionary_and_reproduction_status.md`。

## 核心数字

CRSP 研究样本费用分布：

| sample | stock_months | unique_permnos | mean_percent | std_percent | min_percent | p01_percent | p25_percent | median_percent | p75_percent | p90_percent | p99_percent | max_percent | high_fee_share_gt_1pct | util_mean_raw | util_median_raw | util_p90_raw | util_p99_raw |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CRSP eligible common stocks with Markit fee | 836585 | 10169 | 2.3078 | 11.3754 | 0.1 | 0.2122 | 0.3023 | 0.375 | 0.5 | 3.5 | 40.0 | 983.2684 | 0.1782 | 16.3807 | 7.5693 | 47.3394 | 90.7662 |
| Prototype common universe with 4-of-21 fee and fee_asof | 224142 | 7937 | 1.6251 | 9.356 | 0.1 | 0.2065 | 0.2977 | 0.375 | 0.5 | 1.7762 | 25.6711 | 983.2684 | 0.1315 | 15.1156 | 6.6208 | 43.8322 | 88.1363 |

M0–M3 原型摘要：

| model | months | avg_n_stocks | average_monthly_gross | average_monthly_net | annualized_net | average_turnover | average_transaction_cost | average_short_fee | average_lending_revenue | average_short_weight | average_gross_exposure |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| M0 | 228 | 983.017544 | 0.011731 | 0.011731 | 0.150218 | 2.046359 | 0.0 | 0.0 | 0.0 | 0.25 | 1.5 |
| M1 | 228 | 983.017544 | 0.011728 | 0.001601 | 0.019377 | 2.025442 | 0.010127 | 0.0 | 0.0 | 0.25 | 1.5 |
| M2 | 228 | 983.017544 | 0.011728 | -0.000356 | -0.00426 | 2.025442 | 0.010127 | 0.001992 | 3.5e-05 | 0.25 | 1.5 |
| M3 | 228 | 983.017544 | 0.011432 | -0.000498 | -0.005958 | 2.027761 | 0.010139 | 0.001827 | 3.5e-05 | 0.25 | 1.5 |

## 限制

- 官方 JKMP 所需 `usa.csv`、`usa_dsf.csv`、`world_ret_monthly.csv`、`Factor Details.xlsx`、`Cluster Labels.csv`、`market_returns.csv`、`ff3_m.csv` 等输入未在本工作区齐备。
- 本机未具备 R/Rscript 与 SLURM/HPC 环境，无法宣称官方代码全量复现。
- 当前原型使用价量信号和简化风险代理，用于验证借券费内生化机制。
