"""Full study: does any simple rule beat buy & hold after costs, taxes and luck?

    python run_study.py            -> reports/study.json + reports/study.md
    python run_study.py --refresh  -> re-download data first

SIMULATION ONLY. No orders, no broker, no wallet.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from edgelab import backtest, data, research, signals, stats, tax
from edgelab.risk import RiskRules

ROOT = Path(__file__).resolve().parent
REPORTS = ROOT / "reports"

SETUPS = {
    # cost per side: liquid ETF ~5 bps all-in; retail crypto broker ~25 bps (spread + fee).
    # Shiller prices are monthly averages: trading "at" the average you just used for the
    # signal is look-ahead, so the monthly study also waits one period (delay=1).
    "nasdaq": dict(cost=5.0, delay=1, daily=True, regime=tax.EQUITY, core=("sma_trend", {"n": 200})),
    "bitcoin": dict(cost=25.0, delay=1, daily=True, regime=tax.CRYPTO, core=("sma_trend", {"n": 200})),
    "sp500_monthly": dict(cost=5.0, delay=1, daily=False, regime=tax.EQUITY, core=("sma_trend", {"n": 10})),
}


def series_for_chart(results: dict[str, pd.Series], freq: str) -> dict:
    eq = pd.DataFrame({k: (1 + v).cumprod() for k, v in results.items()}).dropna()
    eq = eq.resample(freq).last().dropna()
    eq = eq / eq.iloc[0]
    dd = eq / eq.cummax() - 1
    return {"dates": [d.strftime("%Y-%m-%d") for d in eq.index],
            "equity": {k: [round(x, 4) for x in eq[k]] for k in eq},
            "drawdown": {k: [round(x, 4) for x in dd[k]] for k in dd}}


def study_market(key: str, cfg: dict) -> dict:
    m = data.MARKETS[key]()
    rules = RiskRules(cost_bps_per_side=cfg["cost"])
    delay = cfg["delay"]

    # 1) every candidate rule, all counted
    trials = research.grid(m, research.default_grid(cfg["daily"]), rules, delay)
    bh = backtest.run(m, signals.buy_and_hold(m.prices), rules, delay, "Buy & Hold")
    core_fam, core_prm = cfg["core"]
    core_label = f"SMA{core_prm['n']} (vorab festgelegt)"
    core = backtest.run(m, signals.SIGNALS[core_fam](m.prices, **core_prm), rules, delay, core_label)
    vt_rules = RiskRules(cost_bps_per_side=cfg["cost"], vol_target=0.15 if key != "bitcoin" else 0.40,
                         vol_lookback=60 if cfg["daily"] else 6, rebalance_band=0.10)
    core_vt = backtest.run(m, signals.SIGNALS[core_fam](m.prices, **core_prm), vt_rules, delay,
                           f"SMA{core_prm['n']} + Vol-Target {int(vt_rules.vol_target * 100)} %")

    start = research.common_start([t.result for t in trials] + [core, core_vt])

    def cut(res: backtest.Result) -> backtest.Result:
        s = res.returns.index > start
        return backtest.Result(res.name, res.returns[s], res.weights[s], res.turnover[s], res.costs[s])

    bh, core, core_vt = cut(bh), cut(core), cut(core_vt)
    for t in trials:
        t.result = cut(t.result)

    # 2) best of grid = what a hobby optimizer would publish
    rf, ppy = m.rf_period, m.periods_per_year
    trial_sr = np.array([stats.period_sharpe(t.result.returns, rf) for t in trials])
    best = trials[int(np.argmax(trial_sr))]
    best_res = best.result
    best_res.name = f"Bester von {len(trials)} ({best.label})"

    # 3) walk-forward: only past data picks the rule
    wf = research.walk_forward(m, trials, rules, is_years=4 if key == "bitcoin" else 10,
                               oos_years=1 if key == "bitcoin" else 2)
    wf_ret = wf["returns"]
    wf_res = backtest.Result("Walk-Forward (out of sample)", wf_ret,
                             pd.Series(np.nan, wf_ret.index), pd.Series(0.0, wf_ret.index),
                             pd.Series(0.0, wf_ret.index))

    rows = [stats.summary(r, m) for r in (bh, core, core_vt, best_res)]
    wf_sum = {"name": wf_res.name, "start": str(wf_ret.index[0].date()), "end": str(wf_ret.index[-1].date()),
              "years": round(len(wf_ret) / ppy, 1), "cagr": stats.cagr(wf_ret, ppy),
              "vol": float(wf_ret.std() * np.sqrt(ppy)), "sharpe": stats.sharpe(wf_ret, rf, ppy),
              "sortino": stats.sortino(wf_ret, rf, ppy), "max_dd": stats.max_drawdown(wf_ret),
              "psr_vs_0": stats.psr(wf_ret, rf)}
    bh_wf = bh.returns.reindex(wf_ret.index)
    wf_sum["bh_same_window"] = {"cagr": stats.cagr(bh_wf, ppy), "sharpe": stats.sharpe(bh_wf, rf, ppy),
                                "max_dd": stats.max_drawdown(bh_wf)}

    # 4) luck tests
    bh_sr_period = stats.period_sharpe(bh.returns, rf)
    luck = {
        "n_trials": len(trials),
        "best_label": best.label,
        "best_sharpe": stats.sharpe(best_res.returns, rf, ppy),
        "best_psr_vs_bh": stats.psr(best_res.returns, rf, bh_sr_period),
        "best_dsr": stats.dsr(best_res.returns, rf, trial_sr),
        "core_psr_vs_bh": stats.psr(core.returns, rf, bh_sr_period),
        "core_vs_bh_bootstrap": stats.bootstrap_sharpe_diff(core.returns, bh.returns, rf, ppy,
                                                           block=21 if cfg["daily"] else 6),
        "reality_check_vs_bh": stats.reality_check(
            pd.DataFrame({t.label: t.result.returns for t in trials}), bh.returns, rf, ppy,
            block=21 if cfg["daily"] else 6),
        "monkey_core": research.monkey_test(m, core, rules),
        "monkey_best": research.monkey_test(m, best_res, rules),
        "walk_forward_is_vs_oos": {"mean_is_sharpe": wf["mean_is_sharpe"],
                                   "mean_oos_sharpe": wf["mean_oos_sharpe"]},
        "trial_sharpes": sorted([round(float(stats.sharpe(t.result.returns, rf, ppy)), 3) for t in trials]),
        "bh_sharpe": stats.sharpe(bh.returns, rf, ppy),
    }

    # 4b) where does the edge come from? Sharpe by decade
    decades = []
    for d0 in range(bh.returns.index[0].year // 10 * 10, bh.returns.index[-1].year + 1, 10):
        sl = slice(f"{d0}-01-01", f"{d0 + 9}-12-31")
        rb, rc = bh.returns.loc[sl], core.returns.loc[sl]
        if len(rb) < ppy:
            continue
        decades.append({"decade": f"{d0}er", "bh_sharpe": stats.sharpe(rb, rf, ppy),
                        "core_sharpe": stats.sharpe(rc, rf, ppy),
                        "bh_cagr": stats.cagr(rb, ppy), "core_cagr": stats.cagr(rc, ppy),
                        "bh_maxdd": stats.max_drawdown(rb), "core_maxdd": stats.max_drawdown(rc)})

    # 5) frictions: costs and execution delay
    sig_core = signals.SIGNALS[core_fam](m.prices, **core_prm)
    frictions = []
    for c in [0, 5, 10, 25, 50]:
        for d in (0, 1):
            r = cut(backtest.run(m, sig_core, RiskRules(cost_bps_per_side=c), d)).returns
            frictions.append({"cost_bps": c, "delay": d, "cagr": stats.cagr(r, ppy),
                              "sharpe": stats.sharpe(r, rf, ppy)})

    # 6) German taxes (binary strategies only)
    at_bh = tax.after_tax_returns(bh, m, cfg["regime"])
    at_core = tax.after_tax_returns(core, m, cfg["regime"])
    taxes = {"regime": cfg["regime"].name,
             "bh": {"pre_tax_cagr": stats.cagr(bh.returns, ppy), "after_tax_cagr": stats.cagr(at_bh, ppy)},
             "core": {"pre_tax_cagr": stats.cagr(core.returns, ppy), "after_tax_cagr": stats.cagr(at_core, ppy)}}

    # 7) what the pre-registered rule says right now (goes into the ledger, not into a trade)
    last = m.prices.index[-1]
    now = {"asof": str(last.date()), "price": float(m.prices.iloc[-1]),
           "core_signal": float(sig_core.iloc[-1]),
           "sma": float(m.prices.rolling(core_prm["n"]).mean().iloc[-1])}

    freq = "W" if cfg["daily"] else "QE"
    chart = series_for_chart({"Buy & Hold": bh.returns, core.name: core.returns,
                              core_vt.name: core_vt.returns, best_res.name: best_res.returns}, freq)
    wf_chart = series_for_chart({"Buy & Hold": bh_wf, "Walk-Forward (out of sample)": wf_ret}, freq)

    return {"name": m.name, "note": m.note, "cost_bps_per_side": cfg["cost"], "delay": delay,
            "periods_per_year": ppy, "summary": rows, "walk_forward": wf_sum, "wf_picks": wf["picks"],
            "luck": luck, "decades": decades, "frictions": frictions, "taxes": taxes, "now": now,
            "series": chart, "wf_series": wf_chart}


def fmt_pct(x):
    return f"{x * 100:,.1f} %".replace(",", "X").replace(".", ",").replace("X", ".")


def to_markdown(study: dict) -> str:
    out = [f"# Edge Lab Studie ({study['generated_utc'][:10]})", "",
           "SIMULATION. Keine Anlageberatung. Vergangene Daten, keine Prognose.", ""]
    for key, s in study["markets"].items():
        out += [f"## {s['name']}", "", f"_{s['note']}_", "",
                f"Kosten {s['cost_bps_per_side']} bps je Seite, Ausführung mit {s['delay']} Periode(n) Verzögerung.", "",
                "| Strategie | Zeitraum | CAGR | Vol | Sharpe | Max DD | Zeit im Markt | Trades/J |",
                "|---|---|---:|---:|---:|---:|---:|---:|"]
        for r in s["summary"]:
            out.append(f"| {r['name']} | {r['start'][:4]}-{r['end'][:4]} | {fmt_pct(r['cagr'])} | {fmt_pct(r['vol'])} | "
                       f"{r['sharpe']:.2f} | {fmt_pct(r['max_dd'])} | {fmt_pct(r['time_in_market'])} | {r['trades_per_year']:.1f} |")
        w = s["walk_forward"]
        out.append(f"| {w['name']} | {w['start'][:4]}-{w['end'][:4]} | {fmt_pct(w['cagr'])} | {fmt_pct(w['vol'])} | "
                   f"{w['sharpe']:.2f} | {fmt_pct(w['max_dd'])} | | |")
        out.append(f"| Buy & Hold im WF-Fenster | | {fmt_pct(w['bh_same_window']['cagr'])} | | "
                   f"{w['bh_same_window']['sharpe']:.2f} | {fmt_pct(w['bh_same_window']['max_dd'])} | | |")
        L = s["luck"]
        out += ["", "**Glück oder Können?**", "",
                f"- {L['n_trials']} Regeln getestet. Beste: {L['best_label']} mit Sharpe {L['best_sharpe']:.2f} "
                f"(Buy & Hold {L['bh_sharpe']:.2f}).",
                f"- Deflated Sharpe Ratio der besten Regel: {fmt_pct(L['best_dsr'])} "
                "(Wahrscheinlichkeit, dass ihr Sharpe nach Korrektur für die Anzahl der Versuche über null liegt).",
                f"- Walk-Forward: Sharpe in-sample im Schnitt {L['walk_forward_is_vs_oos']['mean_is_sharpe']:.2f}, "
                f"out-of-sample {L['walk_forward_is_vs_oos']['mean_oos_sharpe']:.2f}.",
                f"- Affentest Kernregel: besser als {fmt_pct(L['monkey_core']['percentile'])} von "
                f"{L['monkey_core']['n']} Zufallsstrategien mit gleicher Marktquote und Handelsfrequenz.",
                f"- Sharpe-Differenz Kernregel minus Buy & Hold: {L['core_vs_bh_bootstrap']['sharpe_diff']:+.2f}, "
                f"95 %-KI [{L['core_vs_bh_bootstrap']['ci95'][0]:+.2f}; {L['core_vs_bh_bootstrap']['ci95'][1]:+.2f}] (Block-Bootstrap).",
                f"- White Reality Check (beste der {L['reality_check_vs_bh']['n_candidates']} Regeln schlägt Buy & Hold nur durch Glück?): "
                f"p = {L['reality_check_vs_bh']['p_value']:.2f}.",
                ""]
        out += ["| Jahrzehnt | Sharpe B&H | Sharpe Kernregel | CAGR B&H | CAGR Kernregel | MaxDD B&H | MaxDD Kernregel |",
                "|---|---:|---:|---:|---:|---:|---:|"]
        for d in s["decades"]:
            out.append(f"| {d['decade']} | {d['bh_sharpe']:.2f} | {d['core_sharpe']:.2f} | {fmt_pct(d['bh_cagr'])} | "
                       f"{fmt_pct(d['core_cagr'])} | {fmt_pct(d['bh_maxdd'])} | {fmt_pct(d['core_maxdd'])} |")
        out += ["", "**Reibung (Kernregel):** " + ", ".join(
            f"{f['cost_bps']} bps/Delay {f['delay']}: {fmt_pct(f['cagr'])}" for f in s["frictions"]), ""]
        t = s["taxes"]
        out += [f"**Nach deutscher Steuer** ({t['regime']}): Buy & Hold {fmt_pct(t['bh']['pre_tax_cagr'])} -> "
                f"{fmt_pct(t['bh']['after_tax_cagr'])}, Kernregel {fmt_pct(t['core']['pre_tax_cagr'])} -> "
                f"{fmt_pct(t['core']['after_tax_cagr'])} p.a.", ""]
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true")
    args = ap.parse_args()
    if args.refresh:
        data.refresh()
    REPORTS.mkdir(exist_ok=True)
    study = {"generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
             "mode": "SIMULATION_ONLY", "markets": {}}
    for key, cfg in SETUPS.items():
        print(f"[study] {key} ...", flush=True)
        study["markets"][key] = study_market(key, cfg)
    (REPORTS / "study.json").write_text(json.dumps(study, ensure_ascii=False, indent=1))
    md = to_markdown(study)
    (REPORTS / "study.md").write_text(md)
    print(md)


if __name__ == "__main__":
    main()
