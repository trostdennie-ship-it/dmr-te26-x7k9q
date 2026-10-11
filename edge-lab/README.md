# Edge Lab

Antwort auf den Guide "Build a Six-Bot AI Trading Team With Grok" (@seb.ai).

Der Grok-Guide baut sechs LLM-Bots, die über **einen** fiktiven Markt abstimmen und
`BUY / WAIT / SKIP` ausgeben. Er sagt selbst: *"No evaluation loop measures outcomes."*
Damit kann das System nie wissen, ob es irgendetwas kann.

Edge Lab dreht die Reihenfolge um: **erst messen, dann glauben.**

| Frage | Grok Six-Bot | Edge Lab |
|---|---|---|
| Daten | 1 fiktiver Ticker (EXMP) | 55 J. NASDAQ täglich, 11 J. Bitcoin, 90 J. S&P 500 TR monatlich, echte Cash-Zinsen |
| Signale | LLM-Meinungen, LLM rechnet Chart-Levels | deterministischer Code, rechnet exakt, reproduzierbar |
| Look-ahead | nicht adressiert | Ausführung mit Verzögerung erzwungen, Test verändert Zukunftspreise |
| Benchmark | keiner | Buy & Hold im gleichen Zeitfenster |
| Kosten | keine | Kosten je Seite, Sensitivität 0 bis 50 bps |
| Steuern | keine | deutsche Abgeltungsteuer, Teilfreistellung, § 23 EStG Krypto |
| Glück vs. Können | nicht adressiert | Deflated Sharpe, White Reality Check, Affentest, Walk-Forward |
| Risk Gate | LLM-Bot + Code-Cap | nur Code, eingefrorene Regeln, kein Hebel, kein Short |
| Evaluation | keine | Hash-verkettetes Forward-Ledger, misst auch Grok-Entscheidungen |

## Ergebnis in einem Satz

Einfache Trendregeln senken Drawdowns deutlich, aber **keine** der getesteten Regeln
schlägt Buy & Hold nach Kosten, Steuern und Glückskorrektur belastbar. Genau das
hätte das Six-Bot-System nie herausfinden können. Details: `reports/study.md`.

## Quickstart

```bash
pip install -r requirements.txt
python -m pytest -q          # 31 Tests: Look-ahead, Kosten, Risk Rules, Steuern, Ledger
python run_study.py          # komplette Studie -> reports/study.json + study.md (ca. 10 s)
python run_study.py --refresh  # vorher frische Daten von FRED + Shiller laden
python record_today.py       # heutige Signale ins Forward-Ledger schreiben, danach committen
python record_today.py --grok decision.json   # Groks Decision-Bot-Output gleich mitmessen
python -m edgelab.critic     # optional: Claude als Red-Team-Reviewer der Studie (API-Key nötig)
```

## Aufbau

```
edgelab/data.py       Snapshots + Refresh (FRED, Shiller), Notes zu Datenschwächen
edgelab/signals.py    SMA-Trend, SMA-Cross, Time-Series-Momentum, RSI(2)-Mean-Reversion
edgelab/backtest.py   Point-in-time Backtester: Delay, Kosten, Cash-Zins, Vol-Target, DD-Kill-Switch
edgelab/risk.py       Eingefrorene, validierte Risk Rules (kein Hebel, kein Short)
edgelab/stats.py      Sharpe, Sortino, MaxDD, PSR, DSR, Block-Bootstrap, White Reality Check
edgelab/research.py   Parameter-Grid, Walk-Forward, Affentest
edgelab/tax.py        Deutsche Steuerlast (vereinfacht, siehe Annahmen im Code)
edgelab/ledger.py     Append-only Forward-Ledger mit Hash-Kette, Grok-Adapter, Scoring
edgelab/critic.py     Optionaler LLM-Reviewer (Claude), sieht nur Ergebnisse, setzt nie Positionen
```

## Wo LLMs hingehören (und wo nicht)

* **Nicht** als Rechenmaschine für Kurse, Levels oder Positionsgrößen. Code ist dort exakt.
* **Nicht** historisch backtesten: Ein LLM kennt die Zukunft der Trainingsdaten. Jede
  Rückrechnung von "Grok hätte 2022 verkauft" ist kontaminiert. LLM-Signale lassen sich
  nur **vorwärts** messen, deshalb das Ledger.
* **Ja** als Red-Team-Reviewer (`critic.py`), zum Strukturieren von Text in Features mit
  Zeitstempel, und als Erklärer. Immer mit Mensch am Ende.

## Grenzen (ehrlich)

* NASDAQCOM ist ein Preisindex ohne Dividenden, das bevorzugt Timing-Regeln leicht.
* Shiller-Daten sind Monatsdurchschnitte. Mit Ausführung im selben Monat entsteht
  Look-ahead (SMA10 springt von 9,5 % auf 11,5 % CAGR). Die Studie rechnet deshalb mit 1 Monat Verzögerung.
* Steuermodell vereinfacht (keine Kirchensteuer, Vorabpauschale, Freibeträge). § 23 EStG
  für Krypto nach Stand meines Wissens, vor Nutzung mit Steuerberater prüfen.
* Kein Survivorship-Problem bei Indizes, aber jeder Einzeltitel-Test bräuchte ein
  Point-in-time-Universum.

**SIMULATION ONLY. Keine Anlageberatung. Kein Order-, Broker- oder Wallet-Code.**
