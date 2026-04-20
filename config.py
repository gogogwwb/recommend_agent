"""
Configuration management for the insurance recommendation agent system
"""
import os
from typing import Optional
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings"""
    
    # Database settings
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = ""
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "insurance_agent"
    
    # Redis settings
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None
    
    # FAISS settings
    FAISS_INDEX_PATH: str = "data/faiss_index"
    FAISS_DIMENSION: int = 768
    
    # LLM settings
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_API_BASE: Optional[str] = None
    LLM_MODEL: str = "gpt-4"
    LLM_TEMPERATURE: float = 0.7
    LLM_MAX_TOKENS: int = 2000
    
    # Embedding settings
    EMBEDDING_MODEL: str = "text-embedding-ada-002"
    
    # Application settings
    APP_NAME: str = "Insurance Recommendation Agent"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    
    # API settings
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    
    # Session settings
    SESSION_TIMEOUT_MINUTES: int = 30
    MAX_CONVERSATION_TURNS: int = 15
    HOT_DATA_RETENTION_TURNS: int = 5
    
    # Short-term memory settings
    MAX_TOKENS_BEFORE_SUMMARY: int = 5000  # Token threshold for summarization
    MESSAGES_TO_KEEP: int = 20  # Number of recent messages to preserve (10 turns = 20 messages)
    SUMMARIZATION_MODEL: str = "gpt-4o-mini"  # Model for conversation summarization
    MAX_TOKENS_FOR_SUMMARIZATION: int = 1000  # Max tokens for summary output
    
    # Performance settings
    MAX_CONCURRENT_SESSIONS: int = 100
    TOKEN_BUDGET_PER_SESSION: int = 6000
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
    
    @property
    def database_url(self) -> str:
        """Get PostgreSQL database URL"""
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
    
    @property
    def redis_url(self) -> str:
        """Get Redis connection URL"""
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()
