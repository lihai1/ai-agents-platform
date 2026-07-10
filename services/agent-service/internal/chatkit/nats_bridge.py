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
        # Publish to agent.chat.{run_id}.start for container creation with all run parameters
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
            chatkit_thread_id=conversation_id,
            max_tokens=metadata.get("max_tokens", 0),
            max_cost=metadata.get("max_cost", 0.0),
            max_repair_count=metadata.get("max_repair_count", 2),
        )

    async def subscribe_run_events(self, run_id: str) -> AsyncIterator[dict[str, Any]]:
        # This method is no longer used - ChatKit server now uses global event stream
        # Kept for backward compatibility but not called
        raise NotImplementedError("subscribe_run_events is deprecated - use global event stream instead")
