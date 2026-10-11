"""Write today's calls into the forward-test ledger (SIMULATION ONLY).

    python record_today.py                       -> rule-based calls (SMA200) + buy & hold control
    python record_today.py --grok decision.json  -> also log a Grok Decision Bot output for nasdaq

Run it after each data refresh, then commit ledger/ledger.jsonl: the git
timestamp is the external proof that the call existed before the outcome.
Score later with:  python -c "from edgelab import ledger, data; print(ledger.score('ledger/ledger.jsonl', {k: f() for k, f in data.MARKETS.items()}))"
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from edgelab import data, ledger, signals

LEDGER = Path(__file__).resolve().parent / "ledger" / "ledger.jsonl"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--grok", help="path to a Grok Decision Bot JSON output")
    ap.add_argument("--market", default="nasdaq")
    args = ap.parse_args()
    LEDGER.parent.mkdir(exist_ok=True)

    for key in ("nasdaq", "bitcoin"):
        m = data.MARKETS[key]()
        asof, px = str(m.prices.index[-1].date()), float(m.prices.iloc[-1])
        sig = float(signals.sma_trend(m.prices, 200).iloc[-1])
        sma = float(m.prices.rolling(200).mean().iloc[-1])
        for strategy, exposure, payload in [
            ("SMA200", sig, {"sma200": round(sma, 2), "rule": "long if close > SMA200, else cash"}),
            ("Buy & Hold (Kontrolle)", 1.0, {}),
        ]:
            e = ledger.record(LEDGER, market=key, asof=asof, exposure=exposure, source="edgelab",
                              strategy=strategy, ref_price=px, payload=payload)
            print(f"[{e['seq']}] {key} {asof} {strategy}: exposure {exposure:.0%}  hash {e['hash'][:12]}")

    if args.grok:
        decision = json.loads(Path(args.grok).read_text())
        m = data.MARKETS[args.market]()
        e = ledger.record(LEDGER, market=args.market, asof=str(m.prices.index[-1].date()),
                          exposure=ledger.from_grok_decision(decision), source="grok-six-bot",
                          strategy="Grok Decision Bot", ref_price=float(m.prices.iloc[-1]), payload=decision)
        print(f"[{e['seq']}] grok {e['strategy']}: exposure {e['exposure']:.0%}")
    print(f"ledger verified: {ledger.verify(LEDGER)} entries")


if __name__ == "__main__":
    main()
