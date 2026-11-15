"""
Analysis tab: metrics, trends, period comparisons, drivers and charts.
"""


import numpy as np
import pandas as pd
import streamlit as st

from data_processor import AdvancedDataProcessor
from visualizer import bar_top_categories, heatmap_corr, line_trend


def show_period_analysis(results):
    """Latest-month comparisons, what drove the change, and unusual months."""
    comparisons = results.get('period_comparisons') or {}
    drivers = results.get('drivers') or {}
    anomalies = results.get('anomalies') or []
    if not (comparisons or drivers or anomalies):
        return

    def pct(v):
        return "–" if v is None else f"{v:+.1f}%"

    if comparisons:
        st.markdown("### 🗓️ Latest Month vs Earlier")
        st.dataframe(pd.DataFrame([{
            "Measure": m.replace('_', ' ').title(),
            "Monthly": "total" if c['aggregation'] == 'sum' else "average",
            "Latest month": c['latest_period'],
            "Vs previous month": pct(c['mom_change_pct']),
            "Vs same month last year": pct(c['yoy_change_pct']),
        } for m, c in comparisons.items()]), hide_index=True, width="stretch")

    if drivers:
        st.markdown("### 🧭 What Drove the Change")
        for dim, d in drivers.items():
            st.caption(f"{d['measure'].replace('_', ' ').title()} {pct(d['total_change_pct'])} from "
                       f"{d['from_period']} to {d['to_period']}, by {dim.replace('_', ' ')} "
                       "(shares can exceed 100% when other segments fell)")
            st.dataframe(pd.DataFrame([{
                dim.replace('_', ' ').title(): s['segment'],
                "Change": f"{s['change']:+,.0f}",
                "Share of the change": f"{s['share_of_change_pct']:.0f}%",
            } for s in d['segments']]), hide_index=True, width="stretch")

    if anomalies:
        st.markdown("### ⚠️ Unusual Months")
        st.dataframe(pd.DataFrame([{
            "Measure": a['measure'].replace('_', ' ').title(),
            "Month": a['period'],
            "Vs a typical month": pct(a['deviation_pct']),
        } for a in anomalies]), hide_index=True, width="stretch")

def analysis_results_section():
    """Display comprehensive analysis results."""
    
    st.markdown("""
    <div style="background: linear-gradient(135deg, #1e40af 0%, #3b82f6 100%); 
                padding: 2.5rem 2rem; border-radius: 16px; color: white; margin-bottom: 2rem;
                text-align: center; box-shadow: 0 8px 24px rgba(30, 64, 175, 0.15);">
        <h1 style="color: white; font-size: 2.4rem; margin-bottom: 0.8rem; font-weight: 700; text-shadow: 0 2px 4px rgba(0,0,0,0.2);">📊 Analysis Dashboard</h1>
        <p style="color: #dbeafe; font-size: 1.2rem; font-weight: 400; margin: 0;">Advanced business intelligence insights</p>
    </div>
    """, unsafe_allow_html=True)
    
    if st.session_state.analysis_results is None:
        st.warning("⚠️ Upload and analyze data first in the Data Upload tab")
        return
    
    results = st.session_state.analysis_results
    metadata = results.get('metadata', {})
    trends = results.get('trends', {})
    insights = results.get('insights', [])
    kpis = results.get('kpis', {})
    
    # Key Performance Metrics
    st.markdown("### 🎯 Key Performance Metrics")
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric("📊 Total Records", f"{metadata.get('total_rows', 0):,}")
    with col2:
        st.metric("🎯 Data Quality", f"{metadata.get('data_quality_score', 0):.1f}%")
    with col3:
        st.metric("🏢 Business Domain", results.get('business_domain', 'general').title())
    with col4:
        st.metric("📈 Trends Identified", len(trends))
    with col5:
        st.metric("💾 Memory Usage", f"{metadata.get('memory_usage_mb', 0):.1f} MB")
    
    # Trend Analysis Results
    if trends:
        st.markdown("### 📈 Trend Analysis Results")
        
        for metric_name, trend_data in trends.items():
            with st.expander(f"📊 {metric_name.replace('_', ' ').title()} Analysis", expanded=True):
                
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    direction = trend_data.get('trend_direction', 'stable')
                    direction_emoji = "📈" if direction == "increasing" else "📉" if direction == "decreasing" else "➡️"
                    p = trend_data.get('p_value')
                    st.metric(f"{direction_emoji} Direction", direction.replace('_', ' ').title(),
                              help=(f"Linear trend p-value {p:.3f}. A direction is shown only below 0.05; "
                                    "otherwise the changes are ups and downs, not a trend.") if p is not None else None)
                
                by_month = trend_data.get('period') == 'month'
                with col2:
                    change_pct = trend_data.get('total_change_percent', 0)
                    st.metric("📊 First → Last Month" if by_month else "📊 Start → End",
                              f"{change_pct:+.1f}%")
                
                with col3:
                    current_value = trend_data.get('current_value', 0)
                    prefix = "$" if trend_data.get('is_currency') else ""
                    latest_label = {"sum": "💰 Latest Month Total", "mean": "💰 Latest Month Avg"}.get(
                        trend_data.get('aggregation'), "💰 Recent Avg")
                    st.metric(latest_label,
                              f"{prefix}{current_value:,.2f}" if abs(current_value) < 100 else f"{prefix}{current_value:,.0f}")

                with col4:
                    strength = trend_data.get('trend_strength', 'weak')
                    st.metric("💪 Strength", strength.title())

    show_period_analysis(results)
    
    # Business Insights
    if insights:
        st.markdown("### 💡 AI-Generated Business Insights")
        
        for i, insight in enumerate(insights, 1):
            st.markdown(f"""
            <div style="background: #f8fafc; padding: 1.5rem; border-radius: 10px; margin: 0.8rem 0;
                        border-left: 4px solid #3b82f6; box-shadow: 0 2px 8px rgba(0,0,0,0.04);">
                <strong style="color: #1e293b;">{i}.</strong> 
                <span style="color: #334155;">{insight}</span>
            </div>
            """, unsafe_allow_html=True)
    
    # KPI Summary
    if kpis:
        st.markdown("### 🎯 Key Performance Indicators")
        
        kpi_cols = st.columns(min(len(kpis), 4))
        for i, (kpi_name, kpi_value) in enumerate(kpis.items()):
            with kpi_cols[i % 4]:
                if isinstance(kpi_value, (int, float)):
                    display_value = f"{kpi_value:,.0f}" if kpi_value > 1000 else f"{kpi_value:.2f}"
                    st.metric(kpi_name.replace('_', ' ').title(), display_value)
    
    # Next Steps
    st.markdown("### ⏭️ Next Steps")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🤖 Generate AI Narrative", type="primary", width="stretch"):
            st.info("👆 Go to AI Narrative Generation tab")
    
    with col2:
        if st.button("📊 View Visualizations", type="secondary", width="stretch"):
            st.session_state.show_visualizations = True

    # Render outside the button column so charts use the full width
    if st.session_state.get('show_visualizations') and st.session_state.uploaded_data is not None:
        display_advanced_visualizations()

def generate_business_visualizations(df, analysis_results):
    """Build the charts and plain-language descriptions of them (used in the prompt)."""
    
    try:
        processor = st.session_state.data_processor or AdvancedDataProcessor()
        date_col, parsed_dates = processor._find_date_column(df)
        measures = [c for c in df.select_dtypes(include=[np.number]).columns
                    if c in analysis_results.get('trends', {})] or list(df.select_dtypes(include=[np.number]).columns)
        
        if not measures:
            st.warning("⚠️ No numeric columns found for visualization")
            return
        
        viz_data = {
            'charts_generated': [],
            'chart_descriptions': []
        }
        primary = measures[0]
        label = primary.replace('_', ' ').title()
        
        # 1. Primary metric over time (monthly totals), or in file order without a date column
        if date_col is not None:
            monthly = (df.assign(Month=parsed_dates.dt.to_period('M').dt.to_timestamp())
                         .groupby('Month', as_index=False)[primary].sum())
            fig = line_trend(monthly, y=primary, x='Month', title=f"📈 Monthly {label}")
            first, last = monthly[primary].iloc[0], monthly[primary].iloc[-1]
            best = monthly.loc[monthly[primary].idxmax()]
            viz_data['charts_generated'].append(('trend', fig))
            viz_data['chart_descriptions'].append(
                f"Line chart 'Monthly {label}': {len(monthly)} months from {monthly['Month'].iloc[0]:%b %Y} "
                f"to {monthly['Month'].iloc[-1]:%b %Y}, from {first:,.0f} to {last:,.0f}; "
                f"highest in {best['Month']:%b %Y} ({best[primary]:,.0f})")
        elif len(df) > 1:
            fig = line_trend(df.reset_index(), y=primary, x='index', title=f"📈 {label} (file order)")
            viz_data['charts_generated'].append(('trend', fig))
            viz_data['chart_descriptions'].append(f"Line chart of {label} in file order ({len(df)} rows)")
        
        # 2. Breakdown by the first real category column (2-20 distinct values)
        categories = [c for c in df.select_dtypes(include=['object']).columns
                      if c != date_col and 2 <= df[c].nunique() <= 20]
        if categories:
            cat_col = categories[0]
            cat_label = cat_col.replace('_', ' ').title()
            fig = bar_top_categories(df, cat_col, primary, title=f"📊 {label} by {cat_label}")
            totals = df.groupby(cat_col)[primary].sum().sort_values(ascending=False)
            share = totals.iloc[0] / totals.sum() * 100
            viz_data['charts_generated'].append(('category', fig))
            viz_data['chart_descriptions'].append(
                f"Bar chart '{label} by {cat_label}': {len(totals)} groups; top is {totals.index[0]} "
                f"({totals.iloc[0]:,.0f}, {share:.0f}% of total), lowest is {totals.index[-1]} ({totals.iloc[-1]:,.0f})")
        
        # 3. Correlation heatmap
        if len(measures) >= 2:
            fig = heatmap_corr(df[measures], title="🔗 Correlation Between Metrics")
            corr = df[measures].corr()
            pairs = corr.where(np.triu(np.ones(corr.shape, dtype=bool), k=1)).stack()
            viz_data['charts_generated'].append(('correlation', fig))
            if len(pairs):
                (a, b), r = pairs.abs().idxmax(), pairs[pairs.abs().idxmax()]
                viz_data['chart_descriptions'].append(
                    f"Correlation heatmap of {len(measures)} metrics; strongest pair is "
                    f"{a.replace('_', ' ')} vs {b.replace('_', ' ')} (r = {r:.2f})")
        
        # Store for multimodal integration
        st.session_state.visualization_data = viz_data
        
    except Exception as e:
        st.error(f"❌ Visualization error: {e}")

def display_advanced_visualizations():
    """Display professional business visualizations."""
    
    if 'visualization_data' not in st.session_state:
        st.warning("⚠️ Generate visualizations first")
        return
    
    viz_data = st.session_state.visualization_data
    charts = viz_data.get('charts_generated', [])
    
    if not charts:
        st.info("📊 No visualizations available")
        return
    
    st.markdown("### 📊 Executive Business Visualizations")
    
    for chart_type, fig in charts:
        st.plotly_chart(fig, width="stretch")
