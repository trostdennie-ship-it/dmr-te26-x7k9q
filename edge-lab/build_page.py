"""Render reports/edge-lab.html from reports/study.json and the ledger."""
import json
from pathlib import Path

from edgelab import ledger

ROOT = Path(__file__).resolve().parent
study = json.loads((ROOT / "reports" / "study.json").read_text())
entries = ledger.read(ROOT / "ledger" / "ledger.jsonl")
for m in study["markets"].values():
    m.pop("wf_series", None)
    m.pop("wf_picks", None)
html = (ROOT / "reports" / "template.html").read_text()
html = html.replace("__STUDY__", json.dumps(study, ensure_ascii=False, separators=(",", ":")))
html = html.replace("__LEDGER__", json.dumps(entries, ensure_ascii=False, separators=(",", ":")))
(ROOT / "reports" / "edge-lab.html").write_text(html)
print(f"wrote reports/edge-lab.html ({len(html) / 1024:.0f} KB)")
