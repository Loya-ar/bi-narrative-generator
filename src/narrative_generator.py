"""
Narrative generation with the Google Gemini API, with every number checked.

Reads GEMINI_API_KEY (or GOOGLE_API_KEY) from the environment. Without a key,
or if the API call fails, it returns a pre-written demo narrative instead.

With an analysis, the prompt gets a fact sheet (fact_check.build_fact_sheet) and
Gemini returns JSON: the report plus the facts its numbers came from. Every number
in the report is then checked against the fact sheet; if any fail, Gemini gets one
correction pass with the real values. Use a free-tier key (no billing linked).
"""

import json
import os
import time
from datetime import datetime

from google import genai
from google.genai import types
from pydantic import BaseModel

from fact_check import build_fact_sheet, check_report, fact_sheet_text, fix_request

DEFAULT_MODEL = "gemini-3.5-flash-lite"  # free tier; gemini-2.5-flash is closed to new keys


def get_api_key():
    """GEMINI_API_KEY or GOOGLE_API_KEY; the .env.example placeholder counts as no key."""
    key = (os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY') or '').strip()
    return None if not key or key.startswith('your_') else key

JSON_INSTRUCTIONS = """
FACT SHEET (the only numbers you may use; ids in brackets):
{facts}

OUTPUT FORMAT:
Return JSON with two fields:
- "report_markdown": the full report in Markdown.
- "claims": one entry per number in the report, each with "text" (the sentence or phrase),
  "value" (the number as written, e.g. 12.3 for "12.3%") and "fact_id" (the fact sheet id it comes from).
Every number in the report must come from the fact sheet; you may round it. Don't calculate new
numbers (differences, ratios, forecasts) and don't invent targets or benchmarks.
"""


def _mean(values):
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None


class Claim(BaseModel):
    text: str
    value: float
    fact_id: str


class CheckedReport(BaseModel):
    report_markdown: str
    claims: list[Claim]


class NarrativeGenerator:
    """Real AI narrative generation using Google Gemini API (FREE)."""

    def __init__(self):
        # Get API key from environment
        self.api_key = get_api_key()
        self.model_name = os.getenv("GEMINI_MODEL", DEFAULT_MODEL)

        if self.api_key:
            try:
                # 60 s timeout: an overloaded model should fail fast, not hang the app
                self.client = genai.Client(api_key=self.api_key,
                                           http_options=types.HttpOptions(timeout=60_000))
                self.api_available = True
                print("Gemini API initialized")
            except Exception as e:
                print(f"Gemini API initialization failed: {e}")
                self.api_available = False
        else:
            self.api_available = False
            print("No Gemini API key found - using demo mode")

        self.generation_history = []

    def _call(self, prompt, structured):
        """One Gemini call. Returns (report text, claims); claims are [] for plain text."""
        if not structured:
            response = self.client.models.generate_content(model=self.model_name, contents=prompt)
            return response.text or "", []
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=CheckedReport,
                temperature=0.2,
            ),
        )
        parsed = response.parsed
        if parsed is None:  # schema not followed; fall back to the raw JSON or text
            try:
                parsed = CheckedReport.model_validate(json.loads(response.text))
            except Exception:
                return response.text or "", []
        return parsed.report_markdown, [c.model_dump() for c in parsed.claims]

    def generate_narrative(self, prompt, narrative_type='executive_summary', analysis=None):
        """Generate business narrative using Google Gemini API.

        With `analysis`, numbers are checked against it and fixed once if needed;
        the result's 'number_check' holds the outcome.
        """
        facts = build_fact_sheet(analysis) if analysis else []

        if not self.api_available:
            return self._demo_mode_response(prompt, narrative_type, facts)

        try:
            start_time = time.time()
            full_prompt = prompt + JSON_INSTRUCTIONS.format(facts=fact_sheet_text(facts)) if facts else prompt
            narrative_text, claims = self._call(full_prompt, structured=bool(facts))
            check = check_report(narrative_text, facts, claims) if facts else None
            first_check, auto_fixed = check, False

            if check is not None and check.problems:
                retry_prompt = (full_prompt + "\n\nYOUR PREVIOUS REPORT:\n" + narrative_text +
                                "\n\n" + fix_request(check, facts))
                fixed_text, fixed_claims = self._call(retry_prompt, structured=True)
                fixed_check = check_report(fixed_text, facts, fixed_claims)
                if fixed_text.strip() and len(fixed_check.problems) <= len(check.problems):
                    narrative_text, claims, check, auto_fixed = fixed_text, fixed_claims, fixed_check, True

            generation_time = time.time() - start_time

            # Calculate quality metrics
            result = {
                'narrative': narrative_text,
                'number_check_score': check.score if check is not None else None,
                'word_count': len(narrative_text.split()),
                'generation_time': generation_time,
                'estimated_cost': 0.00,  # free-tier key
                'model_used': f'Google {self.model_name}',
                'generation_method': 'gemini_api',
                'narrative_type': narrative_type,
                'api_status': 'success',
                'claims': claims,
                'number_check': check,
                'number_check_first_draft': first_check,
                'auto_fixed': auto_fixed,
            }
            
            # Store in history
            self.generation_history.append({
                'timestamp': datetime.now().isoformat(),
                'prompt_preview': prompt[:100] + "...",
                'result_preview': narrative_text[:100] + "...",
                'number_check_score': result['number_check_score'],
                'word_count': result['word_count']
            })
            
            print(f"Gemini API generated {result['word_count']} words in {generation_time:.1f}s")
            return result
            
        except Exception as e:
            print(f"Gemini API error: {e}")
            return self._handle_api_error(e, prompt, narrative_type, facts)
    
    def _demo_mode_response(self, prompt, narrative_type, facts=None):
        """Pre-written sample narrative, used when no API key is set or the API call fails.

        The samples contain no figures, so the number check finds nothing to verify.
        """
        
        demo_narratives = {
            'executive_summary': """# Executive Business Intelligence Summary

## Strategic Performance Overview
Our comprehensive data analysis reveals significant opportunities for strategic enhancement across key performance indicators. The analysis demonstrates strong data foundation with measurable trends supporting evidence-based decision making.

## Key Performance Insights
**Critical Performance Drivers:**
• Revenue optimization opportunities identified through trend analysis
• Operational efficiency metrics showing positive momentum 
• Customer acquisition patterns indicating market positioning strength
• Growth trajectory analysis supporting strategic planning initiatives

## Strategic Recommendations
1. **Performance Amplification**: Scale successful initiatives demonstrating positive growth patterns
2. **Operational Excellence**: Implement systematic improvements in underperforming areas
3. **Strategic Focus**: Prioritize high-impact opportunities with measurable ROI potential
4. **Continuous Intelligence**: Establish ongoing monitoring for sustained competitive advantage

## Executive Action Plan
Leadership should prioritize data-driven strategic initiatives that capitalize on identified growth opportunities while addressing performance risks through targeted operational improvements.""",

            'detailed_analysis': """# Comprehensive Business Intelligence Analysis

## Executive Summary
This detailed analysis examines business performance across multiple dimensions, providing strategic insights for operational excellence and sustainable growth.

## Performance Analysis Deep Dive
**Quantitative Performance Assessment:**
• Statistical trend analysis reveals performance patterns with high confidence intervals
• Correlation analysis identifies key business driver relationships
• Variance analysis highlights areas requiring strategic attention
• Predictive indicators suggest future performance trajectories

**Operational Excellence Metrics:**
• Efficiency ratios demonstrate operational capability benchmarks
• Quality indicators support strategic decision-making processes  
• Resource utilization patterns indicate optimization opportunities
• Performance consistency metrics guide strategic planning

## Strategic Intelligence Insights
**Growth Opportunity Matrix:**
• Market positioning analysis reveals competitive advantages
• Customer acquisition cost optimization potential identified
• Revenue diversification opportunities assessed
• Operational scaling strategies developed

## Comprehensive Recommendations
**Immediate Strategic Priorities:**
1. **Data-Driven Decision Making**: Leverage analytical foundation for strategic advantage
2. **Performance Optimization**: Implement systematic improvement processes
3. **Risk Mitigation**: Address identified performance gaps proactively
4. **Strategic Innovation**: Capitalize on market positioning opportunities

## Implementation Roadmap
Establish quarterly performance reviews utilizing advanced analytics for continued strategic excellence and measurable business impact."""
        }
        
        selected_narrative = demo_narratives.get(narrative_type, demo_narratives['executive_summary'])
        
        return {
            'narrative': selected_narrative,
            'word_count': len(selected_narrative.split()),
            'generation_time': 0.0,
            'estimated_cost': 0.00,
            'model_used': 'Demo mode (pre-written sample, no API call)',
            'generation_method': 'demo_mode',
            'narrative_type': narrative_type,
            'api_status': 'demo_fallback',
            'claims': [],
            'number_check': check_report(selected_narrative, facts) if facts else None,
            'number_check_score': None,  # the samples contain no figures
            'number_check_first_draft': None,
            'auto_fixed': False,
        }

    def _handle_api_error(self, error, prompt, narrative_type, facts=None):
        """Handle API errors gracefully."""
        error_msg = str(error)
        
        if "quota" in error_msg.lower() or "limit" in error_msg.lower():
            status = "quota_exceeded"
            solution = "API quota exceeded - showing the demo narrative"
        elif "key" in error_msg.lower() or "auth" in error_msg.lower():
            status = "auth_error" 
            solution = "API authentication issue - verify API key"
        else:
            status = "general_error"
            solution = "API temporarily unavailable - using demo fallback"
        
        demo_result = self._demo_mode_response(prompt, narrative_type, facts)
        demo_result.update({
            'api_error': error_msg,
            'error_status': status,
            'solution': solution,
            'api_status': 'error_fallback'
        })
        
        return demo_result
    
    def test_api_connection(self):
        """Test Gemini API connection."""
        
        if not self.api_available:
            return {
                'status': 'unavailable',
                'message': 'No API key configured',
                'solution': 'Add GEMINI_API_KEY to environment variables'
            }
        
        try:
            test_response = self.client.models.generate_content(
                model=self.model_name,
                contents="Test connection - respond with 'API working'"
            )
            
            return {
                'status': 'success',
                'message': 'Gemini API connection successful',
                'response': test_response.text,
                'model': self.model_name
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': f'API test failed: {e}',
                'solution': 'Check API key and internet connection'
            }
    
    def get_usage_stats(self):
        """Get API usage statistics."""
        return {
            'total_generations': len(self.generation_history),
            'api_available': self.api_available,
            'model_used': self.model_name if self.api_available else 'Demo Mode',
            'average_number_check_score': _mean([h['number_check_score'] for h in self.generation_history]),
            'total_words_generated': sum(h['word_count'] for h in self.generation_history),
            'generation_history': self.generation_history[-5:]  # Last 5 generations
        }