"""Market data: versioned CSV snapshots in data/, refreshable from public sources.

Every series is loaded point-in-time friendly: one value per date, no forward
looking adjustments. What each series is (and is not) is stated in Market.note.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}&cosd=1900-01-01"
SHILLER_URL = "https://raw.githubusercontent.com/datasets/s-and-p-500/main/data/data.csv"


@dataclass(frozen=True)
class Market:
    name: str
    prices: pd.Series          # close (or total return index), indexed by date
    rf_annual: pd.Series       # cash yield, decimal p.a., aligned to prices
    periods_per_year: int
    total_return: bool         # True if prices include reinvested dividends
    note: str

    @property
    def returns(self) -> pd.Series:
        return self.prices.pct_change()

    @property
    def rf_period(self) -> pd.Series:
        return (1 + self.rf_annual) ** (1 / self.periods_per_year) - 1

    def slice(self, start=None, end=None) -> "Market":
        p = self.prices.loc[start:end]
        return Market(self.name, p, self.rf_annual.loc[p.index], self.periods_per_year,
                      self.total_return, self.note)


# ---------------------------------------------------------------- refresh

def refresh(series=("NASDAQCOM", "CBBTCUSD", "DTB3", "TB3MS")) -> dict:
    """Download fresh snapshots and record them in data/MANIFEST.json."""
    import requests

    manifest = {}
    targets = {f"fred_{s}.csv": FRED_URL.format(sid=s) for s in series}
    targets["shiller_sp500_monthly.csv"] = SHILLER_URL
    for fname, url in targets.items():
        r = requests.get(url, timeout=60)
        r.raise_for_status()
        (DATA_DIR / fname).write_bytes(r.content)
    for fname, url in targets.items():
        manifest[fname] = _manifest_entry(fname, url)
    (DATA_DIR / "MANIFEST.json").write_text(json.dumps(manifest, indent=2))
    return manifest


def _manifest_entry(fname: str, url: str) -> dict:
    raw = (DATA_DIR / fname).read_bytes()
    lines = raw.decode().strip().splitlines()
    return {
        "source": url,
        "retrieved_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "rows": len(lines) - 1,
        "first": lines[1].split(",")[0],
        "last": lines[-1].split(",")[0],
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


# ---------------------------------------------------------------- loaders

def load_fred(series_id: str) -> pd.Series:
    df = pd.read_csv(DATA_DIR / f"fred_{series_id}.csv", na_values=["."])
    s = df.set_index(pd.to_datetime(df.iloc[:, 0])).iloc[:, 1].astype(float).dropna()
    s.index.name = "date"
    s.name = series_id
    return s


def _align_rf(index: pd.DatetimeIndex, rf_pct: pd.Series) -> pd.Series:
    # T-bill yield known on day t is used for day t; gaps (holidays) forward-filled only.
    rf = rf_pct.reindex(rf_pct.index.union(index)).ffill().reindex(index)
    return (rf / 100.0).fillna(0.0).rename("rf")


def nasdaq() -> Market:
    p = load_fred("NASDAQCOM")
    return Market(
        "NASDAQ Composite (täglich)", p, _align_rf(p.index, load_fred("DTB3")), 252, False,
        "Preisindex ohne Dividenden (FRED NASDAQCOM). Buy & Hold ist dadurch um ca. "
        "0,7-1 % p.a. unterschätzt, das bevorzugt Timing-Strategien. Cash = 3M T-Bill.",
    )


def bitcoin() -> Market:
    p = load_fred("CBBTCUSD")
    return Market(
        "Bitcoin / USD (täglich, Coinbase)", p, _align_rf(p.index, load_fred("DTB3")), 365, True,
        "Coinbase-Schlusskurs (FRED CBBTCUSD), 7 Handelstage/Woche. Cash = 3M T-Bill.",
    )


def sp500_monthly(start: str = "1934-01-01") -> Market:
    """Shiller S&P 500 composite with dividends reinvested, monthly.

    The source leaves the most recent dividends at 0; for those months the last
    known dividend yield is carried forward (stated in the note)."""
    df = pd.read_csv(DATA_DIR / "shiller_sp500_monthly.csv", parse_dates=["Date"]).set_index("Date")
    price = df["SP500"].astype(float)
    div = df["Dividend"].astype(float).replace(0.0, np.nan)
    dy = (div / price).ffill()
    n_filled = int(df["Dividend"].eq(0).sum())
    tr = (price + dy * price / 12).div(price.shift(1)).fillna(1.0).cumprod()
    tr = tr.loc[start:]
    tr = tr / tr.iloc[0] * 100
    tr.index.name = "date"
    rf = _align_rf(tr.index, load_fred("TB3MS"))
    return Market(
        "S&P 500 Total Return (monatlich)", tr.rename("SP500TR"), rf, 12, True,
        f"Shiller-Daten, Dividenden reinvestiert. Für die letzten {n_filled} Monate fehlt die "
        "Dividende in der Quelle, dort wird die letzte bekannte Dividendenrendite fortgeschrieben. "
        "Monatsdurchschnittskurse, keine Monatsschlusskurse. Cash = 3M T-Bill (TB3MS).",
    )


MARKETS = {"nasdaq": nasdaq, "bitcoin": bitcoin, "sp500_monthly": sp500_monthly}
