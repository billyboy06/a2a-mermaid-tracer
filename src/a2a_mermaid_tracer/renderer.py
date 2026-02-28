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

    def render(self, trace: TraceData, *, title: str | None = None) -> str:
        """Render the full Mermaid sequence diagram."""
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

        # Render interactions
        for interaction in trace.interactions:
            line = self._render_interaction(interaction)
            lines.append(f"    {line}")

            # Add timestamp note if available
            if interaction.timestamp and not interaction.is_response:
                safe_sender = _sanitize(interaction.sender)
                lines.append(f"    Note right of {safe_sender}: {interaction.timestamp}")

        return "\n".join(lines) + "\n"

    def _render_interaction(self, interaction: Interaction) -> str:
        """Render a single interaction as a Mermaid arrow."""
        sender = _sanitize(interaction.sender)
        receiver = _sanitize(interaction.receiver)

        # Build the label
        label = self._build_label(interaction)

        # Choose arrow style
        if interaction.is_error:
            # Dashed red arrow for errors (Mermaid doesn't support colors inline,
            # but we use --x for error/failure indication)
            return f"{sender} --x {receiver}: {label}"
        elif interaction.is_response:
            # Dashed arrow for responses
            return f"{receiver} -->> {sender}: {label}"
        else:
            # Solid arrow for requests
            return f"{sender} ->> {receiver}: {label}"

    def _build_label(self, interaction: Interaction) -> str:
        """Build the arrow label text."""
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
    """Sanitize an agent name for Mermaid participant IDs."""
    return name.replace(" ", "_").replace("-", "_").replace(".", "_")
