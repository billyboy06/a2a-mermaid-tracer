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
    task_id: str | None = None
    timestamp: str | None = None
    is_error: bool = False
    error_message: str | None = None
    is_response: bool = False
    summary: str | None = None
    status: str | None = None

    def __post_init__(self) -> None:
        """Validate required fields at construction time."""
        if not self.sender:
            raise ValueError("Interaction sender is required.")
        if not self.receiver:
            raise ValueError("Interaction receiver is required.")
        if not self.method:
            raise ValueError("Interaction method is required.")


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
        if not path:
            raise ValueError("File path is required.")
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Trace file not found: {path}")
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

        # Extract summary from message parts (text content for requests)
        summary = _extract_summary(params)

        # Extract status and result summary from response
        status = None
        if is_response and not is_error:
            result = message.get("result", {})
            if isinstance(result, dict):
                status_obj = result.get("status", {})
                if isinstance(status_obj, dict):
                    status = status_obj.get("state")
                # Extract result summary from artifacts
                if not summary:
                    summary = _extract_artifact_summary(result)

        if is_response:
            method = "response"

        return Interaction(
            sender=sender,
            receiver=receiver,
            method=method or "unknown",
            task_id=task_id,
            timestamp=timestamp,
            is_error=is_error,
            error_message=error_message,
            is_response=is_response,
            summary=summary,
            status=status,
        )


def _extract_summary(params: dict) -> str | None:
    """Extract a text summary from message params.

    Looks for text content in A2A message parts.

    Args:
        params: The params dict from a JSON-RPC message.

    Returns:
        First text part content (truncated to 40 chars), or None.
    """
    if not isinstance(params, dict):
        return None
    inner_msg = params.get("message", {})
    if not isinstance(inner_msg, dict):
        return None
    parts = inner_msg.get("parts", [])
    if not isinstance(parts, list):
        return None
    for part in parts:
        if isinstance(part, dict) and part.get("kind") == "text":
            text = part.get("text", "")
            if text:
                return text[:40]
    return None


def _extract_artifact_summary(result: dict) -> str | None:
    """Extract a text summary from response artifacts.

    Args:
        result: The result dict from a JSON-RPC response.

    Returns:
        First artifact text content (truncated to 40 chars), or None.
    """
    artifacts = result.get("artifacts", [])
    if not isinstance(artifacts, list):
        return None
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            continue
        parts = artifact.get("parts", [])
        if not isinstance(parts, list):
            continue
        for part in parts:
            if isinstance(part, dict) and part.get("kind") == "text":
                text = part.get("text", "")
                if text:
                    return text[:40]
    return None
