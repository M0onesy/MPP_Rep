#!/usr/bin/env python3
"""Run the monthly M0-M3 borrowing-fee prototype.

The problem is convex.  cvxpy is used when installed; a SciPy SLSQP fallback
keeps the pipeline executable in a minimal Python environment.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy import sparse

from pipeline_utils import available_solver, ensure_dirs, write_csv


SIGNALS = ["momentum_12_2", "reversal_1", "log_dollar_volume_1"]
MODELS = ("M0", "M1", "M2", "M3")


def zscore(values: pd.Series) -> pd.Series:
    values = pd.to_numeric(values, errors="coerce")
    std = values.std(ddof=0)
    return pd.Series(0.0, index=values.index) if not np.isfinite(std) or std == 0 else (values - values.mean()) / std


def prepare_month(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    for field in SIGNALS:
        frame[field + "_z"] = zscore(frame[field])
    frame["signal_score"] = frame[[field + "_z" for field in SIGNALS]].mean(axis=1)
    risk = pd.to_numeric(frame.get("volatility_12"), errors="coerce")
    fallback = pd.to_numeric(frame["monthly_retx"], errors="coerce").std()
    fallback = float(fallback) if np.isfinite(fallback) and fallback > 0 else 0.20
    frame["risk_proxy"] = risk.fillna(fallback).clip(lower=0.05, upper=2.0)
    return frame


def solve_scipy(
    alpha: np.ndarray,
    risk: np.ndarray,
    fee: np.ndarray,
    previous: np.ndarray,
    transaction_cost: float,
    gamma: float,
    borrow_in_objective: bool,
    weight_bound: float,
    gross_limit: float,
    fee_scale: float,
) -> tuple[np.ndarray, str, float]:
    fee_monthly = np.nan_to_num(fee, nan=0.0) * fee_scale / 12.0
    n = len(alpha)

    def negative_objective(weights: np.ndarray) -> float:
        turnover = np.abs(weights - previous).sum()
        borrow = np.maximum(-weights, 0.0) @ fee_monthly if borrow_in_objective else 0.0
        return -(
            alpha @ weights
            - gamma * np.sum((risk * weights) ** 2)
            - transaction_cost * turnover
            - borrow
        )

    constraints = [
        {"type": "eq", "fun": lambda weights: float(weights.sum() - 1.0)},
        {"type": "ineq", "fun": lambda weights: float(gross_limit - np.abs(weights).sum())},
    ]
    x0 = np.full(n, 1.0 / n)
    if np.all(np.isfinite(previous)) and abs(previous.sum() - 1.0) < 1e-6:
        x0 = previous.copy()
    x0 = np.clip(x0, -weight_bound, weight_bound)
    if abs(x0.sum() - 1.0) > 1e-6:
        x0 = np.full(n, 1.0 / n)
    result = minimize(
        negative_objective,
        x0,
        method="SLSQP",
        bounds=[(-weight_bound, weight_bound)] * n,
        constraints=constraints,
        options={"maxiter": 500, "ftol": 1e-9, "disp": False},
    )
    status = "SCIPY_OPTIMAL" if result.success else "SCIPY_" + str(result.message)
    weights = result.x if result.success else x0
    return weights, status, float(-negative_objective(weights))


def solve_cvxpy(
    alpha: np.ndarray,
    risk: np.ndarray,
    fee: np.ndarray,
    previous: np.ndarray,
    transaction_cost: float,
    gamma: float,
    borrow_in_objective: bool,
    weight_bound: float,
    gross_limit: float,
    fee_scale: float,
) -> tuple[np.ndarray, str, float]:
    import cvxpy as cp

    solver = available_solver()
    if solver == "SCIPY":
        raise RuntimeError("cvxpy is not installed")
    n = len(alpha)
    weights = cp.Variable(n)
    fee_monthly = np.nan_to_num(fee, nan=0.0) * fee_scale / 12.0
    objective = alpha @ weights - gamma * cp.sum_squares(cp.multiply(risk, weights))
    objective -= transaction_cost * cp.norm1(weights - previous)
    if borrow_in_objective:
        objective -= fee_monthly @ cp.pos(-weights)
    problem = cp.Problem(
        cp.Maximize(objective),
        [
            cp.sum(weights) == 1.0,
            cp.norm1(weights) <= gross_limit,
            weights <= weight_bound,
            weights >= -weight_bound,
        ],
    )
    kwargs = {"warm_start": True}
    if solver == "CLARABEL":
        kwargs.update({"tol_gap_abs": 1e-8, "tol_feas": 1e-8})
    problem.solve(solver=solver, **kwargs)
    if weights.value is None:
        raise RuntimeError(f"cvxpy status={problem.status}")
    return np.asarray(weights.value).ravel(), str(problem.status), float(problem.value)


def solve_osqp(
    alpha: np.ndarray,
    risk: np.ndarray,
    fee: np.ndarray,
    previous: np.ndarray,
    transaction_cost: float,
    gamma: float,
    borrow_in_objective: bool,
    weight_bound: float,
    gross_limit: float,
    fee_scale: float,
) -> tuple[np.ndarray, str, float]:
    """Solve the same convex objective through OSQP's native QP interface."""
    import osqp

    n = len(alpha)
    eye = sparse.eye(n, format="csc")
    zero = sparse.csc_matrix((n, n))
    row_zero = sparse.csc_matrix((1, n))
    # x = [weights, turnover_abs, short_abs, gross_abs].
    P = sparse.block_diag(
        [
            sparse.diags(2.0 * gamma * np.square(risk), format="csc"),
            zero,
            zero,
            zero,
        ],
        format="csc",
    )
    fee_monthly = np.nan_to_num(fee, nan=0.0) * fee_scale / 12.0
    q = np.concatenate(
        [
            -alpha,
            np.full(n, transaction_cost),
            fee_monthly if borrow_in_objective else np.zeros(n),
            np.zeros(n),
        ]
    )
    rows = []
    lower = []
    upper = []

    def add(block: sparse.spmatrix, lo: np.ndarray | float, hi: np.ndarray | float) -> None:
        rows.append(block)
        lower.extend(np.broadcast_to(lo, block.shape[0]).astype(float))
        upper.extend(np.broadcast_to(hi, block.shape[0]).astype(float))

    # Fully invested.
    add(sparse.hstack([np.ones((1, n)), sparse.csc_matrix((1, 3 * n))]), 1.0, 1.0)
    # Position bounds.
    add(sparse.hstack([eye, zero, zero, zero]), -weight_bound, weight_bound)
    # u >= w - previous and u >= previous - w.
    add(sparse.hstack([-eye, eye, zero, zero]), -previous, np.inf)
    add(sparse.hstack([eye, eye, zero, zero]), previous, np.inf)
    add(sparse.hstack([zero, eye, zero, zero]), 0.0, np.inf)
    # v >= -w and v >= 0.
    add(sparse.hstack([eye, zero, eye, zero]), 0.0, np.inf)
    add(sparse.hstack([zero, zero, eye, zero]), 0.0, np.inf)
    # s >= |w| and sum(s) <= gross_limit.
    add(sparse.hstack([-eye, zero, zero, eye]), 0.0, np.inf)
    add(sparse.hstack([eye, zero, zero, eye]), 0.0, np.inf)
    add(sparse.hstack([zero, zero, zero, eye]), 0.0, np.inf)
    add(sparse.hstack([row_zero, row_zero, row_zero, np.ones((1, n))]), -np.inf, gross_limit)

    A = sparse.vstack(rows, format="csc")
    solver = osqp.OSQP()
    solver.setup(
        P=P,
        q=q,
        A=A,
        l=np.asarray(lower),
        u=np.asarray(upper),
        eps_abs=1e-7,
        eps_rel=1e-7,
        max_iter=20_000,
        polish=True,
        adaptive_rho=True,
        verbose=False,
    )
    initial_u = np.abs(previous - previous)
    initial_v = np.maximum(-previous, 0.0)
    initial_s = np.abs(previous)
    solver.warm_start(x=np.concatenate([previous, initial_u, initial_v, initial_s]))
    result = solver.solve()
    if result.x is None:
        raise RuntimeError(f"OSQP status={result.info.status}")
    weights = np.asarray(result.x[:n]).ravel()
    status = "OSQP_" + str(result.info.status).upper().replace(" ", "_")
    return weights, status, float(-result.info.obj_val)


def solve_clarabel(
    alpha: np.ndarray,
    risk: np.ndarray,
    fee: np.ndarray,
    previous: np.ndarray,
    transaction_cost: float,
    gamma: float,
    borrow_in_objective: bool,
    weight_bound: float,
    gross_limit: float,
    fee_scale: float,
) -> tuple[np.ndarray, str, float]:
    import clarabel

    n = len(alpha)
    eye = sparse.eye(n, format="csc")
    zero = sparse.csc_matrix((n, n))
    row_zero = sparse.csc_matrix((1, n))
    # x = [weights, turnover_abs, short_abs, gross_abs]
    p_matrix = sparse.block_diag(
        [
            sparse.diags(2.0 * gamma * np.square(risk), format="csc"),
            zero,
            zero,
            zero,
        ],
        format="csc",
    )
    fee_monthly = np.nan_to_num(fee, nan=0.0) * fee_scale / 12.0
    q = np.concatenate(
        [
            -alpha,
            np.full(n, transaction_cost),
            fee_monthly if borrow_in_objective else np.zeros(n),
            np.zeros(n),
        ]
    )
    eq_a = sparse.hstack([np.ones((1, n)), sparse.csc_matrix((1, 3 * n))], format="csc")
    eq_b = np.array([1.0])
    ineq_rows = []
    ineq_b = []

    def add_le(block: sparse.spmatrix, rhs: np.ndarray | float) -> None:
        ineq_rows.append(block)
        ineq_b.extend(np.broadcast_to(rhs, block.shape[0]).astype(float))

    add_le(sparse.hstack([eye, zero, zero, zero], format="csc"), weight_bound)
    add_le(sparse.hstack([-eye, zero, zero, zero], format="csc"), weight_bound)
    add_le(sparse.hstack([eye, -eye, zero, zero], format="csc"), previous)
    add_le(sparse.hstack([-eye, -eye, zero, zero], format="csc"), -previous)
    add_le(sparse.hstack([zero, -eye, zero, zero], format="csc"), 0.0)
    add_le(sparse.hstack([-eye, zero, -eye, zero], format="csc"), 0.0)
    add_le(sparse.hstack([zero, zero, -eye, zero], format="csc"), 0.0)
    add_le(sparse.hstack([eye, zero, zero, -eye], format="csc"), 0.0)
    add_le(sparse.hstack([-eye, zero, zero, -eye], format="csc"), 0.0)
    add_le(sparse.hstack([zero, zero, zero, -eye], format="csc"), 0.0)
    add_le(sparse.hstack([row_zero, row_zero, row_zero, np.ones((1, n))], format="csc"), gross_limit)

    ineq_a = sparse.vstack(ineq_rows, format="csc")
    a_matrix = sparse.vstack([eq_a, ineq_a], format="csc")
    b = np.concatenate([eq_b, np.asarray(ineq_b, dtype=float)])
    cones = [clarabel.ZeroConeT(1), clarabel.NonnegativeConeT(len(ineq_b))]
    settings = clarabel.DefaultSettings()
    settings.verbose = False
    settings.max_iter = 500
    settings.tol_gap_abs = 1e-8
    settings.tol_feas = 1e-8
    solver = clarabel.DefaultSolver(p_matrix, q, a_matrix, b, cones, settings)
    result = solver.solve()
    status = "CLARABEL_" + str(result.status).upper()
    weights = np.asarray(result.x[:n], dtype=float)
    objective = alpha @ weights
    objective -= gamma * np.sum((risk * weights) ** 2)
    objective -= transaction_cost * np.abs(weights - previous).sum()
    if borrow_in_objective:
        objective -= np.maximum(-weights, 0.0) @ fee_monthly
    return weights, status, float(objective)


def solve_model(
    model: str,
    alpha: np.ndarray,
    risk: np.ndarray,
    fee: np.ndarray,
    previous: np.ndarray,
    transaction_cost: float,
    fee_scale: float,
    weight_bound: float = 0.02,
    gross_limit: float = 1.5,
) -> tuple[np.ndarray, str, float]:
    # M2 uses exactly the M1 optimization rule; only the return evaluation
    # adds the ex-post borrowing fee.
    tc = transaction_cost if model in {"M1", "M2", "M3"} else 0.0
    borrow = model == "M3"
    try:
        if available_solver() == "CLARABEL_DIRECT":
            return solve_clarabel(alpha, risk, fee, previous, tc, 5.0, borrow, weight_bound, gross_limit, fee_scale)
        return solve_cvxpy(alpha, risk, fee, previous, tc, 5.0, borrow, weight_bound, gross_limit, fee_scale)
    except Exception:
        return solve_scipy(alpha, risk, fee, previous, tc, 5.0, borrow, weight_bound, gross_limit, fee_scale)


def evaluate(
    weights: np.ndarray,
    frame: pd.DataFrame,
    previous: np.ndarray,
    transaction_cost: float,
    fee_scale: float,
    include_lending: bool,
    charge_borrow: bool,
) -> dict[str, float]:
    returns = pd.to_numeric(frame["monthly_retx"], errors="coerce").fillna(0.0).to_numpy(float)
    realized_fee = pd.to_numeric(frame["fee_realized"], errors="coerce").fillna(0.0).to_numpy(float)
    lending_rate = pd.to_numeric(frame["long_lending_rate"], errors="coerce").fillna(0.0).to_numpy(float)
    fee_monthly = realized_fee * fee_scale / 12.0
    lending_monthly = lending_rate * fee_scale / 12.0
    turnover = float(np.abs(weights - previous).sum())
    transaction = float(transaction_cost * turnover)
    fee_exposure = float(np.maximum(-weights, 0.0) @ fee_monthly)
    short_fee = fee_exposure if charge_borrow else 0.0
    long_revenue = float(np.maximum(weights, 0.0) @ lending_monthly) if include_lending and charge_borrow else 0.0
    gross = float(weights @ returns)
    net = gross - transaction - short_fee + long_revenue
    return {
        "turnover": turnover,
        "transaction_cost": transaction,
        "short_borrow_cost": short_fee,
        "long_lending_revenue": long_revenue,
        "gross_return": gross,
        "net_return": net,
        "short_weight": float(np.maximum(-weights, 0.0).sum()),
        "gross_exposure": float(np.abs(weights).sum()),
        "fee_exposure": fee_exposure,
    }


def run_model(
    panel: pd.DataFrame,
    model: str,
    start: str,
    end: str,
    n_per_group: int,
    transaction_cost: float,
    fee_scale: float,
    include_lending: bool,
    common_fee_only: bool,
    fee_fill: str = "none",
    keep_weights: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    months = sorted(
        month
        for month in panel["month"].dropna().unique()
        if start[:7] <= str(month) <= end[:7]
    )
    previous_weights: dict[int, float] = {}
    metric_rows: list[dict] = []
    weight_rows: list[dict] = []
    for month in months:
        frame = panel[panel["month"].eq(month)].copy()
        frame = frame[
            frame["in_universe"].fillna(False)
            & frame["universe_rank"].le(n_per_group)
        ].copy()
        if common_fee_only:
            frame = frame[
                frame["markit_match_status"].astype("string").str.contains("fee_4of21", na=False)
                & frame["fee_asof"].notna()
                & frame["fee_realized"].notna()
            ].copy()
        elif fee_fill == "monthly_median":
            for field in ("fee_asof", "fee_realized"):
                median = pd.to_numeric(frame[field], errors="coerce").median()
                if np.isfinite(median):
                    frame[field] = pd.to_numeric(frame[field], errors="coerce").fillna(median)
            frame["long_lending_rate"] = pd.to_numeric(frame["long_lending_rate"], errors="coerce").fillna(0.0)
        frame = frame.dropna(subset=SIGNALS + ["monthly_retx", "lagged_price", "lagged_market_cap"])
        if frame.empty:
            metric_rows.append({"model": model, "month": str(month), "status": "NO_SAMPLE", "n_stocks": 0})
            continue
        frame = prepare_month(frame)
        permnos = frame["permno"].astype(int).to_numpy()
        previous = np.array([previous_weights.get(int(permno), 0.0) for permno in permnos], dtype=float)
        if previous.sum() <= 1e-12:
            previous[:] = 1.0 / len(previous)
        elif abs(previous.sum() - 1.0) > 1e-6:
            previous = previous / previous.sum()
        weights, status, objective = solve_model(
            model,
            frame["signal_score"].to_numpy(float),
            frame["risk_proxy"].to_numpy(float),
            frame["fee_asof"].to_numpy(float),
            previous,
            transaction_cost,
            fee_scale,
        )
        evaluation = evaluate(
            weights,
            frame,
            previous,
            transaction_cost if model in {"M1", "M2", "M3"} else 0.0,
            fee_scale,
            include_lending,
            charge_borrow=model in {"M2", "M3"},
        )
        metric_rows.append(
            {
                "model": model,
                "month": str(month),
                "status": status,
                "n_stocks": int(len(frame)),
                "objective_value": objective,
                **evaluation,
            }
        )
        if keep_weights:
            for permno, weight, score, fee_asof, fee_realized in zip(
                permnos,
                weights,
                frame["signal_score"],
                frame["fee_asof"],
                frame["fee_realized"],
            ):
                weight_rows.append(
                    {
                        "model": model,
                        "month": str(month),
                        "permno": int(permno),
                        "weight": float(weight),
                        "signal_score": float(score),
                        "fee_asof": float(fee_asof) if pd.notna(fee_asof) else np.nan,
                        "fee_realized": float(fee_realized) if pd.notna(fee_realized) else np.nan,
                        "solver_status": status,
                    }
                )
        previous_weights = {int(permno): float(weight) for permno, weight in zip(permnos, weights)}
    return pd.DataFrame(metric_rows), pd.DataFrame(weight_rows)


def summarize_metrics(metrics: pd.DataFrame) -> pd.DataFrame:
    valid = metrics[metrics["status"].astype("string").str.contains("SOLVED|OPTIMAL|SCIPY", regex=True, na=False)].copy()
    if valid.empty:
        return pd.DataFrame()
    return (
        valid.groupby("model")
        .agg(
            months=("month", "nunique"),
            solved_months=("status", lambda x: int(x.astype("string").str.contains("SOLVED|OPTIMAL|SCIPY", regex=True).sum())),
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


def run_sensitivity(
    panel: pd.DataFrame,
    baseline_metrics: pd.DataFrame,
    start: str,
    end: str,
    default_n_per_group: int,
    default_tc: float,
    default_fee_scale: float,
    default_include_lending: bool,
    default_common_fee_only: bool,
    models: list[str],
) -> pd.DataFrame:
    """Run one-way sensitivity cases and return model-level summaries."""
    requested = []
    for value in (0.001, 0.0025, 0.005, 0.01):
        requested.append(("transaction_cost_bps", int(round(value * 10_000)), value, default_fee_scale, default_n_per_group, default_include_lending, default_common_fee_only, "none"))
    for value in (0.5, 1.0, 1.5):
        requested.append(("fee_scale", value, default_tc, value, default_n_per_group, default_include_lending, default_common_fee_only, "none"))
    for value in (100, 200, 300):
        requested.append(("target_stocks", value * 5, default_tc, default_fee_scale, value, default_include_lending, default_common_fee_only, "none"))
    requested.extend(
        [
            ("sample", "common_fee_4of21", default_tc, default_fee_scale, default_n_per_group, default_include_lending, True, "none"),
            ("sample", "all_crsp_monthly_median_fill", default_tc, default_fee_scale, default_n_per_group, default_include_lending, False, "monthly_median"),
            ("lending_revenue", "included", default_tc, default_fee_scale, default_n_per_group, True, default_common_fee_only, "none"),
            ("lending_revenue", "excluded", default_tc, default_fee_scale, default_n_per_group, False, default_common_fee_only, "none"),
        ]
    )

    baseline_key = (
        default_tc,
        default_fee_scale,
        default_n_per_group,
        default_include_lending,
        default_common_fee_only,
        "none",
    )
    baseline_subset = baseline_metrics[baseline_metrics["model"].isin(models)].copy()
    cache: dict[tuple[float, float, int, bool, bool, str], pd.DataFrame] = {baseline_key: baseline_subset}
    rows = []
    for parameter, value, tc, fee_scale, n_per_group, include_lending, common_fee_only, fee_fill in requested:
        key = (tc, fee_scale, n_per_group, include_lending, common_fee_only, fee_fill)
        if key not in cache:
            metric_frames = []
            for model in models:
                print(f"sensitivity {parameter}={value}: running {model}", flush=True)
                metrics, _ = run_model(
                    panel,
                    model,
                    start,
                    end,
                    n_per_group,
                    tc,
                    fee_scale,
                    include_lending=include_lending,
                    common_fee_only=common_fee_only,
                    fee_fill=fee_fill,
                    keep_weights=False,
                )
                metric_frames.append(metrics)
            cache[key] = pd.concat(metric_frames, ignore_index=True) if metric_frames else pd.DataFrame()
        summary = summarize_metrics(cache[key])
        for row in summary.to_dict("records"):
            row.update(
                {
                    "parameter": parameter,
                    "value": value,
                    "transaction_cost": tc,
                    "fee_scale": fee_scale,
                    "stocks_per_size_group": n_per_group,
                    "target_stocks": n_per_group * 5,
                    "sample": "common_fee_4of21" if common_fee_only else "all_crsp_monthly_median_fill",
                    "fee_fill": fee_fill,
                    "include_lending_revenue": include_lending,
                    "status": "actual",
                }
            )
            rows.append(row)
    return pd.DataFrame(rows)


def save_plot(metrics: pd.DataFrame, figure_dir: Path) -> None:
    if metrics.empty:
        return
    ensure_dirs(figure_dir)
    data = metrics.copy()
    data["month"] = pd.to_datetime(data["month"])
    plt.figure(figsize=(12, 6))
    for model, group in data.groupby("model"):
        group = group.sort_values("month").copy()
        group["cum_net"] = (1.0 + group["net_return"].fillna(0.0)).cumprod() - 1.0
        plt.plot(group["month"], group["cum_net"], label=model)
    plt.axhline(0.0, color="gray", linewidth=0.8)
    plt.ylabel("Cumulative net return")
    plt.title("M0-M3 prototype cumulative net returns")
    plt.legend()
    plt.tight_layout()
    plt.savefig(figure_dir / "m0_m3_cumulative_net_returns.png", dpi=160)
    plt.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    root = Path(__file__).resolve().parents[1]
    parser.add_argument("--panel", type=Path, default=root / "data" / "prod" / "crsp_monthly_panel.parquet")
    parser.add_argument("--prod-dir", type=Path, default=root / "data" / "prod")
    parser.add_argument("--figure-dir", type=Path, default=root / "reports" / "figures" / "prototype")
    parser.add_argument("--start", default="2007-01")
    parser.add_argument("--end", default="2025-12")
    parser.add_argument("--tc", type=float, default=0.005)
    parser.add_argument("--fee-scale", type=float, default=1.0)
    parser.add_argument("--no-lending", action="store_true")
    parser.add_argument("--all-crsp", action="store_true")
    parser.add_argument("--models", nargs="+", choices=MODELS, default=list(MODELS))
    parser.add_argument("--sensitivity-models", nargs="+", choices=MODELS, default=list(MODELS))
    parser.add_argument("--n-per-group", type=int, default=200)
    parser.add_argument("--skip-sensitivity", action="store_true")
    args = parser.parse_args()
    ensure_dirs(args.prod_dir, args.figure_dir)
    panel = pd.read_parquet(args.panel)
    panel["month"] = panel["month"].astype("string")
    started = time.time()
    metric_frames = []
    weight_frames = []
    for model in args.models:
        print(f"running {model}", flush=True)
        metrics, weights = run_model(
            panel,
            model,
            args.start,
            args.end,
            args.n_per_group,
            args.tc,
            args.fee_scale,
            include_lending=not args.no_lending,
            common_fee_only=not args.all_crsp,
            fee_fill="monthly_median" if args.all_crsp else "none",
        )
        metric_frames.append(metrics)
        weight_frames.append(weights)
    metrics = pd.concat(metric_frames, ignore_index=True) if metric_frames else pd.DataFrame()
    weights = pd.concat(weight_frames, ignore_index=True) if weight_frames else pd.DataFrame()
    metrics.to_csv(args.prod_dir / "prototype_monthly_metrics.csv", index=False, encoding="utf-8-sig")
    weights.to_parquet(args.prod_dir / "prototype_weights.parquet", index=False, compression="zstd")
    summary = summarize_metrics(metrics)
    write_csv(summary, args.prod_dir / "prototype_summary.csv")
    if args.skip_sensitivity:
        sensitivity = pd.DataFrame([{"status": "skipped"}])
    else:
        sensitivity = run_sensitivity(
            panel,
            metrics,
            args.start,
            args.end,
            args.n_per_group,
            args.tc,
            args.fee_scale,
            default_include_lending=not args.no_lending,
            default_common_fee_only=not args.all_crsp,
            models=args.sensitivity_models,
        )
    write_csv(sensitivity, args.prod_dir / "prototype_sensitivity.csv")
    save_plot(metrics, args.figure_dir)
    metadata = {
        "solver": available_solver(),
        "models": args.models,
        "start": args.start,
        "end": args.end,
        "transaction_cost": args.tc,
        "fee_scale": args.fee_scale,
        "include_lending": not args.no_lending,
        "common_fee_only": not args.all_crsp,
        "n_per_group": args.n_per_group,
        "sensitivity_models": [] if args.skip_sensitivity else args.sensitivity_models,
        "sensitivity_status": "skipped" if args.skip_sensitivity else "actual_one_way",
        "elapsed_seconds": time.time() - started,
        "prototype_status": "Python prototype; not a full JKMP replication",
        "constraints": {
            "sum_weights": 1.0,
            "single_weight_bound": 0.02,
            "gross_exposure_limit": 1.5,
        },
    }
    (args.prod_dir / "prototype_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"prototype finished in {time.time() - started:.1f}s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
