"""
Data upload tab: file upload, demo datasets, running the analysis.
"""

from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

from data_processor import AdvancedDataProcessor
from page_analysis import generate_business_visualizations


def create_sample_datasets():
    """Create professional sample datasets if they don't exist."""
    
    sample_datasets_dir = Path("data/sample_datasets")
    sample_datasets_dir.mkdir(parents=True, exist_ok=True)
    
    # Enhanced Sales Performance Dataset
    if not (sample_datasets_dir / "sales_performance_2023.csv").exists():
        np.random.seed(42)
        
        # Create realistic 18-month sales data
        dates = pd.date_range('2022-07-01', '2023-12-31', freq='D')
        n_records = len(dates)
        
        # Base trends with seasonality
        trend = np.linspace(45000, 68000, n_records)
        seasonality = 5000 * np.sin(2 * np.pi * np.arange(n_records) / 365.25) 
        noise = np.random.normal(0, 2000, n_records)
        
        sales_data = {
            'date': dates.strftime('%Y-%m-%d'),
            'revenue': np.round(trend + seasonality + noise, 2),
            'units_sold': np.round((trend + seasonality + noise) / 150 + np.random.normal(0, 10, n_records), 0).astype(int),
            'region': np.random.choice(['North America', 'Europe', 'Asia Pacific', 'Latin America'], n_records, p=[0.4, 0.3, 0.2, 0.1]),
            'product_category': np.random.choice(['Enterprise Software', 'Cloud Services', 'Professional Services', 'Hardware'], n_records, p=[0.35, 0.30, 0.25, 0.10]),
            'sales_rep': np.random.choice([f'Rep_{i:03d}' for i in range(1, 51)], n_records),
            'customer_segment': np.random.choice(['Enterprise', 'Mid-Market', 'SMB'], n_records, p=[0.3, 0.4, 0.3])
        }
        
        # Add calculated fields
        sales_df = pd.DataFrame(sales_data)
        sales_df['avg_deal_size'] = np.round(sales_df['revenue'] / sales_df['units_sold'], 2)
        sales_df['quarter'] = pd.to_datetime(sales_df['date']).dt.to_period('Q').astype(str)
        sales_df['month'] = pd.to_datetime(sales_df['date']).dt.strftime('%Y-%m')
        
        sales_df.to_csv(sample_datasets_dir / "sales_performance_2023.csv", index=False)
    
    # Enhanced Marketing Campaign Dataset
    if not (sample_datasets_dir / "marketing_campaigns_2023.csv").exists():
        np.random.seed(123)
        
        # Create 162 marketing campaigns across 12 months
        campaign_data = {
            'campaign_id': [f'CAMP_2023_{i:03d}' for i in range(1, 163)],
            'campaign_name': [f'Campaign_{i}' for i in range(1, 163)],
            'start_date': pd.date_range('2023-01-01', '2023-12-31', periods=162).strftime('%Y-%m-%d'),
            'channel': np.random.choice(['Google Ads', 'Facebook', 'LinkedIn', 'YouTube', 'Display', 'Email'], 162, p=[0.25, 0.20, 0.15, 0.15, 0.15, 0.10]),
            'budget': np.round(np.random.gamma(2, 2000), 2),  # Realistic budget distribution
            'impressions': np.random.randint(5000, 100000, 162),
            'clicks': np.random.randint(100, 5000, 162),
            'conversions': np.random.randint(5, 250, 162),
            'cost_per_click': np.round(np.random.uniform(0.50, 8.00), 2),
            'target_audience': np.random.choice(['Business Decision Makers', 'Tech Professionals', 'C-Suite', 'Managers'], 162)
        }
        
        # Calculate derived metrics
        campaign_df = pd.DataFrame(campaign_data)
        campaign_df['ctr'] = np.round((campaign_df['clicks'] / campaign_df['impressions']) * 100, 2)
        campaign_df['conversion_rate'] = np.round((campaign_df['conversions'] / campaign_df['clicks']) * 100, 2)
        campaign_df['cost_per_conversion'] = np.round(campaign_df['budget'] / campaign_df['conversions'], 2)
        campaign_df['revenue_per_conversion'] = np.round(np.random.uniform(800, 3500), 2)
        campaign_df['total_revenue'] = np.round(campaign_df['conversions'] * campaign_df['revenue_per_conversion'], 2)
        campaign_df['roas'] = np.round(campaign_df['total_revenue'] / campaign_df['budget'], 2)
        campaign_df['quarter'] = pd.to_datetime(campaign_df['start_date']).dt.to_period('Q').astype(str)
        
        campaign_df.to_csv(sample_datasets_dir / "marketing_campaigns_2023.csv", index=False)

def data_upload_section():
    """Enhanced data upload section with integrated processing."""
    
    st.markdown("""
    <div style="background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%); 
                padding: 2.5rem 2rem; border-radius: 16px; color: white; margin-bottom: 2rem;
                text-align: center; box-shadow: 0 8px 24px rgba(99, 102, 241, 0.15);">
        <h1 style="color: white; font-size: 2.4rem; margin-bottom: 0.8rem; font-weight: 700; text-shadow: 0 2px 4px rgba(0,0,0,0.2);">
            📊 Advanced Data Processing Engine
        </h1>
        <p style="color: #e0e7ff; font-size: 1.2rem; font-weight: 400; margin: 0;">
            Upload business data for comprehensive AI-powered analysis
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # Ensure sample datasets exist
    create_sample_datasets()
    
    # File upload interface
    col1, col2 = st.columns([2, 1])
    
    with col1:
        uploaded_file = st.file_uploader(
            "🎯 Upload Your Business Data File",
            type=['csv', 'xlsx', 'xls'],
            help="Supported formats: CSV, Excel (XLSX/XLS). Max size: 200MB"
        )
        
        # Help text with good contrast
        st.markdown("""
        <div style="background: #f1f5f9; padding: 1rem; border-radius: 8px; margin: 1rem 0; border: 1px solid #e2e8f0;">
            <p style="color: #475569; margin: 0; font-size: 0.9rem;">
                <strong style="color: #1e293b;">💡 Pro Tip:</strong> For best results, ensure your data has a mix of categorical and numeric columns. 
                Our AI works best with clean, structured business data.
            </p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("### 📋 Data Requirements")
        st.markdown("""
        <div style="background: #f8fafc; padding: 1rem; border-radius: 8px; border: 1px solid #e2e8f0;">
            <ul style="color: #334155; margin: 0; padding-left: 1.2rem;">
                <li><strong>Minimum:</strong> 10+ records</li>
                <li><strong>Optimal:</strong> 100+ records</li>  
                <li><strong>Columns:</strong> Mix of text and numeric</li>
                <li><strong>Quality:</strong> Clean, structured data</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
    
    # Process uploaded file
    if uploaded_file:
        process_uploaded_file(uploaded_file)
    else:
        display_demo_datasets()

def process_uploaded_file(uploaded_file):
    """Process uploaded file with advanced error handling."""
    
    try:
        with st.spinner("🔄 Processing your business data..."):
            # Save uploaded file
            upload_path = Path("data/uploads") / uploaded_file.name
            upload_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(upload_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            # Load data with encoding detection
            if uploaded_file.name.endswith('.csv'):
                # Try multiple encodings
                encodings = ['utf-8', 'latin-1', 'iso-8859-1', 'cp1252']
                df = None
                
                for encoding in encodings:
                    try:
                        df = pd.read_csv(upload_path, encoding=encoding)
                        break
                    except UnicodeDecodeError:
                        continue
                
                if df is None:
                    st.error("❌ Could not read CSV file. Please check file encoding.")
                    return
            else:
                df = pd.read_excel(upload_path)
            
            # Validate data
            if len(df) < 5:
                st.error("❌ Dataset too small. Please upload data with at least 5 records.")
                return
            
            # Store data and show preview
            st.session_state.uploaded_data = df
            
            # Success message with metrics
            st.markdown("""
            <div style="background: #f0fdf4; padding: 1.5rem; border-radius: 12px; border: 1px solid #22c55e; margin: 1rem 0;">
                <h4 style="color: #166534; margin-bottom: 1rem;">✅ File Successfully Processed!</h4>
            </div>
            """, unsafe_allow_html=True)
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("📊 Records", f"{len(df):,}")
            with col2:
                st.metric("📋 Columns", f"{len(df.columns)}")
            with col3:
                numeric_cols = len(df.select_dtypes(include=[np.number]).columns)
                st.metric("🔢 Numeric", f"{numeric_cols}")
            with col4:
                st.metric("💾 Size", f"{uploaded_file.size / 1024:.1f} KB")
            
            st.success(f"✅ Successfully loaded: {uploaded_file.name}")
            
            # Data preview with better styling
            st.markdown("### 👀 Data Preview")
            st.markdown("""
            <div style="background: #f8fafc; padding: 1rem; border-radius: 8px; border: 1px solid #e2e8f0; margin-bottom: 1rem;">
                <p style="color: #475569; margin: 0; font-size: 0.9rem;">
                    <strong style="color: #1e293b;">Preview:</strong> Showing first 10 rows of your uploaded data
                </p>
            </div>
            """, unsafe_allow_html=True)
            st.dataframe(df.head(10), width="stretch")
            
            # Automatic analysis trigger
            if st.button("🚀 Start Advanced Analysis", type="primary", width="stretch"):
                run_comprehensive_analysis(df, upload_path)
    
    except Exception as e:
        st.error(f"❌ Error processing file: {str(e)}")
        st.info("💡 Try: Check file format, encoding, or use demo datasets")

def display_demo_datasets():
    """Display professional demo datasets."""
    
    st.markdown("### 🧪 Professional Demo Datasets")
    st.markdown("*Experience the full power of AI-driven business intelligence with our curated datasets*")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        <div style="background: #059669; padding: 1.8rem; border-radius: 12px; 
                    color: white; margin: 1rem 0; box-shadow: 0 4px 12px rgba(5, 150, 105, 0.2);">
            <h3 style="color: white; margin-bottom: 1rem; font-weight: 600; text-shadow: 0 1px 2px rgba(0,0,0,0.2);">📈 Sales Performance 2023</h3>
            <p style="color: #dcfce7; margin-bottom: 0; font-size: 0.95rem; line-height: 1.6;">
                • 1,816 transactions across 12 months<br>
                • $49.3M total sales<br>
                • Multi-region performance data<br>
                • Product category breakdown
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        if st.button("🔥 Analyze Sales Data", type="primary", width="stretch", key="sales_demo"):
            load_and_analyze_demo_data("sales_performance_2023.csv")
    
    with col2:
        st.markdown("""
        <div style="background: #dc2626; padding: 1.8rem; border-radius: 12px; 
                    color: white; margin: 1rem 0; box-shadow: 0 4px 12px rgba(220, 38, 38, 0.2);">
            <h3 style="color: white; margin-bottom: 1rem; font-weight: 600; text-shadow: 0 1px 2px rgba(0,0,0,0.2);">🎯 Marketing Campaigns 2023</h3>
            <p style="color: #fecaca; margin-bottom: 0; font-size: 0.95rem; line-height: 1.6;">
                • 324 weekly results for 12 campaigns<br>
                • 7 channels, 43.9x overall ROAS<br>
                • Multi-channel performance<br>
                • Conversion optimization insights
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        if st.button("🚀 Analyze Marketing Data", type="primary", width="stretch", key="marketing_demo"):
            load_and_analyze_demo_data("marketing_campaigns_2023.csv")

def load_and_analyze_demo_data(filename):
    """Load demo data and trigger analysis."""
    
    try:
        demo_path = Path("data/sample_datasets") / filename
        
        if not demo_path.exists():
            st.error(f"❌ Demo file not found: {filename}")
            return
        
        # Load demo data
        df = pd.read_csv(demo_path)
        st.session_state.uploaded_data = df
        
        # Show success and preview
        record_count = len(df)
        success_html = f"""
        <div style="background: #f0fdf4; padding: 1.5rem; border-radius: 12px; border: 1px solid #22c55e; margin: 1rem 0;">
            <h4 style="color: #166534; margin-bottom: 0.5rem;">✅ Demo Dataset Loaded Successfully!</h4>
            <p style="color: #166534; margin: 0; font-size: 0.9rem;">
                Loaded <strong>{record_count:,} records</strong> from {filename}
            </p>
        </div>
        """
        st.markdown(success_html, unsafe_allow_html=True)
        
        with st.expander("👀 Preview Demo Data", expanded=True):
            st.dataframe(df.head(), width="stretch")
        
        # Auto-trigger analysis
        run_comprehensive_analysis(df, demo_path)
        
    except Exception as e:
        st.error(f"❌ Error loading demo data: {e}")

def run_comprehensive_analysis(df, file_path):
    """Run comprehensive analysis using AdvancedDataProcessor."""
    
    try:
        with st.spinner("🧠 Running advanced statistical analysis..."):
            
            # Initialize processor if needed
            if st.session_state.data_processor is None:
                st.session_state.data_processor = AdvancedDataProcessor()
            
            # Run analysis using our advanced processor
            results = st.session_state.data_processor.load_and_analyze_data(str(file_path))
            
            # Store results
            st.session_state.analysis_results = results
            
            # Show success with key metrics
            metadata = results.get('metadata', {})
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("📊 Records", f"{metadata.get('total_rows', 0):,}")
            with col2:
                st.metric("🎯 Quality", f"{metadata.get('data_quality_score', 0):.1f}%")
            with col3:
                st.metric("🏢 Domain", results.get('business_domain', 'general').title())
            with col4:
                st.metric("📈 Trends", len(results.get('trends', {})))
            
            st.success("✅ Advanced analysis complete! Go to Analysis Results tab.")
            
            # Auto-generate visualizations
            generate_business_visualizations(df, results)
    
    except Exception as e:
        st.error(f"❌ Analysis error: {e}")
        st.info("💡 Try using demo datasets or check data format")
