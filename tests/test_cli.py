"""Tests for CLI via typer.testing.CliRunner."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from typer.testing import CliRunner

from a2a_mermaid_tracer.cli import app

runner = CliRunner()

SAMPLE_TRACES = [
    {
        "sender": "A",
        "receiver": "B",
        "timestamp": "2025-06-15T10:30:00Z",
        "message": {
            "jsonrpc": "2.0",
            "id": "req-001",
            "method": "message/send",
            "params": {},
        },
    },
    {
        "sender": "B",
        "receiver": "A",
        "timestamp": "2025-06-15T10:30:01Z",
        "message": {
            "jsonrpc": "2.0",
            "id": "req-001",
            "result": {"id": "task-abc", "status": {"state": "completed"}},
        },
    },
]


def _write_trace_file(traces: list[dict], suffix: str = ".json") -> str:
    """Write traces to a temp file and return the path."""
    f = tempfile.NamedTemporaryFile(mode="w", suffix=suffix, delete=False)
    json.dump(traces, f)
    f.flush()
    f.close()
    return f.name


class TestCLIGenerate:
    def test_stdout_output(self):
        path = _write_trace_file(SAMPLE_TRACES)
        result = runner.invoke(app, ["--input", path])
        assert result.exit_code == 0
        assert "sequenceDiagram" in result.output

    def test_output_to_mmd_file(self):
        path = _write_trace_file(SAMPLE_TRACES)
        with tempfile.NamedTemporaryFile(suffix=".mmd", delete=False) as out:
            out_path = out.name
        result = runner.invoke(app, ["--input", path, "--output", out_path])
        assert result.exit_code == 0
        content = Path(out_path).read_text()
        assert content.startswith("sequenceDiagram")
        assert "```mermaid" not in content

    def test_output_to_md_file_wraps_in_codeblock(self):
        path = _write_trace_file(SAMPLE_TRACES)
        with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as out:
            out_path = out.name
        result = runner.invoke(app, ["--input", path, "--output", out_path])
        assert result.exit_code == 0
        content = Path(out_path).read_text()
        assert content.startswith("```mermaid")
        assert "sequenceDiagram" in content

    def test_title_option(self):
        path = _write_trace_file(SAMPLE_TRACES)
        result = runner.invoke(app, ["--input", path, "--title", "My Diagram"])
        assert result.exit_code == 0
        assert "title My Diagram" in result.output

    def test_empty_trace_exits_with_error(self):
        path = _write_trace_file([])
        result = runner.invoke(app, ["--input", path])
        assert result.exit_code == 1

    def test_invalid_json_exits_with_error(self):
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        f.write("not valid json at all")
        f.flush()
        f.close()
        result = runner.invoke(app, ["--input", f.name])
        assert result.exit_code == 1
        assert "Error" in result.output

    def test_interaction_count_in_stderr(self):
        path = _write_trace_file(SAMPLE_TRACES)
        result = runner.invoke(app, ["--input", path])
        assert result.exit_code == 0
        assert "2 interactions" in result.output

    def test_strict_mode(self):
        entries = [{"sender": "A", "receiver": "B"}]  # missing message
        path = _write_trace_file(entries)
        # Non-strict: exits 1 because no interactions parsed (skipped)
        result = runner.invoke(app, ["--input", path])
        assert result.exit_code == 1

        # Strict: exits 1 with error message about missing field
        result_strict = runner.invoke(app, ["--input", path, "--strict"])
        assert result_strict.exit_code == 1
        assert "Error" in result_strict.output

    def test_group_by_task_option(self):
        path = _write_trace_file(SAMPLE_TRACES)
        result = runner.invoke(app, ["--input", path, "--group-by-task"])
        assert result.exit_code == 0
        assert "rect" in result.output
