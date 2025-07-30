import os
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

def get_gemini_api_key():
    return os.getenv("GEMINI_API_KEY")

def get_fmp_api_key():
    return os.getenv("FMP_API_KEY")



def set_gemini_api_key(api_key: str):
    """Sets the Gemini API key programmatically."""
    os.environ["GEMINI_API_KEY"] = api_key
    genai.configure(api_key=api_key)

def set_fmp_api_key(api_key: str):
    """Sets the FMP API key programmatically."""
    os.environ["FMP_API_KEY"] = api_key

# Only validate if not in test environment
if "pytest" not in os.environ.get("_", ""):
    if not get_fmp_api_key():
        raise ValueError("FMP_API_KEY not found in environment variables")
    if not get_gemini_api_key():
        raise ValueError("GEMINI_API_KEY not found in environment variables")
