"""Forward-test ledger: the evaluation loop the Grok guide admits it does not have.

Every call (from a rule, from Grok, from Claude, from a human) is written
*before* the outcome is known into an append-only, hash-chained JSONL file.
Later the ledger is scored against what the market actually did, versus simply
holding the asset. Editing or back-dating an entry breaks the chain.

Committing the ledger to git after each entry adds an external timestamp.
SIMULATION ONLY: nothing here places orders.
"""
from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

from .data import Market

GENESIS = "0" * 64
MAX_STALENESS_DAYS = 5


class LedgerError(RuntimeError):
    pass


def _hash(entry: dict) -> str:
    body = {k: v for k, v in entry.items() if k != "hash"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def read(path: str | Path) -> list[dict]:
    p = Path(path)
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text().splitlines() if line.strip()]


def verify(path: str | Path) -> int:
    prev = GENESIS
    entries = read(path)
    for i, e in enumerate(entries):
        if e.get("seq") != i:
            raise LedgerError(f"entry {i}: sequence broken")
        if e.get("prev_hash") != prev:
            raise LedgerError(f"entry {i}: chain broken (prev_hash mismatch)")
        if _hash(e) != e.get("hash"):
            raise LedgerError(f"entry {i}: content was modified after recording")
        prev = e["hash"]
    return len(entries)


def record(path: str | Path, *, market: str, asof: str, exposure: float, source: str,
           strategy: str, ref_price: float, payload: dict | None = None,
           now: datetime | None = None) -> dict:
    """Append one call. `asof` = last data date the call was allowed to see."""
    if not 0.0 <= exposure <= 1.0:
        raise LedgerError("exposure must be within [0, 1] (long/flat, no leverage)")
    now = now or datetime.now(timezone.utc)
    asof_d = date.fromisoformat(asof)
    age = (now.date() - asof_d).days
    if age < 0:
        raise LedgerError("asof lies in the future")
    if age > MAX_STALENESS_DAYS:
        raise LedgerError(f"asof is {age} days old: back-dated calls are not accepted")
    verify(path)
    entries = read(path)
    entry = {
        "seq": len(entries),
        "recorded_utc": now.isoformat(timespec="seconds"),
        "asof": asof,
        "market": market,
        "source": source,
        "strategy": strategy,
        "exposure": float(exposure),
        "ref_price": float(ref_price),
        "payload": payload or {},
        "prev_hash": entries[-1]["hash"] if entries else GENESIS,
    }
    entry["hash"] = _hash(entry)
    with Path(path).open("a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


GROK_DECISIONS = {"BUY — SIMULATION ONLY": 1.0, "BUY - SIMULATION ONLY": 1.0,
                  "WAIT": 0.0, "SKIP": 0.0}


def from_grok_decision(decision: dict) -> float:
    """Map the six-bot Decision Bot JSON to an exposure so it can be scored too."""
    d = str(decision.get("decision", "")).strip()
    if d not in GROK_DECISIONS:
        raise LedgerError(f"unknown Grok decision: {d!r}")
    if decision.get("human_review_required") is not True:
        raise LedgerError("Grok decision without human_review_required=true is rejected")
    return GROK_DECISIONS[d]


def score(path: str | Path, markets: dict[str, Market], horizon: int = 21) -> pd.DataFrame:
    """Score every entry whose horizon has passed: call vs. simply holding."""
    verify(path)
    rows = []
    for e in read(path):
        m = markets[e["market"]]
        p = m.prices
        start = p.index.searchsorted(pd.Timestamp(e["asof"]), side="right")  # first bar after the call
        end = start + horizon
        if end >= len(p):
            rows.append({**_brief(e), "status": "pending"})
            continue
        asset = p.iloc[end] / p.iloc[start] - 1   # executed at the next close (delay=1)
        cash = float((1 + m.rf_period.iloc[start + 1:end + 1]).prod() - 1)
        call = e["exposure"] * asset + (1 - e["exposure"]) * cash
        rows.append({**_brief(e), "status": "scored", "asset_ret": asset,
                     "call_ret": call, "edge_vs_hold": call - asset})
    return pd.DataFrame(rows)


def _brief(e: dict) -> dict:
    return {k: e[k] for k in ("seq", "asof", "market", "source", "strategy", "exposure")}
