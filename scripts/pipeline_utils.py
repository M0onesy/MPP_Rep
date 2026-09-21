#!/usr/bin/env python3
"""Shared helpers for the local research pipeline."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


MISSING = {"", "nan", "nat", "none", "null", "n/a", "."}


def clean_identifier(series: pd.Series) -> pd.Series:
    values = series.astype("string").str.strip().str.upper()
    return values.mask(values.str.lower().isin(MISSING))


def normalize_cusip(series: pd.Series) -> tuple[pd.Series, pd.Series]:
    """Return normalized CUSIP8 and CUSIP9 values."""
    cleaned = series.astype("string").str.upper().str.replace(r"[^0-9A-Z]", "", regex=True)
    cleaned = cleaned.mask(cleaned.str.lower().isin(MISSING))
    cusip8 = cleaned.str[:8].mask(cleaned.str.len() < 8)
    cusip9 = cleaned.str[:9].mask(cleaned.str.len() < 9)
    return cusip8, cusip9


def numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def month_string(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce").dt.to_period("M").astype("string")


def ensure_dirs(*paths: Path) -> None:
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)


def write_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding="utf-8-sig")


def available_solver() -> str:
    try:
        import clarabel  # noqa: F401

        return "CLARABEL_DIRECT"
    except Exception:
        pass
    try:
        import cvxpy as cp

        installed = set(cp.installed_solvers())
        for solver in ("CLARABEL", "OSQP", "ECOS", "SCS"):
            if solver in installed:
                return solver
    except Exception:
        pass
    return "SCIPY"


def finite_float(value: object, default: float = np.nan) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if np.isfinite(result) else default
