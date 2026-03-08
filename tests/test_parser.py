"""Tests for TraceParser."""

from __future__ import annotations

import json
import tempfile

import pytest

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
                "artifacts": [{"parts": [{"kind": "text", "text": "3628800"}]}],
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


class TestTraceParserBasic:
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


class TestTraceParserEdgeCases:
    def test_empty_string_raises(self):
        parser = TraceParser()
        with pytest.raises(ValueError, match="empty"):
            parser.parse_string("")

    def test_whitespace_only_raises(self):
        parser = TraceParser()
        with pytest.raises(ValueError, match="empty"):
            parser.parse_string("   \n  ")

    def test_empty_json_array(self):
        parser = TraceParser()
        trace = parser.parse_string("[]")
        assert len(trace.interactions) == 0
        assert len(trace.agents) == 0

    def test_single_interaction(self):
        parser = TraceParser()
        trace = parser.parse_string(json.dumps([SAMPLE_TRACES[0]]))
        assert len(trace.interactions) == 1
        assert trace.interactions[0].method == "message/send"

    def test_all_errors_trace(self):
        entries = [
            {
                "sender": "A",
                "receiver": "B",
                "message": {
                    "jsonrpc": "2.0",
                    "id": "1",
                    "error": {"code": -1, "message": "fail"},
                },
            },
            {
                "sender": "A",
                "receiver": "C",
                "message": {
                    "jsonrpc": "2.0",
                    "id": "2",
                    "error": {"code": -2, "message": "also fail"},
                },
            },
        ]
        parser = TraceParser()
        trace = parser.parse_string(json.dumps(entries))
        assert len(trace.interactions) == 2
        assert all(i.is_error for i in trace.interactions)

    def test_invalid_json_raises(self):
        parser = TraceParser()
        with pytest.raises(ValueError, match="Invalid JSON"):
            parser.parse_string("[{invalid json")

    def test_single_object_parsed_as_ndjson(self):
        """A single JSON object is valid NDJSON with one line."""
        parser = TraceParser()
        entry = {
            "sender": "A",
            "receiver": "B",
            "message": {"jsonrpc": "2.0", "id": "1", "method": "message/send", "params": {}},
        }
        trace = parser.parse_string(json.dumps(entry))
        assert len(trace.interactions) == 1

    def test_invalid_format_raises(self):
        parser = TraceParser()
        with pytest.raises(ValueError, match="Invalid trace format"):
            parser.parse_string("not json at all")

    def test_missing_sender_skips_in_non_strict(self):
        entries = [
            {
                "receiver": "B",
                "message": {"jsonrpc": "2.0", "id": "1", "method": "message/send"},
            }
        ]
        parser = TraceParser()
        trace = parser.parse_string(json.dumps(entries))
        assert len(trace.interactions) == 0

    def test_missing_receiver_skips_in_non_strict(self):
        entries = [
            {
                "sender": "A",
                "message": {"jsonrpc": "2.0", "id": "1", "method": "message/send"},
            }
        ]
        parser = TraceParser()
        trace = parser.parse_string(json.dumps(entries))
        assert len(trace.interactions) == 0

    def test_missing_message_skips_in_non_strict(self):
        entries = [{"sender": "A", "receiver": "B"}]
        parser = TraceParser()
        trace = parser.parse_string(json.dumps(entries))
        assert len(trace.interactions) == 0

    def test_empty_file_raises(self):
        parser = TraceParser()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("")
            f.flush()
            with pytest.raises(ValueError, match="empty"):
                parser.parse_file(f.name)

    def test_message_stream_method(self):
        entries = [
            {
                "sender": "A",
                "receiver": "B",
                "message": {
                    "jsonrpc": "2.0",
                    "id": "1",
                    "method": "message/stream",
                    "params": {},
                },
            }
        ]
        parser = TraceParser()
        trace = parser.parse_string(json.dumps(entries))
        assert trace.interactions[0].method == "message/stream"

    def test_task_id_from_params_direct(self):
        entries = [
            {
                "sender": "A",
                "receiver": "B",
                "message": {
                    "jsonrpc": "2.0",
                    "id": "1",
                    "method": "tasks/getTask",
                    "params": {"taskId": "task-direct-123"},
                },
            }
        ]
        parser = TraceParser()
        trace = parser.parse_string(json.dumps(entries))
        assert trace.interactions[0].task_id == "task-direct-123"

    def test_no_timestamp_produces_none(self):
        entries = [
            {
                "sender": "A",
                "receiver": "B",
                "message": {
                    "jsonrpc": "2.0",
                    "id": "1",
                    "method": "message/send",
                    "params": {},
                },
            }
        ]
        parser = TraceParser()
        trace = parser.parse_string(json.dumps(entries))
        assert trace.interactions[0].timestamp is None


class TestTraceParserSummaryAndStatus:
    def test_summary_extracted_from_text_parts(self):
        parser = TraceParser()
        trace = parser.parse_string(json.dumps(SAMPLE_TRACES))
        req = trace.interactions[0]
        assert req.summary == "Compute factorial of 10"

    def test_summary_truncated_at_40_chars(self):
        entries = [
            {
                "sender": "A",
                "receiver": "B",
                "message": {
                    "jsonrpc": "2.0",
                    "id": "1",
                    "method": "message/send",
                    "params": {
                        "message": {
                            "parts": [{"kind": "text", "text": "A" * 60}],
                        }
                    },
                },
            }
        ]
        parser = TraceParser()
        trace = parser.parse_string(json.dumps(entries))
        assert len(trace.interactions[0].summary) == 40

    def test_summary_none_when_no_parts(self):
        entries = [
            {
                "sender": "A",
                "receiver": "B",
                "message": {
                    "jsonrpc": "2.0",
                    "id": "1",
                    "method": "message/send",
                    "params": {},
                },
            }
        ]
        parser = TraceParser()
        trace = parser.parse_string(json.dumps(entries))
        assert trace.interactions[0].summary is None

    def test_status_extracted_from_response(self):
        parser = TraceParser()
        trace = parser.parse_string(json.dumps(SAMPLE_TRACES))
        resp = trace.interactions[1]
        assert resp.status == "completed"

    def test_status_none_on_request(self):
        parser = TraceParser()
        trace = parser.parse_string(json.dumps(SAMPLE_TRACES))
        req = trace.interactions[0]
        assert req.status is None

    def test_status_none_on_error(self):
        parser = TraceParser()
        trace = parser.parse_string(json.dumps(SAMPLE_TRACES))
        err = trace.interactions[3]
        assert err.status is None

    def test_artifact_summary_extracted_from_response(self):
        parser = TraceParser()
        trace = parser.parse_string(json.dumps(SAMPLE_TRACES))
        resp = trace.interactions[1]
        assert resp.summary == "3628800"

    def test_artifact_summary_truncated_at_40_chars(self):
        entries = [
            {
                "sender": "B",
                "receiver": "A",
                "message": {
                    "jsonrpc": "2.0",
                    "id": "1",
                    "result": {
                        "id": "task-1",
                        "status": {"state": "completed"},
                        "artifacts": [{"parts": [{"kind": "text", "text": "X" * 60}]}],
                    },
                },
            }
        ]
        parser = TraceParser()
        trace = parser.parse_string(json.dumps(entries))
        assert len(trace.interactions[0].summary) == 40


class TestTraceParserStrict:
    def test_strict_missing_sender_raises(self):
        entries = [
            {
                "receiver": "B",
                "message": {"jsonrpc": "2.0", "id": "1", "method": "message/send"},
            }
        ]
        parser = TraceParser(strict=True)
        with pytest.raises(ValueError, match="sender"):
            parser.parse_string(json.dumps(entries))

    def test_strict_missing_message_raises(self):
        entries = [{"sender": "A", "receiver": "B"}]
        parser = TraceParser(strict=True)
        with pytest.raises(ValueError, match="message"):
            parser.parse_string(json.dumps(entries))

    def test_strict_invalid_ndjson_line_raises(self):
        data = '{"sender":"A","receiver":"B","message":{"jsonrpc":"2.0","method":"x"}}\n{bad}'
        parser = TraceParser(strict=True)
        with pytest.raises(ValueError, match="line 2"):
            parser.parse_string(data)

    def test_non_strict_invalid_ndjson_line_skips(self):
        good = '{"sender":"A","receiver":"B","message":{"jsonrpc":"2.0","method":"x","id":"1"}}'
        data = f"{good}\n{{bad}}"
        parser = TraceParser()
        trace = parser.parse_string(data)
        assert len(trace.interactions) == 1
