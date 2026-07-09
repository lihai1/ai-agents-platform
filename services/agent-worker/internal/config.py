from pydantic_settings import BaseSettings
from pydantic import field_validator

class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://agentic:agentic@postgres:5432/agentic"
    jwt_secret: str = "dev-secret-change-in-production"
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    ollama_base_url: str = "http://host.docker.internal:11434"
    langsmith_api_key: str = ""
    langsmith_project: str = "agentic-engineering-platform"
    model_provider: str = "ollama"
    model_name: str = "qwen3.5:9b"
    mock_mode: bool = False

    @field_validator('database_url', mode='before')
    @classmethod
    def normalize_database_url(cls, v: str) -> str:
        if isinstance(v, str) and v.startswith('postgres://'):
            return v.replace('postgres://', 'postgresql+asyncpg://', 1)
        return v

    class Config:
        env_file = ".env"

settings = Settings()
