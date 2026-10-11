"""Safety and correctness tests. Synthetic data unless a test needs the snapshots."""
import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pytest

from edgelab import backtest, ledger, research, signals, stats, tax
from edgelab.data import Market, nasdaq
from edgelab.risk import RiskRuleError, RiskRules


def synth(n=1500, seed=0, ppy=252, drift=0.0004, vol=0.012) -> Market:
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2000-01-03", periods=n)
    p = pd.Series(100 * np.exp(np.cumsum(rng.normal(drift, vol, n))), idx)
    return Market("synthetic", p, pd.Series(0.02, idx), ppy, True, "synthetic GBM")


SIGNAL_CASES = [
    ("sma_trend", {"n": 50}), ("sma_cross", {"fast": 10, "slow": 50}),
    ("tsmom", {"lookback": 126, "skip": 21}), ("rsi_meanrev", {"trend": 50}),
    ("buy_and_hold", {}),
]


# ------------------------------------------------------------ look-ahead

@pytest.mark.parametrize("family,params", SIGNAL_CASES)
def test_signals_never_use_future_prices(family, params):
    m = synth()
    cut = 900
    base = signals.SIGNALS[family](m.prices, **params)
    future_changed = m.prices.copy()
    future_changed.iloc[cut + 1:] *= np.random.default_rng(1).uniform(0.3, 3.0, len(m.prices) - cut - 1)
    alt = signals.SIGNALS[family](future_changed, **params)
    pd.testing.assert_series_equal(base.iloc[:cut + 1], alt.iloc[:cut + 1])


def test_execution_delay_is_applied():
    m = synth()
    sig = signals.sma_trend(m.prices, 50)
    for delay in (0, 1, 2):
        res = backtest.run(m, sig, RiskRules(cost_bps_per_side=0), delay=delay)
        expected = sig.shift(1 + delay).reindex(res.weights.index)
        pd.testing.assert_series_equal(res.weights, expected, check_names=False)


def test_perfect_foresight_is_impossible_through_the_api():
    """A signal that peeks one day ahead must not earn the peeked return."""
    m = synth()
    cheat = (m.returns.shift(-1) > 0).astype(float)   # knows tomorrow
    res = backtest.run(m, cheat, RiskRules(cost_bps_per_side=0), delay=1)
    # with the enforced delay the peek lands on the wrong day: no miracle Sharpe
    assert stats.sharpe(res.returns, m.rf_period, 252) < 1.5


# ------------------------------------------------------------ accounting

def test_buy_and_hold_without_costs_equals_asset():
    m = synth()
    res = backtest.run(m, signals.buy_and_hold(m.prices), RiskRules(cost_bps_per_side=0), delay=0)
    pd.testing.assert_series_equal(res.returns, m.returns.reindex(res.returns.index), check_names=False)


def test_round_trip_costs_exactly_two_sides():
    m = synth(n=10)
    sig = pd.Series([1, 1, 1, 0, 0, 0, 0, 0, 0, 0], m.prices.index, dtype=float)
    res = backtest.run(m, sig, RiskRules(cost_bps_per_side=10), delay=0)
    assert res.costs.sum() == pytest.approx(2 * 10 / 1e4)


def test_flat_earns_cash():
    m = synth(n=50)
    res = backtest.run(m, pd.Series(0.0, m.prices.index), RiskRules(cost_bps_per_side=0), delay=0)
    np.testing.assert_allclose(res.returns, m.rf_period.reindex(res.returns.index))


# ------------------------------------------------------------ risk rules

@pytest.mark.parametrize("bad", [{"max_weight": 1.5}, {"allow_short": True}, {"vol_target": 2.0},
                                 {"dd_kill": 1.2}, {"cost_bps_per_side": -1}])
def test_risk_rules_reject_dangerous_values(bad):
    with pytest.raises(RiskRuleError):
        RiskRules(**bad)


def test_risk_rules_file_rejects_unknown_keys(tmp_path):
    f = tmp_path / "rules.json"
    f.write_text(json.dumps({"max_weight": 1.0, "let_the_model_decide": True}))
    with pytest.raises(RiskRuleError):
        RiskRules.load(f)


def test_risk_rules_are_immutable():
    r = RiskRules()
    with pytest.raises(Exception):
        r.max_weight = 3.0


def test_exposure_never_exceeds_cap_or_goes_short():
    m = synth()
    wild = pd.Series(np.random.default_rng(3).normal(0, 5, len(m.prices)), m.prices.index)
    res = backtest.run(m, wild, RiskRules(max_weight=0.6, vol_target=0.5), delay=1)
    assert res.weights.max() <= 0.6 + 1e-12
    assert res.weights.min() >= 0.0


def test_drawdown_kill_switch_limits_losses():
    m = synth(drift=-0.002, vol=0.02, seed=5)   # a crash
    sig = signals.buy_and_hold(m.prices)
    free = backtest.run(m, sig, RiskRules(cost_bps_per_side=0), delay=0)
    guarded = backtest.run(m, sig, RiskRules(cost_bps_per_side=0, dd_kill=0.2, dd_cooldown=10_000), delay=0)
    assert stats.max_drawdown(free.returns) < -0.5
    assert stats.max_drawdown(guarded.returns) > -0.3


def test_rebalance_band_cuts_trading():
    m = synth()
    sig = signals.sma_trend(m.prices, 50)
    tight = backtest.run(m, sig, RiskRules(vol_target=0.1), delay=1)
    banded = backtest.run(m, sig, RiskRules(vol_target=0.1, rebalance_band=0.1), delay=1)
    assert (banded.turnover > 0).sum() < (tight.turnover > 0).sum() / 3


# ------------------------------------------------------------ statistics

def test_dsr_penalises_many_trials():
    m = synth(seed=8)
    r = backtest.run(m, signals.sma_trend(m.prices, 50), RiskRules(), delay=1).returns
    few = stats.dsr(r, m.rf_period, np.random.default_rng(0).normal(0, 0.01, 2))
    many = stats.dsr(r, m.rf_period, np.random.default_rng(0).normal(0, 0.01, 1000))
    assert many < few


def test_reality_check_does_not_find_skill_in_noise():
    m = synth(n=2500, seed=21, drift=0.0)
    trials = research.grid(m, research.default_grid(True)[:20], RiskRules(), 1)
    start = research.common_start([t.result for t in trials])
    df = pd.DataFrame({t.label: t.result.returns.loc[start:] for t in trials})
    bh = backtest.run(m, signals.buy_and_hold(m.prices), RiskRules(), 1).returns.loc[start:]
    rc = stats.reality_check(df, bh, m.rf_period, 252, n=200)
    assert rc["p_value"] > 0.05


def test_monkey_test_matches_exposure_and_is_reproducible():
    m = synth()
    res = backtest.run(m, signals.sma_trend(m.prices, 50), RiskRules(), delay=1)
    a = research.monkey_test(m, res, RiskRules(), n=200, seed=1)
    b = research.monkey_test(m, res, RiskRules(), n=200, seed=1)
    assert a == b
    assert 0 <= a["percentile"] <= 1


# ------------------------------------------------------------ taxes

def test_tax_buy_and_hold_only_pays_at_the_end():
    m = synth(drift=0.001, vol=0.0)
    res = backtest.run(m, signals.buy_and_hold(m.prices), RiskRules(cost_bps_per_side=0), delay=0)
    at = tax.after_tax_returns(res, m, tax.EQUITY)
    pre_final = (1 + res.returns).prod()
    post_final = (1 + at).prod()
    assert post_final == pytest.approx(1 + (pre_final - 1) * (1 - tax.EQUITY_ETF), rel=1e-6)
    assert np.allclose(at.iloc[:-1], res.returns.iloc[:-1])


def test_crypto_long_hold_is_tax_free_short_hold_is_not():
    m = synth(n=900, drift=0.001, vol=0.0)
    hold = backtest.run(m, signals.buy_and_hold(m.prices), RiskRules(cost_bps_per_side=0), delay=0)
    assert (1 + tax.after_tax_returns(hold, m, tax.CRYPTO)).prod() == pytest.approx((1 + hold.returns).prod())
    flips = pd.Series(np.where((np.arange(900) // 100) % 2 == 0, 1.0, 0.0), m.prices.index)
    churn = backtest.run(m, flips, RiskRules(cost_bps_per_side=0), delay=0)
    assert (1 + tax.after_tax_returns(churn, m, tax.CRYPTO)).prod() < (1 + churn.returns).prod()


# ------------------------------------------------------------ ledger

NOW = datetime(2026, 10, 11, 12, tzinfo=timezone.utc)


def _rec(path, **kw):
    base = dict(market="nasdaq", asof="2026-10-09", exposure=1.0, source="test",
                strategy="SMA200", ref_price=100.0, now=NOW)
    base.update(kw)
    return ledger.record(path, **base)


def test_ledger_chain_detects_tampering(tmp_path):
    f = tmp_path / "l.jsonl"
    _rec(f)
    _rec(f, exposure=0.0)
    assert ledger.verify(f) == 2
    lines = f.read_text().splitlines()
    e = json.loads(lines[0])
    e["exposure"] = 0.0          # rewrite history after the fact
    f.write_text(json.dumps(e) + "\n" + lines[1] + "\n")
    with pytest.raises(ledger.LedgerError):
        ledger.verify(f)


def test_ledger_rejects_backdating_and_leverage(tmp_path):
    f = tmp_path / "l.jsonl"
    with pytest.raises(ledger.LedgerError):
        _rec(f, asof="2025-01-02")
    with pytest.raises(ledger.LedgerError):
        _rec(f, exposure=2.0)
    with pytest.raises(ledger.LedgerError):
        _rec(f, asof="2026-12-01")


def test_grok_decisions_map_and_need_human_review():
    ok = {"decision": "BUY — SIMULATION ONLY", "human_review_required": True}
    assert ledger.from_grok_decision(ok) == 1.0
    assert ledger.from_grok_decision({**ok, "decision": "WAIT"}) == 0.0
    with pytest.raises(ledger.LedgerError):
        ledger.from_grok_decision({**ok, "human_review_required": False})
    with pytest.raises(ledger.LedgerError):
        ledger.from_grok_decision({**ok, "decision": "BUY NOW 10X"})


def test_ledger_scoring_uses_only_prices_after_the_call(tmp_path):
    m = synth(n=60)
    asof = m.prices.index[30]
    f = tmp_path / "l.jsonl"
    ledger.record(f, market="s", asof=str(asof.date()), exposure=1.0, source="t", strategy="x",
                  ref_price=float(m.prices.iloc[30]), now=asof.to_pydatetime().replace(tzinfo=timezone.utc))
    out = ledger.score(f, {"s": m}, horizon=5)
    row = out.iloc[0]
    assert row["status"] == "scored"
    assert row["asset_ret"] == pytest.approx(m.prices.iloc[36] / m.prices.iloc[31] - 1)


# ------------------------------------------------------------ no execution path

def test_package_contains_no_order_execution_code():
    from pathlib import Path
    src = " ".join(p.read_text().lower() for p in Path(backtest.__file__).parent.glob("*.py"))
    for word in ("place_order", "submit_order", "create_order", "api.binance", "alpaca", "private_key"):
        assert word not in src


# ------------------------------------------------------------ real data sanity

def test_snapshot_data_is_sane():
    m = nasdaq()
    assert m.prices.index.is_monotonic_increasing
    assert not m.prices.index.has_duplicates
    assert (m.prices > 0).all()
    assert m.returns.abs().max() < 0.2   # largest NASDAQ day (Oct 1987) was about -11 %
