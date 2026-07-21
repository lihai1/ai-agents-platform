import json
import re
from typing import Any
from chatkit.types import ProgressUpdateEvent


def _sanitize_terminal_data(data: str) -> str:
    """Strip non-SGR ANSI escape sequences that cause messy display in web terminals.

    Keeps SGR color/style codes (ending in 'm') and removes cursor movement,
    cursor positioning, line/screen clearing, scroll regions, cursor visibility,
    OSC, DCS, APC, PM, and other device control sequences meant for interactive
    terminals that produce repeated/duplicate output in web terminal log displays.
    """
    # Keep SGR (color/style), cursor positioning (G), erase line (K), erase display (J)
    # cursor up (A), cursor visibility (?25l/?25h) for Rich's cursor-overwrite pattern
    data = re.sub(
        r'\x1b\[[\x30-\x3F]*[\x20-\x2F]*([\x40-\x7E])',
        lambda m: m.group(1) in 'mGKJA' and m.group(0) or '',
        data,
    )
    # Remove OSC sequences: ESC ] ... ST (BEL or ESC \)
    data = re.sub(r'\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)', '', data)
    # Remove DCS, APC, PM sequences: ESC P/^/_/ ... ST
    data = re.sub(r'\x1b[P^_].*?(?:\x1b\\|\x9C)', '', data, flags=re.DOTALL)
    # Remove other single-letter ESC sequences (excluding ESC[ already handled)
    data = re.sub(r'\x1b[()\]{}#%`~=>\\]', '', data)
    # Remove control characters that disrupt log display (keep \n, \r, \t, ESC)
    data = re.sub(r'[\x00\x08\x0b\x0c\x0e-\x1a\x1c-\x1f\x7f]', '', data)
    return data


def _payload(event: dict[str, Any]) -> dict[str, Any]:
    return event.get("payload") or event


def get_event_type(event: dict[str, Any]) -> str:
    return str(
        event.get("event_type")
        or event.get("type")
        or event.get("name")
        or event.get("command_type")
        or ""
    )


def is_completed_event(event: dict[str, Any]) -> bool:
    event_type = get_event_type(event)
    return event_type in {
        "agent.completed",
        "agent.run.completed",
        "run.completed",
        "final_answer",
        "agent.final_answer",
    }


def is_failed_event(event: dict[str, Any]) -> bool:
    event_type = get_event_type(event)
    payload = _payload(event)
    # Treat explicit error payloads as failed unless they are cancellations.
    if payload.get("error") is True and payload.get("status") != "cancelled":
        return True
    if event_type == "final_answer" and payload.get("status") == "failed":
        return True
    return event_type in {
        "agent.failed",
        "agent.run.failed",
        "run.failed",
    }


def is_cancelled_event(event: dict[str, Any]) -> bool:
    event_type = get_event_type(event)
    payload = _payload(event)
    if payload.get("status") == "cancelled":
        return True
    return event_type in {
        "agent.cancelled",
        "agent.run.cancelled",
        "run.cancelled",
    }


def final_answer_from_event(event: dict[str, Any]) -> str:
    payload = _payload(event)
    event_type = get_event_type(event)
    
    # Handle failed events with error content
    if payload.get("error") or event_type in {"failed", "agent.failed", "agent.run.failed", "run.failed"}:
        error_content = (
            payload.get("content")
            or payload.get("message")
            or payload.get("error_message")
            or (payload.get("error") if isinstance(payload.get("error"), str) else None)
        )
        if error_content:
            return error_content
        errors = payload.get("errors", [])
        if errors:
            return f"Task failed: {errors[0]}"
        return "Task failed with unknown error"
    
    return (
        payload.get("content")
        or payload.get("message")
        or event.get("final_answer")
        or event.get("answer")
        or event.get("content")
        or event.get("message")
        or "Agent run completed."
    )


def progress_from_event(event: dict[str, Any]) -> ProgressUpdateEvent:
    event_type = get_event_type(event)
    payload = _payload(event)

    # Pure state lifecycle events are handled via final_answer / terminal events.
    # Avoid emitting them as generic progress so they do not terminate the SSE stream early.
    if event_type in {"completed", "failed", "cancelled"}:
        return ProgressUpdateEvent(text="")

    if event_type in {"agent.accepted", "accepted", "run.accepted"}:
        return ProgressUpdateEvent(
            icon="check",
            text="Agent run accepted.",
        )

    if event_type in {"agent.scheduled", "scheduled", "run.scheduled"}:
        return ProgressUpdateEvent(
            icon="desktop",
            text="Agent runner scheduled.",
        )

    if event_type in {"agent.started", "agent.run.started", "started", "run.started", "run.start"}:
        return ProgressUpdateEvent(
            icon="play",
            text="Agent runner started.",
        )

    if event_type in {"agent.progress", "progress", "run.progress", "progress_update"}:
        return ProgressUpdateEvent(
            icon="agent",
            text=payload.get("content")
            or payload.get("message")
            or event.get("message", "Agent is working..."),
        )

    if event_type in {
        "tool.requested",
        "agent.tool.requested",
        "agent.run.tool.requested",
    }:
        return ProgressUpdateEvent(
            icon="settings-slider",
            text=(
                f"Tool requested: {payload.get('tool', 'unknown')} "
                f"on {payload.get('resource', 'unknown')}"
            ),
        )

    if event_type in {"tool.executed", "agent.tool.executed", "agent.run.tool.executed"}:
        tool_name = payload.get('tool', 'unknown')
        action = payload.get('action', 'unknown')
        return ProgressUpdateEvent(
            icon="settings-slider",
            text=f"Tool executed: {tool_name} ({action})",
        )

    if event_type in {"tool.allowed", "agent.tool.allowed", "agent.run.tool.allowed"}:
        return ProgressUpdateEvent(
            icon="check",
            text=f"Aegis allowed: {payload.get('tool', 'unknown')}",
        )

    if event_type in {"tool.denied", "agent.tool.denied", "agent.run.tool.denied"}:
        return ProgressUpdateEvent(
            icon="check-circle",
            text=(
                f"Aegis denied: {payload.get('tool', 'unknown')}. "
                f"Reason: {payload.get('reason', 'policy_denied')}"
            ),
        )

    if event_type in {
        "approval.required",
        "agent.approval.required",
        "agent.run.approval.required",
    }:
        return ProgressUpdateEvent(
            icon="info",
            text=(
                f"Approval required: {payload.get('action', 'unknown')} "
                f"on {payload.get('resource', 'unknown')}"
            ),
        )

    if event_type in {"waiting_input", "agent.waiting_input"}:
        prompt = payload.get("prompt") or ""
        if isinstance(prompt, str):
            try:
                parsed = json.loads(prompt)
                if isinstance(parsed, dict) and parsed.get("message"):
                    text = parsed["message"]
                else:
                    text = prompt
            except Exception:
                text = prompt
        else:
            text = str(prompt)

        if not text:
            text = payload.get("message") or "Waiting for user input"

        return ProgressUpdateEvent(
            icon="circle-question",
            text=text,
        )

    # Semantic workflow progress
    if event_type == "workflow.progress":
        graph_node = payload.get("graph_node", "")
        msg = payload.get("message") or f"Workflow: {graph_node}"
        return ProgressUpdateEvent(
            icon="agent",
            text=msg,
        )

    # Handle workflow state events
    if event_type in {
        "created",
        "preparing_workspace",
        "scouting",
        "planning",
        "designing",
        "implementing",
        "testing",
        "reviewing",
        "verifying",
        "reasoning",
    }:
        state_text = {
            "created": "Initializing workflow",
            "preparing_workspace": "Preparing workspace",
            "scouting": "Scouting repository",
            "planning": "Planning implementation",
            "designing": "Designing solution",
            "implementing": "Implementing changes",
            "testing": "Running tests",
            "reviewing": "Reviewing changes",
            "verifying": "Verifying results",
            "reasoning": "Reasoning",
        }.get(event_type, event_type.replace("_", " ").title())
        
        return ProgressUpdateEvent(
            icon="agent",
            text=state_text,
        )

    # Fallback: only include event_type if it's not empty
    fallback_text = f"Event received: {event_type}" if event_type else "Event received"
    return ProgressUpdateEvent(
        icon="info",
        text=payload.get("message")
        or payload.get("content")
        or event.get("message", fallback_text),
    )
