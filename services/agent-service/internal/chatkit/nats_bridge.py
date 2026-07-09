from collections.abc import AsyncIterator
from typing import Any
from internal.messaging.nats import NATSMessaging
import asyncio


class NatsBridge:
    def __init__(self, nats_client: NATSMessaging):
        self.nats = nats_client
        self._event_queue: asyncio.Queue = None

    async def publish_agent_start(
        self,
        *,
        run_id: str,
        conversation_id: str,
        user_subject: str,
        prompt: str,
        metadata: dict,
    ) -> None:
        # Publish to chat.start for container creation
        await self.nats.publish_chat_start(
            run_id=run_id,
            repository_id=metadata.get("repository_id", ""),
            project_id=metadata.get("project_id", ""),
            mock_mode=metadata.get("mock_mode", False),
        )

        # Publish to agent.chat.{run_id}.user.events for run request
        await self.nats.publish_orchestration_command(
            command_type="run.start",
            run_id=run_id,
            payload={
                "user_id": user_subject,
                "project_id": metadata.get("project_id", ""),
                "repository_id": metadata.get("repository_id", ""),
                "task": prompt,
                "run_id": run_id,
                "mock_mode": metadata.get("mock_mode", False),
                "llm_provider": metadata.get("llm_provider", "ollama"),
            },
        )

    async def subscribe_run_events(self, run_id: str) -> AsyncIterator[dict[str, Any]]:
        # This method is no longer used - ChatKit server now uses global event stream
        # Kept for backward compatibility but not called
        raise NotImplementedError("subscribe_run_events is deprecated - use global event stream instead")
