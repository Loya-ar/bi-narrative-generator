"""Tests for the period analysis: significant trends, comparisons, drivers, unusual months."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from data_processor import AdvancedDataProcessor  # noqa: E402
from fact_check import build_fact_sheet, check_report  # noqa: E402
from prompt_engine import DynamicPromptEngine  # noqa: E402


def analyse(df):
    return AdvancedDataProcessor()._analyze_dataframe(df)


def monthly_frame(values_by_region, start="2022-01-01"):
    """Two rows per month per region, so monthly totals differ from row averages."""
    rows = []
    months = pd.period_range(start, periods=len(next(iter(values_by_region.values()))), freq="M")
    for region, values in values_by_region.items():
        for month, v in zip(months, values):
            for day in (5, 20):
                rows.append({"Date": month.to_timestamp() + pd.Timedelta(days=day - 1),
                             "Region": region, "Revenue": v / 2, "Conversion_Rate": 3.0})
    return pd.DataFrame(rows)


# ---------- aggregation ----------

@pytest.mark.parametrize("column, agg", [
    ("Revenue", "sum"), ("Operational_Costs", "sum"), ("Leads_Generated", "sum"),
    ("Revenue_Per_Unit", "mean"), ("Click_Through_Rate", "mean"), ("Gross_Margin_Percent", "mean"),
    ("Customer_Acquisition_Cost", "mean"), ("Return_on_Ad_Spend", "mean"), ("ctr", "mean"),
])
def test_rates_are_averaged_and_amounts_summed(column, agg):
    assert AdvancedDataProcessor()._aggregation(column) == agg


def test_monthly_values_are_totals_for_amounts():
    r = analyse(monthly_frame({"West": [100.0] * 6, "East": [50.0] * 6}))
    trend = r["trends"]["Revenue"]
    assert trend["aggregation"] == "sum"
    assert trend["current_value"] == pytest.approx(150.0)  # 2 rows x 2 regions per month
    assert r["trends"]["Conversion_Rate"]["aggregation"] == "mean"


# ---------- significance ----------

def test_noisy_series_has_no_clear_trend():
    rng = np.random.default_rng(1)
    values = 1000 + rng.normal(0, 200, 12)
    values[-1] = values[0] * 1.4  # big first-to-last jump, but no trend
    trend = analyse(monthly_frame({"West": list(values)}))["trends"]["Revenue"]
    assert trend["p_value"] >= 0.05
    assert trend["trend_direction"] == "no_clear_trend" and not trend["significant"]


def test_steady_growth_is_a_trend():
    trend = analyse(monthly_frame({"West": [1000 + 50 * i for i in range(12)]}))["trends"]["Revenue"]
    assert trend["significant"] and trend["p_value"] < 0.05
    assert trend["trend_direction"] == "increasing"


# ---------- period comparisons ----------

def test_month_over_month_and_year_over_year():
    values = [100.0 + i for i in range(13)]  # Jan 2022 .. Jan 2023
    c = analyse(monthly_frame({"West": values}))["period_comparisons"]["Revenue"]
    assert c["latest_period"] == "2023-01" and c["previous_period"] == "2022-12"
    assert c["mom_change_pct"] == pytest.approx((112 - 111) / 111 * 100)
    assert c["yoy_period"] == "2022-01"
    assert c["yoy_change_pct"] == pytest.approx(12.0)


def test_no_year_over_year_with_under_13_months():
    c = analyse(monthly_frame({"West": [100.0] * 6}))["period_comparisons"]["Revenue"]
    assert c["yoy_change_pct"] is None


# ---------- drivers ----------

def test_drivers_split_the_change_by_segment():
    r = analyse(monthly_frame({"West": [100, 100, 170], "East": [100, 100, 130], "North": [100, 100, 100]}))
    d = r["drivers"]["Region"]
    assert d["measure"] == "Revenue" and (d["from_period"], d["to_period"]) == ("2022-01", "2022-03")
    assert d["total_change"] == pytest.approx(100)
    shares = {s["segment"]: s["share_of_change_pct"] for s in d["segments"]}
    assert shares == pytest.approx({"West": 70.0, "East": 30.0, "North": 0.0})
    assert d["segments"][0]["segment"] == "West"  # biggest change first


def test_small_changes_are_not_explained():
    r = analyse(monthly_frame({"West": [100, 100, 102], "East": [100, 100, 100]}))
    assert r["drivers"] == {}


def test_no_drivers_without_a_date_column():
    df = pd.DataFrame({"Region": ["A", "B"] * 10, "Revenue": range(20)})
    assert analyse(df)["drivers"] == {} and analyse(df)["period_comparisons"] == {}


# ---------- unusual months ----------

def test_spike_month_is_flagged():
    values = [100, 102, 98, 101, 99, 100, 300, 101, 100, 99]
    [a] = analyse(monthly_frame({"West": values}))["anomalies"]
    assert a["measure"] == "Revenue" and a["period"] == "2022-07"
    assert a["deviation_pct"] == pytest.approx(200.0)


def test_flat_series_has_no_anomalies():
    assert analyse(monthly_frame({"West": [100.0] * 10}))["anomalies"] == []


# ---------- fact sheet and prompt ----------

@pytest.fixture(scope="module")
def driver_analysis():
    return analyse(monthly_frame({"West": [100, 100, 170], "East": [100, 100, 130], "North": [100, 100, 100]}))


def test_fact_sheet_has_the_new_numbers(driver_analysis):
    ids = {f.id for f in build_fact_sheet(driver_analysis)}
    assert {"cmp.Revenue.mom_pct", "driver.Region.west.share_pct", "driver.Region.total_change",
            "trend.Revenue.p_value"} <= ids


def test_a_driver_sentence_is_checked(driver_analysis):
    facts = build_fact_sheet(driver_analysis)
    result = check_report("West drove 70% of the growth and East 30%; North added 55%.", facts)
    assert [n.text for n in result.problems] == ["55%"]


def test_prompt_mentions_the_new_sections(driver_analysis):
    prompt = DynamicPromptEngine().generate_dynamic_prompt(driver_analysis, "executive_summary", "executive")
    assert "LATEST MONTH COMPARISONS" in prompt and "WHAT DROVE THE CHANGE" in prompt
    assert "West 70%" in prompt


def test_prompt_says_when_a_trend_is_not_clear():
    rng = np.random.default_rng(1)
    r = analyse(monthly_frame({"West": list(1000 + rng.normal(0, 200, 12))}))
    prompt = DynamicPromptEngine().generate_dynamic_prompt(r, "executive_summary", "executive")
    assert "no statistically clear trend" in prompt
