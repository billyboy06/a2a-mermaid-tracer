"""TraceParser — Parse A2A JSON-RPC traces into structured interaction records."""

from __future__ import annotations

import json
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

    def parse_file(self, path: str | Path) -> TraceData:
        """Parse a trace file (JSON array or NDJSON)."""
        path = Path(path)
        content = path.read_text(encoding="utf-8").strip()

        if content.startswith("["):
            entries = json.loads(content)
        else:
            entries = [json.loads(line) for line in content.splitlines() if line.strip()]

        return self._parse_entries(entries)

    def parse_string(self, data: str) -> TraceData:
        """Parse trace data from a string."""
        data = data.strip()
        if data.startswith("["):
            entries = json.loads(data)
        else:
            entries = [json.loads(line) for line in data.splitlines() if line.strip()]
        return self._parse_entries(entries)

    def _parse_entries(self, entries: list[dict]) -> TraceData:
        """Convert raw log entries into TraceData."""
        trace = TraceData()

        for entry in entries:
            interaction = self._parse_entry(entry)
            if interaction:
                trace.interactions.append(interaction)
                trace.agents.add(interaction.sender)
                trace.agents.add(interaction.receiver)

        return trace

    def _parse_entry(self, entry: dict) -> Interaction | None:
        """Parse a single log entry into an Interaction."""
        sender = entry.get("sender", "Unknown")
        receiver = entry.get("receiver", "Unknown")
        timestamp = entry.get("timestamp")
        message = entry.get("message", entry)

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
