#!/usr/bin/env python3
"""Process Markit American Equities in bounded chunks.

The source has more than 64 million records.  This script filters ordinary
US-equity categories, writes annual Parquet partitions, then creates compact
stock-month summaries used by the CRSP join and the descriptive analysis.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from pipeline_utils import ensure_dirs, normalize_cusip, numeric, write_csv


MARKET_AREAS = [
    "US Equity (Others)",
    "US Equity (RUSSELL 2000)",
    "US Equity (S&P500)",
]
ALL_FIELDS = [
    "dxlid",
    "datadate",
    "isin",
    "sedol",
    "cusip",
    "marketarea",
    "indicativefee",
    "indicativerebate",
    "dcbs",
    "saf",
    "sar",
    "utilisation",
    "activeutilisation",
    "lendablevalue",
    "lendablequantity",
    "valueonloan",
    "quantityonloan",
    "shortloanvalue",
    "shortloanquantity",
]
NUMERIC_FIELDS = [
    "indicativefee",
    "indicativerebate",
    "dcbs",
    "saf",
    "sar",
    "utilisation",
    "activeutilisation",
    "lendablevalue",
    "lendablequantity",
    "valueonloan",
    "quantityonloan",
    "shortloanvalue",
    "shortloanquantity",
]
QUALITY_FIELDS = [
    "indicativefee",
    "dcbs",
    "saf",
    "sar",
    "utilisation",
    "activeutilisation",
]


def partition_schema() -> pa.Schema:
    return pa.schema(
        [
            ("dxlid", pa.string()),
            ("datadate", pa.date32()),
            ("isin", pa.string()),
            ("sedol", pa.string()),
            ("cusip", pa.string()),
            ("cusip8", pa.string()),
            ("cusip9", pa.string()),
            ("marketarea", pa.string()),
            ("indicativefee", pa.float64()),
            ("indicativerebate", pa.float64()),
            ("dcbs", pa.float64()),
            ("saf", pa.float64()),
            ("sar", pa.float64()),
            ("utilisation", pa.float64()),
            ("activeutilisation", pa.float64()),
            ("lendablevalue", pa.float64()),
            ("lendablequantity", pa.float64()),
            ("valueonloan", pa.float64()),
            ("quantityonloan", pa.float64()),
            ("shortloanvalue", pa.float64()),
            ("shortloanquantity", pa.float64()),
            ("quality_flags", pa.string()),
        ]
    )


def prepare_chunk(chunk: pd.DataFrame) -> pd.DataFrame:
    for field in ("dxlid", "isin", "sedol", "cusip", "marketarea"):
        chunk[field] = chunk[field].astype("string").str.strip().replace({"": pd.NA})
    chunk["datadate"] = pd.to_datetime(chunk["datadate"], errors="coerce")
    chunk = chunk[chunk["datadate"].notna()].copy()
    chunk["cusip8"], chunk["cusip9"] = normalize_cusip(chunk["cusip"])
    for field in NUMERIC_FIELDS:
        chunk[field] = numeric(chunk[field])

    flags = pd.Series("", index=chunk.index, dtype="string")

    def add_flag(mask: pd.Series, label: str) -> None:
        nonlocal flags
        flags = flags.mask(mask & flags.eq(""), label)
        flags = flags.mask(mask & flags.ne("") & ~flags.str.contains(label, regex=False), flags + ";" + label)

    add_flag(chunk["indicativefee"].lt(0) | chunk["indicativefee"].gt(100), "indicativefee_outlier")
    add_flag(~chunk["dcbs"].between(1, 10) & chunk["dcbs"].notna(), "dcbs_outside_1_10")
    add_flag(~chunk["utilisation"].between(0, 1) & chunk["utilisation"].notna(), "utilisation_unit_check")
    add_flag(~chunk["activeutilisation"].between(0, 1) & chunk["activeutilisation"].notna(), "activeutilisation_unit_check")
    chunk["quality_flags"] = flags
    return chunk


def update_coverage(stats: dict[str, dict[str, Any]], quality_counts: dict[str, int], frame: pd.DataFrame) -> None:
    if frame.empty:
        return
    frame = frame.copy()
    frame["year"] = frame["datadate"].dt.year
    frame["month"] = frame["datadate"].dt.to_period("M").astype(str)
    for year, group in frame.groupby("year", sort=False):
        target = stats.setdefault(str(int(year)), {"period": str(int(year)), "rows": 0})
        target["rows"] += int(len(group))
        for field in QUALITY_FIELDS:
            count = int(group[field].notna().sum())
            target[f"{field}_nonmissing"] = target.get(f"{field}_nonmissing", 0) + count
            quality_counts[field] = quality_counts.get(field, 0) + count
        target["cusip_nonmissing"] = target.get("cusip_nonmissing", 0) + int(group["cusip"].notna().sum())
        target["cusip8_nonmissing"] = target.get("cusip8_nonmissing", 0) + int(group["cusip8"].notna().sum())
        target["cusip9_nonmissing"] = target.get("cusip9_nonmissing", 0) + int(group["cusip9"].notna().sum())
    for month, group in frame.groupby("month", sort=False):
        target = stats.setdefault("month:" + str(month), {"period": str(month), "rows": 0})
        target["rows"] += int(len(group))
        for field in QUALITY_FIELDS:
            target[f"{field}_nonmissing"] = target.get(f"{field}_nonmissing", 0) + int(group[field].notna().sum())


def aggregate_annual(path: Path, output: Path) -> pd.DataFrame:
    frame = pd.read_parquet(path)
    if frame.empty:
        return pd.DataFrame()
    frame["datadate"] = pd.to_datetime(frame["datadate"])
    frame["month"] = frame["datadate"].dt.to_period("M").astype(str)
    frame = frame[frame["cusip8"].notna()].copy()
    frame = frame.sort_values(["cusip8", "cusip9", "month", "datadate"])
    group_cols = ["cusip8", "cusip9", "month"]
    summary = (
        frame.groupby(group_cols, dropna=False, sort=False)
        .agg(
            marketarea=("marketarea", "last"),
            fee_obs_count=("indicativefee", "count"),
            dcbs_obs_count=("dcbs", "count"),
            saf_obs_count=("saf", "count"),
            sar_obs_count=("sar", "count"),
            utilisation_obs_count=("utilisation", "count"),
            activeutilisation_obs_count=("activeutilisation", "count"),
            fee_mean=("indicativefee", "mean"),
            fee_median=("indicativefee", "median"),
            fee_max=("indicativefee", "max"),
            utilisation_mean=("utilisation", "mean"),
            utilisation_median=("utilisation", "median"),
            lendablevalue_mean=("lendablevalue", "mean"),
            lendablequantity_mean=("lendablequantity", "mean"),
            last_date=("datadate", "max"),
        )
        .reset_index()
    )
    last = (
        frame.dropna(subset=["indicativefee"])
        .drop_duplicates(group_cols, keep="last")
        [group_cols + ["indicativefee", "utilisation", "activeutilisation", "quality_flags"]]
        .rename(
            columns={
                "indicativefee": "fee_last",
                "utilisation": "utilisation_last",
                "activeutilisation": "activeutilisation_last",
                "quality_flags": "last_quality_flags",
            }
        )
    )
    summary = summary.merge(last, on=group_cols, how="left")
    summary["qualifies_4of21_month_prefilter"] = summary["fee_obs_count"].ge(4)
    summary["year"] = summary["month"].str[:4].astype(int)
    output.parent.mkdir(parents=True, exist_ok=True)
    summary.to_parquet(output, index=False, compression="zstd")
    return summary


def make_descriptive_outputs(monthly: pd.DataFrame, prod_dir: Path, figure_dir: Path, main_start: str, main_end: str) -> None:
    if monthly.empty:
        return
    full_monthly = monthly.copy()
    full_monthly["month"] = full_monthly["month"].astype("string")
    full_monthly.to_parquet(prod_dir / "markit_stock_monthly.parquet", index=False, compression="zstd")
    monthly = full_monthly[
        (full_monthly["month"] >= main_start[:7])
        & (full_monthly["month"] <= main_end[:7])
    ].copy()
    valid = monthly[monthly["fee_last"].notna()].copy()
    valid["fee_percent"] = valid["fee_last"] * 100.0
    valid["high_fee"] = valid["fee_last"].gt(0.01)
    valid["entity"] = valid["cusip9"].fillna(valid["cusip8"])
    valid = valid.sort_values(["entity", "month"])
    rows: list[dict[str, Any]] = []
    for period, group in valid.groupby("month", sort=True):
        values = group["fee_percent"]
        util = group["utilisation_last"].dropna()
        rows.append(
            {
                "period": str(period),
                "stock_month_observations": int(values.size),
                "unique_cusip8": int(group["cusip8"].nunique()),
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
                "high_fee_share": group["high_fee"].mean(),
                "util_mean_raw": util.mean() if not util.empty else np.nan,
                "util_median_raw": util.median() if not util.empty else np.nan,
                "util_p90_raw": util.quantile(0.90) if not util.empty else np.nan,
                "util_p99_raw": util.quantile(0.99) if not util.empty else np.nan,
                "fee_qualifying_share": group["qualifies_4of21_month_prefilter"].mean(),
            }
        )
    time_series = pd.DataFrame(rows)
    write_csv(time_series, prod_dir / "markit_fee_timeseries.csv")

    all_values = valid["fee_percent"]
    all_row = {
        "period": "all",
        "stock_month_observations": int(all_values.size),
        "unique_cusip8": int(valid["cusip8"].nunique()),
        "mean_percent": all_values.mean(),
        "std_percent": all_values.std(ddof=1),
        "min_percent": all_values.min(),
        "p01_percent": all_values.quantile(0.01),
        "p25_percent": all_values.quantile(0.25),
        "median_percent": all_values.median(),
        "p75_percent": all_values.quantile(0.75),
        "p90_percent": all_values.quantile(0.90),
        "p99_percent": all_values.quantile(0.99),
        "max_percent": all_values.max(),
        "high_fee_share": valid["high_fee"].mean(),
        "util_mean_raw": valid["utilisation_last"].mean(),
        "util_median_raw": valid["utilisation_last"].median(),
        "util_p90_raw": valid["utilisation_last"].quantile(0.90),
        "util_p99_raw": valid["utilisation_last"].quantile(0.99),
        "fee_qualifying_share": valid["qualifies_4of21_month_prefilter"].mean(),
    }
    descriptive = pd.DataFrame([all_row] + [
        {
            "period": str(row["period"]),
            **{key: value for key, value in row.items() if key != "period"},
        }
        for row in rows
    ])
    write_csv(descriptive, prod_dir / "markit_fee_descriptive.csv")

    quality = []
    count_columns = {
        "indicativefee": "fee_obs_count",
        "dcbs": "dcbs_obs_count",
        "saf": "saf_obs_count",
        "sar": "sar_obs_count",
        "utilisation": "utilisation_obs_count",
        "activeutilisation": "activeutilisation_obs_count",
    }
    for field in QUALITY_FIELDS:
        count_column = count_columns[field]
        quality.append(
            {
                "field": field,
                "nonmissing_stock_months": int(monthly[count_column].gt(0).sum()),
                "nonmissing_daily_rows": int(monthly[count_column].sum()),
                "interpretation": (
                    "primary annual decimal fee field"
                    if field == "indicativefee"
                    else "raw field retained; units/outliers require dictionary validation"
                ),
            }
        )
    write_csv(pd.DataFrame(quality), prod_dir / "markit_fee_quality.csv")

    make_variance_and_persistence(valid, prod_dir)
    make_figures(time_series, valid, figure_dir)


def make_variance_and_persistence(valid: pd.DataFrame, prod_dir: Path) -> None:
    if valid.empty:
        return
    frame = valid[["entity", "month", "fee_last"]].dropna().copy()
    frame["month"] = frame["month"].astype("string")
    frame = frame.sort_values(["entity", "month"]).drop_duplicates(["entity", "month"], keep="last")
    y = frame["fee_last"].astype(float)
    overall = float(y.mean())
    total_ss = float(((y - overall) ** 2).sum())
    entity_mean = frame.groupby("entity")["fee_last"].transform("mean")
    time_mean = frame.groupby("month")["fee_last"].transform("mean")
    entity_ss = float(((entity_mean - overall) ** 2).sum())
    time_ss = float(((time_mean - overall) ** 2).sum())
    residual = y - entity_mean - time_mean + overall
    two_way_r2 = 1.0 - float((residual**2).sum()) / total_ss if total_ss else np.nan
    variance = pd.DataFrame(
        [
            {"component": "total", "sum_squares": total_ss, "r2": 1.0},
            {"component": "entity_means_only", "sum_squares": entity_ss, "r2": entity_ss / total_ss if total_ss else np.nan},
            {"component": "time_means_only", "sum_squares": time_ss, "r2": time_ss / total_ss if total_ss else np.nan},
            {"component": "two_way_entity_time", "sum_squares": total_ss - float((residual**2).sum()), "r2": two_way_r2},
            {"component": "residual_after_two_way", "sum_squares": float((residual**2).sum()), "r2": 1.0 - two_way_r2 if np.isfinite(two_way_r2) else np.nan},
        ]
    )
    write_csv(variance, prod_dir / "markit_fee_variance_decomposition.csv")

    persistence_rows = []
    for lag in (1, 3, 6, 12):
        shifted = frame.groupby("entity")["fee_last"].shift(lag)
        valid_pair = frame["fee_last"].notna() & shifted.notna()
        corr = frame.loc[valid_pair, "fee_last"].corr(shifted.loc[valid_pair]) if valid_pair.sum() > 2 else np.nan
        high_now = frame["fee_last"].gt(0.01)
        high_future = frame.groupby("entity")["fee_last"].shift(-lag).gt(0.01)
        transition = float(high_future[high_now & high_future.notna()].mean()) if (high_now & high_future.notna()).any() else np.nan
        persistence_rows.append(
            {
                "lag_months": lag,
                "pair_observations": int(valid_pair.sum()),
                "fee_autocorrelation": corr,
                "high_fee_threshold": 0.01,
                "high_fee_persistence_probability": transition,
            }
        )
    write_csv(pd.DataFrame(persistence_rows), prod_dir / "markit_fee_persistence.csv")


def make_figures(time_series: pd.DataFrame, valid: pd.DataFrame, figure_dir: Path) -> None:
    if time_series.empty:
        return
    ensure_dirs(figure_dir)
    dates = pd.to_datetime(time_series["period"])
    plt.figure(figsize=(12, 6))
    plt.plot(dates, time_series["median_percent"], label="median", color="#1f77b4")
    plt.plot(dates, time_series["mean_percent"], label="mean", color="#d62728", alpha=0.75)
    plt.fill_between(dates, time_series["p25_percent"], time_series["p75_percent"], alpha=0.18, label="25-75 percentile")
    plt.plot(dates, time_series["p90_percent"], label="90th percentile", color="#2ca02c", alpha=0.8)
    for mark in ("2008-09", "2020-03", "2021-01"):
        plt.axvline(pd.Timestamp(mark), color="gray", linestyle="--", alpha=0.5)
    plt.ylabel("Indicative fee (%)")
    plt.title("Markit indicative fee over time")
    plt.legend()
    plt.tight_layout()
    plt.savefig(figure_dir / "fee_timeseries.png", dpi=160)
    plt.close()

    clipped = valid["fee_percent"].clip(lower=0.001, upper=valid["fee_percent"].quantile(0.999))
    plt.figure(figsize=(10, 6))
    plt.hist(np.log10(clipped), bins=80, color="#4c78a8", alpha=0.85)
    plt.xlabel("log10(fee percent)")
    plt.ylabel("stock-month observations")
    plt.title("Distribution of indicative fees")
    plt.tight_layout()
    plt.savefig(figure_dir / "fee_log_histogram.png", dpi=160)
    plt.close()

    valid = valid.copy()
    valid["size_group"] = pd.qcut(
        valid.groupby("month")["fee_last"].transform(lambda x: x.rank(method="first")),
        q=5,
        labels=False,
    )
    # The plot is a diagnostic by month-level rank; the CRSP-linked size-group
    # plot is produced after the monthly panel is built.
    box_data = [group["fee_percent"].dropna().clip(upper=group["fee_percent"].quantile(0.99)) for _, group in valid.groupby("size_group")]
    plt.figure(figsize=(10, 6))
    plt.boxplot(box_data, labels=[f"Group {i}" for i in range(1, len(box_data) + 1)], showfliers=False)
    plt.ylabel("Indicative fee (%)")
    plt.title("Fee distribution diagnostic by within-month rank")
    plt.tight_layout()
    plt.savefig(figure_dir / "fee_rank_group_boxplot.png", dpi=160)
    plt.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    root = Path(__file__).resolve().parents[1]
    raw = root / "data" / "raw"
    parser.add_argument("--input", type=Path, default=raw / "American Equities.csv")
    parser.add_argument("--mid-dir", type=Path, default=root / "data" / "mid" / "markit")
    parser.add_argument("--prod-dir", type=Path, default=root / "data" / "prod")
    parser.add_argument("--figure-dir", type=Path, default=root / "reports" / "figures" / "markit")
    parser.add_argument("--chunk-size", type=int, default=250_000)
    parser.add_argument("--start", default="2002-01-01")
    parser.add_argument("--end", default="2026-12-31")
    parser.add_argument("--main-start", default="2007-01")
    parser.add_argument("--main-end", default="2025-12")
    parser.add_argument("--rebuild", action="store_true")
    parser.add_argument("--aggregate-only", action="store_true", help="reuse existing annual daily Parquet partitions")
    args = parser.parse_args()
    ensure_dirs(args.mid_dir / "daily", args.mid_dir / "monthly", args.prod_dir, args.figure_dir)
    daily_dir = args.mid_dir / "daily"
    monthly_dir = args.mid_dir / "monthly"
    if args.rebuild:
        for path in daily_dir.glob("markit_fee_*.parquet"):
            path.unlink()
        for path in monthly_dir.glob("markit_fee_monthly_*.parquet"):
            path.unlink()
    schema = partition_schema()
    writers: dict[int, pq.ParquetWriter] = {}
    coverage: dict[str, dict[str, Any]] = {}
    quality_counts: dict[str, int] = {}
    start, end = pd.Timestamp(args.start), pd.Timestamp(args.end)
    started = time.time()
    if not args.aggregate_only:
        dtype = {field: "string" for field in ("dxlid", "isin", "sedol", "cusip", "marketarea")}
        for index, chunk in enumerate(
            pd.read_csv(args.input, usecols=ALL_FIELDS, dtype=dtype, chunksize=args.chunk_size, low_memory=False),
            1,
        ):
            chunk = prepare_chunk(chunk)
            if chunk.empty:
                continue
            chunk = chunk[
                chunk["datadate"].between(start, end)
                & chunk["marketarea"].isin(MARKET_AREAS)
            ].copy()
            if chunk.empty:
                continue
            update_coverage(coverage, quality_counts, chunk)
            for year, group in chunk.groupby(chunk["datadate"].dt.year, sort=False):
                year = int(year)
                path = daily_dir / f"markit_fee_{year}.parquet"
                output = group.reindex(columns=schema.names)
                table = pa.Table.from_pandas(output, schema=schema, preserve_index=False, safe=False)
                if year not in writers:
                    writers[year] = pq.ParquetWriter(path, schema=schema, compression="zstd")
                writers[year].write_table(table)
            if index % 20 == 0:
                print(f"Markit chunks={index}; elapsed={time.time() - started:.1f}s", flush=True)
        for writer in writers.values():
            writer.close()

        coverage_rows = [values for _, values in sorted(coverage.items())]
        coverage_frame = pd.DataFrame(coverage_rows)
        if not coverage_frame.empty:
            coverage_frame["rows"] = pd.to_numeric(coverage_frame["rows"])
            for field in QUALITY_FIELDS:
                if f"{field}_nonmissing" in coverage_frame:
                    coverage_frame[f"{field}_coverage"] = coverage_frame[f"{field}_nonmissing"] / coverage_frame["rows"]
        write_csv(coverage_frame, args.prod_dir / "markit_coverage.csv")
        (args.prod_dir / "markit_coverage.json").write_text(
            json.dumps({"market_areas": MARKET_AREAS, "quality_counts": quality_counts}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    else:
        writers = {int(path.stem.rsplit("_", 1)[-1]): None for path in daily_dir.glob("markit_fee_*.parquet")}

    monthly_frames = []
    for year_path in sorted(daily_dir.glob("markit_fee_*.parquet")):
        year = year_path.stem.rsplit("_", 1)[-1]
        output = monthly_dir / f"markit_fee_monthly_{year}.parquet"
        print(f"aggregating {year_path.name}", flush=True)
        summary = aggregate_annual(year_path, output)
        if not summary.empty:
            monthly_frames.append(summary)
    if monthly_frames:
        monthly = pd.concat(monthly_frames, ignore_index=True)
        make_descriptive_outputs(monthly, args.prod_dir, args.figure_dir, args.main_start, args.main_end)
        print(f"stock-month rows={len(monthly):,}", flush=True)
    print(f"Markit finished in {time.time() - started:.1f}s; annual partitions={len(writers)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
