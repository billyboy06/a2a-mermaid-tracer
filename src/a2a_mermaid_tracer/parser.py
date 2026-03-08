"""TraceParser — Parse A2A JSON-RPC traces into structured interaction records."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Interaction:
    """A single interaction between two agents."""

    sender: str
    receiver: str
    method: str
    message_id: str | None = None
    task_id: str | None = None
    timestamp: str | None = None
    is_error: bool = False
    error_message: str | None = None
    is_response: bool = False
    note: str | None = None


@dataclass
class TraceData:
    """Parsed trace data containing all interactions."""

    interactions: list[Interaction] = field(default_factory=list)
    agents: set[str] = field(default_factory=set)


class TraceParser:
    """Parse A2A JSON-RPC 2.0 trace logs into structured interaction data.

    Supports two input formats:
    1. JSON array of JSON-RPC messages with metadata (sender/receiver fields)
    2. NDJSON (newline-delimited JSON) log format

    Expected message structure:
    {
        "sender": "AgentA",
        "receiver": "AgentB",
        "timestamp": "2025-01-15T10:30:00Z",
        "message": {
            "jsonrpc": "2.0",
            "id": "123",
            "method": "message/send",
            "params": { ... }
        }
    }

    Or for responses:
    {
        "sender": "AgentB",
        "receiver": "AgentA",
        "timestamp": "2025-01-15T10:30:01Z",
        "message": {
            "jsonrpc": "2.0",
            "id": "123",
            "result": { ... }
        }
    }
    """

    def __init__(self, *, strict: bool = False) -> None:
        """Initialize the parser.

        Args:
            strict: If True, raise on malformed entries instead of skipping them.
        """
        self._strict = strict

    def parse_file(self, path: str | Path) -> TraceData:
        """Parse a trace file (JSON array or NDJSON).

        Args:
            path: Path to the trace file.

        Returns:
            Parsed trace data.

        Raises:
            ValueError: If the file is empty or contains invalid JSON.
            FileNotFoundError: If the file does not exist.
        """
        path = Path(path)
        content = path.read_text(encoding="utf-8").strip()
        if not content:
            raise ValueError(f"Trace file is empty: {path}")
        return self._parse_content(content)

    def parse_stdin(self) -> TraceData:
        """Parse trace data from stdin.

        Returns:
            Parsed trace data.

        Raises:
            ValueError: If stdin is empty or contains invalid JSON.
        """
        content = sys.stdin.read().strip()
        if not content:
            raise ValueError("No data received from stdin.")
        return self._parse_content(content)

    def parse_string(self, data: str) -> TraceData:
        """Parse trace data from a string.

        Args:
            data: JSON array or NDJSON string.

        Returns:
            Parsed trace data.

        Raises:
            ValueError: If the string is empty or contains invalid JSON.
        """
        data = data.strip()
        if not data:
            raise ValueError("Trace data is empty.")
        return self._parse_content(data)

    def _parse_content(self, content: str) -> TraceData:
        """Parse content string detecting format automatically.

        Args:
            content: Non-empty, stripped content string.

        Returns:
            Parsed trace data.

        Raises:
            ValueError: If the content is not valid JSON or NDJSON.
        """
        if content.startswith("["):
            try:
                entries = json.loads(content)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON array: {e}") from e
            if not isinstance(entries, list):
                raise ValueError("Expected a JSON array of trace entries.")
        elif content.startswith("{"):
            # NDJSON: one JSON object per line
            entries = []
            for i, line in enumerate(content.splitlines(), 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError as e:
                    if self._strict:
                        raise ValueError(f"Invalid JSON on line {i}: {e}") from e
                    continue
                if not isinstance(obj, dict):
                    if self._strict:
                        raise ValueError(
                            f"Expected JSON object on line {i}, got {type(obj).__name__}"
                        )
                    continue
                entries.append(obj)
        else:
            raise ValueError(
                "Invalid trace format: expected JSON array (starting with '[') "
                "or NDJSON (starting with '{')."
            )

        return self._parse_entries(entries)

    def _parse_entries(self, entries: list[dict]) -> TraceData:
        """Convert raw log entries into TraceData.

        Args:
            entries: List of raw JSON-RPC trace entry dicts.

        Returns:
            Parsed trace data.
        """
        trace = TraceData()

        for i, entry in enumerate(entries):
            try:
                interaction = self._parse_entry(entry)
            except (KeyError, TypeError) as e:
                if self._strict:
                    raise ValueError(f"Malformed entry at index {i}: {e}") from e
                continue

            if interaction:
                trace.interactions.append(interaction)
                trace.agents.add(interaction.sender)
                trace.agents.add(interaction.receiver)

        return trace

    def _parse_entry(self, entry: dict) -> Interaction | None:
        """Parse a single log entry into an Interaction.

        Args:
            entry: A single trace entry dict with sender/receiver/message fields.

        Returns:
            Parsed interaction, or None if the entry cannot be parsed in non-strict mode.

        Raises:
            ValueError: In strict mode, if required fields are missing.
        """
        sender = entry.get("sender")
        receiver = entry.get("receiver")

        if not sender or not receiver:
            if self._strict:
                raise ValueError(
                    f"Entry missing required 'sender' or 'receiver' field: {entry!r:.200}"
                )
            return None

        timestamp = entry.get("timestamp")
        message = entry.get("message")

        if not isinstance(message, dict):
            if self._strict:
                raise ValueError(f"Entry missing 'message' dict: {entry!r:.200}")
            return None

        # Determine if this is a request or response
        method = message.get("method")
        msg_id = str(message.get("id", "")) if message.get("id") is not None else None
        is_response = method is None and ("result" in message or "error" in message)
        is_error = "error" in message

        # Extract task ID from params if available
        task_id = None
        params = message.get("params", {})
        if isinstance(params, dict):
            task_id = params.get("taskId") or params.get("id")
            # Also check nested message for task context
            inner_msg = params.get("message", {})
            if isinstance(inner_msg, dict) and not task_id:
                task_id = inner_msg.get("taskId")

        # For responses, extract from result
        if is_response and not task_id:
            result = message.get("result", {})
            if isinstance(result, dict):
                task_id = result.get("id") or result.get("taskId")

        # Build label
        error_message = None
        if is_error:
            err = message.get("error", {})
            error_message = err.get("message", str(err))

        if is_response:
            method = "response"

        # Build note for timestamp-based duration annotations
        note = None
        if timestamp:
            note = f"at {timestamp}"

        return Interaction(
            sender=sender,
            receiver=receiver,
            method=method or "unknown",
            message_id=msg_id,
            task_id=task_id,
            timestamp=timestamp,
            is_error=is_error,
            error_message=error_message,
            is_response=is_response,
            note=note,
        )
