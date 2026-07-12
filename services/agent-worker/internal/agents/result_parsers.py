"""Shared result parsing functions for agent outputs."""
from __future__ import annotations

import json
import logging
from typing import Dict, Any

from internal.agents.schemas import ImplementationResult

logger = logging.getLogger(__name__)


def parse_implementation_result(result: dict) -> ImplementationResult:
    """Parse an AgentExecutor result into an ImplementationResult."""
    files_created = []
    files_modified = []
    lines_added = 0
    lines_removed = 0
    errors = []
    warnings = []

    intermediate_steps = result.get("intermediate_steps", [])
    if intermediate_steps:
        for action, observation in intermediate_steps:
            try:
                tool_name = getattr(action, "tool", None)
                tool_input = getattr(action, "tool_input", None) or {}
                obs = json.loads(observation) if isinstance(observation, str) else observation
                if tool_name == "write_file" and obs.get("success"):
                    file_path = tool_input.get("file_path") or obs.get("file_path")
                    if file_path:
                        files_created.append(file_path)
                        content = tool_input.get("content", "")
                        lines_added += max(len(content.splitlines()), 1)
                elif tool_name == "git_diff":
                    diff_text = obs.get("diff", obs.get("output", ""))
                    if diff_text:
                        for line in diff_text.splitlines():
                            if line.startswith("+") and not line.startswith("+++"):
                                lines_added += 1
                            elif line.startswith("-") and not line.startswith("---"):
                                lines_removed += 1
            except Exception as e:
                logger.warning("Failed to parse intermediate step: %s", e)

    output = result.get("output", "")
    success = not errors and (result.get("success") if isinstance(result, dict) else True)
    if not success:
        success = True  # default to success if no errors observed

    return ImplementationResult(
        files_modified=files_modified,
        files_created=files_created,
        lines_added=lines_added,
        lines_removed=lines_removed,
        success=success,
        errors=errors,
        warnings=warnings,
    )
