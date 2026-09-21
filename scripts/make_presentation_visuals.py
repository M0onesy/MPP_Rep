#!/usr/bin/env python3
"""Create presentation-oriented visuals for the next meeting report.

The script reads existing production outputs only.  It does not rebuild the
Markit/CRSP/prototype pipeline.
"""

from __future__ import annotations

from pathlib import Path
import textwrap

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
PROD = ROOT / "data" / "prod"
FIG_DIR = ROOT / "reports" / "figures" / "presentation"

COLORS = {
    "blue": "#2F6B9A",
    "orange": "#E07A2F",
    "green": "#3B8F48",
    "red": "#C44E52",
    "purple": "#7B5FA4",
    "gray": "#6B7280",
    "light": "#EEF2F6",
}

EVENTS = [
    ("2008 financial crisis", "2008-09-15"),
    ("2020 COVID shock", "2020-03-01"),
    ("2021 meme / post-COVID", "2021-01-01"),
    ("2023-2025 high-fee phase", "2023-01-01"),
]


def setup_style() -> None:
    plt.rcParams.update(
        {
            "font.sans-serif": ["Microsoft YaHei", "SimHei", "Arial Unicode MS", "DejaVu Sans"],
            "axes.unicode_minus": False,
            "figure.dpi": 120,
            "savefig.dpi": 180,
            "axes.titlesize": 15,
            "axes.labelsize": 11,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
            "legend.fontsize": 9,
        }
    )


def ensure_output() -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)


def save(fig: plt.Figure, name: str) -> None:
    path = FIG_DIR / name
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {path}")


def conclusion(fig: plt.Figure, text: str) -> None:
    fig.text(
        0.01,
        0.01,
        "报告结论：" + textwrap.fill(text, width=78),
        ha="left",
        va="bottom",
        fontsize=10,
        color="#111827",
        bbox={"boxstyle": "round,pad=0.35", "facecolor": "#FFF7ED", "edgecolor": "#FDBA74"},
    )


def parse_month(values: pd.Series) -> pd.Series:
    return pd.to_datetime(values.astype("string") + "-01", errors="coerce")


def add_event_lines(ax: plt.Axes, ymax: float | None = None) -> None:
    for label, date in EVENTS:
        stamp = pd.Timestamp(date)
        if label.startswith("2023"):
            ax.axvspan(pd.Timestamp("2023-01-01"), pd.Timestamp("2025-12-31"), color="#E5E7EB", alpha=0.35)
            ax.text(pd.Timestamp("2023-03-01"), ymax if ymax else ax.get_ylim()[1] * 0.92, "2023-2025\nhigh-fee", fontsize=8, color=COLORS["gray"])
        else:
            ax.axvline(stamp, color="#9CA3AF", linestyle="--", linewidth=1.0)
            ax.text(stamp, ymax if ymax else ax.get_ylim()[1] * 0.92, label.split()[0], rotation=90, va="top", ha="right", fontsize=8, color=COLORS["gray"])


def plot_coverage_heatmap() -> None:
    coverage = pd.read_csv(PROD / "markit_coverage.csv")
    annual = coverage[coverage["period"].astype(str).str.fullmatch(r"\d{4}")].copy()
    annual["year"] = annual["period"].astype(int)
    annual = annual[(annual["year"] >= 2006) & (annual["year"] <= 2026)]
    matching = pd.read_csv(PROD / "crsp_markit_matching_summary.csv")
    matching["year"] = matching["year"].astype(int)

    rows: dict[str, pd.Series] = {
        "IndicativeFee": annual.set_index("year")["indicativefee_coverage"],
        "DCBS": annual.set_index("year")["dcbs_coverage"],
        "SAF": annual.set_index("year")["saf_coverage"],
        "SAR": annual.set_index("year")["sar_coverage"],
        "Utilisation": annual.set_index("year")["utilisation_coverage"],
        "CUSIP9": annual.set_index("year")["cusip9_nonmissing"] / annual.set_index("year")["rows"],
        "CRSP fee matched": matching.set_index("year")["fee_observed_share"],
        "CRSP 4-of-21": matching.set_index("year")["four_of_21_share"],
    }
    years = list(range(2006, 2027))
    matrix = pd.DataFrame(rows).T.reindex(columns=years).astype(float)

    fig, ax = plt.subplots(figsize=(13, 5.6))
    image = ax.imshow(matrix.values * 100, aspect="auto", cmap="YlGnBu", vmin=0, vmax=100)
    ax.set_title("图1 数据覆盖总览：IndicativeFee 从早期即有可用覆盖，CRSP 匹配稳定")
    ax.set_xticks(range(len(years)))
    ax.set_xticklabels(years, rotation=45, ha="right")
    ax.set_yticks(range(len(matrix.index)))
    ax.set_yticklabels(matrix.index)
    for y in range(matrix.shape[0]):
        for x in range(matrix.shape[1]):
            value = matrix.iat[y, x]
            if pd.notna(value):
                color = "white" if value > 0.65 else "#111827"
                ax.text(x, y, f"{value * 100:.0f}", ha="center", va="center", fontsize=7, color=color)
    cbar = fig.colorbar(image, ax=ax, fraction=0.025, pad=0.02)
    cbar.set_label("覆盖率 / 匹配率 (%)")
    conclusion(fig, "数据不是只有单日或单年；核心费率、CUSIP 和 CRSP 匹配在主研究期内足以支持原型分析。")
    save(fig, "fig01_coverage_heatmap.png")


def plot_sample_timeline() -> None:
    markit = pd.read_parquet(
        PROD / "markit_stock_monthly.parquet",
        columns=["month", "fee_obs_count", "qualifies_4of21_month_prefilter"],
    )
    markit_summary = (
        markit.assign(
            month_date=parse_month(markit["month"]),
            fee_available=markit["fee_obs_count"].fillna(0).gt(0),
        )
        .groupby("month_date")
        .agg(
            markit_stock_months=("month", "size"),
            fee_available=("fee_available", "sum"),
            markit_4of21=("qualifies_4of21_month_prefilter", "sum"),
        )
        .reset_index()
    )
    panel = pd.read_parquet(
        PROD / "crsp_monthly_panel.parquet",
        columns=["month", "fee_asof", "fee_realized", "qualifies_4of21", "in_universe"],
    )
    panel_summary = (
        panel.assign(
            month_date=parse_month(panel["month"]),
            common_fee=panel["fee_asof"].notna() & panel["fee_realized"].notna() & panel["qualifies_4of21"],
        )
        .groupby("month_date")
        .agg(crsp_common_fee=("common_fee", "sum"), selected_universe=("in_universe", "sum"))
        .reset_index()
    )
    data = markit_summary.merge(panel_summary, on="month_date", how="left").sort_values("month_date")
    data = data[(data["month_date"] >= "2006-01-01") & (data["month_date"] <= "2026-08-31")]

    fig, ax = plt.subplots(figsize=(13, 5.8))
    ax.plot(data["month_date"], data["fee_available"], label="Markit 有费率股票数", color=COLORS["blue"], linewidth=2)
    ax.plot(data["month_date"], data["markit_4of21"], label="满足 4-of-21", color=COLORS["green"], linewidth=2)
    ax.plot(data["month_date"], data["crsp_common_fee"], label="CRSP 共同样本", color=COLORS["orange"], linewidth=2)
    ax.plot(data["month_date"], data["selected_universe"], label="原型目标宇宙", color=COLORS["purple"], linewidth=1.8)
    ax.set_title("图2 Markit 样本规模时间线：共同样本足以支撑每月约 1,000 只股票原型")
    ax.set_ylabel("股票数 / 股票-月数")
    ax.grid(axis="y", alpha=0.25)
    add_event_lines(ax)
    ax.legend(ncol=2, frameon=True)
    conclusion(fig, "从 2007 年起，Markit 费率和 CRSP 共同样本稳定覆盖，原型每月目标宇宙约 1,000 只股票有数据支撑。")
    save(fig, "fig02_sample_timeline.png")


def plot_fee_timeseries() -> None:
    data = pd.read_csv(PROD / "markit_fee_timeseries.csv")
    data["date"] = parse_month(data["period"])
    data = data.dropna(subset=["date"]).sort_values("date")

    fig, axes = plt.subplots(2, 1, figsize=(13, 7.6), sharex=True, gridspec_kw={"height_ratios": [2.0, 1.15]})
    ax = axes[0]
    ax.fill_between(data["date"], data["p25_percent"], data["p75_percent"], color="#BFDBFE", alpha=0.55, label="p25-p75")
    ax.plot(data["date"], data["median_percent"], color=COLORS["blue"], linewidth=2, label="median")
    ax.plot(data["date"], data["mean_percent"], color=COLORS["red"], linewidth=2, label="mean")
    ax.plot(data["date"], data["p90_percent"], color=COLORS["green"], linewidth=2, label="p90")
    ax.set_title("图3 借券费时间序列：均值、p90 与 p99 在 2023-2025 明显抬升")
    ax.set_ylabel("median / mean / p90 (%)")
    ax.grid(axis="y", alpha=0.25)
    ax.set_ylim(bottom=0)
    add_event_lines(ax)
    ax.legend(ncol=4, loc="upper left")

    ax2 = axes[1]
    ax2.plot(data["date"], data["p99_percent"], color=COLORS["purple"], linewidth=1.9, label="p99")
    ax2.fill_between(data["date"], 0, data["p99_percent"], color=COLORS["purple"], alpha=0.12)
    ax2.set_ylabel("p99 (%)")
    ax2.set_xlabel("月份")
    ax2.grid(axis="y", alpha=0.25)
    ax2.set_ylim(bottom=0)
    add_event_lines(ax2)
    ax2.legend(loc="upper left")
    conclusion(fig, "费率不是固定常数；高分位随时间大幅变化，说明把借券费当作动态持有成本是有数据基础的。")
    save(fig, "fig03_fee_timeseries_annotated.png")


def plot_key_year_distributions() -> None:
    monthly = pd.read_parquet(PROD / "markit_stock_monthly.parquet", columns=["month", "fee_median"])
    monthly["year"] = monthly["month"].astype(str).str[:4].astype(int)
    monthly["fee_percent"] = monthly["fee_median"] * 100.0
    years = [2006, 2008, 2020, 2024]

    fig, axes = plt.subplots(2, 2, figsize=(13, 8), sharex=True, sharey=True)
    bins = np.logspace(np.log10(0.1), np.log10(200), 55)
    for ax, year in zip(axes.ravel(), years):
        values = monthly.loc[monthly["year"].eq(year), "fee_percent"].dropna()
        values = values[(values > 0) & np.isfinite(values)].clip(upper=200)
        ax.hist(values, bins=bins, color=COLORS["blue"], alpha=0.75, density=True)
        ax.set_xscale("log")
        if not values.empty:
            stats = values.quantile([0.5, 0.9, 0.99])
            for quantile, color in zip([0.5, 0.9, 0.99], [COLORS["orange"], COLORS["green"], COLORS["red"]]):
                ax.axvline(stats.loc[quantile], color=color, linestyle="--", linewidth=1.4)
            ax.text(
                0.04,
                0.92,
                f"p50={stats.loc[0.5]:.2f}%\np90={stats.loc[0.9]:.2f}%\np99={stats.loc[0.99]:.1f}%",
                transform=ax.transAxes,
                va="top",
                fontsize=9,
                bbox={"boxstyle": "round,pad=0.3", "facecolor": "white", "edgecolor": "#D1D5DB"},
            )
        ax.set_title(f"{year} 年横截面分布")
        ax.grid(axis="y", alpha=0.25)
    for ax in axes[-1, :]:
        ax.set_xlabel("Indicative fee (%)，log scale")
    for ax in axes[:, 0]:
        ax.set_ylabel("密度")
    fig.suptitle("图4 关键年份横截面分布：右尾长期存在，2024 高费尾部更突出", y=0.995)
    conclusion(fig, "导师点名的年份都显示明显右偏分布；高费尾部不是个别月份噪声。")
    save(fig, "fig04_key_year_fee_distributions.png")


def plot_size_gradient() -> None:
    data = pd.read_csv(PROD / "crsp_fee_by_size_group.csv").sort_values("market_cap_group")
    fig, ax = plt.subplots(figsize=(11, 6))
    x = data["market_cap_group"]
    ax.plot(x, data["median_percent"], marker="o", linewidth=2, color=COLORS["blue"], label="median")
    ax.plot(x, data["p90_percent"], marker="o", linewidth=2, color=COLORS["orange"], label="p90")
    ax.plot(x, data["p99_percent"], marker="o", linewidth=2, color=COLORS["green"], label="p99")
    ax.axhline(30.0, linestyle="--", color=COLORS["red"], linewidth=1.5, label="MPP p99 = 30%")
    ax.axhline(1.1, linestyle=":", color=COLORS["gray"], linewidth=1.8, label="JKMP large-stock p99 = 1.1%")
    ax.set_yscale("log")
    ax.set_ylim(0.1, 120)
    ax.set_xticks([1, 2, 3, 4, 5])
    ax.set_xticklabels(["1 小盘", "2", "3", "4", "5 大盘"])
    ax.set_ylabel("Indicative fee (%)，log scale")
    ax.set_title("图5 市值分组借券费梯度：高费风险主要集中在小盘端")
    ax.grid(axis="y", alpha=0.25, which="both")
    ax.legend(loc="upper right")
    conclusion(fig, "大盘组接近 JKMP 的 modest 场景；小盘组 p99 远高于 30%，说明投资域扩展后借券费可能成为一阶摩擦。")
    save(fig, "fig05_fee_by_size_group.png")


def plot_variance_persistence() -> None:
    variance = pd.read_csv(PROD / "markit_fee_variance_decomposition.csv")
    persistence = pd.read_csv(PROD / "markit_fee_persistence.csv")
    labels = {
        "entity_means_only": "股票固定效应",
        "time_means_only": "月份固定效应",
        "two_way_entity_time": "双向固定效应",
        "residual_after_two_way": "残差",
    }
    var_data = variance[variance["component"].isin(labels)].copy()
    var_data["label"] = var_data["component"].map(labels)

    fig, axes = plt.subplots(1, 2, figsize=(13, 5.6))
    axes[0].bar(var_data["label"], var_data["r2"] * 100, color=[COLORS["blue"], COLORS["orange"], COLORS["green"], COLORS["gray"]])
    axes[0].set_ylabel("解释比例 / R² (%)")
    axes[0].set_title("横截面 vs 时间序列变异")
    axes[0].tick_params(axis="x", rotation=20)
    for idx, value in enumerate(var_data["r2"] * 100):
        axes[0].text(idx, value + 1, f"{value:.1f}%", ha="center", fontsize=9)

    axes[1].plot(persistence["lag_months"], persistence["fee_autocorrelation"], marker="o", linewidth=2, label="费率自相关", color=COLORS["blue"])
    axes[1].plot(persistence["lag_months"], persistence["high_fee_persistence_probability"], marker="o", linewidth=2, label="高费仍为高费概率", color=COLORS["red"])
    axes[1].set_ylim(0, 1.0)
    axes[1].set_xticks(persistence["lag_months"])
    axes[1].set_xlabel("滞后月数")
    axes[1].set_title("费率持续性")
    axes[1].grid(axis="y", alpha=0.25)
    axes[1].legend()
    fig.suptitle("图6 费率变异度分解：横截面差异强，且高费状态具有持续性", y=1.02)
    conclusion(fig, "股票间差异解释约 55%，1 个月自相关约 0.85；借券费既有横截面信息，也不是瞬时噪声。")
    save(fig, "fig06_variance_persistence.png")


def plot_matching_funnel() -> None:
    panel = pd.read_parquet(
        PROD / "crsp_monthly_panel.parquet",
        columns=[
            "month",
            "eligible_crsp",
            "in_universe",
            "fee_realized",
            "fee_asof",
            "qualifies_4of21",
        ],
    )
    panel = panel[(panel["month"].astype(str) >= "2007-01") & (panel["month"].astype(str) <= "2025-12")].copy()
    counts = pd.Series(
        {
            "CRSP common monthly panel": len(panel),
            "Price / market-cap eligible": int(panel["eligible_crsp"].sum()),
            "CUSIP fee matched": int(panel["fee_realized"].notna().sum()),
            "fee_asof available": int(panel["fee_asof"].notna().sum()),
            "4-of-21 qualified": int((panel["qualifies_4of21"] & panel["fee_asof"].notna()).sum()),
            "Prototype selected universe": int(panel["in_universe"].sum()),
        }
    )
    fig, ax = plt.subplots(figsize=(12, 6))
    y = np.arange(len(counts))
    colors = [COLORS["blue"], COLORS["blue"], COLORS["green"], COLORS["green"], COLORS["orange"], COLORS["purple"]]
    ax.barh(y, counts.values, color=colors, alpha=0.85)
    ax.set_yticks(y)
    ax.set_yticklabels(counts.index)
    ax.invert_yaxis()
    ax.set_xlabel("股票-月观测数")
    ax.set_title("图7 CRSP-Markit 匹配漏斗：共同样本从面板到原型宇宙可追踪")
    max_value = counts.max()
    for idx, value in enumerate(counts.values):
        ax.text(value + max_value * 0.01, idx, f"{value:,}", va="center", fontsize=10)
    ax.grid(axis="x", alpha=0.25)
    conclusion(fig, "样本筛选路径透明：费用匹配与 4-of-21 条件不会把主研究期压成不可用小样本。")
    save(fig, "fig07_crsp_markit_funnel.png")


def bar_panel(ax: plt.Axes, data: pd.DataFrame, field: str, title: str, scale: float = 1.0, ylabel: str = "") -> None:
    values = data[field] * scale
    ax.bar(data["model"], values, color=[COLORS["blue"], COLORS["orange"], COLORS["red"], COLORS["green"]])
    ax.set_title(title)
    if ylabel:
        ax.set_ylabel(ylabel)
    ax.grid(axis="y", alpha=0.25)
    for idx, value in enumerate(values):
        ax.text(idx, value + (abs(values).max() or 1) * 0.04, f"{value:.2f}", ha="center", fontsize=8)


def plot_m0_m3_dashboard() -> None:
    summary = pd.read_csv(PROD / "prototype_summary.csv")
    fig, axes = plt.subplots(2, 3, figsize=(14, 8))
    bar_panel(axes[0, 0], summary, "annualized_net", "年化净收益", 100, "%")
    bar_panel(axes[0, 1], summary, "average_transaction_cost", "月均交易成本", 100, "%")
    bar_panel(axes[0, 2], summary, "average_short_fee", "月均空头借券费", 100, "%")
    bar_panel(axes[1, 0], summary, "average_lending_revenue", "月均多头出借收入", 100, "%")
    bar_panel(axes[1, 1], summary, "average_turnover", "月均换手", 1, "")
    bar_panel(axes[1, 2], summary, "average_short_weight", "平均空头权重", 100, "%")
    fig.suptitle("图8 M0-M3 原型仪表板：成本项逐步吞噬无摩擦收益", y=1.02)
    conclusion(fig, "M0 到 M3 的差异主要来自交易成本与空头借券费；当前结果用于验证机制，不代表官方 JKMP 复现。")
    save(fig, "fig08_m0_m3_dashboard.png")


def plot_method_flow() -> None:
    fig, ax = plt.subplots(figsize=(13, 6.4))
    ax.axis("off")
    boxes = [
        (0.04, 0.66, 0.22, 0.18, "输入数据\nCRSP 价量信号\nMarkit fee_asof\n12个月风险代理", COLORS["blue"]),
        (0.35, 0.66, 0.24, 0.18, "月度单期 QP\n权重和=1\n单股 [-2%,2%]\n总杠杆 <= 1.5", COLORS["purple"]),
        (0.70, 0.66, 0.24, 0.18, "输出\n权重 / 换手\n交易成本 / 借券费\n净收益 / 求解状态", COLORS["green"]),
        (0.04, 0.26, 0.20, 0.22, "M0\n无交易成本\n无借券费", COLORS["gray"]),
        (0.29, 0.26, 0.20, 0.22, "M1\n交易成本进入目标\n不含借券费", COLORS["orange"]),
        (0.54, 0.26, 0.20, 0.22, "M2\n使用 M1 权重\n事后扣空头借券费", COLORS["red"]),
        (0.78, 0.26, 0.20, 0.22, "M3\n交易成本 + 空头持有费\n同时进入目标", COLORS["green"]),
    ]
    for x, y, w, h, text, color in boxes:
        ax.add_patch(plt.Rectangle((x, y), w, h, facecolor=color, alpha=0.16, edgecolor=color, linewidth=2))
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=12, color="#111827")
    arrows = [
        ((0.26, 0.75), (0.35, 0.75)),
        ((0.59, 0.75), (0.70, 0.75)),
        ((0.47, 0.66), (0.47, 0.48)),
        ((0.47, 0.48), (0.14, 0.48)),
        ((0.47, 0.48), (0.39, 0.48)),
        ((0.47, 0.48), (0.64, 0.48)),
        ((0.47, 0.48), (0.88, 0.48)),
    ]
    for start, end in arrows:
        ax.annotate("", xy=end, xytext=start, arrowprops={"arrowstyle": "->", "linewidth": 1.8, "color": "#374151"})
    ax.text(0.5, 0.94, "图11 M0–M3 原型设计：核心比较是 M2 的事后扣费 vs M3 的目标函数内生化", ha="center", fontsize=16, weight="bold")
    conclusion(fig, "这页用于先讲清楚对象：当前是 Python 研究原型，目标是验证借券费内生化机制，不是官方 JKMP 全量复现。")
    save(fig, "fig11_m0_m3_method_flow.png")


def plot_m2_m3_core() -> None:
    metrics = pd.read_csv(PROD / "prototype_monthly_metrics.csv")
    metrics["date"] = parse_month(metrics["month"])
    subset = metrics[metrics["model"].isin(["M2", "M3"])].sort_values(["model", "date"]).copy()
    summary = pd.read_csv(PROD / "prototype_summary.csv")
    summary = summary[summary["model"].isin(["M2", "M3"])].copy()

    fig, axes = plt.subplots(1, 3, figsize=(14, 5.6))
    for model, color in [("M2", COLORS["orange"]), ("M3", COLORS["green"])]:
        group = subset[subset["model"].eq(model)].copy()
        group["cum_net"] = (1.0 + group["net_return"].fillna(0)).cumprod() - 1.0
        axes[0].plot(group["date"], group["cum_net"] * 100, label=model, color=color, linewidth=2)
    axes[0].set_title("净收益路径")
    axes[0].set_ylabel("累计净收益 (%)")
    axes[0].grid(axis="y", alpha=0.25)
    axes[0].legend()

    metric_table = summary.set_index("model")
    compare = pd.DataFrame(
        {
            "年化净收益(%)": metric_table["annualized_net"] * 100,
            "月均空头费(%)": metric_table["average_short_fee"] * 100,
            "月均换手": metric_table["average_turnover"],
        }
    )
    compare.T.plot(kind="bar", ax=axes[1], color=[COLORS["orange"], COLORS["green"]])
    axes[1].set_title("M2 vs M3 关键指标")
    axes[1].tick_params(axis="x", rotation=20)
    axes[1].grid(axis="y", alpha=0.25)
    axes[1].legend(title="")

    diff = (compare.loc["M3"] - compare.loc["M2"]).rename("M3 - M2")
    colors = [COLORS["green"] if value >= 0 else COLORS["red"] for value in diff]
    axes[2].bar(diff.index, diff.values, color=colors)
    axes[2].axhline(0, color="#111827", linewidth=0.8)
    axes[2].set_title("内生化相对事后扣费的差")
    axes[2].tick_params(axis="x", rotation=20)
    axes[2].grid(axis="y", alpha=0.25)
    for idx, value in enumerate(diff.values):
        axes[2].text(idx, value, f"{value:.3f}", ha="center", va="bottom" if value >= 0 else "top", fontsize=8)
    fig.suptitle("图9 M2 vs M3：事后扣费与目标函数内生化是不同对象", y=1.02)
    conclusion(fig, "M3 会重新配置权重并降低空头费暴露，但在当前简化原型中净收益没有优于 M2；这正是组会要讨论的机制验证结果。")
    save(fig, "fig09_m2_m3_core_comparison.png")


def plot_sensitivity_panel() -> None:
    data = pd.read_csv(PROD / "prototype_sensitivity.csv")
    data["annualized_net_pct"] = data["annualized_net"] * 100
    fig, axes = plt.subplots(2, 3, figsize=(15, 8))
    panels = [
        ("transaction_cost_bps", "交易成本 bps", axes[0, 0]),
        ("fee_scale", "费用缩放", axes[0, 1]),
        ("target_stocks", "目标股票数", axes[0, 2]),
    ]
    for parameter, title, ax in panels:
        subset = data[data["parameter"].eq(parameter)].copy()
        subset["x"] = pd.to_numeric(subset["value"], errors="coerce")
        for model, color in [("M2", COLORS["orange"]), ("M3", COLORS["green"])]:
            group = subset[subset["model"].eq(model)].sort_values("x")
            ax.plot(group["x"], group["annualized_net_pct"], marker="o", linewidth=2, label=model, color=color)
        ax.axhline(0, color="#111827", linewidth=0.8)
        ax.set_title(title)
        ax.set_ylabel("年化净收益 (%)")
        ax.grid(axis="y", alpha=0.25)
        ax.legend()

    sample = data[data["parameter"].eq("sample")].copy()
    sample["label"] = sample["sample"].replace({"common_fee_4of21": "共同样本", "all_crsp_monthly_median_fill": "全CRSP中位填补"})
    for model, color in [("M2", COLORS["orange"]), ("M3", COLORS["green"])]:
        group = sample[sample["model"].eq(model)]
        axes[1, 0].bar(group["label"] + "\n" + model, group["annualized_net_pct"], color=color, alpha=0.85)
    axes[1, 0].axhline(0, color="#111827", linewidth=0.8)
    axes[1, 0].set_title("样本口径")
    axes[1, 0].set_ylabel("年化净收益 (%)")
    axes[1, 0].tick_params(axis="x", rotation=15)
    axes[1, 0].grid(axis="y", alpha=0.25)

    lending = data[data["parameter"].eq("lending_revenue")].copy()
    lending["label"] = lending["value"].replace({"included": "含出借收入", "excluded": "不含出借收入"})
    for model, color in [("M2", COLORS["orange"]), ("M3", COLORS["green"])]:
        group = lending[lending["model"].eq(model)]
        axes[1, 1].bar(group["label"] + "\n" + model, group["annualized_net_pct"], color=color, alpha=0.85)
    axes[1, 1].axhline(0, color="#111827", linewidth=0.8)
    axes[1, 1].set_title("多头出借收入开关")
    axes[1, 1].tick_params(axis="x", rotation=15)
    axes[1, 1].grid(axis="y", alpha=0.25)

    axes[1, 2].axis("off")
    baseline = data[(data["parameter"].eq("transaction_cost_bps")) & (data["value"].astype(str).eq("50"))]
    if not baseline.empty:
        m2 = baseline[baseline["model"].eq("M2")]["annualized_net_pct"].iloc[0]
        m3 = baseline[baseline["model"].eq("M3")]["annualized_net_pct"].iloc[0]
        text = f"默认 50bps 下：\nM2 年化净收益 {m2:.2f}%\nM3 年化净收益 {m3:.2f}%\n\n敏感性结果用于说明\n交易成本假设是当前原型最敏感参数。"
    else:
        text = "敏感性结果已实际重跑，详见 prototype_sensitivity.csv。"
    axes[1, 2].text(0.05, 0.8, text, va="top", fontsize=13, bbox={"boxstyle": "round,pad=0.5", "facecolor": COLORS["light"], "edgecolor": "#CBD5E1"})
    fig.suptitle("图10 M2/M3 敏感性：交易成本设定主导净收益水平", y=1.02)
    conclusion(fig, "敏感性图把稳健性从表格变成可讲的故事：成本越高净收益越低，样本和出借收入改变幅度较小。")
    save(fig, "fig10_sensitivity_panel.png")


def main() -> int:
    setup_style()
    ensure_output()
    plot_coverage_heatmap()
    plot_sample_timeline()
    plot_fee_timeseries()
    plot_key_year_distributions()
    plot_size_gradient()
    plot_variance_persistence()
    plot_matching_funnel()
    plot_method_flow()
    plot_m0_m3_dashboard()
    plot_m2_m3_core()
    plot_sensitivity_panel()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
