# Edge Lab Studie (2026-10-11)

SIMULATION. Keine Anlageberatung. Vergangene Daten, keine Prognose.

## NASDAQ Composite (täglich)

_Preisindex ohne Dividenden (FRED NASDAQCOM). Buy & Hold ist dadurch um ca. 0,7-1 % p.a. unterschätzt, das bevorzugt Timing-Strategien. Cash = 3M T-Bill._

Kosten 5.0 bps je Seite, Ausführung mit 1 Periode(n) Verzögerung.

| Strategie | Zeitraum | CAGR | Vol | Sharpe | Max DD | Zeit im Markt | Trades/J |
|---|---|---:|---:|---:|---:|---:|---:|
| Buy & Hold | 1973-2026 | 10,6 % | 20,5 % | 0.38 | -77,9 % | 100,0 % | 0.0 |
| SMA200 (vorab festgelegt) | 1973-2026 | 11,5 % | 13,6 % | 0.56 | -52,3 % | 70,5 % | 5.5 |
| SMA200 + Vol-Target 15 % | 1973-2026 | 10,3 % | 10,9 % | 0.56 | -23,5 % | 63,0 % | 7.4 |
| Bester von 49 (X5/50) | 1973-2026 | 12,7 % | 12,8 % | 0.66 | -36,7 % | 63,8 % | 7.5 |
| Walk-Forward (out of sample) | 1983-2026 | 11,6 % | 14,5 % | 0.60 | -30,1 % | | |
| Buy & Hold im WF-Fenster | | 11,4 % | | 0.45 | -77,9 % | | |

**Glück oder Können?**

- 49 Regeln getestet. Beste: X5/50 mit Sharpe 0.66 (Buy & Hold 0.38).
- Deflated Sharpe Ratio der besten Regel: 96,3 % (Wahrscheinlichkeit, dass ihr Sharpe nach Korrektur für die Anzahl der Versuche über null liegt).
- Walk-Forward: Sharpe in-sample im Schnitt 0.97, out-of-sample 0.69.
- Affentest Kernregel: besser als 100,0 % von 1000 Zufallsstrategien mit gleicher Marktquote und Handelsfrequenz.
- Sharpe-Differenz Kernregel minus Buy & Hold: +0.17, 95 %-KI [-0.05; +0.41] (Block-Bootstrap).
- White Reality Check (beste der 49 Regeln schlägt Buy & Hold nur durch Glück?): p = 0.16.

| Jahrzehnt | Sharpe B&H | Sharpe Kernregel | CAGR B&H | CAGR Kernregel | MaxDD B&H | MaxDD Kernregel |
|---|---:|---:|---:|---:|---:|---:|
| 1970er | -0.24 | 0.35 | 2,9 % | 9,5 % | -56,9 % | -17,5 % |
| 1980er | 0.26 | 0.67 | 11,6 % | 15,1 % | -35,9 % | -15,7 % |
| 1990er | 1.06 | 1.03 | 24,4 % | 21,2 % | -30,7 % | -18,6 % |
| 2000er | -0.12 | -0.02 | -5,7 % | 1,0 % | -77,9 % | -52,3 % |
| 2010er | 0.86 | 0.49 | 14,8 % | 6,4 % | -23,6 % | -24,3 % |
| 2020er | 0.68 | 0.95 | 18,0 % | 19,1 % | -36,4 % | -19,0 % |

**Reibung (Kernregel):** 0 bps/Delay 0: 12,8 %, 0 bps/Delay 1: 11,8 %, 5 bps/Delay 0: 12,5 %, 5 bps/Delay 1: 11,5 %, 10 bps/Delay 0: 12,2 %, 10 bps/Delay 1: 11,2 %, 25 bps/Delay 0: 11,3 %, 25 bps/Delay 1: 10,3 %, 50 bps/Delay 0: 9,7 %, 50 bps/Delay 1: 8,8 %

**Nach deutscher Steuer** (Aktien-ETF (Abgeltungsteuer, Teilfreistellung)): Buy & Hold 10,6 % -> 10,2 %, Kernregel 11,5 % -> 9,4 % p.a.

## Bitcoin / USD (täglich, Coinbase)

_Coinbase-Schlusskurs (FRED CBBTCUSD), 7 Handelstage/Woche. Cash = 3M T-Bill._

Kosten 25.0 bps je Seite, Ausführung mit 1 Periode(n) Verzögerung.

| Strategie | Zeitraum | CAGR | Vol | Sharpe | Max DD | Zeit im Markt | Trades/J |
|---|---|---:|---:|---:|---:|---:|---:|
| Buy & Hold | 2016-2026 | 65,4 % | 67,2 % | 1.05 | -83,8 % | 100,0 % | 0.0 |
| SMA200 (vorab festgelegt) | 2016-2026 | 66,9 % | 53,3 % | 1.18 | -64,9 % | 60,4 % | 6.9 |
| SMA200 + Vol-Target 40 % | 2016-2026 | 48,5 % | 33,4 % | 1.28 | -34,3 % | 43,0 % | 12.3 |
| Bester von 49 (X5/100) | 2016-2026 | 83,0 % | 51,8 % | 1.38 | -62,6 % | 58,2 % | 5.0 |
| Walk-Forward (out of sample) | 2020-2026 | 33,5 % | 41,3 % | 0.83 | -48,1 % | | |
| Buy & Hold im WF-Fenster | | 42,4 % | | 0.86 | -76,7 % | | |

**Glück oder Können?**

- 49 Regeln getestet. Beste: X5/100 mit Sharpe 1.38 (Buy & Hold 1.05).
- Deflated Sharpe Ratio der besten Regel: 97,5 % (Wahrscheinlichkeit, dass ihr Sharpe nach Korrektur für die Anzahl der Versuche über null liegt).
- Walk-Forward: Sharpe in-sample im Schnitt 1.37, out-of-sample 0.67.
- Affentest Kernregel: besser als 96,7 % von 1000 Zufallsstrategien mit gleicher Marktquote und Handelsfrequenz.
- Sharpe-Differenz Kernregel minus Buy & Hold: +0.13, 95 %-KI [-0.24; +0.52] (Block-Bootstrap).
- White Reality Check (beste der 49 Regeln schlägt Buy & Hold nur durch Glück?): p = 0.51.

| Jahrzehnt | Sharpe B&H | Sharpe Kernregel | CAGR B&H | CAGR Kernregel | MaxDD B&H | MaxDD Kernregel |
|---|---:|---:|---:|---:|---:|---:|
| 2010er | 1.35 | 1.66 | 115,8 % | 149,4 % | -83,8 % | -64,9 % |
| 2020er | 0.86 | 0.84 | 43,5 % | 34,8 % | -76,7 % | -53,9 % |

**Reibung (Kernregel):** 0 bps/Delay 0: 64,7 %, 0 bps/Delay 1: 69,8 %, 5 bps/Delay 0: 64,1 %, 5 bps/Delay 1: 69,2 %, 10 bps/Delay 0: 63,6 %, 10 bps/Delay 1: 68,6 %, 25 bps/Delay 0: 61,9 %, 25 bps/Delay 1: 66,9 %, 50 bps/Delay 0: 59,1 %, 50 bps/Delay 1: 64,0 %

**Nach deutscher Steuer** (Krypto privat (§ 23 EStG)): Buy & Hold 65,4 % -> 65,4 %, Kernregel 66,9 % -> 59,0 % p.a.

## S&P 500 Total Return (monatlich)

_Shiller-Daten, Dividenden reinvestiert. Für die letzten 39 Monate fehlt die Dividende in der Quelle, dort wird die letzte bekannte Dividendenrendite fortgeschrieben. Monatsdurchschnittskurse, keine Monatsschlusskurse. Cash = 3M T-Bill (TB3MS)._

Kosten 5.0 bps je Seite, Ausführung mit 1 Periode(n) Verzögerung.

| Strategie | Zeitraum | CAGR | Vol | Sharpe | Max DD | Zeit im Markt | Trades/J |
|---|---|---:|---:|---:|---:|---:|---:|
| Buy & Hold | 1936-2026 | 10,9 % | 12,7 % | 0.61 | -49,0 % | 100,0 % | 0.0 |
| SMA10 (vorab festgelegt) | 1936-2026 | 9,5 % | 9,7 % | 0.64 | -53,6 % | 74,4 % | 1.1 |
| SMA10 + Vol-Target 15 % | 1936-2026 | 9,2 % | 9,4 % | 0.62 | -52,7 % | 72,6 % | 1.4 |
| Bester von 27 (SMA7) | 1936-2026 | 10,0 % | 9,3 % | 0.70 | -33,3 % | 72,6 % | 1.7 |
| Walk-Forward (out of sample) | 1946-2026 | 10,3 % | 9,6 % | 0.67 | -26,0 % | | |
| Buy & Hold im WF-Fenster | | 11,2 % | | 0.63 | -49,0 % | | |

**Glück oder Können?**

- 27 Regeln getestet. Beste: SMA7 mit Sharpe 0.70 (Buy & Hold 0.61).
- Deflated Sharpe Ratio der besten Regel: 100,0 % (Wahrscheinlichkeit, dass ihr Sharpe nach Korrektur für die Anzahl der Versuche über null liegt).
- Walk-Forward: Sharpe in-sample im Schnitt 0.89, out-of-sample 0.81.
- Affentest Kernregel: besser als 94,6 % von 1000 Zufallsstrategien mit gleicher Marktquote und Handelsfrequenz.
- Sharpe-Differenz Kernregel minus Buy & Hold: +0.02, 95 %-KI [-0.15; +0.22] (Block-Bootstrap).
- White Reality Check (beste der 27 Regeln schlägt Buy & Hold nur durch Glück?): p = 0.50.

| Jahrzehnt | Sharpe B&H | Sharpe Kernregel | CAGR B&H | CAGR Kernregel | MaxDD B&H | MaxDD Kernregel |
|---|---:|---:|---:|---:|---:|---:|
| 1930er | 0.10 | -0.20 | 0,1 % | -3,7 % | -41,6 % | -31,9 % |
| 1940er | 0.68 | 0.34 | 8,9 % | 3,7 % | -26,5 % | -32,8 % |
| 1950er | 1.60 | 1.49 | 19,3 % | 17,4 % | -15,7 % | -17,5 % |
| 1960er | 0.40 | 0.25 | 7,8 % | 5,7 % | -21,2 % | -12,2 % |
| 1970er | 0.03 | 0.24 | 5,8 % | 8,1 % | -39,2 % | -11,6 % |
| 1980er | 0.64 | 0.63 | 17,3 % | 15,7 % | -26,0 % | -25,0 % |
| 1990er | 1.19 | 0.96 | 18,0 % | 14,0 % | -13,9 % | -11,9 % |
| 2000er | -0.15 | 0.68 | -0,7 % | 7,4 % | -49,0 % | -7,0 % |
| 2010er | 1.30 | 0.85 | 13,3 % | 8,0 % | -11,7 % | -14,1 % |
| 2020er | 0.95 | 0.85 | 15,8 % | 12,7 % | -19,3 % | -18,9 % |

**Reibung (Kernregel):** 0 bps/Delay 0: 11,5 %, 0 bps/Delay 1: 9,6 %, 5 bps/Delay 0: 11,4 %, 5 bps/Delay 1: 9,5 %, 10 bps/Delay 0: 11,4 %, 10 bps/Delay 1: 9,4 %, 25 bps/Delay 0: 11,2 %, 25 bps/Delay 1: 9,2 %, 50 bps/Delay 0: 10,9 %, 50 bps/Delay 1: 8,9 %

**Nach deutscher Steuer** (Aktien-ETF (Abgeltungsteuer, Teilfreistellung)): Buy & Hold 10,9 % -> 10,6 %, Kernregel 9,5 % -> 7,8 % p.a.
