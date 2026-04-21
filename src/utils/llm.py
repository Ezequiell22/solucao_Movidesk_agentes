import os
import logging
from langchain_openai import ChatOpenAI
from src.config import settings

logger = logging.getLogger(__name__)

def get_llm():
    """
    Returns a configured LLM instance using centralized settings.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.error("OPENAI_API_KEY is not set.")
        raise ValueError("OPENAI_API_KEY is not set. A valid API key is required for production.")
    
    model_name = settings.LLM_MODEL_NAME
    temperature = settings.LLM_TEMPERATURE
    
    logger.info(f"Initializing LLM: {model_name} (temp: {temperature})")
    
    return ChatOpenAI(
        model_name=model_name, 
        temperature=temperature, 
        api_key=api_key
    )
