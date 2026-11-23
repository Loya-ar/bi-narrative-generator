"""
Narrative tab: generate the report with Gemini and show each number checked.
"""

from datetime import datetime

import pandas as pd
import streamlit as st

from fact_check import highlight
from narrative_generator import NarrativeGenerator, get_api_key
from prompt_engine import DynamicPromptEngine
from ui_common import initialize_engines


def ai_narrative_section():
    """Advanced AI narrative generation with real integration."""
    
    st.markdown("""
    <div style="background: linear-gradient(135deg, #7c3aed 0%, #a855f7 100%); 
                padding: 2.5rem 2rem; border-radius: 16px; color: white; margin-bottom: 2rem;
                text-align: center; box-shadow: 0 8px 24px rgba(124, 58, 237, 0.15);">
        <h1 style="color: white; font-size: 2.4rem; margin-bottom: 0.8rem; font-weight: 700; text-shadow: 0 2px 4px rgba(0,0,0,0.2);">🤖 AI Narrative Engine</h1>
        <p style="color: #ede9fe; font-size: 1.2rem; font-weight: 400; margin: 0;">Transform data insights into executive narratives</p>
    </div>
    """, unsafe_allow_html=True)
    
    if st.session_state.analysis_results is None:
        st.warning("⚠️ Complete data analysis first")
        return
    
    # Initialize engines
    initialize_engines()
    
    # AI Configuration Interface
    st.markdown("### ⚙️ AI Generation Configuration")
    
    # Add helpful guidance
    st.markdown("""
    <div style="background: #f1f5f9; padding: 1.2rem; border-radius: 8px; margin: 1rem 0; border: 1px solid #e2e8f0;">
        <p style="color: #475569; margin: 0; font-size: 0.9rem;">
            <strong style="color: #1e293b;">🎯 Configuration Guide:</strong> Choose settings that match your presentation context. 
            Executive summaries work best for board meetings, while detailed analysis suits operational reviews.
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        narrative_style = st.selectbox(
            "📝 Narrative Style",
            ["executive_summary", "detailed_analysis", "board_presentation", "strategic_planning"],
            help="Choose the style that matches your audience and purpose"
        )
    
    with col2:
        audience = st.selectbox(
            "👥 Target Audience", 
            ["executive", "manager", "analyst", "board_of_directors"],
            help="Adjusts language complexity and focus areas"
        )
    
    with col3:
        focus_area = st.selectbox(
            "🎯 Focus Area",
            ["overall_performance", "growth_trends", "risk_analysis", "optimization_opportunities"],
            help="Primary analytical focus for the report"
        )
    
    # AI Model Status Check
    st.markdown("### 🔧 AI Generation Mode")
    
    # Check API availability
    api_key = get_api_key()
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        if api_key and not st.session_state.demo_mode:
            st.success("🤖 **Google Gemini AI Ready** - Real AI generation with free API")
            
            # Only on request: Streamlit reruns the page on every click, and each test
            # is a Gemini request against the free-tier limits.
            if st.session_state.narrative_generator and st.button("Test connection", type="secondary"):
                api_status = st.session_state.narrative_generator.test_api_connection()
                if api_status['status'] == 'success':
                    st.info(f"✅ API Test: {api_status['message']}")
                else:
                    st.warning(f"⚠️ API Issue: {api_status['message']}")
        elif not api_key:
            st.warning("⚠️ **API Setup Required** - Add GEMINI_API_KEY to .env file")
            st.markdown("""
            <div style="background: #fef3c7; padding: 1rem; border-radius: 8px; border: 1px solid #f59e0b;">
                <p style="color: #92400e; margin: 0; font-size: 0.85rem;">
                    <strong>Quick Setup:</strong> Get free API key at <a href="https://ai.google.dev/" target="_blank" style="color: #1e40af;">ai.google.dev</a>, 
                    then add to .env file: <code style="background: #fff; padding: 2px 4px; border-radius: 4px;">GEMINI_API_KEY=your_key</code>
                </p>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.info("🎬 **Demo Mode** - no API key found, so a pre-written sample narrative is shown. Add GEMINI_API_KEY to .env for real generation.")
    
    with col2:
        demo_toggle = st.toggle("Demo Mode", value=st.session_state.demo_mode)
        st.session_state.demo_mode = demo_toggle
    
    # Generation Interface
    st.markdown("### 🚀 Generate Executive Narrative")
    
    if st.button("🎯 GENERATE AI NARRATIVE", type="primary", width="stretch"):
        generate_advanced_narrative(narrative_style, audience, focus_area)
    
    # Display generated narrative
    if st.session_state.generated_narrative:
        display_generated_narrative()

def generate_advanced_narrative(narrative_style, audience, focus_area):
    """Generate narrative using advanced prompt engineering."""
    
    try:
        with st.spinner("🧠 Generating AI-powered business narrative..."):
            
            # Get analysis results
            analysis_results = st.session_state.analysis_results
            
            # Generate dynamic prompt using our prompt engine
            if st.session_state.prompt_engine is None:
                st.session_state.prompt_engine = DynamicPromptEngine()
            
            dynamic_prompt = st.session_state.prompt_engine.generate_dynamic_prompt(
                analysis_results=analysis_results,
                narrative_style=narrative_style,
                audience=audience,
                focus_area=focus_area,
            )
            
            # Add multimodal context if visualizations exist
            chart_descriptions = ""
            if 'visualization_data' in st.session_state:
                viz_data = st.session_state.visualization_data
                descriptions = viz_data.get('chart_descriptions', [])
                chart_descriptions = "\n".join(f"- {desc}" for desc in descriptions)
            
            # Generate narrative using AI
            if st.session_state.narrative_generator is None:
                st.session_state.narrative_generator = NarrativeGenerator()
            
            # Multimodal: tell the model which charts the reader is looking at
            if chart_descriptions:
                dynamic_prompt += (
                    "\n\nCHARTS SHOWN ALONGSIDE THIS REPORT:\n" + chart_descriptions +
                    "\nWhere relevant, refer to these charts by name and connect them to the figures above.\n"
                )

            narrative_result = st.session_state.narrative_generator.generate_narrative(
                prompt=dynamic_prompt,
                narrative_type=narrative_style,
                analysis=analysis_results,
            )
            narrative_result['demonstrates_multimodal'] = bool(chart_descriptions)
            
            # Store results
            st.session_state.generated_narrative = narrative_result
            
            # Add to generation history
            st.session_state.generation_history.append({
                'timestamp': datetime.now().isoformat(),
                'style': narrative_style,
                'audience': audience,
                'focus': focus_area,
                'numbers_checked_pct': narrative_result.get('number_check_score'),
                'words': narrative_result.get('word_count', 0)
            })
            
            check = narrative_result.get('number_check')
            if check is not None and check.total:
                st.success(f"🎉 Generated {narrative_result.get('word_count', 0)} words; "
                           f"{check.checked} of {check.total} numbers checked against the analysis.")
            else:
                st.success(f"🎉 Generated {narrative_result.get('word_count', 0)} words.")
    
    except Exception as e:
        st.error(f"❌ Generation error: {e}")
        st.info("💡 Check API configuration or use demo mode")

def display_generated_narrative():
    """Display AI-generated narrative with quality metrics."""
    
    narrative = st.session_state.generated_narrative
    
    # Quality Dashboard
    st.markdown("### 📊 Generation Quality Dashboard")
    
    col1, col2, col3, col4 = st.columns(4)
    
    check = narrative.get('number_check')
    with col1:
        if check is not None and check.total:
            icon = "🟢" if not check.problems else "🔴"
            st.metric(f"{icon} Numbers checked", f"{check.checked} / {check.total}",
                      help="Every number in the report is compared with the computed analysis "
                           "(rounding allowed). Red numbers aren't supported by the data.")
        else:
            st.metric("Numbers checked", "–", help="The report contains no numbers to check.")
    
    with col2:
        word_count = narrative.get('word_count', 0)
        st.metric("📝 Word Count", f"{word_count:,}")
    
    with col3:
        gen_time = narrative.get('generation_time', 0)
        st.metric("⚡ Generation Time", f"{gen_time:.1f}s")
    
    with col4:
        model_used = narrative.get('model_used', 'Unknown')
        st.metric("🤖 AI Model", model_used.split()[0] if model_used else "Demo")
    
    # Display Narrative Content
    st.markdown("### 📄 Executive Business Report")
    
    narrative_text = narrative.get('narrative', '')

    # Report with each number marked: green = matches the analysis, red = not supported
    if check is not None and check.total:
        legend = ("<span style='color:#065f46;background:#d1fae5;padding:0 4px;border-radius:4px'>green</span>"
                  " = matches the analysis · "
                  "<span style='color:#991b1b;background:#fee2e2;padding:0 4px;border-radius:4px'>red</span>"
                  " = not supported by the data (hover a number for details)")
        st.markdown(legend, unsafe_allow_html=True)
        if narrative.get('auto_fixed'):
            first = narrative.get('number_check_first_draft')
            st.info(f"🔧 The first draft had {len(first.problems)} unsupported number(s); "
                    f"Gemini was asked once to correct them using the real values.")
    with st.container(border=True):
        st.markdown(highlight(narrative_text, check) if check is not None else narrative_text,
                    unsafe_allow_html=True)

    if check is not None and check.problems:
        with st.expander(f"⚠️ {len(check.problems)} number(s) not supported by the analysis"):
            st.dataframe(pd.DataFrame([{"As written": n.text, "Problem": n.note} for n in check.problems]),
                         hide_index=True, width="stretch")
    
    # Generation Details
    if narrative.get('demonstrates_multimodal', False) and narrative.get('generation_method') != 'demo_mode':
        st.success("🎯 **Chart-aware** - the prompt included the charts shown in this app, so the narrative can refer to them.")
    
    # Export Options
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.download_button(
            "📥 Download Markdown",
            narrative_text,
            file_name=f"Business_Report_{datetime.now().strftime('%Y%m%d_%H%M')}.md",
            mime="text/markdown",
            width="stretch"
        )
    
    with col2:
        if st.button("📊 Generate Complete Report", type="secondary", width="stretch"):
            st.info("👆 Go to Complete Report tab for integrated view")
    
    with col3:
        if st.button("🔄 Regenerate", type="secondary", width="stretch"):
            # Clear current narrative to trigger regeneration
            st.session_state.generated_narrative = None
            st.rerun()
