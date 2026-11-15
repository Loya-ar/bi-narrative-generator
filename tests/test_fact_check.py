"""Tests for the number checker and the generator's correction pass (no API key or network)."""

import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from data_processor import AdvancedDataProcessor  # noqa: E402
from fact_check import (  # noqa: E402
    Fact, build_fact_sheet, check_report, fact_sheet_text, find_numbers, fix_request, highlight, matches,
)
from narrative_generator import NarrativeGenerator  # noqa: E402

SAMPLES = ROOT / "data" / "sample_datasets"

FACTS = [
    Fact("meta.rows", "Records in the dataset", 1250),
    Fact("trend.revenue.change_pct", "Revenue: change, first to last month", 12.3456, "%"),
    Fact("trend.revenue.latest", "Revenue: latest value", 1_234_567.0, "$"),
    Fact("trend.revenue.r_squared", "Revenue: trend fit", 0.6512),
]


@pytest.fixture(scope="module")
def sales_analysis():
    return AdvancedDataProcessor().load_and_analyze_data(str(SAMPLES / "sales_performance_2023.csv"))


# ---------- fact sheet ----------

def test_fact_sheet_covers_the_analysis(sales_analysis):
    facts = {f.id: f for f in build_fact_sheet(sales_analysis)}
    df = pd.read_csv(SAMPLES / "sales_performance_2023.csv")
    assert facts["meta.rows"].value == len(df)
    for metric in sales_analysis["trends"]:
        assert f"trend.{metric}.change_pct" in facts
        assert facts[f"trend.{metric}.change_pct"].unit == "%"
    assert all(f"kpi.{k}" in facts for k in sales_analysis["kpis"])


def test_fact_sheet_text_lists_ids():
    text = fact_sheet_text(FACTS)
    assert "[trend.revenue.change_pct]" in text and "+12.3%" in text and "$1,234,567.00" in text


# ---------- finding numbers ----------

def test_find_numbers_parses_formats():
    found = {w: (v, d) for w, _, _, v, d, _ in find_numbers(
        "Revenue was $1.2M, up 12.3% on 4,567 orders; costs fell -5% and 0.65 fit.")}
    assert found["$1.2M"][0] == pytest.approx(1_200_000)
    assert found["12.3%"] == (12.3, 1)
    assert found["4,567"][0] == 4567
    assert found["-5%"][0] == -5
    assert found["0.65"] == (0.65, 2)


def test_years_and_list_numbers_are_ignored():
    found = [w for w, *_ in find_numbers("## 1. Summary\nIn 2023 the top 3 regions grew 15%.")]
    assert found == ["15%"]


def test_matches_rounding_percent_and_sign():
    assert matches(12.3, 1, 12.3456)
    assert matches(12.0, 0, 12.3456)
    assert not matches(12.5, 1, 12.3456)
    assert matches(65.0, 0, 0.6512, percent=True)
    assert matches(12.3, 1, -12.3456)  # "fell 12.3%"
    assert matches(1_200_000, -5, 1_234_567)  # "$1.2M"


# ---------- checking a report ----------

def test_correct_report_is_fully_checked():
    text = "We had 1,250 records. Revenue rose 12.3% to $1.23M; the fit was 65%."
    result = check_report(text, FACTS)
    assert (result.checked, result.total, result.score) == (4, 4, 100.0)
    assert not result.problems


def test_invented_number_is_unsupported():
    result = check_report("Revenue rose 12.3%, beating the 15% target.", FACTS)
    assert result.total == 2
    [bad] = result.problems
    assert bad.text == "15%" and bad.status == "unsupported"
    assert result.score == 50.0


def test_claim_citing_wrong_value_is_wrong():
    claims = [{"text": "Revenue rose 18%", "value": 18, "fact_id": "trend.revenue.change_pct"}]
    [bad] = check_report("Revenue rose 18%.", FACTS, claims).problems
    assert bad.status == "wrong"
    assert "trend.revenue.change_pct" in bad.note and "+12.3%" in bad.note


def test_claim_citing_unknown_fact():
    claims = [{"text": "x", "value": 42, "fact_id": "kpi.made_up"}]
    [bad] = check_report("Margin was 42%.", FACTS, claims).problems
    assert bad.status == "unsupported" and "kpi.made_up" in bad.note


def test_report_without_numbers_has_no_score():
    assert check_report("Strong momentum across regions.", FACTS).score is None


def test_highlight_marks_each_number():
    text = "Revenue rose 12.3%, beating the 15% target <b>."
    out = highlight(text, check_report(text, FACTS))
    assert out.count("<span") == 2
    assert "#d1fae5" in out and "#fee2e2" in out  # one green, one red
    assert "&lt;b&gt;" not in out  # only the numbers are replaced; the rest is untouched
    assert out.endswith("target <b>.")


def test_fix_request_lists_problems_and_facts():
    result = check_report("Revenue rose 12.3%, beating the 15% target.", FACTS)
    req = fix_request(result, FACTS)
    assert '"15%": not in the analysis' in req
    assert "[meta.rows]" in req


# ---------- generator: one correction pass ----------

class FakeCalls:
    def __init__(self, *outputs):
        self.outputs = list(outputs)
        self.prompts = []

    def __call__(self, prompt, structured):
        self.prompts.append(prompt)
        return self.outputs.pop(0)


@pytest.fixture
def generator(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    gen = NarrativeGenerator()
    assert gen.api_available
    return gen


def analysis_for(facts):
    return {"metadata": {"total_rows": 1250}, "trends": {"revenue": {
        "total_change_percent": 12.3456, "current_value": 1_234_567.0, "average_value": 1_000_000.0,
        "r_squared": 0.6512, "period": "month", "is_currency": True}}, "kpis": {}, "correlations": {}}


def test_bad_draft_gets_fixed(generator, monkeypatch):
    fake = FakeCalls(("Revenue rose 18% to $1.23M.", []), ("Revenue rose 12.3% to $1.23M.", []))
    monkeypatch.setattr(generator, "_call", fake)
    result = generator.generate_narrative("Write a report.", analysis=analysis_for(FACTS))
    assert result["auto_fixed"]
    assert result["number_check"].problems == []
    assert len(result["number_check_first_draft"].problems) == 1
    assert "FACT SHEET" in fake.prompts[0] and '"18%": not in the analysis' in fake.prompts[1]


def test_good_draft_makes_one_call(generator, monkeypatch):
    fake = FakeCalls(("Revenue rose 12.3%.", []))
    monkeypatch.setattr(generator, "_call", fake)
    result = generator.generate_narrative("Write a report.", analysis=analysis_for(FACTS))
    assert not result["auto_fixed"] and len(fake.prompts) == 1
    assert result["number_check"].score == 100.0


def test_worse_fix_is_discarded(generator, monkeypatch):
    fake = FakeCalls(("Revenue rose 18%.", []), ("Revenue rose 18% and 25% and 40%.", []))
    monkeypatch.setattr(generator, "_call", fake)
    result = generator.generate_narrative("Write a report.", analysis=analysis_for(FACTS))
    assert not result["auto_fixed"]
    assert result["narrative"] == "Revenue rose 18%."


def test_api_error_falls_back_to_demo(generator, monkeypatch):
    def boom(prompt, structured):
        raise RuntimeError("429 RESOURCE_EXHAUSTED quota")
    monkeypatch.setattr(generator, "_call", boom)
    result = generator.generate_narrative("Write a report.", analysis=analysis_for(FACTS))
    assert result["api_status"] == "error_fallback" and result["error_status"] == "quota_exceeded"
    assert result["number_check"].total == 0


def test_demo_mode_reports_no_numbers(monkeypatch, sales_analysis):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    result = NarrativeGenerator().generate_narrative("x", analysis=sales_analysis)
    assert result["generation_method"] == "demo_mode"
    assert result["number_check"].total == 0
