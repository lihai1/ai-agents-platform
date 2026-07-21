"""Unit tests for NATS payload-safe chunking."""

from __future__ import annotations

import sys
import os

# Ensure shared module is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from agentic_shared.chunking import (
    TERMINAL_OUTPUT_MAX_CHUNK_BYTES,
    build_chunked_terminal_output_events,
    byte_length,
    split_terminal_output,
)


class TestByteLength:
    def test_ascii(self):
        assert byte_length("hello") == 5

    def test_empty(self):
        assert byte_length("") == 0

    def test_multibyte_utf8(self):
        # '🎉' is 4 bytes in UTF-8
        assert byte_length("🎉") == 4

    def test_mixed(self):
        # 'a' = 1 byte, 'é' = 2 bytes, '中' = 3 bytes, '🎉' = 4 bytes
        assert byte_length("aé中🎉") == 1 + 2 + 3 + 4


class TestSplitTerminalOutput:
    def test_empty_string(self):
        assert split_terminal_output("") == []

    def test_small_string_no_split(self):
        data = "hello world"
        result = split_terminal_output(data, max_chunk_bytes=100)
        assert result == [data]

    def test_exact_boundary(self):
        data = "a" * 10
        result = split_terminal_output(data, max_chunk_bytes=10)
        assert result == [data]

    def test_split_ascii(self):
        data = "a" * 20
        result = split_terminal_output(data, max_chunk_bytes=10)
        assert len(result) == 2
        assert result[0] == "a" * 10
        assert result[1] == "a" * 10

    def test_split_respects_utf8_boundaries(self):
        # '中' is 3 bytes. With max_chunk_bytes=5, we can fit 1 char (3 bytes) per chunk
        data = "中中中"  # 9 bytes total
        result = split_terminal_output(data, max_chunk_bytes=5)
        # Each chunk should contain complete characters
        for chunk in result:
            # Verify each chunk is valid UTF-8
            chunk.encode("utf-8")
        # Reassembly should equal original
        assert "".join(result) == data

    def test_split_emoji(self):
        # '🎉' is 4 bytes
        data = "🎉🎉🎉"  # 12 bytes
        result = split_terminal_output(data, max_chunk_bytes=5)
        # Each emoji is 4 bytes, max is 5, so 1 emoji per chunk
        assert len(result) == 3
        assert "".join(result) == data

    def test_reassembly_preserves_content(self):
        data = "Hello 世界! 🎉 This is a test with mixed content.\n" * 100
        result = split_terminal_output(data, max_chunk_bytes=200)
        assert len(result) > 1
        reassembled = "".join(result)
        assert reassembled == data

    def test_each_chunk_within_limit(self):
        data = "x" * 1000 + "中" * 500 + "🎉" * 200
        max_bytes = 300
        result = split_terminal_output(data, max_chunk_bytes=max_bytes)
        for chunk in result:
            assert byte_length(chunk) <= max_bytes

    def test_default_max_chunk_bytes(self):
        # Should use the module constant
        small = "a" * 100
        result = split_terminal_output(small)
        assert result == [small]


class TestBuildChunkedEvents:
    def test_empty_data(self):
        events = build_chunked_terminal_output_events(
            run_id="run-1",
            terminal_session_id="sess-1",
            sequence=0,
            data="",
        )
        assert events == []

    def test_single_chunk(self):
        events = build_chunked_terminal_output_events(
            run_id="run-1",
            terminal_session_id="sess-1",
            sequence=5,
            data="hello",
            max_chunk_bytes=100,
        )
        assert len(events) == 1
        e = events[0]
        assert e["event_type"] == "terminal.output"
        assert e["run_id"] == "run-1"
        assert e["terminal_session_id"] == "sess-1"
        assert e["sequence"] == 5
        assert e["chunk_index"] == 0
        assert e["chunk_count"] == 1
        assert e["is_final_chunk"] is True
        assert e["data"] == "hello"
        assert e["encoding"] == "utf-8"
        assert "output_id" in e

    def test_multiple_chunks(self):
        data = "a" * 30
        events = build_chunked_terminal_output_events(
            run_id="run-2",
            terminal_session_id="sess-2",
            sequence=1,
            data=data,
            max_chunk_bytes=10,
        )
        assert len(events) == 3
        # All share same output_id
        output_ids = {e["output_id"] for e in events}
        assert len(output_ids) == 1
        # Check ordering
        for i, e in enumerate(events):
            assert e["chunk_index"] == i
            assert e["chunk_count"] == 3
            assert e["is_final_chunk"] == (i == 2)
        # Reassembly
        reassembled = "".join(e["data"] for e in events)
        assert reassembled == data

    def test_chunk_count_matches(self):
        data = "x" * 100
        events = build_chunked_terminal_output_events(
            run_id="run-3",
            terminal_session_id="sess-3",
            sequence=0,
            data=data,
            max_chunk_bytes=30,
        )
        for e in events:
            assert e["chunk_count"] == len(events)
