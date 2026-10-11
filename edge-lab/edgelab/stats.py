"""Performance statistics with an honest view on luck.

PSR / DSR follow Bailey & López de Prado (2012, 2014):
  PSR: probability that the true Sharpe exceeds a benchmark Sharpe, given
       sample length, skew and fat tails.
  DSR: PSR against the Sharpe you would expect from the *best of N* trials of
       pure noise. That is the right hurdle after a parameter search.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
from scipy import stats as st

EULER_GAMMA = 0.5772156649015329


def max_drawdown(r: pd.Series) -> float:
    eq = (1 + r).cumprod()
    return float((eq / eq.cummax() - 1).min())


def cagr(r: pd.Series, ppy: int) -> float:
    years = len(r) / ppy
    return float((1 + r).prod() ** (1 / years) - 1)


def sharpe(r: pd.Series, rf: pd.Series, ppy: int) -> float:
    ex = (r - rf.reindex(r.index)).dropna()
    sd = ex.std(ddof=1)
    return float(ex.mean() / sd * math.sqrt(ppy)) if sd > 0 else 0.0


def sortino(r: pd.Series, rf: pd.Series, ppy: int) -> float:
    ex = (r - rf.reindex(r.index)).dropna()
    dd = np.sqrt((ex.clip(upper=0) ** 2).mean())
    return float(ex.mean() / dd * math.sqrt(ppy)) if dd > 0 else 0.0


def psr(r: pd.Series, rf: pd.Series, sr_benchmark_period: float = 0.0) -> float:
    """Probabilistic Sharpe Ratio (per-period Sharpe as input)."""
    ex = (r - rf.reindex(r.index)).dropna()
    n = len(ex)
    sr = ex.mean() / ex.std(ddof=1)
    g3 = st.skew(ex)
    g4 = st.kurtosis(ex, fisher=False)
    denom = math.sqrt(max(1 - g3 * sr + (g4 - 1) / 4 * sr**2, 1e-12))
    return float(st.norm.cdf((sr - sr_benchmark_period) * math.sqrt(n - 1) / denom))


def expected_max_sharpe(trial_sharpes_period: np.ndarray) -> float:
    """Expected maximum per-period Sharpe among N independent zero-skill trials."""
    n = len(trial_sharpes_period)
    if n < 2:
        return 0.0
    sd = float(np.std(trial_sharpes_period, ddof=1))
    return sd * ((1 - EULER_GAMMA) * st.norm.ppf(1 - 1 / n)
                 + EULER_GAMMA * st.norm.ppf(1 - 1 / (n * math.e)))


def dsr(r: pd.Series, rf: pd.Series, trial_sharpes_period: np.ndarray) -> float:
    return psr(r, rf, expected_max_sharpe(np.asarray(trial_sharpes_period)))


def period_sharpe(r: pd.Series, rf: pd.Series) -> float:
    ex = (r - rf.reindex(r.index)).dropna()
    return float(ex.mean() / ex.std(ddof=1))


def _block_indices(t: int, block: int, n: int, rng) -> np.ndarray:
    k = math.ceil(t / block)
    starts = rng.integers(0, t, size=(n, k))
    return (starts[:, :, None] + np.arange(block)[None, None, :]).reshape(n, -1)[:, :t] % t


def _sr(x: np.ndarray, axis=0) -> np.ndarray:
    return x.mean(axis=axis) / x.std(axis=axis, ddof=1)


def bootstrap_sharpe_diff(a: pd.Series, b: pd.Series, rf: pd.Series, ppy: int,
                          block: int = 21, n: int = 2000, seed: int = 7) -> dict:
    """Paired circular block bootstrap of Sharpe(a) - Sharpe(b), annualized.

    Same resampled blocks for both series, so their correlation is respected."""
    df = pd.concat([a, b], axis=1).dropna()
    ex = (df.to_numpy() - rf.reindex(df.index).to_numpy()[:, None])
    idx = _block_indices(len(ex), block, n, np.random.default_rng(seed))
    sa = _sr(ex[idx, 0], axis=1)
    sb = _sr(ex[idx, 1], axis=1)
    d = (sa - sb) * math.sqrt(ppy)
    lo, hi = np.percentile(d, [2.5, 97.5])
    obs = float((_sr(ex[:, 0]) - _sr(ex[:, 1])) * math.sqrt(ppy))
    return {"sharpe_diff": obs, "ci95": [float(lo), float(hi)], "p_le_0": float((d <= 0).mean())}


def reality_check(trials: pd.DataFrame, bench: pd.Series, rf: pd.Series, ppy: int,
                  block: int = 21, n: int = 500, seed: int = 11) -> dict:
    """White's (2000) Reality Check on Sharpe differences versus a benchmark.

    H0: no rule in the whole candidate set beats the benchmark's Sharpe.
    The p-value accounts for having picked the best of all candidates."""
    df = pd.concat([trials, bench.rename("__bench__")], axis=1).dropna()
    ex = df.to_numpy() - rf.reindex(df.index).to_numpy()[:, None]
    t = len(ex)
    obs = (_sr(ex[:, :-1]) - _sr(ex[:, -1])) * math.sqrt(ppy)
    v_obs = obs.max() * math.sqrt(t)
    rng = np.random.default_rng(seed)
    v_boot = np.empty(n)
    for i, idx in enumerate(_block_indices(t, block, n, rng)):
        x = ex[idx]
        d = (_sr(x[:, :-1]) - _sr(x[:, -1])) * math.sqrt(ppy)
        v_boot[i] = ((d - obs) * math.sqrt(t)).max()   # recentred under H0
    return {"best_sharpe_diff": float(obs.max()), "n_candidates": int(obs.size),
            "p_value": float((v_boot >= v_obs).mean())}


def summary(res, market) -> dict:
    r, rf, ppy = res.returns, market.rf_period, market.periods_per_year
    years = len(r) / ppy
    return {
        "name": res.name,
        "start": str(r.index[0].date()),
        "end": str(r.index[-1].date()),
        "years": round(years, 1),
        "cagr": cagr(r, ppy),
        "vol": float(r.std(ddof=1) * math.sqrt(ppy)),
        "sharpe": sharpe(r, rf, ppy),
        "sortino": sortino(r, rf, ppy),
        "max_dd": max_drawdown(r),
        "psr_vs_0": psr(r, rf),
        "time_in_market": float(res.weights.mean()),
        "trades_per_year": float((res.turnover > 1e-9).sum() / years),
        "cost_drag_pa": float(res.costs.sum() / years),
    }
