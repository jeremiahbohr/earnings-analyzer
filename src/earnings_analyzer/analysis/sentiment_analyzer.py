import google.generativeai as genai
import json
import logging
import time
import re
from typing import Dict, List, Optional, Union
from earnings_analyzer.config import get_gemini_api_key

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# Available Gemini models (as of 2024)
VALID_GEMINI_MODELS = {
    'gemini-2.5-flash',
    'gemini-1.5-pro',
    'gemini-1.5-flash',
    'gemini-pro'
}

# Rate limiting tracking
_last_request_time = 0
_request_count = 0
_rate_limit_window_start = 0

def _validate_model_name(model_name):
    """Validate that the model name is supported."""
    if not model_name or not isinstance(model_name, str):
        return False
        
    # Check against known models
    if model_name in VALID_GEMINI_MODELS:
        return True
        
    # Allow versioned models (e.g., gemini-1.5-pro-001)
    base_model = re.sub(r'-\d{3}$', '', model_name)
    if base_model in VALID_GEMINI_MODELS:
        return True
        
    logging.warning(f"Model '{model_name}' not in known model list. Proceeding anyway.")
    return True  # Allow unknown models but warn

def _handle_rate_limiting():
    """Handle rate limiting for Gemini API requests."""
    global _last_request_time, _request_count, _rate_limit_window_start
    
    current_time = time.time()
    
    # Reset counter every minute
    if current_time - _rate_limit_window_start > 60:
        _request_count = 0
        _rate_limit_window_start = current_time
    
    # Gemini free tier: 15 requests per minute
    if _request_count >= 15:
        wait_time = 60 - (current_time - _rate_limit_window_start)
        if wait_time > 0:
            logging.info(f"Rate limit reached. Waiting {wait_time:.1f} seconds...")
            time.sleep(wait_time)
            _request_count = 0
            _rate_limit_window_start = time.time()
    
    # Ensure minimum 1 second between requests
    time_since_last = current_time - _last_request_time
    if time_since_last < 1.0:
        time.sleep(1.0 - time_since_last)
    
    _last_request_time = time.time()
    _request_count += 1

def _sanitize_json_response(response_text):
    """Clean and extract JSON from Gemini response."""
    if not response_text:
        return None
        
    # Remove markdown code blocks
    cleaned = re.sub(r'```json\s*', '', response_text)
    cleaned = re.sub(r'```\s*$', '', cleaned)
    cleaned = cleaned.strip()
    
    # Try to find JSON object within the response
    json_patterns = [
        r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}',  # Nested JSON object
        r'\{.*?\}',  # Simple JSON object
    ]
    
    for pattern in json_patterns:
        matches = re.findall(pattern, cleaned, re.DOTALL)
        for match in matches:
            try:
                return json.loads(match)
            except json.JSONDecodeError:
                continue
    
    # If no JSON pattern found, try to parse the whole response
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return None

def _validate_sentiment_response(data, expected_fields):
    """Validate that sentiment response has expected structure."""
    if not isinstance(data, dict):
        return False
        
    # Check required fields
    for field in expected_fields:
        if field not in data:
            logging.warning(f"Missing required field in sentiment response: {field}")
            return False
    
    # Validate data types and ranges
    if 'overall_sentiment_score' in data:
        score = data['overall_sentiment_score']
        if not isinstance(score, (int, float)) or not (1 <= score <= 10):
            logging.warning(f"Invalid sentiment score: {score}. Must be number between 1-10")
            return False
    
    if 'confidence_level' in data:
        confidence = data['confidence_level']
        if not isinstance(confidence, (int, float)) or not (0.0 <= confidence <= 1.0):
            logging.warning(f"Invalid confidence level: {confidence}. Must be number between 0.0-1.0")
            return False
    
    if 'key_themes' in data:
        themes = data['key_themes']
        if not isinstance(themes, list):
            logging.warning(f"Invalid key_themes format: {type(themes)}. Must be list")
            return False
        
        # Validate individual themes
        for theme in themes:
            if not isinstance(theme, str) or len(theme.strip()) == 0:
                logging.warning(f"Invalid theme in key_themes: {theme}")
                return False
    
    return True

def _make_gemini_request(model, prompt, max_retries=3):
    """Make request to Gemini API with retry logic and error handling."""
    for attempt in range(max_retries):
        try:
            _handle_rate_limiting()
            
            response = model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.1,  # Low temperature for consistent results
                    max_output_tokens=2048,
                    candidate_count=1
                )
            )
            
            if not response or not response.text:
                logging.warning(f"Empty response from Gemini (attempt {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                    continue
                return None
            
            return response
            
        except Exception as e:
            error_msg = str(e).lower()
            
            # Handle specific error types
            if 'quota' in error_msg or 'rate limit' in error_msg:
                wait_time = 60 * (2 ** attempt)  # Exponential backoff for quota errors
                logging.warning(f"API quota/rate limit hit. Waiting {wait_time} seconds...")
                time.sleep(wait_time)
                continue
                
            elif 'invalid api key' in error_msg or 'authentication' in error_msg:
                logging.error("Invalid Gemini API key. Please check your GEMINI_API_KEY environment variable.")
                return None
                
            elif 'safety' in error_msg or 'blocked' in error_msg:
                logging.error("Content was blocked by Gemini safety filters")
                return None
                
            elif attempt < max_retries - 1:
                logging.warning(f"Gemini API error (attempt {attempt + 1}/{max_retries}): {e}")
                time.sleep(2 ** attempt)  # Exponential backoff
                continue
            else:
                logging.error(f"Final Gemini API error after {max_retries} attempts: {e}")
                return None
    
    return None

def score_sentiment(transcript_text: str, model_name: str = "gemini-2.5-flash", 
                   custom_prompt: Optional[str] = None, include_key_themes: bool = True, 
                   include_qualitative_assessment: bool = True) -> Optional[Dict]:
    """
    Main composable function to analyze the sentiment of an earnings call transcript using the Gemini API.
    
    This is the primary function for sentiment analysis that can be used
    independently in data pipelines.

    Args:
        transcript_text (str): The full text of the earnings call transcript.
        model_name (str): The name of the Gemini model to use (e.g., 'gemini-2.5-flash', 'gemini-1.5-pro').
        custom_prompt (str, optional): Complete custom prompt to send to Gemini. If provided, overrides the default prompt and ignores include_* parameters.
        include_key_themes (bool): Whether to extract key themes. Defaults to True. Ignored if custom_prompt is provided.
        include_qualitative_assessment (bool): Whether to include qualitative assessment. Defaults to True. Ignored if custom_prompt is provided.

    Returns:
        dict: A dictionary containing the sentiment analysis results. Structure depends on prompt used:
        
        Default prompt returns:
            - overall_sentiment_score: float (1-10 scale)
            - confidence_level: float (0.0-1.0)
            - key_themes: list of str (only if include_key_themes=True, empty list otherwise)
            - qualitative_assessment: str (only if include_qualitative_assessment=True, empty string otherwise)
            - model_name: str (the model used for analysis)
            
        Custom prompt returns:
            - Raw JSON response from Gemini (structure depends on custom prompt)
            - model_name: str (added automatically)
            
        None: If analysis fails or transcript is empty.
    """
    # Input validation
    if not transcript_text or not isinstance(transcript_text, str):
        logging.error("transcript_text must be a non-empty string")
        return None
        
    transcript_text = transcript_text.strip()
    if len(transcript_text) < 100:
        logging.warning(f"Transcript text is very short ({len(transcript_text)} chars). Results may be unreliable.")
    
    if not _validate_model_name(model_name):
        logging.error(f"Invalid model name: {model_name}")
        return None

    # Check API key
    api_key = get_gemini_api_key()
    if not api_key:
        logging.error("GEMINI_API_KEY is not set in the environment variables. Please set it to use Gemini API.")
        return None

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name)
        
        if custom_prompt:
            # Use custom prompt exactly as provided
            if len(transcript_text) > 30000:  # Truncate very long transcripts
                logging.warning("Transcript is very long, truncating to 30000 characters")
                transcript_text = transcript_text[:30000] + "..."
                
            prompt = f"{custom_prompt}\n\nTranscript:\n---\n{transcript_text}\n---"
            logging.info("Using custom prompt for sentiment analysis")
            expected_fields = []  # Can't validate custom prompt structure
        else:
            # Use default prompt with configurable options
            prompt_parts = [
                "As a financial analyst, please analyze the following earnings call transcript.",
                "Based on the language, tone, and key topics discussed by the executives, provide a sentiment analysis.",
                "Return your analysis as a JSON object with the following fields:"
            ]
            
            field_descriptions = [
                "1. `overall_sentiment_score`: A numerical score from 1 (very negative) to 10 (very positive).",
                "2. `confidence_level`: Your confidence in this sentiment score, from 0.0 to 1.0."
            ]
            
            expected_fields = ['overall_sentiment_score', 'confidence_level']
            field_count = 2
            
            if include_key_themes:
                field_count += 1
                field_descriptions.append(f"{field_count}. `key_themes`: A JSON list of the top 3-5 most important themes or topics discussed.")
                expected_fields.append('key_themes')
            
            if include_qualitative_assessment:
                field_count += 1
                if include_key_themes:
                    assessment_desc = f"{field_count}. `qualitative_assessment`: A 2-3 sentence qualitative assessment of the executive sentiment during the earnings call, focusing on the overall tone and the implications of the key themes."
                else:
                    assessment_desc = f"{field_count}. `qualitative_assessment`: A 2-3 sentence qualitative assessment of the executive sentiment during the earnings call, focusing on the overall tone."
                field_descriptions.append(assessment_desc)
                expected_fields.append('qualitative_assessment')
            
            # Add instructions for JSON format
            field_descriptions.extend([
                "",
                "Important: Return ONLY valid JSON. Do not include any explanation or markdown formatting.",
                "Ensure all string values are properly escaped and the JSON is valid."
            ])
            
            # Truncate transcript if too long
            if len(transcript_text) > 25000:  # Leave room for prompt
                logging.warning("Transcript is very long, truncating to 25000 characters")
                transcript_text = transcript_text[:25000] + "..."
            
            # Construct full prompt
            prompt = "\n".join(prompt_parts + field_descriptions + [
                "",
                "Transcript:",
                "---",
                transcript_text,
                "---"
            ])
        
        response = _make_gemini_request(model, prompt)
        if not response:
            logging.error("Failed to get response from Gemini API")
            return None
            
        # Parse JSON response
        analysis_result = _sanitize_json_response(response.text)
        
        if analysis_result is None:
            logging.error(f"Failed to parse JSON from Gemini response. Raw response: {response.text[:500]}...")
            return None
        
        if custom_prompt:
            # For custom prompts, we can't validate expected fields since we don't know the structure
            # Just add model_name and return whatever Gemini provided
            analysis_result['model_name'] = model_name
            logging.info("Successfully completed custom prompt sentiment analysis")
            return analysis_result
        else:
            # Validate the expected fields are present for default prompt
            if not _validate_sentiment_response(analysis_result, expected_fields):
                logging.error("Gemini response failed validation")
                return None
            
            # Ensure optional fields are always present (empty if not included)
            if not include_key_themes:
                analysis_result['key_themes'] = []
            if not include_qualitative_assessment:
                analysis_result['qualitative_assessment'] = ""
            
            # Add model name to result
            analysis_result['model_name'] = model_name
                
            logging.info(f"Successfully analyzed sentiment with score: {analysis_result.get('overall_sentiment_score')}")
            return analysis_result
        
    except Exception as e:
        logging.error(f"Unexpected error during sentiment analysis: {e}")
        return None

def batch_score_sentiment(transcripts: List[Union[str, Dict]], model_name: str = "gemini-2.5-flash", 
                         custom_prompt: Optional[str] = None, include_key_themes: bool = True, 
                         include_qualitative_assessment: bool = True) -> List[Optional[Dict]]:
    """
    Analyzes sentiment for multiple transcripts in batch.
    
    This function is useful for processing multiple earnings calls efficiently
    in data pipeline scenarios.
    
    Args:
        transcripts (list): List of transcript texts or dict objects with 'transcript_text' key
        model_name (str): The name of the Gemini model to use
        custom_prompt (str, optional): Complete custom prompt to send to Gemini. If provided, overrides default prompt.
        include_key_themes (bool): Whether to extract key themes. Defaults to True. Ignored if custom_prompt provided.
        include_qualitative_assessment (bool): Whether to include qualitative assessment. Defaults to True. Ignored if custom_prompt provided.
        
    Returns:
        list: List of sentiment analysis results in the same order as input.
              Failed analyses will be None in the corresponding position.
    """
    if not transcripts or not isinstance(transcripts, list):
        logging.error("transcripts must be a non-empty list")
        return []
    
    results = []
    
    for i, transcript in enumerate(transcripts):
        logging.info(f"Processing transcript {i+1}/{len(transcripts)}")
        
        try:
            # Handle both string transcripts and dict objects
            if isinstance(transcript, dict):
                transcript_text = transcript.get('transcript_text', '')
                if not transcript_text:
                    logging.warning(f"Transcript {i+1} has no 'transcript_text' field")
                    results.append(None)
                    continue
            elif isinstance(transcript, str):
                transcript_text = transcript
            else:
                logging.warning(f"Invalid transcript type at position {i+1}: {type(transcript)}")
                results.append(None)
                continue
                
            result = score_sentiment(transcript_text, model_name, custom_prompt, 
                                   include_key_themes, include_qualitative_assessment)
            results.append(result)
            
        except Exception as e:
            logging.error(f"Error processing transcript {i+1}: {e}")
            results.append(None)
        
        # Small delay between requests to be respectful to API
        if i < len(transcripts) - 1:  # Don't sleep after last request
            time.sleep(1)
        
    return results

def validate_sentiment_result(sentiment_result: Dict) -> bool:
    """
    Validates that a sentiment analysis result has the expected structure.
    
    Args:
        sentiment_result (dict): The result from score_sentiment()
        
    Returns:
        bool: True if the result is valid, False otherwise
    """
    if not isinstance(sentiment_result, dict):
        return False
        
    # For default prompt results, check required fields
    if 'overall_sentiment_score' in sentiment_result:
        required_fields = {
            'overall_sentiment_score': (int, float),
            'confidence_level': (int, float),
            'key_themes': list,
            'qualitative_assessment': str,
            'model_name': str
        }
        
        return _validate_sentiment_response(sentiment_result, list(required_fields.keys()))
    else:
        # For custom prompt results, just check that model_name exists
        return 'model_name' in sentiment_result

def get_sentiment_summary(sentiment_results: List[Dict]) -> Optional[Dict]:
    """
    Creates a summary of multiple sentiment analysis results.
    
    Useful for analyzing trends across multiple earnings calls.
    
    Args:
        sentiment_results (list): List of sentiment analysis result dictionaries
        
    Returns:
        dict: Summary statistics including average scores, confidence levels, common themes
        None: If no valid results provided
    """
    if not sentiment_results or not isinstance(sentiment_results, list):
        logging.error("sentiment_results must be a non-empty list")
        return None
        
    valid_results = [r for r in sentiment_results if r and validate_sentiment_result(r)]
    
    if not valid_results:
        logging.warning("No valid sentiment results found for summary")
        return None
    
    # Only summarize results with standard structure (not custom prompts)
    standard_results = [r for r in valid_results if 'overall_sentiment_score' in r]
    
    if not standard_results:
        logging.warning("No standard sentiment results found for summary")
        return {
            'total_analyses': len(valid_results),
            'standard_analyses': 0,
            'note': 'All results appear to be from custom prompts - limited summary available'
        }
        
    scores = [r['overall_sentiment_score'] for r in standard_results]
    confidences = [r['confidence_level'] for r in standard_results]
    
    # Collect all themes
    all_themes = []
    for result in standard_results:
        if result.get('key_themes'):
            all_themes.extend(result['key_themes'])
    
    # Count theme frequency
    theme_counts = {}
    for theme in all_themes:
        theme_lower = theme.lower().strip()
        theme_counts[theme_lower] = theme_counts.get(theme_lower, 0) + 1
    
    # Get most common themes
    common_themes = sorted(theme_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    
    return {
        'total_analyses': len(valid_results),
        'standard_analyses': len(standard_results),
        'average_sentiment_score': sum(scores) / len(scores),
        'min_sentiment_score': min(scores),
        'max_sentiment_score': max(scores),
        'sentiment_std_dev': (sum((x - sum(scores)/len(scores))**2 for x in scores) / len(scores))**0.5,
        'average_confidence': sum(confidences) / len(confidences),
        'most_common_themes': [theme for theme, count in common_themes],
        'theme_frequencies': dict(common_themes)
    }

def compare_sentiment_trends(sentiment_results: List[Dict], sort_by_date: bool = True) -> Optional[Dict]:
    """
    Compares sentiment trends over time from multiple earnings calls.
    
    Args:
        sentiment_results (list): List of sentiment analysis results with call dates
        sort_by_date (bool): Whether to sort results chronologically
        
    Returns:
        dict: Trend analysis including score progression and theme evolution
        None: If insufficient data for trend analysis
    """
    if not sentiment_results or not isinstance(sentiment_results, list):
        logging.error("sentiment_results must be a non-empty list")
        return None
        
    if len(sentiment_results) < 2:
        logging.warning("Need at least 2 sentiment results for trend analysis")
        return None
        
    valid_results = [r for r in sentiment_results if r and validate_sentiment_result(r)]
    
    # Only analyze results with standard structure
    standard_results = [r for r in valid_results if 'overall_sentiment_score' in r]
    
    if len(standard_results) < 2:
        logging.warning("Need at least 2 valid standard sentiment results for trend analysis")
        return None
    
    if sort_by_date:
        # Sort by call_date if available
        def get_sort_key(x):
            call_date = x.get('call_date', '')
            return call_date if call_date else '0000-00-00'
        
        standard_results.sort(key=get_sort_key, reverse=False)
    
    scores = [r['overall_sentiment_score'] for r in standard_results]
    
    # Calculate trend direction
    score_changes = [scores[i] - scores[i-1] for i in range(1, len(scores))]
    avg_change = sum(score_changes) / len(score_changes) if score_changes else 0
    
    # Determine trend direction
    if avg_change > 0.5:
        trend_direction = "improving"
    elif avg_change < -0.5:
        trend_direction = "declining"
    else:
        trend_direction = "stable"
    
    # Calculate volatility (standard deviation)
    mean_score = sum(scores) / len(scores)
    volatility = (sum((score - mean_score)**2 for score in scores) / len(scores))**0.5
    
    return {
        'trend_direction': trend_direction,
        'average_score_change': avg_change,
        'score_progression': scores,
        'total_calls_analyzed': len(standard_results),
        'latest_score': scores[-1] if scores else None,
        'earliest_score': scores[0] if scores else None,
        'volatility': volatility,
        'score_range': max(scores) - min(scores) if scores else 0,
        'trend_strength': abs(avg_change)  # How strong the trend is
    }