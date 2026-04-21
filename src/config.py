import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """
    Centralized configuration management using Pydantic.
    """
    # Project paths
    BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DATA_DIR: str = os.path.join(BASE_DIR, "data")
    
    # Knowledge Base paths (Unified)
    KB_TICKETS_DIR: str = os.path.join(DATA_DIR, "db", "tickets")
    KB_CODE_DIR: str = os.path.join(DATA_DIR, "db", "code")
    
    # LLM Settings
    LLM_MODEL_NAME: str = "gpt-4o"
    LLM_TEMPERATURE: float = 0.0
    EMBEDDING_MODEL_OPENAI_NAME: str = "text-embedding-3-large" # Opcional: Jina ou OpenAI
    EMBEDDING_MODEL_JINA_NAME: str = "jinaai/jina-embeddings-v2-small-code"
    # Codebase Settings
    CODEBASE_PATH: str = "/Users/ezequielmenegas/git/testeDelphi"
    GIT_SYNC_ENABLED: bool = False # Desabilitado para testes locais
    GIT_SYNC_INTERVAL: int = 300 # 5 minutos
    GIT_REMOTE: str = "origin"
    GIT_BRANCH: str = "main"
    
    # Movidesk Settings
    MOVIDESK_BASE_URL: str = "https://api.movidesk.com/public/v1"
    MOVIDESK_MOCK_PATH: str = os.path.join(BASE_DIR, "mocs", "movideskTickets.txt")

    # Logging
    LOG_LEVEL: str = "INFO"
    
    # Agent Settings
    MAX_AGENT_ITERATIONS: int = 5
    
    class Config:
        env_file = ".env"
        extra = "ignore"

# Singleton instance
settings = Settings()
