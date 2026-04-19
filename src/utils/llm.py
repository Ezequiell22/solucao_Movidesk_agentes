import os
from langchain_openai import ChatOpenAI

def get_llm():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is not set. A valid API key is required for production.")
    
    return ChatOpenAI(model_name="gpt-5", temperature=0, api_key=api_key)
