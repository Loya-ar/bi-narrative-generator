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
            return f"{self.value:+.1f}%" if "change" in self.id else f"{self.value:.1f}%"
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

    for metric, t in (analysis.get("trends") or {}).items():
        if not isinstance(t, dict) or "total_change_percent" not in t:
            continue
        name = _pretty(metric)
        span = "first to last month" if t.get("period") == "month" else "start to end of file"
        money = "$" if t.get("is_currency") else ""
        add(f"trend.{metric}.change_pct", f"{name}: change, {span}", t.get("total_change_percent"), "%")
        add(f"trend.{metric}.latest", f"{name}: latest value", t.get("current_value"), money)
        add(f"trend.{metric}.average", f"{name}: average value", t.get("average_value"), money)
        add(f"trend.{metric}.r_squared", f"{name}: trend fit (R squared, 0-1)", t.get("r_squared"))

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
