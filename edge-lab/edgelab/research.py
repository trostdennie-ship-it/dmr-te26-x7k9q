"""Research tools that separate skill from luck.

grid()          every parameter combination tried is counted (feeds the DSR)
walk_forward()  choose parameters on the past only, trade them on unseen data
monkey_test()   random long/flat timing with the same exposure and trade frequency
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import backtest, signals, stats
from .data import Market
from .risk import RiskRules


@dataclass
class Trial:
    label: str
    family: str
    params: dict
    result: backtest.Result


def default_grid(daily: bool = True) -> list[tuple[str, str, dict]]:
    """The candidate set. Every entry counts as one trial for the DSR."""
    scale = 1 if daily else 21  # monthly data: lookbacks in months
    out = []
    for n in [20, 50, 100, 150, 200, 250, 300]:
        n_eff = n if daily else max(round(n / scale), 2)
        out.append((f"SMA{n_eff}", "sma_trend", {"n": n_eff}))
    for fast in [5, 10, 20, 50, 100]:
        for slow in [50, 100, 150, 200, 250, 300]:
            if fast < slow:
                f, s = (fast, slow) if daily else (max(round(fast / scale), 1), max(round(slow / scale), 2))
                if f < s:
                    out.append((f"X{f}/{s}", "sma_cross", {"fast": f, "slow": s}))
    for lb in [63, 126, 189, 252, 378, 504]:
        lb_eff, sk = (lb, 21) if daily else (max(round(lb / scale), 2), 1)
        out.append((f"MOM{lb_eff}", "tsmom", {"lookback": lb_eff, "skip": sk}))
    if daily:
        for entry in [5, 10, 20]:
            for ex in [50, 70, 90]:
                out.append((f"RSI2<{entry}>{ex}", "rsi_meanrev", {"entry": entry, "exit": ex}))
    seen, uniq = set(), []
    for lab, fam, prm in out:
        if lab not in seen:
            seen.add(lab)
            uniq.append((lab, fam, prm))
    return uniq


def grid(market: Market, candidates, rules: RiskRules, delay: int) -> list[Trial]:
    trials = []
    for label, family, params in candidates:
        sig = signals.SIGNALS[family](market.prices, **params)
        trials.append(Trial(label, family, params, backtest.run(market, sig, rules, delay, label)))
    return trials


def common_start(results) -> pd.Timestamp:
    return max(r.returns.index[0] for r in results)


def walk_forward(market: Market, trials: list[Trial], rules: RiskRules,
                 is_years: int = 10, oos_years: int = 2) -> dict:
    """Pick the best in-sample Sharpe on a trailing window, trade it out of sample."""
    ppy = market.periods_per_year
    start = common_start([t.result for t in trials])
    idx = market.prices.loc[start:].index[1:]
    rf = market.rf_period
    is_n, oos_n = is_years * ppy, oos_years * ppy
    cost = rules.cost_bps_per_side / 1e4

    pieces, picks, prev_w = [], [], 0.0
    pos = is_n
    while pos < len(idx):
        is_idx, oos_idx = idx[pos - is_n:pos], idx[pos:pos + oos_n]
        best = max(trials, key=lambda t: stats.sharpe(t.result.returns.reindex(is_idx).dropna(), rf, ppy))
        r = best.result.returns.reindex(oos_idx).copy()
        w = best.result.weights.reindex(oos_idx)
        # The candidate's own return already paid |w0 - its previous weight|; the
        # stitched portfolio actually trades from the weight it really held.
        cand_prev = best.result.weights.shift(1).reindex(oos_idx).iloc[0]
        cand_prev = 0.0 if pd.isna(cand_prev) else cand_prev
        r.iloc[0] += (abs(w.iloc[0] - cand_prev) - abs(w.iloc[0] - prev_w)) * cost
        prev_w = w.iloc[-1]
        is_sr = stats.sharpe(best.result.returns.reindex(is_idx).dropna(), rf, ppy)
        oos_sr = stats.sharpe(r, rf, ppy)
        picks.append({"oos_start": str(oos_idx[0].date()), "oos_end": str(oos_idx[-1].date()),
                      "pick": best.label, "is_sharpe": is_sr, "oos_sharpe": oos_sr})
        pieces.append(r)
        pos += oos_n
    oos = pd.concat(pieces)
    return {"returns": oos, "picks": picks,
            "mean_is_sharpe": float(np.mean([p["is_sharpe"] for p in picks])),
            "mean_oos_sharpe": float(np.mean([p["oos_sharpe"] for p in picks]))}


def monkey_test(market: Market, result: backtest.Result, rules: RiskRules,
                n: int = 1000, seed: int = 42) -> dict:
    """Null hypothesis: random entries/exits with the same exposure and trade rate.

    Builds a two-state Markov chain whose switch probabilities match the
    strategy's own, so the monkeys hold the asset as often and trade as often."""
    w = (result.weights > 0.5).astype(int).to_numpy()
    ret = market.returns.reindex(result.returns.index).to_numpy()
    rf = market.rf_period.reindex(result.returns.index).to_numpy()
    cost = rules.cost_bps_per_side / 1e4
    ppy = market.periods_per_year

    n_in, n_out = max(w[:-1].sum(), 1), max((1 - w[:-1]).sum(), 1)
    p_exit = max(((w[:-1] == 1) & (w[1:] == 0)).sum() / n_in, 1e-6)
    p_enter = max(((w[:-1] == 0) & (w[1:] == 1)).sum() / n_out, 1e-6)

    rng = np.random.default_rng(seed)
    t = len(w)
    sims = np.empty((n, t))
    state = (rng.random(n) < w.mean()).astype(float)
    u = rng.random((t, n))
    for i in range(t):
        sims[:, i] = state
        flip = np.where(state == 1, u[i] < p_exit, u[i] < p_enter)
        state = np.where(flip, 1 - state, state)
    turnover = np.abs(np.diff(sims, axis=1, prepend=0))
    excess = sims * (ret - rf) - turnover * cost
    srs = excess.mean(axis=1) / excess.std(axis=1, ddof=1) * np.sqrt(ppy)
    real = stats.sharpe(result.returns, market.rf_period, ppy)
    return {"strategy_sharpe": real,
            "monkey_median_sharpe": float(np.median(srs)),
            "monkey_p95_sharpe": float(np.percentile(srs, 95)),
            "percentile": float((srs < real).mean()),
            "p_value": float((srs >= real).mean()),
            "n": n}
