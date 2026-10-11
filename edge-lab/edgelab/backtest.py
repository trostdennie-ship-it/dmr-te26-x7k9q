"""Point-in-time backtester for long/flat strategies with costs and cash yield.

Timing convention (the part most hobby backtests get wrong):
  signal s_t is computed after the close of period t.
  delay=0: traded at that same close (only realistic for monthly data / MOC orders)
  delay=1: traded at the next close (default for daily data)
  The return of period t+1+delay is earned with the new exposure.
  => weight_t = s_{t-1-delay}
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .data import Market
from .risk import RiskRules


@dataclass
class Result:
    name: str
    returns: pd.Series       # net period returns
    weights: pd.Series       # exposure held during each period
    turnover: pd.Series      # |Δweight| per period
    costs: pd.Series         # cost drag per period

    @property
    def equity(self) -> pd.Series:
        return (1 + self.returns).cumprod()


def target_exposure(market: Market, signal: pd.Series, rules: RiskRules) -> pd.Series:
    """Signal -> exposure decided at the close of t (before execution delay)."""
    target = signal.clip(lower=0.0)
    if rules.vol_target is not None:
        realized = market.returns.rolling(rules.vol_lookback, min_periods=rules.vol_lookback).std()
        realized = realized * np.sqrt(market.periods_per_year)
        target = target * (rules.vol_target / realized).clip(upper=rules.max_weight)
    target = target.clip(upper=rules.max_weight)
    if rules.rebalance_band > 0:
        target = _apply_band(target, rules.rebalance_band)
    return target


def _apply_band(target: pd.Series, band: float) -> pd.Series:
    """Hold the current exposure until the target moves more than `band` away.
    Moves to or from zero (signal flips) always trade."""
    v = target.to_numpy()
    out = np.full(len(v), np.nan)
    cur = np.nan
    for i, x in enumerate(v):
        if np.isnan(x):
            continue
        if np.isnan(cur) or x == 0.0 or cur == 0.0 or abs(x - cur) > band:
            cur = x
        out[i] = cur
    return pd.Series(out, index=target.index)


def run(market: Market, signal: pd.Series, rules: RiskRules | None = None,
        delay: int = 1, name: str = "strategy") -> Result:
    rules = rules or RiskRules()
    target = target_exposure(market, signal, rules)
    w = target.shift(1 + delay)
    ret = market.returns
    rf = market.rf_period

    valid = w.notna() & ret.notna()
    w, ret, rf = w[valid], ret[valid], rf[valid]
    cost_rate = rules.cost_bps_per_side / 1e4

    if rules.dd_kill is None:
        turnover = w.diff().abs().fillna(w.abs())
        costs = turnover * cost_rate
        net = w * ret + (1 - w) * rf - costs
        return Result(name, net, w, turnover, costs)

    # Drawdown kill switch needs the path, so it runs sequentially.
    wv, rv, fv = w.to_numpy(), ret.to_numpy(), rf.to_numpy()
    held = np.zeros_like(wv)
    net = np.zeros_like(wv)
    to = np.zeros_like(wv)
    eq, peak, cool, prev = 1.0, 1.0, 0, 0.0
    for i in range(len(wv)):
        x = 0.0 if cool > 0 else wv[i]
        cool = max(cool - 1, 0)
        to[i] = abs(x - prev)
        net[i] = x * rv[i] + (1 - x) * fv[i] - to[i] * cost_rate
        eq *= 1 + net[i]
        peak = max(peak, eq)
        if eq / peak - 1 <= -rules.dd_kill and cool == 0:
            cool, peak = rules.dd_cooldown, eq   # flat for the cooldown, then re-arm
        held[i], prev = x, x
    idx = w.index
    return Result(name, pd.Series(net, idx), pd.Series(held, idx), pd.Series(to, idx),
                  pd.Series(to * cost_rate, idx))
