"""Worker process for executing agent runs"""
import asyncio
import logging
import argparse
import os
from internal.messaging.nats import NATSMessaging
from internal.workflow.graph import create_run
from internal.workflow.checkpointer import get_checkpointer
from internal.config import settings

logger = logging.getLogger(__name__)


class AgentWorker:
    """Worker process that executes agent runs from NATS commands"""
    
    def __init__(self, nats_url: str = "nats://localhost:4222", chat_id: str = None):
        self.nats_url = nats_url
        self.chat_id = chat_id
        self.nats: NATSMessaging = None
        self.running = False
    
    async def start(self) -> None:
        """Start the worker"""
        logger.info(f"Starting agent worker for chat {self.chat_id or 'general'}")
        
        # Connect to NATS
        self.nats = NATSMessaging(nats_url=self.nats_url)
        await self.nats.connect()
        
        # Subscribe to container ready signal (agent.chat.{chat_id}.start)
        if self.chat_id:
            await self.nats.subscribe_to_chat_events(
                chat_id=self.chat_id,
                event_handler=self.handle_container_event
            )
            logger.info(f"Subscribed to container events for chat {self.chat_id}")
        
        # Subscribe to commands (chat-specific if chat_id provided)
        await self.nats.subscribe_to_commands(
            command_handler=self.handle_command,
            queue_group="agent-workers",
            chat_id=self.chat_id
        )
        
        self.running = True
        logger.info(f"Agent worker started and listening for commands on chat {self.chat_id or 'general'}")
    
    async def handle_container_event(self, event: dict) -> None:
        """Handle container events (e.g., container ready signal)"""
        event_type = event.get("event_type") or event.get("command_type")
        chat_id = event.get("chat_id")
        payload = event.get("payload", {})
        
        logger.info(f"[WORKER] Received container event {event_type} for chat {chat_id}")
        logger.info(f"[WORKER] Event payload: {event}")
        
        if event_type == "start":
            logger.info(f"[WORKER] Container ready for chat {chat_id}")
            # Container is ready, worker can now execute workflows
        elif event_type == "run.start":
            logger.info(f"[WORKER] Received run.start command via event subscription")
            # This is actually a command, handle it via command handler
            await self.handle_command(event)
        else:
            logger.warning(f"[WORKER] Unknown container event type: {event_type}")
    
    async def handle_command(self, command: dict) -> None:
        """Handle incoming command"""
        command_type = command.get("command_type")
        run_id = command.get("run_id")
        chat_id = command.get("chat_id") or run_id  # Use chat_id if provided, otherwise run_id
        payload = command.get("payload", {})
        
        logger.info(f"[WORKER] Received command {command_type} for chat {chat_id}")
        logger.info(f"[WORKER] Command payload: {command}")
        
        try:
            if command_type == "run.start":
                await self.handle_run_start(chat_id, payload)
            elif command_type == "run.cancel":
                await self.handle_run_cancel(chat_id, payload)
            elif command_type == "run.resume":
                await self.handle_run_resume(chat_id, payload)
            else:
                logger.warning(f"[WORKER] Unknown command type: {command_type}")
        except Exception as e:
            logger.error(f"[WORKER] Error handling command: {e}")
    
    async def handle_run_start(self, chat_id: str, payload: dict) -> None:
        """Handle run start command"""
        logger.info(f"[WORKER] Starting run for chat {chat_id}")
        logger.info(f"[WORKER] Run payload: {payload}")
        
        try:
            # Get checkpointer
            checkpointer = await get_checkpointer()
            
            # Check for mock mode
            mock_mode = os.getenv("MOCK_MODE", "false").lower() == "true"
            logger.info(f"[WORKER] Mock mode: {mock_mode}")
            
            # Execute the workflow
            result = await create_run({
                "run_id": chat_id,  # chat_id = run_id
                "user_id": payload.get("user_id"),
                "project_id": payload.get("project_id"),
                "repository_id": payload.get("repository_id"),
                "chatkit_thread_id": payload.get("chatkit_thread_id"),
                "task": payload.get("task"),
                "max_tokens": payload.get("max_tokens"),
                "max_cost": payload.get("max_cost"),
                "max_repair_count": payload.get("max_repair_count", 2),
                "mock_mode": mock_mode,
            }, checkpointer)
            
            logger.info(f"[WORKER] Run for chat {chat_id} completed with status {result.get('status')}")
            
        except Exception as e:
            logger.error(f"[WORKER] Run for chat {chat_id} failed: {e}")
    
    async def handle_run_cancel(self, chat_id: str, payload: dict) -> None:
        """Handle run cancel command"""
        logger.info(f"[WORKER] Cancelling run for chat {chat_id}")
        
        # In production, this would update the run state and notify the workflow
        # For now, this is a placeholder
    
    async def handle_run_resume(self, chat_id: str, payload: dict) -> None:
        """Handle run resume command (for approval)"""
        logger.info(f"[WORKER] Resuming run for chat {chat_id}")
        
        # In production, this would resume the workflow from checkpoint
        # For now, this is a placeholder
    
    async def stop(self) -> None:
        """Stop the worker"""
        logger.info("Stopping agent worker")
        self.running = False
        
        if self.nats:
            await self.nats.close()
        
        logger.info("Agent worker stopped")


async def main():
    """Main entry point for worker process"""
    parser = argparse.ArgumentParser(description="Agent worker process")
    parser.add_argument("--chat-id", type=str, help="Chat ID for per-chat worker")
    parser.add_argument("--nats-url", type=str, default="nats://localhost:4222", help="NATS server URL")
    args = parser.parse_args()
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    worker = AgentWorker(nats_url=args.nats_url, chat_id=args.chat_id)
    
    try:
        await worker.start()
        
        # Keep running until interrupted
        while worker.running:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("Received interrupt, shutting down")
    finally:
        await worker.stop()


if __name__ == "__main__":
    asyncio.run(main())
