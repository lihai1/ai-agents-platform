"""NATS payload-safe chunking for terminal output.

NATS has a maximum payload size (default 1 MB). Terminal output can exceed this,
so we split large outputs into ordered chunks that the consumer reassembles.
Each chunk carries metadata for correct ordering and reassembly.
"""

from __future__ import annotations

import math
import uuid
from typing import Any

# Default NATS max payload is 1 MB; leave safety margin for headers + envelope JSON
NATS_MAX_PAYLOAD_BYTES: int = 1_048_576
NATS_PAYLOAD_SAFETY_MARGIN_BYTES: int = 4_096
TERMINAL_OUTPUT_MAX_CHUNK_BYTES: int = NATS_MAX_PAYLOAD_BYTES - NATS_PAYLOAD_SAFETY_MARGIN_BYTES


def byte_length(text: str) -> int:
    """Return UTF-8 byte length of a string.

    JavaScript string length != byte length. Always measure bytes for NATS payloads.
    """
    return len(text.encode("utf-8"))


def split_terminal_output(
    data: str,
    *,
    max_chunk_bytes: int = TERMINAL_OUTPUT_MAX_CHUNK_BYTES,
) -> list[str]:
    """Split terminal output into payload-safe UTF-8 chunks.

    Splits on byte boundaries while respecting UTF-8 character boundaries.
    Each returned chunk is guaranteed to be <= max_chunk_bytes when UTF-8 encoded.

    Args:
        data: The terminal output text to split.
        max_chunk_bytes: Maximum bytes per chunk.

    Returns:
        List of string chunks. Returns [data] if no splitting needed.
    """
    if not data:
        return []

    total_bytes = byte_length(data)
    if total_bytes <= max_chunk_bytes:
        return [data]

    chunks: list[str] = []
    encoded = data.encode("utf-8")
    offset = 0

    while offset < len(encoded):
        end = min(offset + max_chunk_bytes, len(encoded))

        # Don't split in the middle of a multi-byte UTF-8 character
        if end < len(encoded):
            while end > offset and (encoded[end] & 0xC0) == 0x80:
                end -= 1
            if end == offset:
                # Extremely unlikely: single char > max_chunk_bytes
                end = offset + max_chunk_bytes

        chunk_bytes = encoded[offset:end]
        chunks.append(chunk_bytes.decode("utf-8", errors="replace"))
        offset = end

    return chunks


def build_chunked_terminal_output_events(
    *,
    run_id: str,
    terminal_session_id: str,
    sequence: int,
    data: str,
    max_chunk_bytes: int = TERMINAL_OUTPUT_MAX_CHUNK_BYTES,
) -> list[dict[str, Any]]:
    """Build a list of terminal.output event payloads with chunking metadata.

    Args:
        run_id: The agent run ID.
        terminal_session_id: The terminal session this output belongs to.
        sequence: Monotonic sequence number for ordering within the session.
        data: Raw terminal output text.
        max_chunk_bytes: Maximum bytes per chunk.

    Returns:
        List of event payload dicts, one per chunk.
    """
    chunks = split_terminal_output(data, max_chunk_bytes=max_chunk_bytes)
    if not chunks:
        return []

    output_id = f"out-{uuid.uuid4()}"
    chunk_count = len(chunks)

    events: list[dict[str, Any]] = []
    for idx, chunk in enumerate(chunks):
        events.append({
            "event_type": "terminal.output",
            "run_id": run_id,
            "terminal_session_id": terminal_session_id,
            "output_id": output_id,
            "sequence": sequence,
            "chunk_index": idx,
            "chunk_count": chunk_count,
            "is_final_chunk": idx == chunk_count - 1,
            "encoding": "utf-8",
            "data": chunk,
        })

    return events
