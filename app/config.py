"""Configuration management for Grok adapter."""

import os
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Service Configuration
    service_port: int = Field(default=8002, env="GROK_SERVICE_PORT")
    debug: bool = Field(default=False, env="GROK_DEBUG")
    
    # Jubal Integration
    jubal_core_url: str = Field(default="http://jubal-core:8000", env="GROK_JUBAL_CORE_URL")
    redis_url: str = Field(default="redis://jubal-redis:6379/0", env="GROK_REDIS_URL")
    
    # LLM Providers
    ollama_url: str = Field(default="http://10.14.0.2:11434", env="GROK_OLLAMA_URL")
    openrouter_api_key: Optional[str] = Field(default=None, env="GROK_OPENROUTER_API_KEY")
    openrouter_url: str = Field(default="https://openrouter.ai/api/v1", env="GROK_OPENROUTER_URL")
    openrouter_app_name: str = Field(default="grok-intelligence-engine", env="GROK_OPENROUTER_APP_NAME")
    openrouter_app_url: Optional[str] = Field(default=None, env="GROK_OPENROUTER_APP_URL")
    
    # Default Models
    default_model_provider: str = Field(default="local", env="GROK_DEFAULT_MODEL_PROVIDER")
    default_local_model: str = Field(default="llama3.1:8b", env="GROK_DEFAULT_LOCAL_MODEL")
    default_openrouter_model: str = Field(default="openai/gpt-4o-mini", env="GROK_DEFAULT_OPENROUTER_MODEL")
    
    # Processing
    max_concurrent_jobs: int = Field(default=5, env="GROK_MAX_CONCURRENT_JOBS")
    default_temperature: float = Field(default=0.2, env="GROK_DEFAULT_TEMPERATURE")
    default_max_tokens: int = Field(default=2000, env="GROK_DEFAULT_MAX_TOKENS")
    
    # File Management
    profiles_dir: str = Field(default="./profiles", env="GROK_PROFILES_DIR")
    auto_process_new_files: bool = Field(default=False, env="GROK_AUTO_PROCESS_NEW_FILES")

    model_config = {"env_file": ".env", "case_sensitive": False}


# Global settings instance
settings = Settings()