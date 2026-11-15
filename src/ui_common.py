"""
Helpers shared by the app's pages.
"""

import streamlit as st

from data_processor import AdvancedDataProcessor
from narrative_generator import NarrativeGenerator
from prompt_engine import DynamicPromptEngine


def initialize_engines():
    """Initialize AI engines once."""
    if st.session_state.data_processor is None:
        st.session_state.data_processor = AdvancedDataProcessor()
    
    if st.session_state.prompt_engine is None:
        st.session_state.prompt_engine = DynamicPromptEngine()
    
    if st.session_state.narrative_generator is None:
        st.session_state.narrative_generator = NarrativeGenerator()


def numbers_checked_text(narrative):
    """'23 / 24' numbers checked against the analysis, or '–' when there were none."""
    check = narrative.get('number_check')
    return f"{check.checked} / {check.total}" if check is not None and check.total else "–"
