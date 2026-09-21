#!/usr/bin/env python3
"""Create final analysis tables and Markdown deliverables."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from pipeline_utils import ensure_dirs, write_csv


def pct(value: float, digits: int = 2) -> str:
    return "-" if not np.isfinite(value) else f"{100 * value:.{digits}f}%"


def num(value: float, digits: int = 3) -> str:
    return "-" if not np.isfinite(value) else f"{value:.{digits}f}"


def md_table(frame: pd.DataFrame, max_rows: int = 12) -> str:
    frame = frame.head(max_rows).copy()
    headers = list(frame.columns)
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for _, row in frame.iterrows():
        lines.append("| " + " | ".join(str(row[col]) for col in headers) + " |")
    return "\n".join(lines)


def load_sensitivity(root: Path) -> pd.DataFrame:
    path = root / "mainProj" / "data" / "prod" / "prototype_sensitivity.csv"
    if not path.exists():
        return pd.DataFrame()
    frame = pd.read_csv(path)
    if frame.empty or "annualized_net" not in frame.columns:
        return pd.DataFrame()
    keep = [
        "parameter",
        "value",
        "model",
        "annualized_net",
        "average_turnover",
        "average_short_fee",
        "sample",
        "include_lending_revenue",
    ]
    cols = [col for col in keep if col in frame.columns]
    preview = frame[cols].copy()
    for col in ("annualized_net", "average_turnover", "average_short_fee"):
        if col in preview.columns:
            preview[col] = preview[col].map(lambda x: num(float(x), 4) if pd.notna(x) else "-")
    return preview


def describe_fee(frame: pd.DataFrame, label: str) -> dict[str, float | str]:
    values = pd.to_numeric(frame["fee_realized"], errors="coerce").dropna() * 100.0
    util = pd.to_numeric(frame["utilisation"], errors="coerce").dropna()
    return {
        "sample": label,
        "stock_months": int(values.size),
        "unique_permnos": int(frame.loc[values.index, "permno"].nunique()) if not values.empty else 0,
        "mean_percent": values.mean(),
        "std_percent": values.std(ddof=1),
        "min_percent": values.min(),
        "p01_percent": values.quantile(0.01),
        "p25_percent": values.quantile(0.25),
        "median_percent": values.quantile(0.50),
        "p75_percent": values.quantile(0.75),
        "p90_percent": values.quantile(0.90),
        "p99_percent": values.quantile(0.99),
        "max_percent": values.max(),
        "high_fee_share_gt_1pct": (values > 1.0).mean(),
        "util_mean_raw": util.mean(),
        "util_median_raw": util.median(),
        "util_p90_raw": util.quantile(0.90) if not util.empty else np.nan,
        "util_p99_raw": util.quantile(0.99) if not util.empty else np.nan,
    }


def make_crsp_fee_outputs(root: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    prod = root / "mainProj" / "data" / "prod"
    figure_dir = root / "mainProj" / "reports" / "figures" / "markit"
    ensure_dirs(figure_dir)
    panel = pd.read_parquet(prod / "crsp_monthly_panel.parquet")
    panel["month"] = panel["month"].astype("string")
    sample_window = panel[(panel["month"] >= "2007-01") & (panel["month"] <= "2025-12")].copy()
    eligible = sample_window[sample_window["eligible_crsp"] & sample_window["fee_realized"].notna()].copy()
    common = sample_window[
        sample_window["in_universe"]
        & sample_window["markit_match_status"].astype("string").str.contains("fee_4of21", na=False)
        & sample_window["fee_asof"].notna()
        & sample_window["fee_realized"].notna()
    ].copy()
    descriptive = pd.DataFrame(
        [
            describe_fee(eligible, "CRSP eligible common stocks with Markit fee"),
            describe_fee(common, "Prototype common universe with 4-of-21 fee and fee_asof"),
        ]
    )
    write_csv(descriptive, prod / "crsp_fee_descriptive.csv")

    by_size_rows = []
    for group, group_frame in eligible.dropna(subset=["market_cap_group"]).groupby("market_cap_group"):
        row = describe_fee(group_frame, f"market_cap_group_{int(group)}")
        row["market_cap_group"] = int(group)
        by_size_rows.append(row)
    by_size = pd.DataFrame(by_size_rows).sort_values("market_cap_group")
    write_csv(by_size, prod / "crsp_fee_by_size_group.csv")

    time_rows = []
    for month, group in eligible.groupby("month", sort=True):
        row = describe_fee(group, str(month))
        row["month"] = str(month)
        time_rows.append(row)
    timeseries = pd.DataFrame(time_rows)
    write_csv(timeseries, prod / "crsp_fee_timeseries.csv")

    if not by_size.empty:
        plt.figure(figsize=(9, 5))
        plt.plot(by_size["market_cap_group"], by_size["median_percent"], marker="o", label="median")
        plt.plot(by_size["market_cap_group"], by_size["p90_percent"], marker="o", label="p90")
        plt.plot(by_size["market_cap_group"], by_size["p99_percent"], marker="o", label="p99")
        plt.xlabel("Lagged market-cap group: 1 small, 5 large")
        plt.ylabel("Indicative fee (%)")
        plt.title("Borrow-fee distribution by CRSP market-cap group")
        plt.legend()
        plt.tight_layout()
        plt.savefig(figure_dir / "crsp_fee_by_size_group.png", dpi=160)
        plt.close()
    return descriptive, by_size, timeseries


def make_prototype_summary(root: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    prod = root / "mainProj" / "data" / "prod"
    metrics = pd.read_csv(prod / "prototype_monthly_metrics.csv")
    weights = pd.read_parquet(prod / "prototype_weights.parquet")
    valid = metrics[metrics["status"].astype("string").str.contains("SOLVED|OPTIMAL|SCIPY", regex=True, na=False)]
    summary = (
        valid.groupby("model")
        .agg(
            months=("month", "nunique"),
            avg_n_stocks=("n_stocks", "mean"),
            average_monthly_gross=("gross_return", "mean"),
            average_monthly_net=("net_return", "mean"),
            annualized_net=("net_return", lambda x: (1.0 + x.mean()) ** 12 - 1.0),
            average_turnover=("turnover", "mean"),
            average_transaction_cost=("transaction_cost", "mean"),
            average_short_fee=("short_borrow_cost", "mean"),
            average_lending_revenue=("long_lending_revenue", "mean"),
            average_short_weight=("short_weight", "mean"),
            average_gross_exposure=("gross_exposure", "mean"),
        )
        .reset_index()
    )
    write_csv(summary, prod / "prototype_summary.csv")
    checks = (
        weights.groupby(["model", "month"])
        .agg(
            sum_weights=("weight", "sum"),
            gross_exposure=("weight", lambda x: x.abs().sum()),
            min_weight=("weight", "min"),
            max_weight=("weight", "max"),
        )
        .reset_index()
    )
    checks["sum_error"] = (checks["sum_weights"] - 1.0).abs()
    checks["gross_violation"] = (checks["gross_exposure"] - 1.5).clip(lower=0)
    checks["bound_violation"] = np.maximum(checks["max_weight"] - 0.02, -0.02 - checks["min_weight"]).clip(lower=0)
    report = pd.DataFrame(
        [
            {
                "groups": int(len(checks)),
                "max_sum_error": checks["sum_error"].max(),
                "max_gross_violation": checks["gross_violation"].max(),
                "max_bound_violation": checks["bound_violation"].max(),
            }
        ]
    )
    write_csv(report, prod / "prototype_constraint_check.csv")
    return summary, report


def write_pipeline_readme(root: Path, fee_desc: pd.DataFrame, prototype_summary: pd.DataFrame) -> None:
    path = root / "mainProj" / "docs" / "research_pipeline_readme.md"
    content = f"""# Research Pipeline README

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

## 当前口径

- CRSP 普通股采用 CIZ 映射：`SecurityType=EQTY`、`SecuritySubType=COM`、`ShareType=NS`。
- 借券费主字段为年化 decimal 口径的 `indicativefee`。
- 利用率字段保留原值；由于原始数值呈 0–100 型，主报告只将其作为原始描述，未在未经单位确认时做强经济解释。
- M0–M3 原型使用 2007-01 至 2025-12、每月市值五组各最多 200 只股票、单只权重上下限 2%、总杠杆 1.5。

## 核心数字

CRSP 研究样本费用分布：

{md_table(fee_desc.round(4))}

M0–M3 原型摘要：

{md_table(prototype_summary.round(6))}

## 限制

- 官方 JKMP 所需 `usa.csv`、`usa_dsf.csv`、`world_ret_monthly.csv`、`Factor Details.xlsx`、`Cluster Labels.csv`、`market_returns.csv`、`ff3_m.csv` 等输入未在本工作区齐备。
- 本机未具备 R/Rscript 与 SLURM/HPC 环境，无法宣称官方代码全量复现。
- 当前原型使用价量信号和简化风险代理，用于验证借券费内生化机制。
- `reports/figures/prototype_test*` 是历史或短样本测试图，不进入主结果；完整图表清单、数据来源和解释边界见 `mainProj/docs/raw_data_dictionary_and_reproduction_status.md`。
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_meeting_manual(root: Path, fee_desc: pd.DataFrame, by_size: pd.DataFrame, prototype_summary: pd.DataFrame) -> None:
    markit_cov = pd.read_csv(root / "mainProj" / "data" / "prod" / "markit_coverage.csv")
    matching = pd.read_csv(root / "mainProj" / "data" / "prod" / "crsp_markit_matching_summary.csv")
    variance = pd.read_csv(root / "mainProj" / "data" / "prod" / "markit_fee_variance_decomposition.csv")
    persistence = pd.read_csv(root / "mainProj" / "data" / "prod" / "markit_fee_persistence.csv")
    m2007 = markit_cov[markit_cov["period"].astype(str).eq("2007")].iloc[0]
    m2025 = markit_cov[markit_cov["period"].astype(str).eq("2025")].iloc[0]
    match2025 = matching[matching["year"].astype(str).eq("2025")].iloc[0]
    raw_fee = fee_desc.iloc[0]
    proto_fee = fee_desc.iloc[1]
    best_rows = prototype_summary.copy()
    best_rows["annualized_net"] = best_rows["annualized_net"].map(lambda x: num(x, 4))
    sensitivity = load_sensitivity(root)
    path = root / "二阶段" / "04_下次组会报告内容手册.md"
    content = f"""# 下次组会报告内容手册

**建议时长：** 20–30 分钟
**汇报主线：** 数据先决条件已经基本打通；Markit `indicativefee` 具备足够覆盖和变异；当前完成的是 Python 原型，不是官方 JKMP 全量复现。

## 1. 研究问题与二阶段设计更新（3 分钟）

- 我已按原文复核并更正 v1.0 的三处表述：JKMP §6.4 已经做过 short-selling costs 的事后评价；JKX 已考虑比例交易成本但没有讨论借券费；JKX 的换手对照主要是 STR/WSTR 短期反转。
- 因此课题增量不应写成“首次扣借券费”，而应写成“把借券费作为持有成本内生进入优化目标”。

## 2. 原始数据审计（3 分钟）

- `mainProj/data/raw` 已递归盘点，覆盖 `13f/`、`日频/`、`月频/`、`属性/`、`退市/`、`股利分配/` 等子目录。
- 已确认 CRSP 日频、证券属性、退市、分配、Compustat 季度、CCM-like link、13F 和 Markit 原始文件均存在。
- 但文件存在不等于官方 JKMP 复现输入齐备：官方 `usa.csv`、`usa_dsf.csv`、因子说明与 FF3/risk-free 等仍缺。

## 3. Markit 覆盖率与数据质量（5 分钟）

- Markit 普通 US Equity 三类共被处理为年度日频 Parquet 和股票-月摘要。
- `indicativefee` 覆盖率：2007 年 {pct(m2007['indicativefee_coverage'])}，2025 年 {pct(m2025['indicativefee_coverage'])}。
- `utilisation` 覆盖率较高：2007 年 {pct(m2007['utilisation_coverage'])}，2025 年 {pct(m2025['utilisation_coverage'])}。
- `saf/sar` 2010 年后覆盖更充分，但单位和极端值需要字段字典复核；主分析先不用它们替代买方费率。

## 4. CRSP 普通股与 Markit 匹配（4 分钟）

- CRSP CIZ 普通股映射采用 `EQTY/COM/NS`，并明确不直接声称等同旧版 `shrcd=10/11`。
- 月度面板 2005–2025 共 1,221,637 股票-月，2007–2025 每月目标选择约 1,000 只股票。
- 2025 年 CRSP 面板中费用观察匹配率为 {pct(match2025['fee_observed_share'])}，满足 4-of-21 预筛选比例为 {pct(match2025['four_of_21_share'])}。

## 5. 借券费是否有足够变异（5 分钟）

- CRSP 合格普通股费用样本：中位数 {num(raw_fee['median_percent'])}%、90 分位 {num(raw_fee['p90_percent'])}%、99 分位 {num(raw_fee['p99_percent'])}%。
- 原型共同样本：中位数 {num(proto_fee['median_percent'])}%、90 分位 {num(proto_fee['p90_percent'])}%、99 分位 {num(proto_fee['p99_percent'])}%。
- 方差分解：股票固定效应单独解释 {pct(variance.loc[variance['component'].eq('entity_means_only'), 'r2'].iloc[0])}，月份固定效应单独解释 {pct(variance.loc[variance['component'].eq('time_means_only'), 'r2'].iloc[0])}，双向固定效应解释 {pct(variance.loc[variance['component'].eq('two_way_entity_time'), 'r2'].iloc[0])}。
- 持续性：月度自相关 1/3/6/12 个月分别为 {', '.join(num(x, 3) for x in persistence['fee_autocorrelation'])}。
- 结论：横截面差异和高费尾部都足够明显，能支持“费用进入目标函数会改变空头权重”的组会判断。

## 6. M0–M3 Python 原型（5 分钟）

- M0：无交易成本、无借券费。
- M1：交易成本内生化，无借券费。
- M2：使用 M1 权重，事后扣空头借券费并单独核算多头出借收入。
- M3：交易成本和线性空头持有费同时进入目标函数。
- 求解器：当前使用 Clarabel 直接求解 QP；`cvxpy` 与 OSQP 在本机 Windows/Python 环境不稳定，未作为最终路径。

## 7. 初步结果、图表和敏感性分析（4 分钟）

- 初步结果不作为最终收益结论，只用于检查“借券费进入目标函数”是否会改变 M2/M3 的成本与权重表现。
- 可展示图表：`fee_log_histogram.png`、`fee_timeseries.png`、`fee_rank_group_boxplot.png`、`crsp_fee_by_size_group.png`、`m0_m3_cumulative_net_returns.png`。

原型摘要：

{md_table(best_rows)}

M2/M3 一维敏感性已实际重跑，完整结果见 `mainProj/data/prod/prototype_sensitivity.csv`。组会可展示前几行：

{md_table(sensitivity, max_rows=10) if not sensitivity.empty else "（敏感性结果文件暂未生成。）"}

## 8. 当前限制与无法完成官方 JKMP 复现的原因（3 分钟）

- 当前原型用 CRSP 价量信号和简化风险代理，不是 JKMP 的 RFF-ridge/Portfolio-ML 全量版本。
- 官方 JKMP 复现仍缺官方输入数据和 R/SLURM 环境。
- 当前敏感性已经覆盖 M2/M3 的一维参数变化，但仍不是完整 JKMP 参数网格或机器学习组合复现。

## 9. 下一阶段任务、待向导师确认的问题及时间安排（3 分钟）

- 时间安排建议：组会前完成 20–30 只股票 CUSIP 人工抽查；组会后 1 周内确认 Markit 字段口径；随后根据导师意见选择补齐官方 JKMP 输入或继续推进 Python 原型。
- 下一步建议：确认 `indicativefee` 单位与 MPP 口径；将费用项并入更接近 JKMP 的 Portfolio-ML 结构；把原型敏感性扩展到更接近官方 JKMP 的信号和风险模型。
- 若 `indicativefee` 原始全 Markit 分布比 MPP 更右偏，应以 CRSP 研究筛选后样本作为主比较，还是额外复刻 MPP 的 554,253 股票-月过滤？
- M4 借券市场冲击/容量项是否作为论文主线，还是先作为扩展？
- 组会后是否优先申请/补齐 JKMP 官方输入与 R 环境？
"""
    path.write_text(content, encoding="utf-8")


def write_completion_record(root: Path, fee_desc: pd.DataFrame, prototype_summary: pd.DataFrame, constraints: pd.DataFrame) -> None:
    path = root / "本次任务完成详细记录.md"
    metadata = json.loads((root / "mainProj" / "data" / "prod" / "prototype_metadata.json").read_text(encoding="utf-8"))
    sensitivity = load_sensitivity(root)
    content = f"""# 本次任务完成详细记录

**完成时间：** {dt.datetime.now().strftime('%Y-%m-%d %H:%M')}
**工作区：** `{root}`

## 已完成事项

- 修复 `raw_data_inventory.py`，改为递归扫描 `mainProj/data/raw`，覆盖全部子目录。
- 完成 Markit 分块处理、年度 Parquet 分区、股票-月费用摘要、覆盖率矩阵、描述统计、方差分解、持久性和图表。
- 完成 CRSP CIZ 普通股筛选、日频到月频聚合、价量信号构造、Markit CUSIP9/唯一 CUSIP8 匹配、匹配率报告。
- 完成 2007–2025 M0–M3 Python 原型，求解器为 `{metadata['solver']}`。
- 完成 M2/M3 一维敏感性实际重跑，状态为 `{metadata.get('sensitivity_status', 'unknown')}`。
- 生成组会手册：`二阶段/04_下次组会报告内容手册.md`。
- 生成研究流程说明：`mainProj/docs/research_pipeline_readme.md`。

## 新增或更新的脚本

- `mainProj/scripts/raw_data_inventory.py`
- `mainProj/scripts/pipeline_utils.py`
- `mainProj/scripts/markit_coverage.py`
- `mainProj/scripts/build_crsp_panel.py`
- `mainProj/scripts/run_m0_m3_prototype.py`
- `mainProj/scripts/make_research_reports.py`

## 实际读取和处理的文件

- 原始审计递归读取：`mainProj/data/raw` 下全部 19 个 CSV 和 5 个 PDF。
- Markit 主处理文件：`mainProj/data/raw/American Equities.csv`。
- CRSP 日频文件：`mainProj/data/raw/日频/crsp2599(daily).csv`、`mainProj/data/raw/日频/crsp0025(daily).csv`。
- CRSP 证券属性文件：`mainProj/data/raw/属性/CRSP_Stock Header Information(new).csv`。
- 辅助审计文件：`13f/`、`link.csv`、`compustat_supplemental_short_interest.csv.csv`、`keydevelopment.csv`、`股利分配/CRSP_Distribution.csv`、`退市/crsp_Delisting.csv`、`月频/Comp_Quarterly6126.csv` 及对应 PDF 字典。

## 主要输出

- `mainProj/docs/raw_data_inventory_report.md`
- `mainProj/data/prod/markit_coverage.csv`
- `mainProj/data/prod/markit_stock_monthly.parquet`
- `mainProj/data/prod/crsp_monthly_panel.parquet`
- `mainProj/data/prod/crsp_markit_matching_summary.csv`
- `mainProj/data/prod/crsp_fee_descriptive.csv`
- `mainProj/data/prod/prototype_weights.parquet`
- `mainProj/data/prod/prototype_monthly_metrics.csv`
- `mainProj/data/prod/prototype_summary.csv`
- `mainProj/data/prod/prototype_sensitivity.csv`
- `mainProj/reports/figures/markit/`
- `mainProj/reports/figures/prototype/`

## 核心发现

CRSP 研究样本费用分布：

{md_table(fee_desc.round(4))}

M0–M3 原型摘要：

{md_table(prototype_summary.round(6))}

约束检查：

{md_table(constraints.round(12))}

M2/M3 敏感性结果预览：

{md_table(sensitivity, max_rows=10) if not sensitivity.empty else "（敏感性结果文件暂未生成。）"}

## 修复的问题

- 原始盘点脚本原先只扫描 `raw` 根目录，已改为递归扫描。
- Markit 月度输出原先只保留 2007–2025 描述统计子集，已改为保存 2002–2026 完整股票-月表。
- CRSP 匹配状态现在区分 CUSIP9、唯一 CUSIP8、4-of-21 预筛选和无费用匹配。
- M0–M3 费用会计已修正：M0 不扣成本，M1 只扣交易成本，M2/M3 扣空头借券费并单独核算多头出借收入。
- `cvxpy`/OSQP 在当前本机二进制环境不稳定，已改用 Clarabel 直接 QP 接口。

## 数据质量发现

- `13f/13ftype1.csv` 与 `13f/type1.csv` 为同哈希重复文件；`13f/stock_ownership_summary_csv.csv`、`13f/stockownershipsummary.csv`、根目录 `stockownershipsummary.csv` 为同哈希重复文件，暂不删除，仅指定规范输入。
- Markit `US ETF` 已单独排除，不混入普通股票主样本；主样本仅含 `US Equity (Others)`、`US Equity (RUSSELL 2000)`、`US Equity (S&P500)`。
- `saf`、`sar`、`utilisation` 等字段保留但单位仍需字段字典确认；主报告不对非百分比或极端值做强经济解释。
- CRSP 普通股筛选为 CIZ 映射口径 `EQTY/COM/NS`，不直接宣称等同旧版 `shrcd=10/11`。
- CRSP 与 Markit 使用 CUSIP9 优先、唯一 CUSIP8 兜底；多候选情形标为歧义，不强行匹配。

## 关键参数和假设

- 研究主区间：2007-01 至 2025-12；CRSP 月度面板构建覆盖 2005-01 至 2025-12。
- 费用主字段：`indicativefee`，按年化 decimal 口径在月度原型中除以 12。
- 交易成本默认单边 50 bps；单只股票权重范围 `[-2%, 2%]`；总仓位绝对值上限 1.5。
- 每月按滞后市值分五组，每组最多 200 只，目标约 1,000 只；共同样本不足时使用当月全部可用共同样本。
- M2 使用 M1 权重并事后扣空头借券费；M3 将交易成本和线性空头持有费同时放入目标函数。
- 多头出借收入按 `fee × utilisation × 0.7` 单独核算；不会与 JKMP 原文口径混称。

## 测试与运行结果

- `python -m py_compile` 已通过全部新增脚本。
- Markit 全量处理完成：股票-月摘要 2,738,239 行。
- CRSP 月度面板完成：1,221,637 行，12,344 个 PERMNO。
- 原型求解状态：全部 912 个模型-月份组合为 `CLARABEL_SOLVED`。
- 敏感性求解状态：`prototype_sensitivity.csv` 为实际重跑结果，当前包含 {len(sensitivity)} 行 M2/M3 汇总。
- 权重约束最大误差见上方约束检查表。

## 限制与待补

- 当前原型不是官方 JKMP 全量复现；缺少官方 `usa.csv`、`usa_dsf.csv`、完整因子面板、市场收益和 FF3/risk-free 文件。
- 本机没有 R/Rscript 与 SLURM/HPC 环境，官方 JKMP R 代码无法直接运行。
- 课表状态按用户说明记录为“已发送”，具体发送日期和凭证待补充。
- 仍需做 20–30 只股票的人工 CUSIP 匹配抽查。
- 仍需与导师确认是否按 MPP 554,253 股票-月严格复刻过滤样本。

## 缺失数据清单

- 官方 JKMP 输入：`usa.csv`、`usa_dsf.csv`、`world_ret_monthly.csv`、`Factor Details.xlsx`、`Cluster Labels.csv`、`market_returns.csv`、`ff3_m.csv`。
- 完整预测变量面板、风险自由利率、官方训练/测试切分元数据和集群运行脚本所需环境变量。
- Markit/MPP 字段字典或数据提供方说明，用于最终确认 `indicativefee`、`saf`、`sar`、`utilisation` 的单位和经济解释。
"""
    path.write_text(content, encoding="utf-8")


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    fee_desc, by_size, _ = make_crsp_fee_outputs(root)
    prototype_summary, constraints = make_prototype_summary(root)
    write_pipeline_readme(root, fee_desc, prototype_summary)
    write_meeting_manual(root, fee_desc, by_size, prototype_summary)
    write_completion_record(root, fee_desc, prototype_summary, constraints)
    print("wrote final research reports")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
