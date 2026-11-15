"""Tests for the analysis -> prompt -> narrative pipeline (no API key or network needed)."""

import os
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from data_processor import AdvancedDataProcessor  # noqa: E402
from narrative_generator import NarrativeGenerator  # noqa: E402
from prompt_engine import DynamicPromptEngine  # noqa: E402
from visualizer import heatmap_corr, line_trend  # noqa: E402

SAMPLES = ROOT / "data" / "sample_datasets"


@pytest.fixture(scope="module")
def sales_results():
    return AdvancedDataProcessor().load_and_analyze_data(str(SAMPLES / "sales_performance_2023.csv"))


@pytest.fixture
def offline_generator(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    return NarrativeGenerator()


def test_analysis_has_every_section(sales_results):
    for key in ("metadata", "trends", "insights", "business_domain", "kpis", "correlations"):
        assert key in sales_results


def test_metadata_matches_the_file(sales_results):
    df = pd.read_csv(SAMPLES / "sales_performance_2023.csv")
    meta = sales_results["metadata"]
    assert meta["total_rows"] == len(df)
    assert meta["total_columns"] == len(df.columns)
    assert 0 <= meta["data_quality_score"] <= 100


@pytest.mark.parametrize("filename, domain", [
    ("sales_performance_2023.csv", "sales"),
    ("marketing_campaigns_2023.csv", "marketing"),
])
def test_domain_detection(filename, domain):
    results = AdvancedDataProcessor().load_and_analyze_data(str(SAMPLES / filename))
    assert results["business_domain"] == domain


@pytest.mark.parametrize("csv", sorted(p.name for p in SAMPLES.glob("*.csv")))
def test_every_sample_dataset_analyses(csv):
    results = AdvancedDataProcessor().load_and_analyze_data(str(SAMPLES / csv))
    assert results["metadata"]["total_rows"] > 0


def test_prompt_adapts_to_style_and_audience(sales_results):
    engine = DynamicPromptEngine()
    exec_prompt = engine.generate_dynamic_prompt(sales_results, "executive_summary", "executive")
    analyst_prompt = engine.generate_dynamic_prompt(sales_results, "detailed_analysis", "analyst")
    assert exec_prompt != analyst_prompt
    assert engine.audience_adaptations["analyst"] in analyst_prompt
    assert "sales" in exec_prompt.lower()
    assert engine.validate_prompt_quality(exec_prompt)["quality_score"] == 100


def test_demo_mode_without_api_key(offline_generator, sales_results):
    prompt = DynamicPromptEngine().generate_dynamic_prompt(sales_results, "executive_summary", "executive")
    result = offline_generator.generate_narrative(prompt)
    assert offline_generator.api_available is False
    assert result["generation_method"] == "demo_mode"
    assert result["word_count"] > 0
    # Demo text isn't based on the data, so there's no number-check score to report
    assert result["number_check_score"] is None


def test_visualizer_returns_figures():
    df = pd.read_csv(SAMPLES / "sales_performance_2023.csv")
    assert isinstance(line_trend(df, y="Sales_Amount", x="Date"), go.Figure)
    assert isinstance(heatmap_corr(df), go.Figure)


def test_trends_use_monthly_periods_and_skip_date_parts(sales_results):
    trends = sales_results["trends"]
    assert "Month" not in trends and "Quarter" not in trends
    assert trends["Sales_Amount"]["period"] == "month"
    assert trends["Sales_Amount"]["is_currency"] is True
    assert trends["Units_Sold"]["is_currency"] is False
    # Monthly averages keep changes in a sensible range (row-to-row comparison gave +40,000%)
    assert all(abs(t["total_change_percent"]) < 500 for t in trends.values())
