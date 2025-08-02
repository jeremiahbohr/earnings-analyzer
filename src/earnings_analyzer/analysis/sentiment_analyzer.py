import google.generativeai as genai
import json
import logging
from earnings_analyzer.config import get_gemini_api_key

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')


def score_sentiment(transcript_text, model_name="gemini-2.5-flash", custom_prompt=None, include_key_themes=True, include_qualitative_assessment=True):
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
    if not transcript_text or transcript_text.strip() == "":
        logging.warning("Transcript text is empty. Cannot perform sentiment analysis.")
        return None

    api_key = get_gemini_api_key()
    if not api_key:
        logging.error("GEMINI_API_KEY is not set in the environment variables. Please set it to use Gemini API.")
        return None

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name)
        
        if custom_prompt:
            # Use custom prompt exactly as provided
            prompt = f"{custom_prompt}\n\nTranscript:\n---\n{transcript_text}\n---"
            logging.info("Using custom prompt for sentiment analysis")
        else:
            # Use default prompt with configurable options
            prompt_parts = ["As a financial analyst, please analyze the following earnings call transcript.",
                           "Based on the language, tone, and key topics discussed by the executives, provide a sentiment analysis.",
                           "Return your analysis as a JSON object with the following fields:"]
            
            field_descriptions = [
                "1.  `overall_sentiment_score`: A numerical score from 1 (very negative) to 10 (very positive).",
                "2.  `confidence_level`: Your confidence in this sentiment score, from 0.0 to 1.0."
            ]
            
            required_fields = ['overall_sentiment_score', 'confidence_level']
            field_count = 2
            
            if include_key_themes:
                field_count += 1
                field_descriptions.append(f"{field_count}.  `key_themes`: A JSON list of the top 3-5 most important themes or topics discussed.")
                required_fields.append('key_themes')
            
            if include_qualitative_assessment:
                field_count += 1
                if include_key_themes:
                    assessment_desc = f"{field_count}.  `qualitative_assessment`: A 2-3 sentence qualitative assessment of the executive sentiment during the earnings call, focusing on the overall tone and the implications of the key themes."
                else:
                    assessment_desc = f"{field_count}.  `qualitative_assessment`: A 2-3 sentence qualitative assessment of the executive sentiment during the earnings call, focusing on the overall tone."
                field_descriptions.append(assessment_desc)
                required_fields.append('qualitative_assessment')
            
            # Construct full prompt
            prompt = "\n".join(prompt_parts + field_descriptions + [
                "",
                "Transcript:",
                "---",
                transcript_text,
                "---"
            ])
        
        response = model.generate_content(prompt)
        cleaned_json_string = response.text.strip().replace('```json', '').replace('```', '').strip()
        analysis_result = json.loads(cleaned_json_string)
        
        if custom_prompt:
            # For custom prompts, we can't validate expected fields since we don't know the structure
            # Just add model_name and return whatever Gemini provided
            analysis_result['model_name'] = model_name
            logging.info("Successfully completed custom prompt sentiment analysis")
            return analysis_result
        else:
            # Validate the expected fields are present for default prompt
            if not all(field in analysis_result for field in required_fields):
                logging.warning(f"Gemini response missing required fields. Got: {list(analysis_result.keys())}")
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
        
    except json.JSONDecodeError as e:
        logging.error(f"Failed to parse JSON response from Gemini: {e}")
        logging.error(f"Raw response: {response.text if 'response' in locals() else 'No response'}")
        return None
    except Exception as e:
        logging.error(f"An error occurred during sentiment analysis: {e}")
        return None

def batch_score_sentiment(transcripts, model_name="gemini-2.5-flash", custom_prompt=None, include_key_themes=True, include_qualitative_assessment=True):
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
    results = []
    
    for i, transcript in enumerate(transcripts):
        logging.info(f"Processing transcript {i+1}/{len(transcripts)}")
        
        # Handle both string transcripts and dict objects
        if isinstance(transcript, dict):
            transcript_text = transcript.get('transcript_text', '')
        else:
            transcript_text = transcript
            
        result = score_sentiment(transcript_text, model_name, custom_prompt, include_key_themes, include_qualitative_assessment)
        results.append(result)
        
    return results

def validate_sentiment_result(sentiment_result):
    """
    Validates that a sentiment analysis result has the expected structure.
    
    Args:
        sentiment_result (dict): The result from score_sentiment()
        
    Returns:
        bool: True if the result is valid, False otherwise
    """
    if not isinstance(sentiment_result, dict):
        return False
        
    required_fields = {
        'overall_sentiment_score': (int, float),
        'confidence_level': (int, float),
        'key_themes': list,
        'qualitative_assessment': str,
        'model_name': str
    }
    
    for field, expected_types in required_fields.items():
        if field not in sentiment_result:
            return False
        if not isinstance(sentiment_result[field], expected_types):
            return False
            
    # Additional validation
    score = sentiment_result['overall_sentiment_score']
    confidence = sentiment_result['confidence_level']
    
    if not (1 <= score <= 10):
        return False
    if not (0.0 <= confidence <= 1.0):
        return False
        
    return True


def get_sentiment_summary(sentiment_results):
    """
    Creates a summary of multiple sentiment analysis results.
    
    Useful for analyzing trends across multiple earnings calls.
    
    Args:
        sentiment_results (list): List of sentiment analysis result dictionaries
        
    Returns:
        dict: Summary statistics including average scores, confidence levels, common themes
        None: If no valid results provided
    """
    if not sentiment_results:
        return None
        
    valid_results = [r for r in sentiment_results if validate_sentiment_result(r)]
    
    if not valid_results:
        logging.warning("No valid sentiment results found for summary")
        return None
        
    scores = [r['overall_sentiment_score'] for r in valid_results]
    confidences = [r['confidence_level'] for r in valid_results]
    
    # Collect all themes
    all_themes = []
    for result in valid_results:
        if result.get('key_themes'):
            all_themes.extend(result['key_themes'])
    
    # Count theme frequency
    theme_counts = {}
    for theme in all_themes:
        theme_counts[theme] = theme_counts.get(theme, 0) + 1
    
    # Get most common themes
    common_themes = sorted(theme_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    
    return {
        'total_analyses': len(valid_results),
        'average_sentiment_score': sum(scores) / len(scores),
        'min_sentiment_score': min(scores),
        'max_sentiment_score': max(scores),
        'average_confidence': sum(confidences) / len(confidences),
        'most_common_themes': [theme for theme, count in common_themes],
        'theme_frequencies': dict(common_themes)
    }


def compare_sentiment_trends(sentiment_results, sort_by_date=True):
    """
    Compares sentiment trends over time from multiple earnings calls.
    
    Args:
        sentiment_results (list): List of sentiment analysis results with call dates
        sort_by_date (bool): Whether to sort results chronologically
        
    Returns:
        dict: Trend analysis including score progression and theme evolution
        None: If insufficient data for trend analysis
    """
    if len(sentiment_results) < 2:
        logging.warning("Need at least 2 sentiment results for trend analysis")
        return None
        
    valid_results = [r for r in sentiment_results if validate_sentiment_result(r)]
    
    if len(valid_results) < 2:
        logging.warning("Need at least 2 valid sentiment results for trend analysis")
        return None
    
    if sort_by_date:
        # Sort by call_date if available
        valid_results.sort(key=lambda x: x.get('call_date', ''), reverse=False)
    
    scores = [r['overall_sentiment_score'] for r in valid_results]
    
    # Calculate trend direction
    score_changes = [scores[i] - scores[i-1] for i in range(1, len(scores))]
    avg_change = sum(score_changes) / len(score_changes) if score_changes else 0
    
    trend_direction = "improving" if avg_change > 0.5 else "declining" if avg_change < -0.5 else "stable"
    
    return {
        'trend_direction': trend_direction,
        'average_score_change': avg_change,
        'score_progression': scores,
        'total_calls_analyzed': len(valid_results),
        'latest_score': scores[-1] if scores else None,
        'earliest_score': scores[0] if scores else None,
        'volatility': max(scores) - min(scores) if scores else 0
    }