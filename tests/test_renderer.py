"""Tests for MermaidBuilder."""

from __future__ import annotations

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

    def test_error_arrow_direction(self):
        """Error arrows should go from sender to receiver (trace has correct direction)."""
        builder = MermaidBuilder()
        trace = TraceData(
            interactions=[
                Interaction(
                    sender="Responder",
                    receiver="Requester",
                    method="response",
                    is_error=True,
                    error_message="fail",
                ),
            ],
            agents={"Requester", "Responder"},
        )
        diagram = builder.render(trace)
        assert "Responder --x Requester" in diagram

    def test_response_arrow_direction(self):
        """Response arrows should go from sender to receiver (trace has correct direction)."""
        builder = MermaidBuilder()
        trace = TraceData(
            interactions=[
                Interaction(
                    sender="AgentB",
                    receiver="AgentA",
                    method="response",
                    is_response=True,
                ),
            ],
            agents={"AgentA", "AgentB"},
        )
        diagram = builder.render(trace)
        assert "AgentB -->> AgentA" in diagram

    def test_title(self):
        builder = MermaidBuilder()
        diagram = builder.render(self._make_trace(), title="My Trace")
        assert "title My Trace" in diagram

    def test_timestamp_notes_short_format(self):
        builder = MermaidBuilder()
        diagram = builder.render(self._make_trace())
        assert "Note right of" in diagram
        assert "10:30:00" in diagram
        # Full ISO should NOT appear
        assert "2025-06-15" not in diagram

    def test_no_timestamp_note_on_response(self):
        """Responses should not generate timestamp notes."""
        builder = MermaidBuilder()
        trace = TraceData(
            interactions=[
                Interaction(
                    sender="A",
                    receiver="B",
                    method="response",
                    is_response=True,
                    timestamp="2025-01-01T00:00:00Z",
                ),
            ],
            agents={"A", "B"},
        )
        diagram = builder.render(trace)
        assert "Note right of" not in diagram


class TestMermaidBuilderEdgeCases:
    def test_empty_trace(self):
        builder = MermaidBuilder()
        diagram = builder.render(TraceData())
        assert diagram.startswith("sequenceDiagram")
        assert "participant" not in diagram

    def test_single_interaction(self):
        builder = MermaidBuilder()
        trace = TraceData(
            interactions=[
                Interaction(sender="A", receiver="B", method="message/send"),
            ],
            agents={"A", "B"},
        )
        diagram = builder.render(trace)
        assert "A ->> B" in diagram

    def test_long_task_id_truncated(self):
        builder = MermaidBuilder()
        trace = TraceData(
            interactions=[
                Interaction(
                    sender="A",
                    receiver="B",
                    method="message/send",
                    task_id="very-long-task-id-1234567890",
                ),
            ],
            agents={"A", "B"},
        )
        diagram = builder.render(trace)
        assert "Task: very-lon" in diagram
        assert "very-long-task-id-1234567890" not in diagram

    def test_long_error_message_truncated(self):
        builder = MermaidBuilder()
        long_msg = "A" * 100
        trace = TraceData(
            interactions=[
                Interaction(
                    sender="A",
                    receiver="B",
                    method="response",
                    is_error=True,
                    error_message=long_msg,
                ),
            ],
            agents={"A", "B"},
        )
        diagram = builder.render(trace)
        assert "A" * 50 in diagram
        assert "A" * 51 not in diagram

    def test_title_with_special_characters(self):
        builder = MermaidBuilder()
        trace = TraceData(
            interactions=[
                Interaction(sender="A", receiver="B", method="message/send"),
            ],
            agents={"A", "B"},
        )
        diagram = builder.render(trace, title="Test: Agent A → B")
        assert "title Test: Agent A → B" in diagram

    def test_participants_in_discovery_order(self):
        builder = MermaidBuilder()
        trace = TraceData(
            interactions=[
                Interaction(sender="Zulu", receiver="Alpha", method="message/send"),
                Interaction(sender="Bravo", receiver="Zulu", method="message/send"),
            ],
            agents={"Zulu", "Alpha", "Bravo"},
        )
        diagram = builder.render(trace)
        lines = diagram.split("\n")
        participant_lines = [line for line in lines if "participant" in line]
        assert len(participant_lines) == 3
        assert "Zulu" in participant_lines[0]
        assert "Alpha" in participant_lines[1]
        assert "Bravo" in participant_lines[2]


class TestMermaidBuilderGroupByTask:
    def test_group_by_task_creates_rect(self):
        builder = MermaidBuilder(group_by_task=True)
        trace = TraceData(
            interactions=[
                Interaction(
                    sender="A",
                    receiver="B",
                    method="message/send",
                    task_id="task-abc-123",
                ),
                Interaction(
                    sender="B",
                    receiver="A",
                    method="response",
                    task_id="task-abc-123",
                    is_response=True,
                ),
            ],
            agents={"A", "B"},
        )
        diagram = builder.render(trace)
        assert "rect rgb(240, 248, 255)" in diagram
        assert "Task task-abc" in diagram
        assert "end" in diagram

    def test_group_by_task_multiple_tasks(self):
        builder = MermaidBuilder(group_by_task=True)
        trace = TraceData(
            interactions=[
                Interaction(sender="A", receiver="B", method="message/send", task_id="task-111"),
                Interaction(sender="A", receiver="C", method="message/send", task_id="task-222"),
            ],
            agents={"A", "B", "C"},
        )
        diagram = builder.render(trace)
        assert diagram.count("rect") == 2
        # Count "end" as standalone lines (not matching "send")
        end_lines = [line.strip() for line in diagram.split("\n") if line.strip() == "end"]
        assert len(end_lines) == 2

    def test_group_by_task_no_task_id(self):
        builder = MermaidBuilder(group_by_task=True)
        trace = TraceData(
            interactions=[
                Interaction(sender="A", receiver="B", method="message/send"),
            ],
            agents={"A", "B"},
        )
        diagram = builder.render(trace)
        assert "rect" not in diagram

    def test_flat_mode_no_rect(self):
        builder = MermaidBuilder(group_by_task=False)
        trace = TraceData(
            interactions=[
                Interaction(sender="A", receiver="B", method="message/send", task_id="task-111"),
            ],
            agents={"A", "B"},
        )
        diagram = builder.render(trace)
        assert "rect" not in diagram


class TestMermaidBuilderLabels:
    def test_request_with_summary_uses_quoted_text(self):
        builder = MermaidBuilder()
        trace = TraceData(
            interactions=[
                Interaction(
                    sender="A",
                    receiver="B",
                    method="message/send",
                    summary="Compute factorial of 10",
                ),
            ],
            agents={"A", "B"},
        )
        diagram = builder.render(trace)
        assert '"Compute factorial of 10"' in diagram
        assert "message/send" not in diagram

    def test_request_without_summary_falls_back_to_method(self):
        builder = MermaidBuilder()
        trace = TraceData(
            interactions=[
                Interaction(sender="A", receiver="B", method="message/send"),
            ],
            agents={"A", "B"},
        )
        diagram = builder.render(trace)
        assert "message/send" in diagram

    def test_response_with_summary_uses_quoted_text(self):
        builder = MermaidBuilder()
        trace = TraceData(
            interactions=[
                Interaction(
                    sender="B",
                    receiver="A",
                    method="response",
                    is_response=True,
                    summary="3628800",
                ),
            ],
            agents={"A", "B"},
        )
        diagram = builder.render(trace)
        assert '"3628800"' in diagram

    def test_response_with_status_no_summary(self):
        builder = MermaidBuilder()
        trace = TraceData(
            interactions=[
                Interaction(
                    sender="B",
                    receiver="A",
                    method="response",
                    is_response=True,
                    status="completed",
                    task_id="task-abc",
                ),
            ],
            agents={"A", "B"},
        )
        diagram = builder.render(trace)
        assert "completed (Task: task-abc" in diagram

    def test_response_without_status_shows_response(self):
        builder = MermaidBuilder()
        trace = TraceData(
            interactions=[
                Interaction(
                    sender="B",
                    receiver="A",
                    method="response",
                    is_response=True,
                ),
            ],
            agents={"A", "B"},
        )
        diagram = builder.render(trace)
        assert "Response" in diagram

    def test_error_label_with_colon(self):
        builder = MermaidBuilder()
        trace = TraceData(
            interactions=[
                Interaction(
                    sender="B",
                    receiver="A",
                    method="response",
                    is_error=True,
                    error_message="Connection refused",
                ),
            ],
            agents={"A", "B"},
        )
        diagram = builder.render(trace)
        assert "ERROR: Connection refused" in diagram

    def test_timestamp_short_with_millis(self):
        """Milliseconds and Z should be stripped from timestamp notes."""
        builder = MermaidBuilder()
        trace = TraceData(
            interactions=[
                Interaction(
                    sender="A",
                    receiver="B",
                    method="message/send",
                    timestamp="2025-06-15T10:30:05.000Z",
                ),
            ],
            agents={"A", "B"},
        )
        diagram = builder.render(trace)
        assert "10:30:05" in diagram
        assert "2025-06-15" not in diagram
        assert ".000" not in diagram

    def test_timestamp_without_t_kept_as_is(self):
        """Non-ISO timestamps should pass through unchanged."""
        builder = MermaidBuilder()
        trace = TraceData(
            interactions=[
                Interaction(
                    sender="A",
                    receiver="B",
                    method="message/send",
                    timestamp="1718444400",
                ),
            ],
            agents={"A", "B"},
        )
        diagram = builder.render(trace)
        assert "1718444400" in diagram


class TestSanitize:
    def test_spaces(self):
        assert _sanitize("Agent A") == "Agent_A"

    def test_hyphens(self):
        assert _sanitize("my-agent") == "my_agent"

    def test_dots(self):
        assert _sanitize("agent.v2") == "agent_v2"

    def test_combined(self):
        assert _sanitize("my agent-v2.0") == "my_agent_v2_0"

    def test_already_safe(self):
        assert _sanitize("AgentA") == "AgentA"
