"""Heuristic detection of process input prompts."""
from __future__ import annotations

import re

# Common prompt patterns.
_PROMPT_PATTERNS = [
    re.compile(r"\?\s*\[?y/n/?]?\s*$", re.IGNORECASE),
    re.compile(r"\?\s*\([yY]/?[nN]\)\s*$"),
    re.compile(r"\?\s*$"),
    re.compile(r"\:\s*$"),
    re.compile(r">\s*$"),
    re.compile(r"\$\s*$"),
    re.compile(r"\[input\]\s*$", re.IGNORECASE),
    re.compile(r"enter\s+.*?:\s*$", re.IGNORECASE),
    re.compile(r"please\s+provide\s+.*?:\s*$", re.IGNORECASE),
    re.compile(r"waiting\s+for\s+input", re.IGNORECASE),
]

# Lines that look like logs and should not be considered prompts.
_FALSE_POSITIVE_PATTERNS = [
    re.compile(r"^\d{4}[-/]\d{2}[-/]\d{2}"),
    re.compile(r"^\[.*\]\s+"),
    re.compile(r"^(INFO|DEBUG|WARNING|ERROR|CRITICAL)\s+"),
    re.compile(r"^(Traceback|File|ImportError|ModuleNotFoundError)"),
    re.compile(r"^\s+"),
]


def looks_like_input_prompt(text: str, max_prompt_length: int = 120) -> bool:
    """Return True if the trailing text looks like an interactive prompt.

    Avoids false positives for long log lines and structured tracebacks.
    """
    text = text.rstrip()
    if not text:
        return False

    # Consider only the last line.
    last_line = text.splitlines()[-1]
    if len(last_line) > max_prompt_length:
        return False

    for fp in _FALSE_POSITIVE_PATTERNS:
        if fp.search(last_line):
            return False

    for pattern in _PROMPT_PATTERNS:
        if pattern.search(last_line):
            return True

    return False


def extract_prompt_text(text: str) -> str:
    """Extract the prompt text to display to the user."""
    lines = text.rstrip().splitlines()
    if not lines:
        return ""
    # Return the last prompt-looking line.
    for line in reversed(lines):
        if looks_like_input_prompt(line):
            return line.strip()
    return lines[-1][-120:].strip()
