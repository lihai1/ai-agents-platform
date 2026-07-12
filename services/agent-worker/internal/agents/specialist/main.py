"""Worker process for executing specialist agent runs."""
import asyncio

from internal.worker_base import AutostartAgentWorker, run_worker_main


class SpecialistWorker(AutostartAgentWorker):
    """Worker process that executes specialist agent runs from NATS commands."""

    agent_type = "specialist"
    worker_name = "specialist agent worker"


async def main() -> None:
    await run_worker_main(SpecialistWorker)


if __name__ == "__main__":
    asyncio.run(main())
