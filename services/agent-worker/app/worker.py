"""Worker process for executing agent runs"""
import asyncio
import logging
import argparse
import os
import sys
from internal.messaging.nats import NATSMessaging, set_nats_client
from internal.workflow.graph import create_run
from internal.workflow.checkpointer import get_checkpointer
from internal.config import settings
from internal.handlers.nats import (
    handle_run_start,
    publish_worker_ready,
)

logger = logging.getLogger(__name__)


class AgentWorker:
    """Worker process that executes agent runs from NATS commands"""
    
    def __init__(self, nats_url: str = "nats://localhost:4222", run_id: str = None):
        if run_id is None:
            raise ValueError("run_id is required for AgentWorker")
        self.nats_url = nats_url
        self.run_id = run_id
        self.nats: NATSMessaging = None
        self.running = False
    
    async def start(self) -> None:
        """Start the worker and auto-start the run"""
        logger.info(f"Starting agent worker for run {self.run_id or 'general'}")
        
        # Connect to NATS
        self.nats = NATSMessaging(nats_url=self.nats_url)
        await self.nats.connect()
        set_nats_client(self.nats)
        
        # Small delay to ensure connection is stable
        await asyncio.sleep(0.5)
        
        # Auto-start the run immediately (no need to wait for NATS command)
        if self.run_id:
            logger.info(f"Auto-starting run {self.run_id}")
            await handle_run_start(
                self.run_id, 
                {
                    "user_id": os.getenv("USER_ID", ""),
                    "project_id": os.getenv("PROJECT_ID", ""),
                    "repository_id": os.getenv("REPOSITORY_ID", ""),
                    "chatkit_thread_id": os.getenv("CHATKIT_THREAD_ID", ""),
                    "task": os.getenv("TASK", ""),
                    "max_tokens": int(os.getenv("MAX_TOKENS", "0")) if os.getenv("MAX_TOKENS") else None,
                    "max_cost": float(os.getenv("MAX_COST", "0")) if os.getenv("MAX_COST") else None,
                    "max_repair_count": int(os.getenv("MAX_REPAIR_COUNT", "2")),
                    "mock_mode": os.getenv("MOCK_MODE", "false").lower() == "true",
                    "llm_provider": os.getenv("LLM_PROVIDER", "ollama"),
                    "model_name": os.getenv("MODEL_NAME", "qwen3.5:9b"),
                    "agent_type": os.getenv("AGENT_TYPE", "specialist"),
                },
                create_run, 
                get_checkpointer
            )
        else:
            logger.warning("No run_id provided, worker will not auto-start any run")

        # Publish worker ready signal before starting the workflow
        await publish_worker_ready(self.run_id, self.nats)
        self.running = True
        logger.info(f"Agent worker started and auto-started run {self.run_id or 'general'}")
    
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
    parser.add_argument("--run-id", type=str, help="Run ID for per-run worker")
    parser.add_argument("--nats-url", type=str, default=os.getenv("NATS_URL", "nats://localhost:4222"), help="NATS server URL")
    args = parser.parse_args()
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    logger.info(f"Starting worker with NATS URL: {args.nats_url}")
    
    # Get run_id from args or environment variable
    run_id = args.run_id or os.getenv("RUN_ID")
    if not run_id:
        logger.error("run_id is required. Provide it via --run-id argument or RUN_ID environment variable.")
        sys.exit(1)
    
    worker = AgentWorker(nats_url=args.nats_url, run_id=run_id)
    
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
