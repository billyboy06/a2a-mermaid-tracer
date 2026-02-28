"""Tests for TraceParser."""

import json
import tempfile
from pathlib import Path

from a2a_mermaid_tracer.parser import TraceParser


SAMPLE_TRACES = [
    {
        "sender": "OrchestratorAgent",
        "receiver": "MathAgent",
        "timestamp": "2025-06-15T10:30:00Z",
        "message": {
            "jsonrpc": "2.0",
            "id": "req-001",
            "method": "message/send",
            "params": {
                "message": {
                    "messageId": "msg-001",
                    "role": "user",
                    "parts": [{"kind": "text", "text": "Compute factorial of 10"}],
                }
            },
        },
    },
    {
        "sender": "MathAgent",
        "receiver": "OrchestratorAgent",
        "timestamp": "2025-06-15T10:30:02Z",
        "message": {
            "jsonrpc": "2.0",
            "id": "req-001",
            "result": {
                "id": "task-abc",
                "status": {"state": "completed"},
                "artifacts": [
                    {"parts": [{"kind": "text", "text": "3628800"}]}
                ],
            },
        },
    },
    {
        "sender": "OrchestratorAgent",
        "receiver": "SearchAgent",
        "timestamp": "2025-06-15T10:30:03Z",
        "message": {
            "jsonrpc": "2.0",
            "id": "req-002",
            "method": "message/send",
            "params": {
                "message": {
                    "messageId": "msg-002",
                    "role": "user",
                    "parts": [{"kind": "text", "text": "Search for latest news"}],
                }
            },
        },
    },
    {
        "sender": "SearchAgent",
        "receiver": "OrchestratorAgent",
        "timestamp": "2025-06-15T10:30:05Z",
        "message": {
            "jsonrpc": "2.0",
            "id": "req-002",
            "error": {
                "code": -32000,
                "message": "Search service unavailable",
            },
        },
    },
]


class TestTraceParser:
    def test_parse_json_array(self):
        parser = TraceParser()
        trace = parser.parse_string(json.dumps(SAMPLE_TRACES))
        assert len(trace.interactions) == 4
        assert len(trace.agents) == 3

    def test_parse_ndjson(self):
        parser = TraceParser()
        ndjson = "\n".join(json.dumps(entry) for entry in SAMPLE_TRACES)
        trace = parser.parse_string(ndjson)
        assert len(trace.interactions) == 4

    def test_parse_file(self):
        parser = TraceParser()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(SAMPLE_TRACES, f)
            f.flush()
            trace = parser.parse_file(f.name)
        assert len(trace.interactions) == 4

    def test_request_interaction(self):
        parser = TraceParser()
        trace = parser.parse_string(json.dumps(SAMPLE_TRACES))
        req = trace.interactions[0]
        assert req.sender == "OrchestratorAgent"
        assert req.receiver == "MathAgent"
        assert req.method == "message/send"
        assert not req.is_response
        assert not req.is_error

    def test_response_interaction(self):
        parser = TraceParser()
        trace = parser.parse_string(json.dumps(SAMPLE_TRACES))
        resp = trace.interactions[1]
        assert resp.is_response
        assert resp.task_id == "task-abc"

    def test_error_interaction(self):
        parser = TraceParser()
        trace = parser.parse_string(json.dumps(SAMPLE_TRACES))
        err = trace.interactions[3]
        assert err.is_error
        assert "unavailable" in err.error_message

    def test_timestamps_preserved(self):
        parser = TraceParser()
        trace = parser.parse_string(json.dumps(SAMPLE_TRACES))
        assert trace.interactions[0].timestamp == "2025-06-15T10:30:00Z"
