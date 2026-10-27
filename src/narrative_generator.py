"""
Narrative generation with the Google Gemini API.

Reads GEMINI_API_KEY (or GOOGLE_API_KEY) from the environment. Without a key,
or if the API call fails, it returns a pre-written demo narrative instead.
"""

import os
import time
import json
from datetime import datetime
from google import genai

class NarrativeGenerator:
    """Real AI narrative generation using Google Gemini API (FREE)."""
    
    def __init__(self):
        # Get API key from environment
        self.api_key = os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')
        
        if self.api_key:
            try:
                # Initialize Gemini client
                self.client = genai.Client(api_key=self.api_key)
                self.model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
                self.api_available = True
                print("Gemini API initialized")
            except Exception as e:
                print(f"Gemini API initialization failed: {e}")
                self.api_available = False
        else:
            self.api_available = False
            print("No Gemini API key found - using demo mode")
        
        self.generation_history = []
    
    def generate_narrative(self, prompt, narrative_type='executive_summary'):
        """Generate business narrative using Google Gemini API."""
        
        if not self.api_available:
            return self._demo_mode_response(prompt, narrative_type)
        
        try:
            start_time = time.time()
            
            # Make actual API call to Google Gemini
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )
            
            generation_time = time.time() - start_time
            narrative_text = response.text
            
            # Calculate quality metrics
            result = {
                'narrative': narrative_text,
                'quality_score': self._assess_quality(narrative_text),
                'word_count': len(narrative_text.split()),
                'generation_time': generation_time,
                'estimated_cost': 0.00,  # Gemini is free!
                'model_used': f'Google {self.model_name}',
                'generation_method': 'gemini_api',
                'narrative_type': narrative_type,
                'meets_quality_threshold': len(narrative_text.split()) > 200,
                'api_status': 'success'
            }
            
            # Store in history
            self.generation_history.append({
                'timestamp': datetime.now().isoformat(),
                'prompt_preview': prompt[:100] + "...",
                'result_preview': narrative_text[:100] + "...",
                'quality_score': result['quality_score'],
                'word_count': result['word_count']
            })
            
            print(f"Gemini API generated {result['word_count']} words in {generation_time:.1f}s")
            return result
            
        except Exception as e:
            print(f"Gemini API error: {e}")
            return self._handle_api_error(e, prompt, narrative_type)
    
    def _assess_quality(self, narrative_text):
        """Assess narrative quality with comprehensive metrics."""
        words = narrative_text.split()
        
        quality_factors = {
            'appropriate_length': 200 <= len(words) <= 3000,
            'has_structure': any(marker in narrative_text for marker in ['##', '**', '1.', '2.', '•']),
            'business_language': any(term in narrative_text.lower() for term in 
                                   ['strategic', 'performance', 'analysis', 'recommendations', 'insights']),
            'includes_metrics': any(char in narrative_text for char in ['%', '$', ':']),
            'professional_tone': 'strategic' in narrative_text.lower() and 'executive' in narrative_text.lower(),
            'actionable_content': any(word in narrative_text.lower() for word in 
                                    ['recommend', 'should', 'implement', 'focus', 'prioritize']),
            'data_driven': any(word in narrative_text.lower() for word in 
                             ['data', 'analysis', 'trends', 'metrics', 'performance'])
        }
        
        quality_score = sum(quality_factors.values()) / len(quality_factors) * 100
        
        # Bonus points for exceptional content
        if len(words) > 500 and any(phrase in narrative_text.lower() for phrase in 
                                   ['competitive advantage', 'strategic initiative', 'operational excellence']):
            quality_score = min(100, quality_score + 5)
        
        return round(quality_score, 1)
    
    def _demo_mode_response(self, prompt, narrative_type):
        """Pre-written sample narrative, used when no API key is set or the API call fails."""
        
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
            'quality_score': self._assess_quality(selected_narrative),
            'word_count': len(selected_narrative.split()),
            'generation_time': 0.0,
            'estimated_cost': 0.00,
            'model_used': 'Demo mode (pre-written sample, no API call)',
            'generation_method': 'demo_mode',
            'narrative_type': narrative_type,
            'meets_quality_threshold': True,
            'api_status': 'demo_fallback'
        }
    
    def _handle_api_error(self, error, prompt, narrative_type):
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
        
        demo_result = self._demo_mode_response(prompt, narrative_type)
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
            'average_quality': sum(h['quality_score'] for h in self.generation_history) / max(1, len(self.generation_history)),
            'total_words_generated': sum(h['word_count'] for h in self.generation_history),
            'generation_history': self.generation_history[-5:]  # Last 5 generations
        }