import google.generativeai as genai
import json
import logging
from earnings_analyzer.config import get_gemini_api_key

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# DO NOT configure genai at module level - move it into functions

def analyze_sentiment(transcript_text, model_name="gemini-2.5-flash"):
    """
    Analyzes the sentiment of an earnings call transcript using the Gemini API.

    Args:
        transcript_text: The full text of the earnings call transcript.
        model_name: The name of the Gemini model to use (e.g., 'gemini-2.5-flash', 'gemini-1.5-pro').

    Returns:
        A dictionary containing the sentiment analysis results, or None on failure.
    """
    if not transcript_text or transcript_text.strip() == "":
        logging.warning("Transcript text is empty. Cannot perform sentiment analysis.")
        return None

    api_key = get_gemini_api_key()
    if api_key:
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(model_name)
            
            prompt = f"""As a financial analyst, please analyze the following earnings call transcript.
    Based on the language, tone, and key topics discussed by the executives, provide a sentiment analysis.
    Return your analysis as a JSON object with the following four fields:
    1.  `overall_sentiment_score`: A numerical score from 1 (very negative) to 10 (very positive).
    2.  `confidence_level`: Your confidence in this sentiment score, from 0.0 to 1.0.
    3.  `key_themes`: A JSON list of the top 3-5 most important themes or topics discussed.
    4.  `qualitative_assessment`: A 2-3 sentence qualitative assessment of the executive sentiment during the earnings call, focusing on the overall tone and the implications of the key themes.

    Transcript:
    ---
    {transcript_text} # Use the full transcript
    ---
    """
            response = model.generate_content(prompt)
            cleaned_json_string = response.text.strip().replace('```json', '').replace('```', '').strip()
            analysis_result = json.loads(cleaned_json_string)
            return analysis_result
        except Exception as e:
            logging.error(f"An error occurred during sentiment analysis: {e}")
            return None
    else:
        logging.error("GEMINI_API_KEY is not set in the environment variables. Please set it to use Gemini API.")
        return None