#!/usr/bin/env python3
"""Build ordinary-common-stock CRSP panels and join Markit stock-month fees."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from pipeline_utils import ensure_dirs, normalize_cusip, numeric, write_csv


DAILY_FIELDS = [
    "PERMNO",
    "DlyCalDt",
    "DlyPrc",
    "DlyCap",
    "DlyRet",
    "DlyRetx",
    "DlyVol",
    "CUSIP",
    "CUSIP9",
    "HdrCUSIP9",
    "PrimaryExch",
    "SecurityType",
    "SecuritySubType",
    "ShareType",
    "SecurityNm",
]
DAILY_SCHEMA = pa.schema(
    [
        ("permno", pa.int64()),
        ("date", pa.timestamp("ns")),
        ("price", pa.float64()),
        ("market_cap", pa.float64()),
        ("ret", pa.float64()),
        ("retx", pa.float64()),
        ("volume", pa.float64()),
        ("cusip8", pa.string()),
        ("cusip9", pa.string()),
        ("primary_exch", pa.string()),
        ("security_name", pa.string()),
    ]
)


def read_header_map(path: Path) -> pd.DataFrame:
    fields = [
        "PERMNO",
        "SecInfoStartDt",
        "SecInfoEndDt",
        "SecurityBegDt",
        "SecurityEndDt",
        "CUSIP",
        "CUSIP9",
        "HdrCUSIP9",
        "SecurityType",
        "SecuritySubType",
        "ShareType",
        "SecurityNm",
    ]
    frame = pd.read_csv(path, usecols=fields, dtype="string", low_memory=False)
    for field in ("SecInfoStartDt", "SecInfoEndDt", "SecurityBegDt", "SecurityEndDt"):
        frame[field] = pd.to_datetime(frame[field], errors="coerce")
    raw_cusip = frame["CUSIP9"].fillna(frame["CUSIP"]).fillna(frame["HdrCUSIP9"])
    frame["cusip8"], frame["cusip9"] = normalize_cusip(raw_cusip)
    frame["permno"] = pd.to_numeric(frame["PERMNO"], errors="coerce")
    frame = frame[
        frame["SecurityType"].eq("EQTY")
        & frame["SecuritySubType"].eq("COM")
        & frame["ShareType"].eq("NS")
    ].dropna(subset=["permno", "cusip8"])
    frame["permno"] = frame["permno"].astype("int64")
    frame["valid_from"] = frame[["SecInfoStartDt", "SecurityBegDt"]].min(axis=1)
    frame["valid_to"] = frame[["SecInfoEndDt", "SecurityEndDt"]].max(axis=1)
    frame["valid_from"] = frame["valid_from"].fillna(pd.Timestamp("1900-01-01"))
    frame["valid_to"] = frame["valid_to"].fillna(pd.Timestamp("2100-01-01"))
    return frame[["permno", "cusip8", "cusip9", "valid_from", "valid_to"]].drop_duplicates()


def prepare_daily(chunk: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    chunk["date"] = pd.to_datetime(chunk["DlyCalDt"], errors="coerce")
    chunk = chunk[chunk["date"].between(start, end)].copy()
    chunk = chunk[
        chunk["SecurityType"].eq("EQTY")
        & chunk["SecuritySubType"].eq("COM")
        & chunk["ShareType"].eq("NS")
    ].copy()
    if chunk.empty:
        return pd.DataFrame(columns=[field.name for field in DAILY_SCHEMA])
    raw_cusip = chunk["CUSIP9"].fillna(chunk["CUSIP"]).fillna(chunk["HdrCUSIP9"])
    cusip8, cusip9 = normalize_cusip(raw_cusip)
    dly_cap = numeric(chunk["DlyCap"])
    # CIZ DlyCap is reported in thousands of dollars in this export; the
    # output is explicitly named market_cap in dollars.
    return pd.DataFrame(
        {
            "permno": pd.to_numeric(chunk["PERMNO"], errors="coerce"),
            "date": chunk["date"],
            "price": numeric(chunk["DlyPrc"]).abs(),
            "market_cap": dly_cap.abs() * 1_000.0,
            "ret": numeric(chunk["DlyRet"]),
            "retx": numeric(chunk["DlyRetx"]),
            "volume": numeric(chunk["DlyVol"]).abs(),
            "cusip8": cusip8,
            "cusip9": cusip9,
            "primary_exch": chunk["PrimaryExch"].astype("string"),
            "security_name": chunk["SecurityNm"].astype("string"),
        }
    ).dropna(subset=["permno", "date"])


def stream_daily(paths: Iterable[Path], start: pd.Timestamp, end: pd.Timestamp, chunk_size: int):
    dtype = {
        "PERMNO": "Int64",
        "CUSIP": "string",
        "CUSIP9": "string",
        "HdrCUSIP9": "string",
        "PrimaryExch": "string",
        "SecurityType": "string",
        "SecuritySubType": "string",
        "ShareType": "string",
        "SecurityNm": "string",
    }
    for source in paths:
        print(f"reading {source}", flush=True)
        for chunk in pd.read_csv(
            source,
            usecols=DAILY_FIELDS,
            dtype=dtype,
            chunksize=chunk_size,
            low_memory=False,
        ):
            prepared = prepare_daily(chunk, start, end)
            if not prepared.empty:
                yield prepared


def write_daily_partitions(
    paths: list[Path],
    out_dir: Path,
    start: pd.Timestamp,
    end: pd.Timestamp,
    chunk_size: int,
) -> tuple[dict[int, Path], int]:
    daily_dir = out_dir / "daily"
    ensure_dirs(daily_dir)
    writers: dict[int, pq.ParquetWriter] = {}
    counts = 0
    for index, frame in enumerate(stream_daily(paths, start, end, chunk_size), 1):
        counts += len(frame)
        frame["year"] = frame["date"].dt.year
        for year, group in frame.groupby("year", sort=False):
            year = int(year)
            output = group.drop(columns=["year"]).reindex(columns=DAILY_SCHEMA.names)
            table = pa.Table.from_pandas(output, schema=DAILY_SCHEMA, preserve_index=False, safe=False)
            path = daily_dir / f"crsp_common_daily_{year}.parquet"
            if year not in writers:
                writers[year] = pq.ParquetWriter(path, schema=DAILY_SCHEMA, compression="zstd")
            writers[year].write_table(table)
        if index % 20 == 0:
            print(f"CRSP chunks={index}; ordinary rows written={counts:,}", flush=True)
    for writer in writers.values():
        writer.close()
    paths_by_year = {year: out_dir / "daily" / f"crsp_common_daily_{year}.parquet" for year in writers}
    return paths_by_year, counts


def compound(values: pd.Series) -> float:
    values = pd.to_numeric(values, errors="coerce").dropna()
    return float((1.0 + values).prod() - 1.0) if len(values) else np.nan


def aggregate_daily_file(path: Path) -> pd.DataFrame:
    frame = pd.read_parquet(path)
    if frame.empty:
        return pd.DataFrame()
    frame["date"] = pd.to_datetime(frame["date"])
    frame = frame.sort_values(["permno", "date"]).drop_duplicates(["permno", "date"], keep="last")
    frame["month"] = frame["date"].dt.to_period("M").astype("string")
    frame["dollar_volume"] = frame["price"] * frame["volume"]
    result = (
        frame.groupby(["permno", "month"], sort=False)
        .agg(
            last_date=("date", "max"),
            price_end=("price", "last"),
            market_cap_end=("market_cap", "last"),
            monthly_ret=("ret", compound),
            monthly_retx=("retx", compound),
            avg_volume=("volume", "mean"),
            avg_dollar_volume=("dollar_volume", "mean"),
            trading_days=("date", "nunique"),
            cusip8=("cusip8", "last"),
            cusip9=("cusip9", "last"),
            primary_exch=("primary_exch", "last"),
            security_name=("security_name", "last"),
        )
        .reset_index()
    )
    return result


def add_lagged_features(monthly: pd.DataFrame) -> pd.DataFrame:
    monthly = monthly.sort_values(["permno", "month"]).copy()
    grouped = monthly.groupby("permno", sort=False)
    monthly["lagged_price"] = grouped["price_end"].shift(1)
    monthly["lagged_market_cap"] = grouped["market_cap_end"].shift(1)
    monthly["ret_lag1"] = grouped["monthly_ret"].shift(1)
    monthly["momentum_12_2"] = grouped["monthly_ret"].transform(
        lambda values: values.shift(2).rolling(11, min_periods=9).apply(compound, raw=False)
    )
    monthly["reversal_1"] = -monthly["ret_lag1"]
    monthly["log_dollar_volume_1"] = np.log1p(
        grouped["avg_dollar_volume"].shift(1).clip(lower=0.0)
    )
    monthly["volatility_12"] = grouped["monthly_retx"].transform(
        lambda values: values.shift(1).rolling(12, min_periods=6).std()
    )
    monthly["month"] = monthly["month"].astype("string")
    return monthly


def attach_markit(monthly: pd.DataFrame, markit_path: Path) -> pd.DataFrame:
    if not markit_path.exists():
        result = monthly.copy()
        result["markit_match_status"] = "markit_monthly_missing"
        for field in ("fee_asof", "fee_realized", "fee_observation_count", "utilisation", "utilisation_normalized", "long_lending_rate"):
            result[field] = np.nan
        return result
    markit = pd.read_parquet(markit_path)
    if markit.empty:
        return attach_markit(monthly, Path("__missing__"))
    markit["month"] = markit["month"].astype("string")
    markit["cusip8"] = markit["cusip8"].astype("string")
    markit["cusip9"] = markit["cusip9"].astype("string")
    markit["last_date"] = pd.to_datetime(markit["last_date"], errors="coerce")
    exact = (
        markit.dropna(subset=["cusip9"])
        .sort_values(["cusip9", "month", "last_date"])
        .drop_duplicates(["cusip9", "month"], keep="last")
    )
    exact = exact[
        [
            "cusip9",
            "month",
            "fee_last",
            "fee_obs_count",
            "utilisation_last",
            "qualifies_4of21_month_prefilter",
        ]
    ].rename(
        columns={
            "fee_last": "fee_exact",
            "fee_obs_count": "fee_obs_exact",
            "utilisation_last": "util_exact",
            "qualifies_4of21_month_prefilter": "qualifies_exact",
        }
    )
    fallback = (
        markit.groupby(["cusip8", "month"], dropna=False, sort=False)
        .agg(
            cusip9_count=("cusip9", "nunique"),
            fee_fallback=("fee_last", "last"),
            fee_obs_fallback=("fee_obs_count", "sum"),
            util_fallback=("utilisation_last", "last"),
            qualifies_fallback=("qualifies_4of21_month_prefilter", "any"),
        )
        .reset_index()
    )
    fallback.loc[fallback["cusip9_count"] > 1, ["fee_fallback", "fee_obs_fallback", "util_fallback"]] = np.nan
    result = monthly.merge(exact, on=["cusip9", "month"], how="left")
    result = result.merge(fallback, on=["cusip8", "month"], how="left")
    result["fee_realized"] = result["fee_exact"].combine_first(result["fee_fallback"])
    result["fee_observation_count"] = result["fee_obs_exact"].combine_first(result["fee_obs_fallback"])
    result["utilisation"] = result["util_exact"].combine_first(result["util_fallback"])
    result["qualifies_4of21"] = result["qualifies_exact"].combine_first(result["qualifies_fallback"]).fillna(False)
    result["utilisation_normalized"] = result["utilisation"].where(result["utilisation"].between(0, 1))
    result["long_lending_rate"] = (
        result["fee_realized"] * result["utilisation_normalized"] * 0.7
    )
    result["markit_match_status"] = np.select(
        [
            result["fee_exact"].notna() & result["qualifies_exact"].fillna(False),
            result["fee_exact"].notna(),
            result["fee_fallback"].notna() & result["qualifies_fallback"].fillna(False),
            result["fee_fallback"].notna(),
            result["cusip9"].notna() | result["cusip8"].notna(),
        ],
        [
            "matched_cusip9_fee_4of21_prefilter",
            "matched_cusip9_fee_below_4of21_prefilter",
            "matched_unique_cusip8_fee_4of21_prefilter",
            "matched_unique_cusip8_fee_below_4of21_prefilter",
            "cusip_no_fee",
        ],
        default="no_cusip",
    )
    # Use the latest fee known before the holding month as the ex-ante input.
    result = result.sort_values(["permno", "month"])
    result["fee_asof"] = result.groupby("permno", sort=False)["fee_realized"].shift(1)
    result["fee_asof_available"] = result["fee_asof"].notna()
    return result


def assign_universe(monthly: pd.DataFrame, n_per_group: int) -> pd.DataFrame:
    monthly = monthly.copy()
    eligible = (
        monthly["lagged_price"].ge(1.0)
        & monthly["lagged_market_cap"].ge(50_000_000)
        & monthly["momentum_12_2"].notna()
        & monthly["reversal_1"].notna()
        & monthly["log_dollar_volume_1"].notna()
    )
    monthly["eligible_crsp"] = eligible
    monthly["market_cap_group"] = pd.Series(pd.NA, index=monthly.index, dtype="Int64")
    monthly["universe_rank"] = np.nan
    monthly["in_universe"] = False
    selected_parts = []
    for month, group in monthly[eligible].groupby("month", sort=False):
        group = group.copy()
        ranks = group["lagged_market_cap"].rank(method="first", ascending=True)
        group["market_cap_group"] = np.floor((ranks - 1) * 5 / len(group)).astype(int).clip(0, 4) + 1
        group["universe_rank"] = group.groupby("market_cap_group")["lagged_market_cap"].rank(
            method="first", ascending=False
        )
        group["in_universe"] = group["universe_rank"].le(n_per_group)
        selected_parts.append(group[["permno", "month", "market_cap_group", "universe_rank", "in_universe"]])
    if selected_parts:
        selected = pd.concat(selected_parts, ignore_index=True)
        monthly = monthly.drop(columns=["market_cap_group", "universe_rank", "in_universe"])
        monthly = monthly.merge(selected, on=["permno", "month"], how="left")
    monthly["market_cap_group"] = pd.to_numeric(monthly["market_cap_group"], errors="coerce").astype("Int64")
    monthly["universe_rank"] = pd.to_numeric(monthly["universe_rank"], errors="coerce")
    monthly["in_universe"] = monthly["in_universe"].fillna(False).astype(bool)
    return monthly


def make_match_report(monthly: pd.DataFrame, prod_dir: Path) -> None:
    frame = monthly.copy()
    frame["year"] = frame["month"].str[:4]
    report = (
        frame.groupby(["year", "markit_match_status"], dropna=False)
        .agg(rows=("permno", "size"), permnos=("permno", "nunique"))
        .reset_index()
    )
    write_csv(report, prod_dir / "crsp_markit_matching.csv")
    summary = (
        frame.groupby("year")
        .agg(
            stock_months=("permno", "size"),
            unique_permnos=("permno", "nunique"),
            fee_observed=("fee_realized", lambda values: int(values.notna().sum())),
            fee_asof_observed=("fee_asof", lambda values: int(values.notna().sum())),
            four_of_21=("qualifies_4of21", "sum"),
            crsp_eligible=("eligible_crsp", "sum"),
            selected_universe=("in_universe", "sum"),
        )
        .reset_index()
    )
    for field in ("fee_observed", "fee_asof_observed", "four_of_21", "crsp_eligible", "selected_universe"):
        summary[field + "_share"] = summary[field] / summary["stock_months"]
    write_csv(summary, prod_dir / "crsp_markit_matching_summary.csv")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    root = Path(__file__).resolve().parents[1]
    raw = root / "data" / "raw"
    parser.add_argument("--daily", nargs="+", type=Path, default=[raw / "日频" / "crsp2599(daily).csv", raw / "日频" / "crsp0025(daily).csv"])
    parser.add_argument("--header", type=Path, default=raw / "属性" / "CRSP_Stock Header Information(new).csv")
    parser.add_argument("--markit", type=Path, default=root / "data" / "prod" / "markit_stock_monthly.parquet")
    parser.add_argument("--mid-dir", type=Path, default=root / "data" / "mid" / "crsp")
    parser.add_argument("--prod-dir", type=Path, default=root / "data" / "prod")
    parser.add_argument("--start", default="2005-01-01")
    parser.add_argument("--end", default="2025-12-31")
    parser.add_argument("--chunk-size", type=int, default=500_000)
    parser.add_argument("--n-per-group", type=int, default=200)
    parser.add_argument("--rebuild", action="store_true")
    parser.add_argument("--monthly-only", action="store_true", help="reuse existing mid/crsp/monthly parquet files")
    args = parser.parse_args()
    ensure_dirs(args.mid_dir / "daily", args.mid_dir / "monthly", args.prod_dir)
    if args.rebuild:
        for path in (args.mid_dir / "daily").glob("crsp_common_daily_*.parquet"):
            path.unlink()
    start, end = pd.Timestamp(args.start), pd.Timestamp(args.end)
    started = time.time()
    header_map = read_header_map(args.header)
    written_rows = 0
    duplicate_removed = 0
    monthly_frames = []
    if args.monthly_only:
        for path in sorted((args.mid_dir / "monthly").glob("crsp_monthly_*.parquet")):
            monthly_frames.append(pd.read_parquet(path))
    else:
        daily_paths, written_rows = write_daily_partitions(args.daily, args.mid_dir, start, end, args.chunk_size)
        for year, daily_path in sorted(daily_paths.items()):
            frame = pd.read_parquet(daily_path)
            before = len(frame)
            frame = frame.sort_values(["permno", "date"]).drop_duplicates(["permno", "date"], keep="last")
            duplicate_removed += before - len(frame)
            frame.to_parquet(daily_path, index=False, compression="zstd")
            monthly_frame = aggregate_daily_file(daily_path)
            if not monthly_frame.empty:
                monthly_frame.to_parquet(
                    args.mid_dir / "monthly" / f"crsp_monthly_{year}.parquet",
                    index=False,
                    compression="zstd",
                )
                monthly_frames.append(monthly_frame)
    if not monthly_frames:
        raise SystemExit("no monthly CRSP rows after filtering")
    monthly = add_lagged_features(pd.concat(monthly_frames, ignore_index=True))
    monthly = attach_markit(monthly, args.markit)
    monthly = assign_universe(monthly, args.n_per_group)
    monthly = monthly[
        (monthly["month"] >= args.start[:7])
        & (monthly["month"] <= args.end[:7])
    ].copy()
    output = args.prod_dir / "crsp_monthly_panel.parquet"
    monthly.to_parquet(output, index=False, compression="zstd")
    make_match_report(monthly, args.prod_dir)
    metadata = {
        "daily_rows_written_before_deduplication": int(written_rows) if not args.monthly_only else None,
        "daily_duplicate_keys_removed": int(duplicate_removed) if not args.monthly_only else None,
        "daily_rows_after_deduplication": int(written_rows - duplicate_removed) if not args.monthly_only else None,
        "monthly_rows": int(len(monthly)),
        "unique_permnos": int(monthly["permno"].nunique()),
        "header_common_stock_rows": int(len(header_map)),
        "ordinary_common_stock_mapping": "SecurityType=EQTY & SecuritySubType=COM & ShareType=NS",
        "DlyCap_conversion": "market_cap = abs(DlyCap) * 1000; output dollars",
        "start": args.start,
        "end": args.end,
        "monthly_only": bool(args.monthly_only),
        "elapsed_seconds": time.time() - started,
    }
    (args.prod_dir / "crsp_panel_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(
        f"CRSP finished: daily={written_rows - duplicate_removed:,}, "
        f"monthly={len(monthly):,}, elapsed={time.time() - started:.1f}s",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
