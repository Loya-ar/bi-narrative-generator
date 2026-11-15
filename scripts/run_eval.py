"""
Measure how many numbers in generated reports are supported by the analysis.

For each sample dataset and report style it records:
  baseline     the original approach: plain prompt, no fact sheet, no JSON
  first draft  with the fact sheet and JSON claims
  final        after the one correction pass (what the app shows)
and writes evaluation/results.csv, evaluation/summary.md and evaluation/examples/.

Needs GEMINI_API_KEY in .env. Use a free-tier key (no billing linked); requests are
paced to 5 a minute to stay under the free limits.

    python scripts/run_eval.py
    python scripts/run_eval.py --datasets sales_performance_2023.csv --styles executive_summary:executive
"""

import argparse
import csv
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from data_processor import AdvancedDataProcessor  # noqa: E402
from fact_check import build_fact_sheet, check_report  # noqa: E402
from narrative_generator import NarrativeGenerator  # noqa: E402
from prompt_engine import DynamicPromptEngine  # noqa: E402

SAMPLES = ROOT / "data" / "sample_datasets"
OUT = ROOT / "evaluation"
DATASETS = [  # sales_sample.csv is a 20-row slice of sales_performance_2023.csv, so it's left out
    "sales_performance_2023.csv", "sales_data.csv", "marketing_campaigns_2023.csv",
    "marketing_performance_2023.csv", "marketing_data.csv",
    "financial_kpis_2022_2023.csv", "financial_performance_2022_2023.csv",
]
STYLES = ["executive_summary:executive", "detailed_analysis:analyst"]


class Paced:
    """Wraps NarrativeGenerator._call so requests stay under `per_minute`."""

    def __init__(self, call, per_minute):
        self.call, self.gap, self.last, self.count = call, 60.0 / per_minute, 0.0, 0

    def __call__(self, prompt, structured):
        wait = self.last + self.gap - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        self.last = time.monotonic()
        self.count += 1
        return self.call(prompt, structured)


def merge_with_previous(rows, fields):
    """Keep earlier results for dataset/style pairs not run this time (so one case can be re-run)."""
    path = OUT / "results.csv"
    if not path.exists():
        return rows
    done = {(r["dataset"], r["style"]) for r in rows}
    numeric = {f for f in fields if f.endswith(("_checked", "_total", "_pct")) or f in ("facts", "claims", "words", "seconds")}
    previous = []
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if (r["dataset"], r["style"]) in done:
                continue
            for k in numeric:
                if r.get(k) not in (None, ""):
                    r[k] = float(r[k]) if k in ("seconds",) or k.endswith("_pct") else int(float(r[k]))
            r["auto_fixed"] = r.get("auto_fixed") == "True"
            previous.append(r)
    order = {(d, s.split(":")[0]): i for i, (d, s) in enumerate((d, s) for d in DATASETS for s in STYLES)}
    return sorted(previous + rows, key=lambda r: order.get((r["dataset"], r["style"]), len(order)))


def pct(checked, total):
    return round(100 * checked / total, 1) if total else None


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--datasets", nargs="*", default=DATASETS)
    parser.add_argument("--styles", nargs="*", default=STYLES, help="style:audience pairs")
    parser.add_argument("--per-minute", type=float, default=5)
    args = parser.parse_args()

    gen = NarrativeGenerator()
    if not gen.api_available:
        raise SystemExit("No Gemini key found: add GEMINI_API_KEY to .env")
    paced = Paced(gen._call, args.per_minute)
    gen._call = paced
    engine = DynamicPromptEngine()
    (OUT / "examples").mkdir(parents=True, exist_ok=True)

    rows = []
    for name in args.datasets:
        analysis = AdvancedDataProcessor().load_and_analyze_data(str(SAMPLES / name))
        facts = build_fact_sheet(analysis)
        for pair in args.styles:
            style, audience = pair.split(":")
            label = f"{name} / {style} / {audience}"
            print(f"[{len(rows) + 1}] {label}", flush=True)
            prompt = engine.generate_dynamic_prompt(analysis, style, audience)
            row = {"dataset": name, "style": style, "audience": audience, "facts": len(facts)}
            try:
                baseline_text, _ = paced(prompt, structured=False)
                base = check_report(baseline_text, facts)
                row.update(baseline_checked=base.checked, baseline_total=base.total,
                           baseline_pct=pct(base.checked, base.total))
            except Exception as e:  # rate limit or outage: record it and move on
                row.update(error=f"baseline: {str(e)[:120]}")
                rows.append(row)
                continue

            result = gen.generate_narrative(prompt, style, analysis=analysis)
            if result.get("api_status") != "success":
                row.update(error=f"generation: {result.get('api_error', '')[:120]}")
                rows.append(row)
                continue
            first, final = result["number_check_first_draft"], result["number_check"]
            row.update(
                first_checked=first.checked, first_total=first.total, first_pct=pct(first.checked, first.total),
                final_checked=final.checked, final_total=final.total, final_pct=pct(final.checked, final.total),
                auto_fixed=result["auto_fixed"], claims=len(result["claims"]), words=result["word_count"],
                seconds=round(result["generation_time"], 1), error="",
            )
            rows.append(row)
            problems = "\n".join(f"- `{n.text}`: {n.note}" for n in final.problems) or "- none"
            (OUT / "examples" / f"{Path(name).stem}__{style}.md").write_text(
                f"<!-- {label}; numbers checked: {final.checked}/{final.total}; "
                f"first draft {first.checked}/{first.total}; auto-fixed: {result['auto_fixed']} -->\n\n"
                f"{result['narrative']}\n\n---\n\n**Unsupported numbers:**\n{problems}\n",
                encoding="utf-8")
            print(f"    baseline {row['baseline_checked']}/{row['baseline_total']}  "
                  f"first {first.checked}/{first.total}  final {final.checked}/{final.total}", flush=True)

    fields = ["dataset", "style", "audience", "facts", "baseline_checked", "baseline_total", "baseline_pct",
              "first_checked", "first_total", "first_pct", "final_checked", "final_total", "final_pct",
              "auto_fixed", "claims", "words", "seconds", "error"]
    rows = merge_with_previous(rows, fields)
    with open(OUT / "results.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    ok = [r for r in rows if not r.get("error")]

    def total(prefix):
        checked = sum(r[f"{prefix}_checked"] for r in ok)
        numbers = sum(r[f"{prefix}_total"] for r in ok)
        return checked, numbers, pct(checked, numbers)

    lines = [
        "# Evaluation results", "",
        f"Model: `{gen.model_name}` (free tier). {len(ok)} of {len(rows)} reports generated.", "",
        "| Version | Numbers supported by the analysis | Share |", "|---|---|---|",
    ]
    for prefix, title in [("baseline", "Baseline: plain prompt, no fact sheet (the original app)"),
                          ("first", "With fact sheet and JSON claims, first draft"),
                          ("final", "After the correction pass (what the app shows)")]:
        c, n, p = total(prefix)
        lines.append(f"| {title} | {c} / {n} | {p}% |")
    lines += ["", f"Correction pass used in {sum(bool(r['auto_fixed']) for r in ok)} of {len(ok)} reports.", "",
              "| Dataset | Style | Baseline | First draft | Final |", "|---|---|---|---|---|"]
    for r in rows:
        if r.get("error"):
            lines.append(f"| {r['dataset']} | {r['style']} | error: {r['error'][:60]} | | |")
        else:
            lines.append(f"| {r['dataset']} | {r['style']} | {r['baseline_checked']}/{r['baseline_total']} | "
                         f"{r['first_checked']}/{r['first_total']} | {r['final_checked']}/{r['final_total']} |")
    (OUT / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
