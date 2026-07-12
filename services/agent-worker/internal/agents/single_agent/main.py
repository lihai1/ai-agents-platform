"""Worker process for executing single agent runs."""
import asyncio

from internal.worker_base import AutostartAgentWorker, run_worker_main


class SingleAgentWorker(AutostartAgentWorker):
    """Worker process that executes single agent runs from NATS commands."""

    agent_type = "single-agent"
    worker_name = "single agent worker"


async def main() -> None:
    await run_worker_main(SingleAgentWorker)


if __name__ == "__main__":
    asyncio.run(main())
