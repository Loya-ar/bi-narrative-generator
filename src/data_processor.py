"""
Advanced Data Processor - Working Implementation
Author: Arjun Loya
"""

import re

import pandas as pd
import numpy as np
from scipy import stats
import warnings
warnings.filterwarnings('ignore')

class AdvancedDataProcessor:
    """Advanced data processing with statistical analysis."""
    
    def __init__(self):
        self.analysis_results = {}
    
    def load_and_analyze_data(self, file_path):
        """Load and perform comprehensive analysis."""
        try:
            # Load data with encoding support
            if file_path.endswith('.csv'):
                encodings = ['utf-8', 'latin-1', 'iso-8859-1', 'cp1252']
                df = None
                
                for encoding in encodings:
                    try:
                        df = pd.read_csv(file_path, encoding=encoding)
                        break
                    except UnicodeDecodeError:
                        continue
                    except Exception:
                        continue
                        
                if df is None:
                    raise ValueError("Could not read CSV with any supported encoding")
            else:
                df = pd.read_excel(file_path)
            
            # Perform comprehensive analysis
            results = self._analyze_dataframe(df)
            return results
            
        except Exception as e:
            raise Exception(f"Data processing error: {e}")
    
    def _analyze_dataframe(self, df):
        """Perform comprehensive DataFrame analysis."""
        monthly = self._monthly(df)
        results = {
            'metadata': self._get_metadata(df),
            'trends': self._analyze_trends(df, monthly),
            'insights': self._generate_insights(df),
            'business_domain': self._detect_domain(df),
            'kpis': self._calculate_kpis(df),
            'correlations': self._analyze_correlations(df),
            'period_comparisons': self._period_comparisons(monthly),
            'drivers': self._drivers(df, monthly),
            'anomalies': self._anomalies(monthly),
        }
        return results
    
    def _get_metadata(self, df):
        """Extract metadata from DataFrame."""
        return {
            'total_rows': len(df),
            'total_columns': len(df.columns),
            'numeric_columns': len(df.select_dtypes(include=[np.number]).columns),
            'data_quality_score': self._calculate_quality_score(df),
            'memory_usage_mb': df.memory_usage(deep=True).sum() / 1024 / 1024
        }
    
    def _calculate_quality_score(self, df):
        """Calculate data quality score."""
        completeness = 1 - (df.isnull().sum().sum() / (len(df) * len(df.columns)))
        uniqueness = 1 - (df.duplicated().sum() / len(df))
        quality_score = (completeness * 0.7 + uniqueness * 0.3) * 100
        return min(100, max(0, quality_score))
    
    # Numeric columns that are date parts or identifiers, not business measures
    _NON_MEASURES = ('month', 'quarter', 'year', 'day', 'week', 'id')
    _CURRENCY_WORDS = ('sales', 'revenue', 'amount', 'commission', 'cost', 'budget',
                       'spend', 'price', 'profit', 'income', 'expense', 'per_unit')

    def _find_date_column(self, df):
        """Return the first column that parses as dates, or None."""
        for col in df.columns:
            if not any(word in col.lower() for word in ('date', 'week', 'time', 'period')):
                continue
            parsed = pd.to_datetime(df[col], errors='coerce')
            if parsed.notna().mean() > 0.8:
                return col, parsed
        return None, None

    # Measures that are rates or ratios: averaged per month. Everything else is summed.
    # Matched as whole words, so "Operational" doesn't count as "ratio".
    _RATIO_WORDS = {'rate', 'percent', 'pct', 'ratio', 'margin', 'per', 'ctr', 'roas',
                    'score', 'average', 'avg'}
    _RATIO_PHRASES = ('return_on', 'acquisition_cost', 'lifetime_value')
    _MIN_CHANGE_TO_EXPLAIN = 5.0  # % change below which a segment breakdown isn't shown
    _SIGNIFICANCE = 0.05   # a trend counts only if the regression p-value is below this
    _MAX_MEASURES = 5      # measures analysed per file
    _MAX_SEGMENTS = 12     # a column with more distinct values isn't used to explain changes

    def _measures(self, df):
        return [c for c in df.select_dtypes(include=[np.number]).columns
                if not any(c.lower() == w or c.lower().endswith('_' + w) or c.lower().startswith(w + '_')
                           for w in self._NON_MEASURES)]

    def _aggregation(self, col):
        name = col.lower()
        words = set(re.split(r'[^a-z]+', name))
        is_ratio = bool(words & self._RATIO_WORDS) or any(p in name for p in self._RATIO_PHRASES)
        return 'mean' if is_ratio else 'sum'

    def _monthly(self, df):
        """Monthly totals (or averages, for rates) of each measure, or None without a date column.

        Returns {'table': DataFrame indexed by month, 'agg': {measure: 'sum'|'mean'},
                 'periods': month of each row, 'measures': [...]}.
        """
        date_col, parsed_dates = self._find_date_column(df)
        if date_col is None:
            return None
        measures = self._measures(df)[:self._MAX_MEASURES]
        if not measures:
            return None
        periods = parsed_dates.dt.to_period('M')
        agg = {c: self._aggregation(c) for c in measures}
        table = df.assign(_period=periods).dropna(subset=['_period']).groupby('_period')[measures].agg(agg)
        return {'table': table, 'agg': agg, 'periods': periods, 'measures': measures}

    def _analyze_trends(self, df, monthly=None):
        """Analyze trends in numeric columns.

        With a date column, each measure is totalled per month (averaged for rates and
        ratios) and the trend is fitted on those monthly values. Without one, rows are
        taken in file order and the change compares the first and last 10% of rows.
        """
        trends = {}
        if monthly is not None:
            measures = monthly['measures']
            series_by_col = {c: monthly['table'][c] for c in measures}
            period = 'month'
        else:
            measures = self._measures(df)[:self._MAX_MEASURES]
            series_by_col = {c: df[c] for c in measures}
            period = 'row'

        for col in measures:
            series = series_by_col[col].dropna()
            if len(series) >= 3 and (period == 'month' or len(series) > 10):
                trend_data = self._analyze_column_trend(series, period)
                trend_data['is_currency'] = any(w in col.lower() for w in self._CURRENCY_WORDS)
                trend_data['aggregation'] = monthly['agg'][col] if monthly is not None else 'row'
                trends[col] = trend_data

        return trends

    def _analyze_column_trend(self, series, period='row'):
        """Analyze trend for a single (already ordered) series."""
        clean_series = series.dropna()

        if len(clean_series) < 3:
            return {'trend_direction': 'insufficient_data'}

        # Linear regression
        x = np.arange(len(clean_series))
        y = clean_series.values.astype(float)

        slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)
        significant = bool(p_value < self._SIGNIFICANCE)

        # Determine trend: a direction is claimed only when the slope is statistically
        # significant; otherwise the series is noise around a level, whatever its sign.
        if not significant:
            direction = 'no_clear_trend'
            strength = 'none'
        elif abs(slope) * len(y) < np.std(y) * 0.5:
            direction = 'stable'
            strength = 'weak'
        elif slope > 0:
            direction = 'increasing'
            strength = 'strong' if r_value**2 > 0.7 else 'moderate' if r_value**2 > 0.3 else 'weak'
        else:
            direction = 'decreasing'
            strength = 'strong' if r_value**2 > 0.7 else 'moderate' if r_value**2 > 0.3 else 'weak'

        # Percentage change: first vs last month, or first vs last 10% of rows
        window = 1 if period == 'month' else max(1, len(y) // 10)
        first_val = y[:window].mean()
        last_val = y[-window:].mean()
        pct_change = ((last_val - first_val) / abs(first_val) * 100) if first_val != 0 else 0

        return {
            'trend_direction': direction,
            'trend_strength': strength,
            'total_change_percent': pct_change,
            'current_value': last_val,
            'average_value': np.mean(y),
            'r_squared': r_value**2,
            'p_value': p_value,
            'significant': significant,
            'slope': slope,
            'period': period,
            'volatility_level': 'high' if np.std(y) / abs(np.mean(y)) > 0.3 else 'low'
        }

    def _period_comparisons(self, monthly):
        """Latest month vs the month before, and vs the same month a year earlier."""
        if monthly is None:
            return {}
        table, out = monthly['table'], {}
        for col in monthly['measures']:
            series = table[col].dropna()
            if len(series) < 2:
                continue
            latest_period, latest, previous = series.index[-1], series.iloc[-1], series.iloc[-2]
            entry = {
                'aggregation': monthly['agg'][col],
                'latest_period': str(latest_period),
                'latest_value': float(latest),
                'previous_period': str(series.index[-2]),
                'previous_value': float(previous),
                'mom_change_pct': self._pct_change(previous, latest),
                'yoy_period': None,
                'yoy_value': None,
                'yoy_change_pct': None,
            }
            year_ago = latest_period - 12
            if year_ago in series.index:
                entry.update(yoy_period=str(year_ago), yoy_value=float(series[year_ago]),
                             yoy_change_pct=self._pct_change(series[year_ago], latest))
            out[col] = entry
        return out

    @staticmethod
    def _pct_change(old, new):
        return float((new - old) / abs(old) * 100) if old else None

    def _segment_columns(self, df):
        """Text columns with 2-12 values that describe a segment (region, product, channel...)."""
        date_parts = ('month', 'quarter', 'day', 'week', 'year', 'date', 'time', 'period')
        return [c for c in df.select_dtypes(include=['object', 'category', 'string']).columns
                if not any(w in c.lower() for w in date_parts)
                and 2 <= df[c].nunique() <= self._MAX_SEGMENTS]

    def _drivers(self, df, monthly, max_dimensions=2, top=3):
        """Which segments drove the change in the main measure, first month to last.

        Only for summed measures (a share of a change in an average isn't additive).
        """
        if monthly is None:
            return {}
        summed = [c for c in monthly['measures'] if monthly['agg'][c] == 'sum']
        if not summed:
            return {}
        measure = next((c for c in summed if any(w in c.lower() for w in self._CURRENCY_WORDS)), summed[0])
        periods = monthly['periods']
        months = monthly['table'].index
        first, last = months[0], months[-1]
        if first == last:
            return {}

        out = {}
        for dim in self._segment_columns(df)[:max_dimensions]:
            frame = df.assign(_period=periods)
            by_segment = (frame[frame['_period'].isin([first, last])]
                          .groupby([dim, '_period'])[measure].sum().unstack(fill_value=0))
            by_segment = by_segment.reindex(columns=[first, last], fill_value=0)
            change = by_segment[last] - by_segment[first]
            total_change = change.sum()
            total_change_pct = self._pct_change(by_segment[first].sum(), by_segment[last].sum())
            if not total_change or total_change_pct is None or abs(total_change_pct) < self._MIN_CHANGE_TO_EXPLAIN:
                continue
            ranked = change.reindex(change.abs().sort_values(ascending=False).index)[:top]
            out[dim] = {
                'measure': measure,
                'from_period': str(first),
                'to_period': str(last),
                'total_change': float(total_change),
                'total_change_pct': total_change_pct,
                'segments': [{'segment': str(seg), 'change': float(v),
                              'share_of_change_pct': float(v / total_change * 100)}
                             for seg, v in ranked.items()],
            }
        return out

    def _anomalies(self, monthly, threshold=3.5, limit=5):
        """Months far from the usual level (robust z-score on median and MAD above 3.5)."""
        if monthly is None:
            return []
        found = []
        for col in monthly['measures']:
            series = monthly['table'][col].dropna()
            if len(series) < 6:
                continue
            median = series.median()
            mad = (series - median).abs().median()
            if not mad:
                continue
            robust_z = 0.6745 * (series - median) / mad
            for period, z in robust_z[robust_z.abs() > threshold].items():
                found.append({
                    'measure': col,
                    'period': str(period),
                    'value': float(series[period]),
                    'typical_value': float(median),
                    'deviation_pct': self._pct_change(median, series[period]),
                    'robust_z': float(z),
                })
        return sorted(found, key=lambda a: -abs(a['robust_z']))[:limit]

    def _detect_domain(self, df):
        """Detect business domain from column names."""
        columns_text = ' '.join(df.columns).lower()
        
        domain_keywords = {
            'sales': ['revenue', 'sales', 'orders', 'customers', 'deals', 'units'],
            'marketing': ['campaign', 'impressions', 'clicks', 'ctr', 'roas', 'leads'],
            'finance': ['profit', 'margin', 'expenses', 'cost', 'budget', 'cash'],
            'hr': ['employee', 'salary', 'performance', 'training'],
            'operations': ['efficiency', 'productivity', 'capacity', 'inventory']
        }
        
        domain_scores = {}
        for domain, keywords in domain_keywords.items():
            score = sum(1 for keyword in keywords if keyword in columns_text)
            domain_scores[domain] = score
        
        return max(domain_scores, key=domain_scores.get) if max(domain_scores.values()) > 0 else 'general'
    
    def _calculate_kpis(self, df, domain=None):
        """Calculate relevant KPIs."""
        kpis = {}
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        
        if len(numeric_cols) > 0:
            primary_col = numeric_cols[0]
            kpis[f'{primary_col}_total'] = df[primary_col].sum()
            kpis[f'{primary_col}_average'] = df[primary_col].mean()
            kpis['total_records'] = len(df)
            
            if len(numeric_cols) > 1:
                secondary_col = numeric_cols[1] 
                kpis['efficiency_ratio'] = df[primary_col].sum() / df[secondary_col].sum() if df[secondary_col].sum() != 0 else 0
        
        return kpis
    
    def _analyze_correlations(self, df):
        """Analyze correlations between numeric columns."""
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        
        if len(numeric_cols) < 2:
            return {}
        
        corr_matrix = df[numeric_cols].corr()
        
        return {
            'matrix': corr_matrix.to_dict(),
            'summary': {
                'avg_correlation': np.mean(np.abs(corr_matrix.values)),
                'max_correlation': np.max(corr_matrix.values),
                'min_correlation': np.min(corr_matrix.values)
            }
        }
    
    def _generate_insights(self, df):
        """Generate business insights."""
        insights = []
        
        # Basic insights
        insights.append(f"Dataset contains {len(df):,} records across {len(df.columns)} dimensions")
        
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        if len(numeric_cols) > 0:
            primary_metric = numeric_cols[0]
            total_value = df[primary_metric].sum()
            insights.append(f"Total {primary_metric.replace('_', ' ')}: ${total_value:,.0f}")
        
        # Data quality insight
        completeness = 1 - (df.isnull().sum().sum() / (len(df) * len(df.columns)))
        if completeness > 0.95:
            insights.append("Excellent data quality enables confident analysis")
        elif completeness > 0.8:
            insights.append("Good data quality with minor gaps")
        else:
            insights.append("Data quality improvements recommended")
        
        return insights