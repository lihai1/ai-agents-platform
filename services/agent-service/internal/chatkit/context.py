from dataclasses import dataclass
from fastapi import Request
import os


@dataclass(frozen=True)
class RequestContext:
    user_subject: str
    org_id: str
    request_id: str | None
    authorization: str | None
    project_id: str | None = None
    repository_id: str | None = None
    run_id: str | None = None
    mock_mode: bool = False
    llm_provider: str = "ollama"
    model_name: str = "qwen3.5:9b"
    agent_type: str = "specialist"
    api_key: str = ""


def _env_mock_mode() -> bool:
    return os.getenv("MOCK_MODE", "false").lower() == "true"


def _env_llm_provider() -> str:
    return os.getenv("LLM_PROVIDER", "ollama")


def context_from_request(request: Request) -> RequestContext:
    user_subject = request.headers.get("X-User-Subject")
    if not user_subject:
        raise ValueError("X-User-Subject header is required")
    
    return RequestContext(
        user_subject=user_subject,
        org_id=request.headers.get("X-Org-Id", "org:aegis-demo"),
        request_id=request.headers.get("X-Request-Id"),
        authorization=request.headers.get("Authorization"),
        mock_mode=_env_mock_mode(),
        llm_provider=_env_llm_provider(),
    )
