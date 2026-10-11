"""Deterministic signals. Each returns a target exposure in [0, 1] per date.

Contract: the value at date t may only use prices up to and including t.
tests/test_lookahead.py enforces this for every signal registered in SIGNALS.
Warm-up periods are NaN so the study can start every strategy on the same date.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def buy_and_hold(p: pd.Series) -> pd.Series:
    return pd.Series(1.0, index=p.index)


def sma_trend(p: pd.Series, n: int = 200) -> pd.Series:
    """Long when price closes above its n-period simple moving average (Faber-style)."""
    sma = p.rolling(n, min_periods=n).mean()
    return (p > sma).astype(float).where(sma.notna())


def sma_cross(p: pd.Series, fast: int = 50, slow: int = 200) -> pd.Series:
    if fast >= slow:
        raise ValueError("fast must be < slow")
    f = p.rolling(fast, min_periods=fast).mean()
    s = p.rolling(slow, min_periods=slow).mean()
    return (f > s).astype(float).where(s.notna())


def tsmom(p: pd.Series, lookback: int = 252, skip: int = 21) -> pd.Series:
    """Time-series momentum: long if the return from t-lookback to t-skip is positive."""
    past = p.shift(skip) / p.shift(lookback) - 1
    return (past > 0).astype(float).where(past.notna())


def rsi(p: pd.Series, n: int = 2) -> pd.Series:
    d = p.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))


def rsi_meanrev(p: pd.Series, n: int = 2, entry: float = 10, exit: float = 70,
                trend: int = 200) -> pd.Series:
    """Popular retail swing rule: buy short-term oversold dips inside an uptrend."""
    r = rsi(p, n).to_numpy()
    sma = p.rolling(trend, min_periods=trend).mean().to_numpy()
    px = p.to_numpy()
    out = np.full(len(p), np.nan)
    pos = 0.0
    for i in range(len(p)):
        if np.isnan(sma[i]) or np.isnan(r[i]):
            continue
        if pos == 0.0 and r[i] < entry and px[i] > sma[i]:
            pos = 1.0
        elif pos == 1.0 and (r[i] > exit or px[i] < sma[i]):
            pos = 0.0
        out[i] = pos
    return pd.Series(out, index=p.index)


SIGNALS = {
    "buy_and_hold": buy_and_hold,
    "sma_trend": sma_trend,
    "sma_cross": sma_cross,
    "tsmom": tsmom,
    "rsi_meanrev": rsi_meanrev,
}
