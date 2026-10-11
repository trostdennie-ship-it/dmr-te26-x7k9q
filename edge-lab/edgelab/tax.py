"""German private-investor tax drag (simplified, illustrative, not tax advice).

Assumptions (state of law as I know it; verify with a Steuerberater):
  * Equity ETF: Abgeltungsteuer 25 % + Soli 5.5 % = 26.375 %, Teilfreistellung 30 %
    -> 18.46 % effective on gains. Kirchensteuer, Vorabpauschale and the
    Sparerpauschbetrag are ignored.
  * Cash interest: 26.375 %, taxed as it accrues.
  * Crypto held privately (§ 23 EStG): gains tax-free after > 1 year holding,
    otherwise personal income tax rate (default 42 % + Soli = 44.31 %).
  * Losses go into a loss pot and offset later gains of the same kind.
  * Buy & hold is liquidated (and taxed) at the end, so deferral is credited fairly.
Only binary (0/1 exposure) strategies are supported.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .backtest import Result
from .data import Market

ABGELTUNG = 0.26375
EQUITY_ETF = ABGELTUNG * 0.70
CRYPTO_SHORT = 0.42 * 1.055


@dataclass(frozen=True)
class TaxRegime:
    name: str
    gain_rate: float
    interest_rate: float = ABGELTUNG
    tax_free_after_days: int | None = None


EQUITY = TaxRegime("Aktien-ETF (Abgeltungsteuer, Teilfreistellung)", EQUITY_ETF)
CRYPTO = TaxRegime("Krypto privat (§ 23 EStG)", CRYPTO_SHORT, tax_free_after_days=365)


def after_tax_returns(res: Result, market: Market, regime: TaxRegime) -> pd.Series:
    w = res.weights.to_numpy()
    if not np.all(np.isin(np.round(w, 9), [0.0, 1.0])):
        raise ValueError("after-tax model supports binary exposure only")
    idx = res.returns.index
    ret = market.returns.reindex(idx).to_numpy()
    rf = market.rf_period.reindex(idx).to_numpy()
    cost = res.costs.to_numpy()

    eq, basis, entry_date, loss_pot = 1.0, 0.0, None, 0.0
    out = np.empty(len(w))

    def realize(gain: float, held_days: int) -> float:
        nonlocal loss_pot
        if regime.tax_free_after_days is not None and held_days > regime.tax_free_after_days:
            return 0.0
        if gain < 0:
            loss_pot += -gain
            return 0.0
        offset = min(gain, loss_pot)
        loss_pot -= offset
        return (gain - offset) * regime.gain_rate

    prev = 0.0
    for i in range(len(w)):
        start_eq = eq
        tax = 0.0
        if prev == 1.0 and w[i] == 0.0:  # exit at the start of this period
            tax = realize(eq - basis, (idx[i] - entry_date).days)
            eq -= tax
        eq *= 1 - cost[i]
        if prev == 0.0 and w[i] == 1.0:
            basis, entry_date = eq, idx[i]
        if w[i] == 1.0:
            eq *= 1 + ret[i]
        else:
            eq *= 1 + rf[i] * (1 - regime.interest_rate)
        if i == len(w) - 1 and w[i] == 1.0:  # liquidate at the end
            eq -= realize(eq - basis, (idx[i] - entry_date).days)
        out[i] = eq / start_eq - 1
        prev = w[i]
    return pd.Series(out, idx)
