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
        """
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
                lines.append(f"    Note right of {safe_sender}: {interaction.timestamp}")

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
                lines.append(f"    Note right of {safe_sender}: {interaction.timestamp}")

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

        # Choose arrow style — errors and responses both go receiver→sender
        if interaction.is_error:
            return f"{receiver} --x {sender}: {label}"
        elif interaction.is_response:
            return f"{receiver} -->> {sender}: {label}"
        else:
            return f"{sender} ->> {receiver}: {label}"

    def _build_label(self, interaction: Interaction) -> str:
        """Build the arrow label text.

        Args:
            interaction: The interaction to label.

        Returns:
            The label string.
        """
        parts = []

        if interaction.is_error:
            parts.append("ERROR")
            if interaction.error_message:
                msg = interaction.error_message[:50]
                parts.append(f"({msg})")
        elif interaction.is_response:
            parts.append("Response")
            if interaction.task_id:
                parts.append(f"(Task: {interaction.task_id[:8]})")
        else:
            parts.append(interaction.method)
            if interaction.task_id:
                parts.append(f"(Task: {interaction.task_id[:8]})")

        return " ".join(parts)


def _sanitize(name: str) -> str:
    """Sanitize an agent name for Mermaid participant IDs.

    Args:
        name: Agent display name.

    Returns:
        Safe identifier with only alphanumeric and underscores.
    """
    return name.replace(" ", "_").replace("-", "_").replace(".", "_")
