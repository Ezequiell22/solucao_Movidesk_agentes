import os
from langchain_groq import ChatGroq

def get_llm():
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY is not set. A valid API key is required for production.")
    
    return ChatGroq(model_name="llama-3.3-70b-versatile", temperature=0)
