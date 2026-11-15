"""The Streamlit app end to end, headless: demo dataset -> analysis -> narrative -> report.

Gemini is replaced by a fake, so no key or network is needed.
"""

import sys
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import narrative_generator  # noqa: E402

APP = str(ROOT / "src" / "app.py")
REPORT = "## Summary\nThe dataset has 1,816 records; sales beat the 37.5% target."


@pytest.fixture
def app(monkeypatch):
    calls = []

    def fake_call(self, prompt, structured):
        calls.append(structured)
        return REPORT, []

    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(narrative_generator.NarrativeGenerator, "_call", fake_call)
    at = AppTest.from_file(APP, default_timeout=120)
    at.run()
    assert not at.exception, at.exception
    at.calls = calls
    return at


def button(at, text):
    return next(b for b in at.button if text in (b.label or ""))  # case matters: two "generate" buttons


def test_tabs_render(app):
    assert [t.label for t in app.tabs] == [
        "📊 Data Upload & Processing", "🔍 Analysis Results",
        "🤖 AI Narrative Generation", "📈 Complete Intelligence Report"]
    assert app.calls == []  # loading the page makes no Gemini request


def test_full_flow_checks_numbers(app):
    button(app, "Analyze Sales Data").click().run()
    assert not app.exception, app.exception
    assert app.session_state["analysis_results"]["metadata"]["total_rows"] == 1816

    button(app, "GENERATE AI NARRATIVE").click().run()
    assert not app.exception, app.exception
    narrative = app.session_state["generated_narrative"]
    assert narrative["number_check"].checked == 1 and narrative["number_check"].total == 2
    assert app.calls == [True, True]  # first draft + one correction pass

    page = " ".join(m.value for m in app.markdown)
    assert "#d1fae5" in page and "#fee2e2" in page  # green and red numbers
    assert "1 / 2" in [m.value for m in app.metric if "Numbers" in m.label]
