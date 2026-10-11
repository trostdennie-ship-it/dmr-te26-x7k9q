"""Human-owned risk rules. Loaded read-only, validated, enforced in code.

No model output can change these values: the backtester and the ledger only
ever receive a frozen RiskRules object, and nothing in this package writes the
rules file.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, fields
from pathlib import Path


class RiskRuleError(ValueError):
    pass


@dataclass(frozen=True)
class RiskRules:
    max_weight: float = 1.0          # 1.0 = fully invested, never leverage
    allow_short: bool = False
    vol_target: float | None = None  # e.g. 0.15 = scale exposure to 15 % annual vol
    vol_lookback: int = 60
    rebalance_band: float = 0.0      # only trade when target drifts this far from the holding
    dd_kill: float | None = None     # e.g. 0.20 = go flat after a 20 % drawdown of the strategy
    dd_cooldown: int = 21            # periods to stay flat after the kill switch fires
    cost_bps_per_side: float = 5.0   # spread + slippage + fees, per trade side

    def __post_init__(self):
        if not 0 < self.max_weight <= 1.0:
            raise RiskRuleError("max_weight must be in (0, 1]: no leverage")
        if self.allow_short:
            raise RiskRuleError("short selling is not supported by this lab")
        if self.vol_target is not None and not 0 < self.vol_target <= 1.0:
            raise RiskRuleError("vol_target must be in (0, 1]")
        if self.dd_kill is not None and not 0 < self.dd_kill < 1:
            raise RiskRuleError("dd_kill must be in (0, 1)")
        if not 0 <= self.rebalance_band < 1:
            raise RiskRuleError("rebalance_band must be in [0, 1)")
        if self.cost_bps_per_side < 0:
            raise RiskRuleError("costs cannot be negative")

    @classmethod
    def load(cls, path: str | Path) -> "RiskRules":
        raw = json.loads(Path(path).read_text())
        known = {f.name for f in fields(cls)}
        unknown = set(raw) - known
        if unknown:
            raise RiskRuleError(f"unknown risk rule keys: {sorted(unknown)}")
        return cls(**raw)
