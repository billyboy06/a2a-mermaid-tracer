"""Tests for MermaidBuilder."""

from a2a_mermaid_tracer.parser import Interaction, TraceData
from a2a_mermaid_tracer.renderer import MermaidBuilder, _sanitize


class TestMermaidBuilder:
    def _make_trace(self) -> TraceData:
        return TraceData(
            interactions=[
                Interaction(
                    sender="AgentA",
                    receiver="AgentB",
                    method="message/send",
                    task_id="task-123",
                    timestamp="2025-06-15T10:30:00Z",
                ),
                Interaction(
                    sender="AgentB",
                    receiver="AgentA",
                    method="response",
                    task_id="task-123",
                    is_response=True,
                ),
                Interaction(
                    sender="AgentA",
                    receiver="AgentC",
                    method="message/send",
                    is_error=True,
                    error_message="Service unavailable",
                ),
            ],
            agents={"AgentA", "AgentB", "AgentC"},
        )

    def test_renders_valid_mermaid(self):
        builder = MermaidBuilder()
        diagram = builder.render(self._make_trace())
        assert diagram.startswith("sequenceDiagram")
        assert "participant" in diagram

    def test_includes_participants(self):
        builder = MermaidBuilder()
        diagram = builder.render(self._make_trace())
        assert "AgentA" in diagram
        assert "AgentB" in diagram
        assert "AgentC" in diagram

    def test_request_arrow(self):
        builder = MermaidBuilder()
        diagram = builder.render(self._make_trace())
        assert "->>" in diagram

    def test_response_arrow(self):
        builder = MermaidBuilder()
        diagram = builder.render(self._make_trace())
        assert "-->>" in diagram

    def test_error_arrow(self):
        builder = MermaidBuilder()
        diagram = builder.render(self._make_trace())
        assert "--x" in diagram
        assert "ERROR" in diagram

    def test_title(self):
        builder = MermaidBuilder()
        diagram = builder.render(self._make_trace(), title="My Trace")
        assert "title My Trace" in diagram

    def test_timestamp_notes(self):
        builder = MermaidBuilder()
        diagram = builder.render(self._make_trace())
        assert "Note right of" in diagram
        assert "2025-06-15T10:30:00Z" in diagram


class TestSanitize:
    def test_spaces(self):
        assert _sanitize("Agent A") == "Agent_A"

    def test_hyphens(self):
        assert _sanitize("my-agent") == "my_agent"

    def test_dots(self):
        assert _sanitize("agent.v2") == "agent_v2"
