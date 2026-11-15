"""
Streamlit app: upload or pick a dataset, analyse it, generate an AI narrative
with Google Gemini (or demo mode without a key), and export the report.

Run from the repository root:
    streamlit run src/app.py
"""

import streamlit as st


# CRITICAL: Page config must be first
st.set_page_config(
    page_title="🏆 BI Narrative Generator | Arjun Loya",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Standard imports
import sys
import os
from pathlib import Path
import warnings
from dotenv import load_dotenv

warnings.filterwarnings('ignore')

# Load environment variables
load_dotenv()

# Add src to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

# Import our custom modules
try:
    from narrative_generator import get_api_key
    from page_upload import data_upload_section
    from page_analysis import analysis_results_section
    from page_narrative import ai_narrative_section
    from page_report import complete_report_section
except ImportError as e:
    st.error(f"❌ Import Error: {e}")
    st.info("🔧 Make sure all Python files are in the src/ directory")

def ensure_directories():
    """Create all required directories."""
    directories = [
        "data/sample_datasets",
        "data/uploads", 
        "data/outputs",
        "config",
        "assets/screenshots",
        "tests"
    ]
    
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)


def apply_professional_styling():
    """Apply the app's CSS (src/styles.css)."""
    css = (Path(current_dir) / "styles.css").read_text(encoding="utf-8")
    st.markdown(f"<style>\n{css}</style>", unsafe_allow_html=True)


def initialize_session_state():
    """Initialize all session state variables."""
    defaults = {
        'analysis_results': None,
        'generated_narrative': None,
        'data_processor': None,
        'prompt_engine': None,
        'narrative_generator': None,
        'uploaded_data': None,
        'demo_mode': False,
        'generation_history': [],
        'export_ready': False
    }
    
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def create_professional_header():
    """Create header with excellent readability."""
    st.markdown("""
    <div style="background: linear-gradient(135deg, #1e293b 0%, #3b82f6 100%); 
                padding: 3rem 2rem; border-radius: 16px; color: white; 
                text-align: center; margin-bottom: 2rem;
                box-shadow: 0 8px 24px rgba(30, 41, 59, 0.15);">
        <h1 style="color: white; font-size: 3.2rem; font-weight: 800; margin-bottom: 1rem; text-shadow: 0 2px 4px rgba(0,0,0,0.3);">
            🏆 Business Intelligence Narrative Generator
        </h1>
        <p style="color: #e2e8f0; font-size: 1.4rem; margin: 1rem 0; font-weight: 400;">
            Advanced AI-Powered Executive Reporting System
        </p>
        <div style="margin-top: 2rem; display: flex; justify-content: center; gap: 1rem; flex-wrap: wrap;">
            <span style="background: rgba(255,255,255,0.15); padding: 0.7rem 1.3rem; 
                         border-radius: 20px; color: white; font-weight: 500; font-size: 0.9rem;
                         border: 1px solid rgba(255,255,255,0.2);">
                📚 Author: Arjun Loya
            </span>
            <span style="background: rgba(255,255,255,0.15); padding: 0.7rem 1.3rem; 
                         border-radius: 20px; color: white; font-weight: 500; font-size: 0.9rem;
                         border: 1px solid rgba(255,255,255,0.2);">
                🎓 Course: ST. Prompt Engineering & AI
            </span>
            <span style="background: rgba(255,255,255,0.15); padding: 0.7rem 1.3rem; 
                         border-radius: 20px; color: white; font-weight: 500; font-size: 0.9rem;
                         border: 1px solid rgba(255,255,255,0.2);">
                🤖 Advanced AI Engineering
            </span>
        </div>
    </div>
    """, unsafe_allow_html=True)


def system_status_sidebar():
    """System status in sidebar with clear readability."""
    
    with st.sidebar:
        st.markdown("""
        <div style="background: white; padding: 1.5rem; border-radius: 12px; border: 1px solid #e2e8f0; margin-bottom: 1rem;">
            <h3 style="color: #1e293b; margin-bottom: 1rem; font-weight: 600;">🔧 System Status</h3>
        """, unsafe_allow_html=True)
        
        # API Status
        api_key = get_api_key()
        if api_key:
            st.markdown("""
            <div style="background: #f0fdf4; padding: 0.7rem; border-radius: 6px; border: 1px solid #22c55e; margin-bottom: 0.5rem;">
                <span style="color: #166534; font-weight: 500;">🤖 Gemini API: Ready</span>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div style="background: #fef3c7; padding: 0.7rem; border-radius: 6px; border: 1px solid #f59e0b; margin-bottom: 0.5rem;">
                <span style="color: #92400e; font-weight: 500;">⚠️ API: Not configured</span>
            </div>
            """, unsafe_allow_html=True)
        
        # Component Status
        st.markdown('<p style="color: #1e293b; font-weight: 600; margin: 1rem 0 0.5rem 0;">Component Status:</p>', unsafe_allow_html=True)
        
        components = {
            "Data Processor": st.session_state.data_processor is not None,
            "Prompt Engine": st.session_state.prompt_engine is not None,
            "AI Generator": st.session_state.narrative_generator is not None,
            "Analysis Results": st.session_state.analysis_results is not None,
            "Generated Narrative": st.session_state.generated_narrative is not None
        }
        
        for component, status in components.items():
            if status:
                st.markdown(f"""
                <div style="background: #f0fdf4; padding: 0.4rem 0.8rem; border-radius: 4px; margin: 0.2rem 0; border: 1px solid #22c55e;">
                    <span style="color: #166534; font-size: 0.85rem;">✅ {component}</span>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div style="background: #f8fafc; padding: 0.4rem 0.8rem; border-radius: 4px; margin: 0.2rem 0; border: 1px solid #e2e8f0;">
                    <span style="color: #64748b; font-size: 0.85rem;">⚪ {component}</span>
                </div>
                """, unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Quick Actions
        st.markdown("""
        <div style="background: white; padding: 1.5rem; border-radius: 12px; border: 1px solid #e2e8f0; margin-top: 1rem;">
            <h4 style="color: #1e293b; margin-bottom: 1rem; font-weight: 600;">⚡ Quick Actions</h4>
        </div>
        """, unsafe_allow_html=True)
        
        if st.button("🔄 Reset All", width="stretch"):
            for key in st.session_state.keys():
                if key not in ['data_processor', 'prompt_engine', 'narrative_generator']:
                    del st.session_state[key]
            st.rerun()
        
        if st.button("🎬 Toggle Demo Mode", width="stretch"):
            st.session_state.demo_mode = not st.session_state.demo_mode
            st.rerun()

def main():
    """Main application entry point."""
    
    # Initialize everything
    ensure_directories()
    apply_professional_styling()
    initialize_session_state()
    
    # Create beautiful header
    create_professional_header()
    
    # System status sidebar
    system_status_sidebar()
    
    # Main navigation
    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Data Upload & Processing",
        "🔍 Analysis Results", 
        "🤖 AI Narrative Generation",
        "📈 Complete Intelligence Report"
    ])
    
    with tab1:
        data_upload_section()
    
    with tab2:
        analysis_results_section()
    
    with tab3:
        ai_narrative_section()
    
    with tab4:
        complete_report_section()
    
    # Professional Footer
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; padding: 2.5rem 2rem; background: white; border-radius: 16px; 
                margin-top: 2rem; box-shadow: 0 4px 12px rgba(0,0,0,0.06); border: 1px solid #e2e8f0;">
        <h2 style="color: #1e293b; margin-bottom: 1.5rem; font-weight: 700;">🚀 Business Intelligence Narrative Generator</h2>
        <div style="margin: 1.5rem 0;">
            <span style="background: #3b82f6; color: white; padding: 0.6rem 1.2rem; 
                         border-radius: 20px; margin: 0 0.4rem; font-size: 0.85rem; font-weight: 500;">
                Advanced Prompt Engineering
            </span>
            <span style="background: #7c3aed; color: white; padding: 0.6rem 1.2rem; 
                         border-radius: 20px; margin: 0 0.4rem; font-size: 0.85rem; font-weight: 500;">
                Multimodal Integration
            </span>
        </div>
        <p style="color: #64748b; margin: 1rem 0; font-size: 0.95rem;">
            <strong style="color: #1e293b;">Author:</strong> Arjun Loya | 
            <strong style="color: #1e293b;">Course:</strong> ST. Prompt Engineering & AI | 
            <strong style="color: #1e293b;">Submission:</strong> August 2025
        </p>
        <p style="color: #64748b; font-style: italic; font-size: 0.9rem;">
            Transforming raw business data into executive-grade intelligence through advanced AI engineering
        </p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()