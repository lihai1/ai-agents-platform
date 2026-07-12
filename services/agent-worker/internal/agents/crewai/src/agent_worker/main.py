"""Entry point for the CrewAI agent worker."""
from __future__ import annotations

import asyncio
import json
import logging
import signal
import sys
from typing import Optional

from agent_worker.bootstrap import (
    BootstrapError,
    detect_command,
    resolve_runnable_folder,
    find_crewai_projects_recursive,
    WORKSPACE_ROOT,
)
from agent_worker.config import resolve_config
from agent_worker.nats_client import CrewAINatsClient
from agent_worker.runner import ProcessRunner

logger = logging.getLogger(__name__)


class CrewAIWorker:
    """High-level worker that bootstraps and runs a CrewAI project."""

    def __init__(self):
        self.config = resolve_config()
        self.nats: Optional[CrewAINatsClient] = None
        self.runner: Optional[ProcessRunner] = None
        self._shutting_down = False

    async def start(self) -> None:
        """Connect to NATS and start the run."""
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )

        logger.info("Starting CrewAI worker for run %s", self.config.run_id)

        self.nats = CrewAINatsClient(
            nats_url=self.config.nats_url,
            uid=self.config.uid,
            run_id=self.config.run_id,
            session_id=self.config.session_id,
        )
        await self.nats.connect()

        # Subscribe to user input and control close
        await self.nats.subscribe_user_events(self._handle_user_event)
        await self.nats.subscribe_control_close(self._handle_control_close)

        # Publish ready signal
        await self.nats.publish_control_ready()

        # Resolve runnable folder and command
        try:
            resolved_folder = resolve_runnable_folder(
                self.config.folder,
                self.config.example,
            )
            command = self.config.command or detect_command(resolved_folder)
        except BootstrapError as e:
            logger.error("Bootstrap failed: %s", e.message)
            
            # If no runnable folder found, scan for CrewAI projects
            if e.reason == "no_runnable_folder":
                logger.info("Scanning workspace for CrewAI projects...")
                crewai_projects = find_crewai_projects_recursive(WORKSPACE_ROOT)
                
                if crewai_projects:
                    logger.info("Found %d CrewAI projects", len(crewai_projects))
                    await self._publish_crewai_projects(crewai_projects)
                else:
                    logger.info("No CrewAI projects found in workspace")
                    await self._publish_bootstrap_error(e)
            else:
                await self._publish_bootstrap_error(e)
            return

        logger.info("Resolved folder: %s", resolved_folder)
        logger.info("Resolved command: %s", command)

        # Start process runner
        self.runner = ProcessRunner(
            nats=self.nats,
            command=command,
            cwd=resolved_folder,
            input_idle_seconds=self.config.input_idle_seconds,
            output_max_buffer_chars=self.config.output_max_buffer_chars,
            command_timeout=self.config.command_timeout_seconds,
        )

        # Handle signals
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            try:
                loop.add_signal_handler(sig, lambda: asyncio.create_task(self.stop()))
            except Exception:
                pass

        try:
            await self.runner.run()
        finally:
            await self.stop()

    async def _handle_user_event(self, data: dict) -> None:
        """Dispatch user input events to the runner."""
        event_type = data.get("type") or data.get("event_type")
        if event_type in ("user_input", "prompt"):
            if self.runner:
                await self.runner.handle_user_input(data)
        else:
            logger.info("Ignoring user event type: %s", event_type)

    async def _handle_control_close(self) -> None:
        """Handle control close by cancelling the runner."""
        logger.info("Received control close, cancelling run")
        if self.runner:
            await self.runner.cancel()

    async def _publish_bootstrap_error(self, exc: BootstrapError) -> None:
        """Publish bootstrap failure as failed state and final answer."""
        if not self.nats:
            return
        from agent_worker.events import state_failed, chat_final

        await self.nats.publish_state(
            "failed",
            state_failed(
                self.config.run_id,
                self.config.uid,
                error=exc.message,
                reason=exc.reason,
                candidates=exc.candidates,
            )["payload"],
        )
        await self.nats.publish_chat(
            "final_answer",
            chat_final(
                self.config.run_id,
                self.config.uid,
                content=exc.message,
                status="failed",
                error=True,
            )["payload"],
        )

    async def _publish_crewai_projects(self, projects: list) -> None:
        """Publish discovered CrewAI projects as a chat event for user selection."""
        if not self.nats:
            return
        from agent_worker.events import chat_final
        import json

        projects_json = json.dumps(projects)

        await self.nats.publish_chat(
            "final_answer",
            chat_final(
                self.config.run_id,
                self.config.uid,
                content=projects_json,
                status="project_selection_required",
                error=False,
                projects=projects,
            )["payload"],
        )

    async def stop(self) -> None:
        """Stop the worker and close NATS."""
        if self._shutting_down:
            return
        self._shutting_down = True
        logger.info("Stopping CrewAI worker")
        if self.runner:
            await self.runner.cancel()
        if self.nats:
            await self.nats.close()


async def main() -> None:
    """Main entry point."""
    worker = CrewAIWorker()
    try:
        await worker.start()
    except Exception as e:
        logger.exception("CrewAI worker failed: %s", e)
        await self.nats.close()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
