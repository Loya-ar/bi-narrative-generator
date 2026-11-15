"""
Number checking for generated reports.

1. `build_fact_sheet` turns the analysis into numbered facts (id, label, value, unit).
   These are the only numbers the model is allowed to use.
2. `check_report` finds every number in the report text and checks it against the
   facts, allowing for rounding, percent scaling and K/M/B suffixes. Numbers the
   model declared as claims are also checked against the fact they cite.
3. `highlight` marks each number green (checked) or red (wrong or unsupported).

Years (1990-2035) and small integers (0-10, e.g. list numbering) are not counted.
"""

from __future__ import annotations

import html
import math
import re
from dataclasses import dataclass, field

_NUMBER = re.compile(
    r"(?<![\w.])(?P<sign>[-+−])?(?P<cur>\$)?"
    r"(?P<num>\d{1,3}(?:,\d{3})+|\d+)(?P<frac>\.\d+)?"
    r"\s?(?P<suffix>%|[kKmMbB](?![a-zA-Z])|pp\b|percentage points)?"
)
_SCALE = {"k": 1e3, "m": 1e6, "b": 1e9}


@dataclass
class Fact:
    id: str
    label: str
    value: float
    unit: str = ""  # "%", "$" or ""

    def shown(self) -> str:
        if self.unit == "%":
            signed = any(w in self.id for w in ("change", "mom", "yoy", "deviation"))
            return f"{self.value:+.1f}%" if signed else f"{self.value:.1f}%"
        if self.unit == "$":
            return f"${self.value:,.2f}"
        if float(self.value).is_integer():
            return f"{self.value:,.0f}"
        return f"{self.value:,.4g}" if abs(self.value) < 10 else f"{self.value:,.2f}"


@dataclass
class NumberCheck:
    text: str          # as written, e.g. "$1.2M"
    start: int
    end: int
    value: float       # parsed, e.g. 1200000.0
    status: str        # "checked", "unsupported" or "wrong"
    fact_id: str | None = None
    note: str = ""


@dataclass
class CheckResult:
    numbers: list[NumberCheck] = field(default_factory=list)

    @property
    def checked(self) -> int:
        return sum(n.status == "checked" for n in self.numbers)

    @property
    def total(self) -> int:
        return len(self.numbers)

    @property
    def problems(self) -> list[NumberCheck]:
        return [n for n in self.numbers if n.status != "checked"]

    @property
    def score(self) -> float | None:
        """Share of numbers checked, 0-100; None when the report has no numbers."""
        return round(100 * self.checked / self.total, 1) if self.total else None


# ---------- fact sheet ----------

def _num(x) -> float | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _pretty(name: str) -> str:
    return str(name).replace("_", " ").strip().title()


def _slug(name) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(name).lower()).strip("_")


def build_fact_sheet(analysis: dict) -> list[Fact]:
    """Every number the analysis computed, with a stable id and a readable label."""
    facts: list[Fact] = []

    def add(fid, label, value, unit=""):
        v = _num(value)
        if v is not None:
            facts.append(Fact(fid, label, v, unit))

    meta = analysis.get("metadata", {})
    add("meta.rows", "Records in the dataset", meta.get("total_rows"))
    add("meta.columns", "Columns in the dataset", meta.get("total_columns"))
    add("meta.data_quality", "Data quality score (0-100)", meta.get("data_quality_score"))

    trends = analysis.get("trends") or {}

    def money_unit(metric):
        t = trends.get(metric) or {}
        return "$" if t.get("is_currency") else ""

    def how(metric, agg=None):
        agg = agg or (trends.get(metric) or {}).get("aggregation")
        return {"sum": "monthly total", "mean": "monthly average"}.get(agg, "value")

    for metric, t in trends.items():
        if not isinstance(t, dict) or "total_change_percent" not in t:
            continue
        name = _pretty(metric)
        span = "first to last month" if t.get("period") == "month" else "start to end of file"
        money = money_unit(metric)
        add(f"trend.{metric}.change_pct", f"{name}: change, {span}", t.get("total_change_percent"), "%")
        add(f"trend.{metric}.latest", f"{name}: latest {how(metric)}", t.get("current_value"), money)
        average_label = "average of the monthly averages" if how(metric) == "monthly average" else f"average {how(metric)}"
        add(f"trend.{metric}.average", f"{name}: {average_label}", t.get("average_value"), money)
        add(f"trend.{metric}.r_squared", f"{name}: trend fit (R squared, 0-1)", t.get("r_squared"))
        add(f"trend.{metric}.p_value", f"{name}: trend p-value (below 0.05 = statistically clear)", t.get("p_value"))

    for metric, c in (analysis.get("period_comparisons") or {}).items():
        name, money, kind = _pretty(metric), money_unit(metric), how(metric, c.get("aggregation"))
        add(f"cmp.{metric}.latest", f"{name}: {kind}, {c.get('latest_period')}", c.get("latest_value"), money)
        add(f"cmp.{metric}.previous", f"{name}: {kind}, {c.get('previous_period')}", c.get("previous_value"), money)
        add(f"cmp.{metric}.mom_pct", f"{name}: change {c.get('previous_period')} to {c.get('latest_period')}",
            c.get("mom_change_pct"), "%")
        if c.get("yoy_period"):
            add(f"cmp.{metric}.yoy_value", f"{name}: {kind}, {c.get('yoy_period')}", c.get("yoy_value"), money)
            add(f"cmp.{metric}.yoy_pct", f"{name}: change {c.get('yoy_period')} to {c.get('latest_period')} "
                                         "(year over year)", c.get("yoy_change_pct"), "%")

    for dim, d in (analysis.get("drivers") or {}).items():
        measure, span = _pretty(d.get("measure")), f"{d.get('from_period')} to {d.get('to_period')}"
        money = money_unit(d.get("measure"))
        add(f"driver.{dim}.total_change", f"{measure}: total change, {span}", d.get("total_change"), money)
        add(f"driver.{dim}.total_change_pct", f"{measure}: % change, {span}", d.get("total_change_pct"), "%")
        for s in d.get("segments") or []:
            seg = _slug(s.get("segment"))
            add(f"driver.{dim}.{seg}.change", f"{measure} change from {_pretty(dim)} = {s.get('segment')}, {span}",
                s.get("change"), money)
            add(f"driver.{dim}.{seg}.share_pct",
                f"Share of the {measure} change from {_pretty(dim)} = {s.get('segment')}", s.get("share_of_change_pct"), "%")

    for a in analysis.get("anomalies") or []:
        metric, period = a.get("measure"), a.get("period")
        name, money = _pretty(metric), money_unit(metric)
        add(f"anomaly.{metric}.{period}.value", f"{name}: unusual month {period}, value", a.get("value"), money)
        add(f"anomaly.{metric}.{period}.typical", f"{name}: typical month (median)", a.get("typical_value"), money)
        add(f"anomaly.{metric}.{period}.deviation_pct", f"{name}: {period} vs typical month",
            a.get("deviation_pct"), "%")

    for kpi, value in (analysis.get("kpis") or {}).items():
        money = "$" if any(w in kpi.lower() for w in ("sales", "revenue", "amount", "cost", "profit", "spend")) \
            and "ratio" not in kpi.lower() else ""
        add(f"kpi.{kpi}", _pretty(kpi), value, money)

    corr = (analysis.get("correlations") or {}).get("summary") or {}
    add("corr.strongest", "Strongest correlation between two measures", _strongest_pair(analysis))
    add("corr.average", "Average absolute correlation", corr.get("avg_correlation"))
    return facts


def _strongest_pair(analysis: dict):
    matrix = (analysis.get("correlations") or {}).get("matrix") or {}
    best = None
    for a, row in matrix.items():
        for b, v in row.items():
            v = _num(v)
            if a != b and v is not None and (best is None or abs(v) > abs(best)):
                best = v
    return best


def fact_sheet_text(facts: list[Fact]) -> str:
    return "\n".join(f"- [{f.id}] {f.label}: {f.shown()}" for f in facts)


# ---------- finding and matching numbers ----------

def find_numbers(text: str) -> list[tuple[str, int, int, float, int, str]]:
    """(as written, start, end, value, decimals shown, suffix) for each counted number."""
    out = []
    for m in _NUMBER.finditer(text or ""):
        num, frac = m.group("num"), m.group("frac") or ""
        suffix = (m.group("suffix") or "").lower()
        value = float(num.replace(",", "") + frac)
        decimals = len(frac) - 1 if frac else 0
        if suffix in _SCALE:
            value *= _SCALE[suffix]
            decimals -= int(round(math.log10(_SCALE[suffix])))
        if m.group("sign") in ("-", "−"):
            value = -value
        plain_int = not frac and not suffix and not m.group("cur") and "," not in num
        if plain_int and (abs(value) <= 10 or 1990 <= value <= 2035):
            continue  # list numbers, "top 3", years
        out.append((m.group(0).strip(), m.start(), m.start() + len(m.group(0).rstrip()), value, decimals, suffix))
    return out


def matches(value: float, decimals: int, target: float, percent: bool = False) -> bool:
    """`value` as written could be `target` rounded to the decimals shown.

    A fraction may be written as a percent (0.65 -> "65%"). Signs are ignored,
    because "fell 12%" is usually written without a minus.
    """
    tol = 0.5 * 10 ** (-decimals) + 1e-9
    targets = [target, target * 100] if percent or abs(target) <= 1 else [target]
    return any(abs(abs(value) - abs(t)) <= tol for t in targets)


def check_report(text: str, facts: list[Fact], claims: list[dict] | None = None) -> CheckResult:
    """Check every number in the report against the fact sheet."""
    by_id = {f.id: f for f in facts}
    claimed = {}
    for c in claims or []:
        v = _num(c.get("value"))
        if v is not None and c.get("fact_id"):
            claimed.setdefault(round(v, 6), []).append(c["fact_id"])

    result = CheckResult()
    for written, start, end, value, decimals, suffix in find_numbers(text):
        percent = suffix in ("%", "pp", "percentage points")
        cited = claimed.get(round(value, 6)) or claimed.get(round(-value, 6)) or []
        cited_facts = [by_id[i] for i in cited if i in by_id]
        unknown = [i for i in cited if i not in by_id]

        hit = next((f for f in cited_facts if matches(value, decimals, f.value, percent)), None)
        if hit is None:
            hit = next((f for f in facts if matches(value, decimals, f.value, percent)), None)

        if hit is not None:
            result.numbers.append(NumberCheck(written, start, end, value, "checked", hit.id))
        elif cited_facts:
            f = cited_facts[0]
            result.numbers.append(NumberCheck(written, start, end, value, "wrong", f.id,
                                              f"cites {f.id}, whose value is {f.shown()}"))
        else:
            note = f"cites unknown fact {unknown[0]}" if unknown else "not in the analysis"
            result.numbers.append(NumberCheck(written, start, end, value, "unsupported", None, note))
    return result


def fix_request(result: CheckResult, facts: list[Fact]) -> str:
    """Instructions for one correction pass, listing each bad number."""
    lines = []
    for n in result.problems:
        lines.append(f'- "{n.text}": {n.note}')
    return (
        "Some numbers in your report are not supported by the fact sheet:\n" + "\n".join(lines) +
        "\n\nRewrite the report so every number comes from the fact sheet below (rounding is fine). "
        "Remove any number you can't support. Keep the same structure and length.\n\nFACT SHEET:\n" +
        fact_sheet_text(facts)
    )


# ---------- display ----------

def highlight(text: str, result: CheckResult) -> str:
    """Markdown with each number wrapped in a green or red span (for st.markdown(unsafe_allow_html=True))."""
    out, pos = [], 0
    for n in sorted(result.numbers, key=lambda n: n.start):
        out.append(text[pos:n.start])
        ok = n.status == "checked"
        color, bg = ("#065f46", "#d1fae5") if ok else ("#991b1b", "#fee2e2")
        title = html.escape(f"checked against {n.fact_id}" if ok else n.note, quote=True)
        out.append(f'<span title="{title}" style="color:{color};background:{bg};'
                   f'padding:0 3px;border-radius:4px;font-weight:600">{html.escape(n.text)}</span>')
        pos = n.end
    out.append(text[pos:])
    return "".join(out)
