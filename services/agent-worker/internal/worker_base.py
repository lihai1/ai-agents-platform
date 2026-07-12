"""Shared base for agent workers that auto-start a single run from NATS."""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from abc import ABC
from typing import ClassVar

from internal.handlers.nats import handle_run_start
from internal.messaging.nats import NATSMessaging, set_nats_client
from internal.workflow.checkpointer import get_checkpointer
from internal.workflow.graph import create_run

logger = logging.getLogger(__name__)


class AutostartAgentWorker(ABC):
    """Base worker that connects to NATS and auto-starts a run from environment."""

    agent_type: ClassVar[str]
    worker_name: ClassVar[str]

    def __init__(self, nats_url: str = "nats://localhost:4222", run_id: str | None = None):
        if run_id is None:
            raise ValueError(f"run_id is required for {self.__class__.__name__}")
        self.nats_url = nats_url
        self.run_id = run_id
        self.nats: NATSMessaging | None = None
        self.running = False
        self.graph = None

    def _sanitize_user_id(self) -> str:
        """Replace colons with hyphens for NATS subject compatibility."""
        return os.getenv("USER_ID", "").replace(":", "-")

    def _build_run_options(self, user_id: str) -> dict[str, str | bool | int | None]:
        """Build the run payload from environment variables."""
        return {
            "user_id": user_id,
            "project_id": os.getenv("PROJECT_ID", ""),
            "repository_id": os.getenv("REPOSITORY_ID", ""),
            "task": os.getenv("TASK", ""),
            "max_tokens": int(os.getenv("MAX_TOKENS", "0")) if os.getenv("MAX_TOKENS") else None,
            "max_cost": float(os.getenv("MAX_COST", "0")) if os.getenv("MAX_COST") else None,
            "max_repair_count": int(os.getenv("MAX_REPAIR_COUNT", "2")),
            "mock_mode": os.getenv("MOCK_MODE", "false").lower() == "true",
            "llm_provider": os.getenv("LLM_PROVIDER", "ollama"),
            "model_name": os.getenv("MODEL_NAME", "qwen3.5:9b"),
            "agent_type": self.agent_type,
        }

    async def start(self) -> None:
        """Connect to NATS and auto-start the run."""
        logger.info("Starting %s for run %s", self.worker_name, self.run_id or "general")

        self.nats = NATSMessaging(nats_url=self.nats_url)
        await self.nats.connect()
        set_nats_client(self.nats)

        user_id = self._sanitize_user_id()

        await self.nats.publish_control_ready(self.run_id, user_id)
        await asyncio.sleep(0.5)

        if self.run_id:
            from internal.handlers.nats import handle_user_event

            await self.nats.subscribe_to_user_events(
                run_id=self.run_id,
                user_id=user_id,
                user_event_handler=lambda event: handle_user_event(event, self),
            )
            logger.info("Subscribed to user events for run %s", self.run_id)

        if self.run_id:
            logger.info("Auto-starting run %s", self.run_id)
            await handle_run_start(
                self.run_id,
                self._build_run_options(user_id),
                create_run,
                get_checkpointer,
                self,
            )
        else:
            logger.warning("No run_id provided, worker will not auto-start any run")

        self.running = True
        logger.info("%s started and auto-started run %s", self.worker_name, self.run_id or "general")

    async def stop(self) -> None:
        """Stop the worker."""
        logger.info("Stopping %s", self.worker_name)
        self.running = False
        if self.nats:
            await self.nats.close()
        logger.info("%s stopped", self.worker_name)


async def run_worker_main(worker_class: type[AutostartAgentWorker]) -> None:
    """Generic entry point for auto-starting worker processes."""
    parser = argparse.ArgumentParser(description=f"{worker_class.__name__} process")
    parser.add_argument("--run-id", type=str, help="Run ID for per-run worker")
    parser.add_argument(
        "--nats-url",
        type=str,
        default=os.getenv("NATS_URL", "nats://localhost:4222"),
        help="NATS server URL",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    logger.info("Starting %s with NATS URL: %s", worker_class.__name__, args.nats_url)

    run_id = args.run_id or os.getenv("RUN_ID")
    if not run_id:
        logger.error(
            "run_id is required. Provide it via --run-id argument or RUN_ID environment variable."
        )
        sys.exit(1)

    worker = worker_class(nats_url=args.nats_url, run_id=run_id)

    try:
        await worker.start()
        while worker.running:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("Received interrupt, shutting down")
    finally:
        await worker.stop()
