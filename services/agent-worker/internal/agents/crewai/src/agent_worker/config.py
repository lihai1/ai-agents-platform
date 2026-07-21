"""Configuration and CLI argument parsing for the CrewAI worker."""
from __future__ import annotations

import argparse
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WorkerConfig:
    """Resolved worker configuration."""

    nats_url: str
    uid: str
    run_id: str
    session_id: str
    folder: str
    example: Optional[str]
    command: Optional[str]
    command_timeout_seconds: Optional[int]
    input_idle_seconds: float = 30.0
    output_max_buffer_chars: int = 5000
    chunk_size_bytes: int = 2500
    chunk_delay_seconds: float = 3.0

    @property
    def user_id(self) -> str:
        """Alias for uid, matching existing platform field naming."""
        return self.uid


def _get_env_or_default(name: str, default: str) -> str:
    value = os.getenv(name)
    if value:
        return value
    return default


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="CrewAI agent worker")
    parser.add_argument(
        "--nats-url",
        type=str,
        default=os.getenv("NATS_URL", "nats://localhost:4222"),
        help="NATS server URL",
    )
    parser.add_argument(
        "--folder",
        type=str,
        default=os.getenv("AGENT_FOLDER", "/workspace"),
        help="Base folder or repo path inside /workspace",
    )
    parser.add_argument(
        "--example",
        type=str,
        default=os.getenv("AGENT_EXAMPLE"),
        help="Optional example sub-folder to run",
    )
    parser.add_argument(
        "--command",
        type=str,
        default=os.getenv("AGENT_COMMAND"),
        help="Command to run (auto-detected if omitted)",
    )
    parser.add_argument(
        "--uid",
        type=str,
        default=os.getenv("USER_ID") or os.getenv("UID"),
        help="User identifier",
    )
    parser.add_argument(
        "--run-id",
        type=str,
        default=os.getenv("RUN_ID"),
        help="Run identifier",
    )
    parser.add_argument(
        "--session-id",
        type=str,
        default=os.getenv("SESSION_ID"),
        help="Session identifier (defaults to run_id)",
    )
    parser.add_argument(
        "--command-timeout-seconds",
        type=int,
        default=int(os.getenv("COMMAND_TIMEOUT_SECONDS", "0") or 0),
        help="Optional per-command timeout (0 means no timeout)",
    )
    parser.add_argument(
        "--input-idle-seconds",
        type=float,
        default=float(os.getenv("INPUT_IDLE_SECONDS", "30")),
        help="Idle seconds before treating output as a prompt",
    )
    parser.add_argument(
        "--output-max-buffer-chars",
        type=int,
        default=int(os.getenv("OUTPUT_MAX_BUFFER_CHARS", "8000")),
        help="Maximum output buffer characters per chunk",
    )
    parser.add_argument(
        "--chunk-size-bytes",
        type=int,
        default=int(os.getenv("CHUNK_SIZE_BYTES", "1250")),
        help="Maximum bytes per chunk for NATS/UI streaming (default: 1.25KB)",
    )
    parser.add_argument(
        "--chunk-delay-seconds",
        type=float,
        default=float(os.getenv("CHUNK_DELAY_SECONDS", "3.0")),
        help="Delay in seconds between sending chunks to UI (default: 3.0s)",
    )
    return parser.parse_args(argv)


def resolve_config(args: Optional[argparse.Namespace] = None) -> WorkerConfig:
    """Resolve configuration from CLI args and environment variables."""
    if args is None:
        args = parse_args()

    if not args.uid:
        raise ValueError("uid is required: set --uid, USER_ID, or UID")
    if not args.run_id:
        raise ValueError("run_id is required: set --run-id or RUN_ID")

    # Sanitize user_id for NATS subject compatibility (existing convention)
    uid = args.uid.replace(":", "-")
    run_id = args.run_id
    session_id = args.session_id or run_id

    return WorkerConfig(
        nats_url=args.nats_url,
        uid=uid,
        run_id=run_id,
        session_id=session_id,
        folder=args.folder,
        example=args.example,
        command=args.command,
        command_timeout_seconds=args.command_timeout_seconds or None,
        input_idle_seconds=args.input_idle_seconds,
        output_max_buffer_chars=args.output_max_buffer_chars,
        chunk_size_bytes=args.chunk_size_bytes,
        chunk_delay_seconds=args.chunk_delay_seconds,
    )


def env_vars_from_config(config: WorkerConfig) -> dict[str, str]:
    """Return a dict of env vars useful for container injection."""
    env = {
        "NATS_URL": config.nats_url,
        "USER_ID": config.uid,
        "RUN_ID": config.run_id,
        "SESSION_ID": config.session_id,
        "AGENT_FOLDER": config.folder,
        "AGENT_EXAMPLE": config.example or "",
        "AGENT_COMMAND": config.command or "",
        "COMMAND_TIMEOUT_SECONDS": str(config.command_timeout_seconds or 0),
        "INPUT_IDLE_SECONDS": str(config.input_idle_seconds),
        "OUTPUT_MAX_BUFFER_CHARS": str(config.output_max_buffer_chars),
        "CHUNK_SIZE_BYTES": str(config.chunk_size_bytes),
        "CHUNK_DELAY_SECONDS": str(config.chunk_delay_seconds),
    }
    return env


def get_workspace_root() -> Path:
    """Return the workspace root."""
    return Path(os.getenv("WORKSPACE_PATH", "/workspace"))
