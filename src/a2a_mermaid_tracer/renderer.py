"""MermaidBuilder — Generate Mermaid.js sequence diagram syntax from parsed traces."""

from __future__ import annotations

from a2a_mermaid_tracer.parser import Interaction, TraceData


class MermaidBuilder:
    """Build Mermaid.js sequence diagram code from A2A trace data.

    Usage:
        parser = TraceParser()
        trace = parser.parse_file("traces.json")
        builder = MermaidBuilder()
        diagram = builder.render(trace)
        print(diagram)
    """

    def __init__(self, *, group_by_task: bool = False) -> None:
        """Initialize the builder.

        Args:
            group_by_task: If True, wrap interactions sharing a task ID in rect blocks.
        """
        self._group_by_task = group_by_task

    def render(self, trace: TraceData, *, title: str | None = None) -> str:
        """Render the full Mermaid sequence diagram.

        Args:
            trace: Parsed trace data.
            title: Optional diagram title.

        Returns:
            Mermaid sequence diagram as a string.

        Raises:
            ValueError: If trace is None.
        """
        if trace is None:
            raise ValueError("TraceData is required.")
        lines: list[str] = []
        lines.append("sequenceDiagram")

        if title:
            lines.append(f"    title {title}")

        # Declare participants in discovery order
        seen: list[str] = []
        for interaction in trace.interactions:
            for agent in [interaction.sender, interaction.receiver]:
                if agent not in seen:
                    seen.append(agent)

        for agent in seen:
            safe = _sanitize(agent)
            lines.append(f"    participant {safe} as {agent}")

        lines.append("")

        if self._group_by_task:
            self._render_grouped(trace.interactions, lines)
        else:
            self._render_flat(trace.interactions, lines)

        return "\n".join(lines) + "\n"

    def _render_flat(self, interactions: list[Interaction], lines: list[str]) -> None:
        """Render interactions as a flat sequence."""
        for interaction in interactions:
            line = self._render_interaction(interaction)
            lines.append(f"    {line}")

            if interaction.timestamp and not interaction.is_response:
                safe_sender = _sanitize(interaction.sender)
                short_ts = _short_timestamp(interaction.timestamp)
                lines.append(f"    Note right of {safe_sender}: {short_ts}")

    def _render_grouped(self, interactions: list[Interaction], lines: list[str]) -> None:
        """Render interactions grouped by task ID in rect blocks."""
        current_task: str | None = None
        in_rect = False

        for interaction in interactions:
            task = interaction.task_id

            # Close previous rect if task changed
            if in_rect and task != current_task:
                lines.append("    end")
                in_rect = False

            # Open new rect if new task with an ID
            if task and task != current_task:
                short = task[:8]
                lines.append("    rect rgb(240, 248, 255)")
                lines.append(f"    Note over {_sanitize(interaction.sender)}: Task {short}")
                in_rect = True
                current_task = task
            elif not task and in_rect:
                lines.append("    end")
                in_rect = False
                current_task = None

            line = self._render_interaction(interaction)
            lines.append(f"    {line}")

            if interaction.timestamp and not interaction.is_response:
                safe_sender = _sanitize(interaction.sender)
                short_ts = _short_timestamp(interaction.timestamp)
                lines.append(f"    Note right of {safe_sender}: {short_ts}")

        if in_rect:
            lines.append("    end")

    def _render_interaction(self, interaction: Interaction) -> str:
        """Render a single interaction as a Mermaid arrow.

        Args:
            interaction: The interaction to render.

        Returns:
            A Mermaid diagram line (without leading whitespace).
        """
        sender = _sanitize(interaction.sender)
        receiver = _sanitize(interaction.receiver)

        # Build the label
        label = self._build_label(interaction)

        # Choose arrow style — sender/receiver in trace already reflect direction
        if interaction.is_error:
            return f"{sender} --x {receiver}: {label}"
        elif interaction.is_response:
            return f"{sender} -->> {receiver}: {label}"
        else:
            return f"{sender} ->> {receiver}: {label}"

    def _build_label(self, interaction: Interaction) -> str:
        """Build the arrow label text.

        Uses summary text for requests when available, status for responses.

        Args:
            interaction: The interaction to label.

        Returns:
            The label string.
        """
        if interaction.is_error:
            if interaction.error_message:
                return f"ERROR: {interaction.error_message[:50]}"
            return "ERROR"

        if interaction.is_response:
            if interaction.summary:
                return f'"{interaction.summary}"'
            parts = []
            if interaction.status:
                parts.append(interaction.status)
            else:
                parts.append("Response")
            if interaction.task_id:
                parts.append(f"(Task: {interaction.task_id[:8]})")
            return " ".join(parts)

        # Request: prefer summary over method name
        if interaction.summary:
            label = f'"{interaction.summary}"'
        else:
            label = interaction.method
        if interaction.task_id:
            label += f" (Task: {interaction.task_id[:8]})"
        return label


def _sanitize(name: str) -> str:
    """Sanitize an agent name for Mermaid participant IDs.

    Args:
        name: Agent display name.

    Returns:
        Safe identifier with only alphanumeric and underscores.
    """
    return name.replace(" ", "_").replace("-", "_").replace(".", "_")


def _short_timestamp(ts: str) -> str:
    """Extract the time portion from an ISO timestamp.

    Args:
        ts: ISO 8601 timestamp string (e.g. "2025-06-15T10:30:00.000Z").

    Returns:
        Time portion only (e.g. "10:30:00"), or original string if parsing fails.
    """
    if "T" in ts:
        time_part = ts.split("T", 1)[1]
        # Strip trailing Z and milliseconds for readability
        time_part = time_part.rstrip("Z")
        if "." in time_part:
            time_part = time_part.split(".", 1)[0]
        return time_part
    return ts
