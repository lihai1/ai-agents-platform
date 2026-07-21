"""NATS bridge for ChatKit server — publishes agent lifecycle and user input events."""

from __future__ import annotations

import logging
from typing import Any

from internal.messaging.nats import NATSMessaging

logger = logging.getLogger(__name__)


class NatsBridge:
    """Thin wrapper exposing NATS operations needed by AegisChatKitServer."""

    def __init__(self, nats_client: NATSMessaging):
        self.nats = nats_client

    async def publish_agent_start(
        self,
        *,
        run_id: str,
        conversation_id: str,
        user_subject: str,
        prompt: str,
        metadata: dict,
    ) -> None:
        """Publish agent start to NATS control plane for container creation."""
        await self.nats.publish_chat_start(
            run_id=run_id,
            repository_id=metadata.get("repository_id", ""),
            project_id=metadata.get("project_id", ""),
            mock_mode=metadata.get("mock_mode", False),
            agent_type=metadata.get("agent_type", "specialist"),
            llm_provider=metadata.get("llm_provider", "ollama"),
            model_name=metadata.get("model_name", "qwen3.5:9b"),
            api_key=metadata.get("api_key", ""),
            user_id=user_subject,
            task=prompt,
            max_tokens=metadata.get("max_tokens", 0),
            max_cost=metadata.get("max_cost", 0.0),
            max_repair_count=metadata.get("max_repair_count", 2),
        )

    async def publish_user_input(
        self,
        *,
        run_id: str,
        user_subject: str,
        input_text: str,
        approval_request_id: str | None = None,
    ) -> None:
        """Publish user text input to running worker via NATS chat events."""
        payload: dict[str, Any] = {"type": "user_input", "input": input_text}
        if approval_request_id:
            payload["approval_request_id"] = approval_request_id
        await self.nats.publish_chat_event(
            event_type="user_input",
            run_id=run_id,
            payload=payload,
            user_id=user_subject,
        )
        logger.debug("Published user_input for run %s", run_id)

    async def publish_stdin_input(
        self,
        *,
        run_id: str,
        user_subject: str,
        input_text: str,
        terminal_session_id: str | None = None,
    ) -> None:
        """Publish stdin input targeted at a running ProcessRunner."""
        payload: dict[str, Any] = {
            "type": "user_input",
            "input": input_text,
            "source": "stdin",
        }
        if terminal_session_id:
            payload["terminal_session_id"] = terminal_session_id
        await self.nats.publish_chat_event(
            event_type="user_input",
            run_id=run_id,
            payload=payload,
            user_id=user_subject,
        )
        logger.debug("Published stdin_input for run %s (session=%s)", run_id, terminal_session_id)
