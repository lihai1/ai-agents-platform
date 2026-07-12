from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Singleton configuration object for agent-service."""
    
    # Database
    database_url: str = "postgresql+asyncpg://agentic:agentic@localhost:5432/agentic"
    
    # Authentication
    jwt_secret: str = "dev-secret-change-in-production"
    
    # LLM Providers
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434"
    
    # LangSmith
    langsmith_api_key: str = ""
    langsmith_project: str = "agentic-engineering-platform"
    
    # NATS
    nats_url: str = "nats://localhost:4222"
    service_id: str = "agent-service"
    
    # Control Plane
    control_plane_url: str = "http://localhost:8080"
    
    # Proxy Configuration
    proxy_timeout: float = 30.0
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# Singleton instance
settings = Settings()
