"""pexpect-based process runner for the CrewAI worker."""
from __future__ import annotations

import asyncio
import logging
import os
import shlex
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pexpect

from agent_worker.events import (
    state_cancelled,
    state_completed,
    state_failed,
    state_output,
    state_waiting_input,
    chat_final,
    chat_progress,
    semantic_terminal_started,
    semantic_terminal_output_chunked,
    semantic_terminal_input_required,
    semantic_terminal_completed,
    semantic_terminal_failed,
    semantic_terminal_cancelled,
)
from agent_worker.nats_client import CrewAINatsClient
from agent_worker.prompt_detection import extract_prompt_text, looks_like_input_prompt

logger = logging.getLogger(__name__)


class RunnerError(Exception):
    """Error from the process runner."""

    def __init__(self, message: str, reason: str = "runner_error"):
        super().__init__(message)
        self.reason = reason
        self.message = message


@dataclass
class ProcessResult:
    """Bounded result returned by ProcessRunner.run()."""

    exit_code: int
    cancelled: bool
    timed_out: bool
    stdout_tail: str
    stderr_tail: str


class ProcessRunner:
    """Run a child process with pexpect, stream output, and handle input."""

    def __init__(
        self,
        nats: CrewAINatsClient,
        command: str,
        cwd: Path,
        input_idle_seconds: float = 30.0,
        output_max_buffer_chars: int = 8000,
        command_timeout: Optional[int] = None,
        command_args: Optional[Sequence[str]] = None,
        env: Optional[dict] = None,
        publish_started: bool = True,
        cancel_event: Optional[asyncio.Event] = None,
        chunk_size_bytes: int = 1250,
        chunk_delay_seconds: float = 3.0,
    ):
        self.nats = nats
        self.command = command
        self.command_args = command_args
        self.env = env
        self.cwd = cwd
        self.input_idle_seconds = input_idle_seconds
        self.output_max_buffer_chars = output_max_buffer_chars
        self.command_timeout = command_timeout
        self.publish_started = publish_started
        self.cancel_event = cancel_event or asyncio.Event()
        self.chunk_size_bytes = chunk_size_bytes
        self.chunk_delay_seconds = chunk_delay_seconds
        self.child: Optional[pexpect.spawn] = None
        self._cancelled = False
        self._timed_out = False
        self._waiting_input = False
        self._input_event: Optional[asyncio.Event] = None
        self._pending_input: Optional[str] = None
        # Keep only a bounded tail of stdout for run summaries. Full output is
        # streamed via chunked terminal.output events to stay under NATS limits.
        self._stdout_tail: str = ""
        self._max_tail_chars: int = 2000
        self._stderr_tail: str = ""
        self._process_started: bool = False
        self._start_time: float = 0.0
        # Semantic terminal event state
        self._terminal_session_id: str = f"tsess-{__import__('uuid').uuid4()}"
        self._terminal_sequence: int = 0

    async def run(self) -> ProcessResult:
        """Run the command and stream events until completion."""
        display = self.command or shlex.join(self.command_args or [])
        logger.info("Running command: %s in %s", display, self.cwd)
        env = os.environ.copy()
        if self.env:
            env.update(self.env)
        env.setdefault("PYTHONUNBUFFERED", "1")
        env.setdefault("FORCE_COLOR", "0")

        self._start_time = time.monotonic()

        try:
            if self.command_args:
                self.child = pexpect.spawn(
                    self.command_args[0],
                    list(self.command_args[1:]),
                    cwd=str(self.cwd),
                    env=env,
                    encoding="utf-8",
                    codec_errors="replace",
                    timeout=max(0.1, self.input_idle_seconds),
                    maxread=65536,
                    searchwindowsize=200,
                    echo=False,
                )
            else:
                self.child = pexpect.spawn(
                    "bash",
                    ["-lc", self.command],
                    cwd=str(self.cwd),
                    env=env,
                    encoding="utf-8",
                    codec_errors="replace",
                    timeout=max(0.1, self.input_idle_seconds),
                    maxread=65536,
                    searchwindowsize=200,
                    echo=False,
                )
        except Exception as e:
            await self._publish_failure(f"Failed to spawn process: {e}")
            return ProcessResult(exit_code=1, cancelled=False, timed_out=False, stdout_tail="", stderr_tail=str(e))

        if self.publish_started:
            await self.nats.publish_state(
                "started",
                {
                    "status": "started",
                    "command": display,
                    "cwd": str(self.cwd),
                },
            )
            # Semantic terminal.started
            started_event = semantic_terminal_started(
                run_id=self.nats.run_id,
                user_id=self.nats.uid,
                terminal_session_id=self._terminal_session_id,
                execution_id=f"exec-{__import__('uuid').uuid4()}",
                sequence=self._next_seq(),
                command=display,
            )
            await self.nats.publish_chat(
                "terminal.started",
                started_event["payload"],
            )
        self._process_started = True

        try:
            exit_code = await self._read_loop()
        except Exception as e:
            logger.exception("Runner loop failed")
            await self._publish_failure(f"Runner loop error: {e}")
            exit_code = 1
        finally:
            await self._cleanup()

        return ProcessResult(
            exit_code=exit_code,
            cancelled=self._cancelled,
            timed_out=self._timed_out,
            stdout_tail=self._stdout_tail,
            stderr_tail=self._stderr_tail,
        )

    async def _read_loop(self) -> int:
        """Read child output until EOF, cancellation, or command timeout. Returns the process exit code."""
        buffer = ""
        last_output_time = time.monotonic()

        while self.child and self.child.isalive():
            if self._cancelled:
                break
            if self.cancel_event.is_set():
                await self.cancel()
                break
            if self.command_timeout and self.command_timeout > 0:
                elapsed = time.monotonic() - self._start_time
                if elapsed >= self.command_timeout:
                    self._timed_out = True
                    logger.warning("Command timed out after %s seconds", elapsed)
                    await self._terminate()
                    break

            try:
                index = await self.child.expect(
                    ["\n", "\r", pexpect.EOF, pexpect.TIMEOUT],
                    timeout=0.1,
                    async_=True,
                )
            except pexpect.exceptions.TIMEOUT:
                index = 3
            except pexpect.exceptions.EOF:
                index = 2

            if index in (0, 1):
                chunk = self.child.before
                if chunk is None:
                    chunk = ""
                chunk += self.child.match.group(0) if self.child.match else ""
                buffer, last_output_time = await self._process_chunk(
                    buffer + chunk, last_output_time
                )
            elif index == 2:
                # EOF
                if buffer:
                    await self._flush_buffer(buffer)
                    buffer = ""
                break
            elif index == 3:
                # Timeout: check for pending input and idle prompt detection
                if buffer:
                    idle = time.monotonic() - last_output_time
                    if idle >= self.input_idle_seconds:
                        if looks_like_input_prompt(buffer):
                            await self._handle_input_prompt(buffer)
                            buffer = ""
                        else:
                            await self._flush_buffer(buffer)
                            buffer = ""

        # Collect remaining output without blocking on a still-running process.
        try:
            remaining = await self._drain_remaining_output()
            if remaining:
                await self._flush_buffer(remaining)
        except Exception:
            pass

        # Final output from remaining buffer
        if buffer:
            await self._flush_buffer(buffer)

        if self._cancelled:
            await self._publish_cancelled()
            return 1

        if self._timed_out:
            await self._publish_failure(
                f"Command timed out after {self.command_timeout} seconds",
                exit_code=124,
            )
            return 124

        exit_code = self.child.exitstatus
        if exit_code is None:
            try:
                exit_code = await self._async_wait_for_exit()
            except Exception:
                exit_code = 1

        if exit_code == 0:
            await self.nats.publish_state(
                "completed",
                state_completed(self.nats.run_id, self.nats.uid, exit_code=0)["payload"],
            )
            # Update terminal panel before terminating the stream.
            completed_event = semantic_terminal_completed(
                run_id=self.nats.run_id,
                user_id=self.nats.uid,
                terminal_session_id=self._terminal_session_id,
                sequence=self._next_seq(),
                exit_code=0,
            )
            await self.nats.publish_chat(
                "terminal.completed",
                completed_event["payload"],
            )
            # Bounded final answer: never send the entire accumulated stdout.
            # Chunked terminal.output events carry the full stream safely.
            final_content = self._stdout_tail or "CrewAI run completed successfully."
            if len(final_content) > self._max_tail_chars:
                final_content = final_content[-self._max_tail_chars:]
            await self.nats.publish_chat(
                "final_answer",
                chat_final(
                    self.nats.run_id,
                    self.nats.uid,
                    content=final_content,
                    status="completed",
                )["payload"],
            )
            return 0
        else:
            await self._publish_failure(
                f"Process exited with code {exit_code}",
                exit_code=exit_code,
            )
            return exit_code

    async def _process_chunk(self, text: str, last_output_time: float) -> tuple[str, float]:
        """Accumulate and possibly flush output."""
        if len(text) >= self.output_max_buffer_chars:
            await self._flush_buffer(text)
            return "", time.monotonic()
        return text, last_output_time

    def _next_seq(self) -> int:
        """Return and increment the monotonic terminal sequence counter."""
        seq = self._terminal_sequence
        self._terminal_sequence += 1
        return seq

    async def _flush_buffer(self, text: str) -> None:
        """Publish buffered output as chat events and keep a bounded tail."""
        if not text:
            return
        # Keep \r for ANSI cursor positioning (Rich overwrites lines with \r + cursor sequences)
        # Update bounded tail; full output is sent via chunked terminal.output.
        self._stdout_tail = (self._stdout_tail + text)[-self._max_tail_chars:]
        # Semantic terminal.output (chunked with UI-optimized size and delay)
        chunk_events = semantic_terminal_output_chunked(
            run_id=self.nats.run_id,
            user_id=self.nats.uid,
            terminal_session_id=self._terminal_session_id,
            sequence=self._next_seq(),
            data=text,
            max_chunk_bytes=self.chunk_size_bytes,
        )
        for idx, chunk_event in enumerate(chunk_events):
            await self.nats.publish_chat(
                "terminal.output",
                chunk_event["payload"],
            )
            # Add delay between chunks for UI performance (except for last chunk)
            if idx < len(chunk_events) - 1 and self.chunk_delay_seconds > 0:
                await asyncio.sleep(self.chunk_delay_seconds)

    async def _drain_remaining_output(self) -> str:
        """Read buffered output without blocking until EOF or a short deadline.

        pexpect.spawn.read() waits for EOF, which can hang if the process is
        still alive (e.g. after a cancellation/timeout). Running read() in a
        thread and capping the wait lets us drain whatever pexpect has already
        buffered without blocking the asyncio event loop.
        """
        if not self.child:
            return ""
        try:
            # read() returns data that pexpect already has buffered and will
            # block only until EOF. The timeout keeps the event loop free.
            return await asyncio.wait_for(
                asyncio.to_thread(self.child.read),
                timeout=2.0,
            )
        except asyncio.TimeoutError:
            logger.debug("Drain timed out; returning what was already buffered")
            return ""
        except Exception:
            return ""

    async def _async_wait_for_exit(self) -> int:
        """Wait for the child process exit without blocking the event loop."""
        if not self.child:
            return 1
        try:
            # pexpect.wait() blocks, so run it in a thread and cap the wait.
            exit_code = await asyncio.wait_for(
                asyncio.to_thread(self.child.wait),
                timeout=5.0,
            )
        except asyncio.TimeoutError:
            logger.warning("Child process did not exit within 5 seconds, killing it")
            try:
                self.child.kill(9)
            except Exception:
                pass
            return 1
        except Exception as exc:
            logger.warning("_async_wait_for_exit failed: %s", exc, exc_info=True)
            return self.child.exitstatus if self.child and self.child.exitstatus is not None else 1
        return exit_code or 0

    def _tail(self, buffer: list[str], limit: int = 2000) -> str:
        """Return the last `limit` characters of the collected buffer."""
        text = "".join(buffer)
        if len(text) <= limit:
            return text
        return "..." + text[-limit:]

    async def _terminate(self) -> None:
        """Gracefully terminate the child process."""
        if not self.child or not self.child.isalive():
            return
        try:
            self.child.sendintr()  # SIGINT
            await asyncio.sleep(1.0)
            if self.child.isalive():
                self.child.sendeof()
                await asyncio.sleep(1.0)
            if self.child.isalive():
                self.child.kill(9)
        except Exception as e:
            logger.warning("Failed to terminate process: %s", e)

    async def _handle_input_prompt(self, text: str) -> None:
        """Publish a waiting_input state and wait for user input."""
        prompt = extract_prompt_text(text)
        logger.info("Detected input prompt: %s", prompt)
        # Legacy events
        await self.nats.publish_state(
            "waiting_input",
            state_waiting_input(
                self.nats.run_id,
                self.nats.uid,
                prompt=prompt,
                reason="process_idle",
            )["payload"],
        )
        await self.nats.publish_chat(
            "progress_update",
            chat_progress(
                self.nats.run_id,
                self.nats.uid,
                message=f"Waiting for input: {prompt}",
            )["payload"],
        )
        # Semantic terminal.input_required
        input_req_event = semantic_terminal_input_required(
            run_id=self.nats.run_id,
            user_id=self.nats.uid,
            terminal_session_id=self._terminal_session_id,
            request_id=f"ireq-{__import__('uuid').uuid4()}",
            sequence=self._next_seq(),
            prompt=prompt,
        )
        await self.nats.publish_chat(
            "terminal.input_required",
            input_req_event["payload"],
        )
        self._waiting_input = True

    async def _send_input(self, user_input: str) -> None:
        """Send user input to the child process and echo it."""
        if not self.child or not self.child.isalive():
            return
        line = user_input.rstrip("\n") + "\n"
        self.child.sendline(line)
        await self.nats.publish_state(
            "output",
            state_output(
                self.nats.run_id,
                self.nats.uid,
                data=f"{line}",
                stream="stdin",
            )["payload"],
        )
        self._waiting_input = False

    async def handle_user_input(self, data: dict) -> None:
        """Handle a user input event from NATS.

        Accepts either a flat dict with input/text/content or an event envelope
        containing a `payload` with those fields.
        """
        payload = data.get("payload") or {}
        user_input = (
            data.get("input")
            or data.get("text")
            or data.get("content")
            or payload.get("input")
            or payload.get("text")
            or payload.get("content")
        )
        if not user_input:
            logger.warning("Received user_input event without text: %s", data)
            return
        logger.info("Received user input for run %s", self.nats.run_id)

        # Check if process is still running
        if not self.child or not self.child.isalive():
            if self._process_started:
                # Process already ran and completed
                logger.warning("Process already completed, cannot send more input")
                await self.nats.publish_chat(
                    "final_answer",
                    {"message": "The agent has completed its task. Please start a new conversation."}
                )
                return
            else:
                # Process never started, start it now
                logger.info("Process not started yet, starting...")
                await self.run()
                return

        # Process is running, send input directly
        self.child.sendline(user_input)
        await self.nats.publish_state(
            "output",
            state_output(
                self.nats.run_id,
                self.nats.uid,
                data=f"{user_input}\n",
                stream="stdin",
            )["payload"],
        )

    async def cancel(self) -> None:
        """Cancel the running process."""
        self._cancelled = True
        await self._terminate()

    async def _publish_failure(self, error: str, exit_code: Optional[int] = None) -> None:
        """Publish failed state, terminal failed, and final answer error."""
        await self.nats.publish_state(
            "failed",
            state_failed(
                self.nats.run_id,
                self.nats.uid,
                error=error,
                reason="process_error",
                exit_code=exit_code,
            )["payload"],
        )
        # Update terminal panel before terminating the stream.
        failed_event = semantic_terminal_failed(
            run_id=self.nats.run_id,
            user_id=self.nats.uid,
            terminal_session_id=self._terminal_session_id,
            sequence=self._next_seq(),
            exit_code=exit_code,
            error=error,
        )
        await self.nats.publish_chat(
            "terminal.failed",
            failed_event["payload"],
        )
        await self.nats.publish_chat(
            "final_answer",
            chat_final(
                self.nats.run_id,
                self.nats.uid,
                content=error,
                status="failed",
                error=True,
            )["payload"],
        )

    async def _publish_cancelled(self) -> None:
        """Publish cancelled state, terminal cancelled, and final answer."""
        await self.nats.publish_state(
            "cancelled",
            state_cancelled(
                self.nats.run_id,
                self.nats.uid,
                reason="control_close_received",
            )["payload"],
        )
        # Update terminal panel before terminating the stream.
        cancelled_event = semantic_terminal_cancelled(
            run_id=self.nats.run_id,
            user_id=self.nats.uid,
            terminal_session_id=self._terminal_session_id,
            sequence=self._next_seq(),
            reason="control_close_received",
        )
        await self.nats.publish_chat(
            "terminal.cancelled",
            cancelled_event["payload"],
        )
        await self.nats.publish_chat(
            "final_answer",
            chat_final(
                self.nats.run_id,
                self.nats.uid,
                content="CrewAI run was cancelled.",
                status="cancelled",
                error=True,
            )["payload"],
        )

    async def _cleanup(self) -> None:
        """Close the child process without blocking on wait()."""
        if not self.child:
            return
        try:
            if self.child.isalive():
                self.child.kill(9)
            # close() in pexpect can call wait(); run it in a thread with a tight
            # deadline so it cannot hang the event loop.
            await asyncio.wait_for(asyncio.to_thread(self.child.close, True), timeout=2.0)
        except Exception:
            pass
        finally:
            self.child = None

    @property
    def waiting_input(self) -> bool:
        return self._waiting_input
