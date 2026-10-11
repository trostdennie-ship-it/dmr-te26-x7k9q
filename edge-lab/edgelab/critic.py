"""Optional LLM red-team review of a finished study (Claude via the Anthropic SDK).

The model gets the study JSON and is asked to attack it: biases, data problems,
overfitting, what would falsify the result. It never sees an order interface
and never sets an exposure; its output is a text report for a human.
Needs ANTHROPIC_API_KEY (or an `ant auth login` profile).
"""
from __future__ import annotations

import json
from pathlib import Path

MODEL = "claude-opus-5-5"

SYSTEM = """You are a skeptical quantitative researcher reviewing a backtest study \
for a private investor in Germany. Your job is to find reasons the results could be \
wrong or not transferable, not to cheerlead. Check specifically: look-ahead bias, \
survivorship and index-construction bias, price vs. total-return data, execution \
timing, transaction costs, taxes, multiple testing (use the reported number of \
trials and the deflated Sharpe ratio), regime dependence, and sample size. \
Separate what the numbers show from what you infer. Do not give buy or sell \
recommendations. Write in German, concise, with a ranked list of the three biggest \
risks to the conclusion and one concrete next experiment that could falsify it."""


def review(study_path: str | Path, out_path: str | Path | None = None) -> str:
    import anthropic

    study = json.loads(Path(study_path).read_text())
    for m in study.get("markets", {}).values():
        m.pop("series", None)  # charts are not needed for the review
    client = anthropic.Anthropic()
    try:
        response = client.beta.messages.create(
            model=MODEL,
            max_tokens=16000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            output_config={"effort": "high"},
            system=SYSTEM,
            messages=[{"role": "user", "content":
                       "<study>\n" + json.dumps(study, ensure_ascii=False) + "\n</study>\n"
                       "Review this study."}],
        )
    except anthropic.AuthenticationError:
        raise SystemExit("No valid Anthropic credentials (ANTHROPIC_API_KEY or `ant auth login`).")
    except anthropic.RateLimitError:
        raise SystemExit("Rate limited by the Anthropic API, try again later.")
    except anthropic.APIConnectionError:
        raise SystemExit("Could not reach the Anthropic API.")

    if response.stop_reason == "refusal":
        raise SystemExit("The review request was declined by the model.")
    text = "".join(b.text for b in response.content if b.type == "text")
    if out_path:
        Path(out_path).write_text(text)
    return text


if __name__ == "__main__":
    import sys

    root = Path(__file__).resolve().parent.parent
    print(review(sys.argv[1] if len(sys.argv) > 1 else root / "reports" / "study.json",
                 root / "reports" / "critic.md"))
