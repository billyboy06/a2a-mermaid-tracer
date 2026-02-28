# Testing Standards

## Mandatory Coverage

- Every new public function or method MUST ship with tests
- Every bug fix MUST include a regression test
- No code is considered complete until tests pass: `pytest` must exit 0

## Test Organization

- Unit tests in `tests/` mirroring `src/` structure
- Integration tests in `tests/integration/` (optional, for CLI end-to-end flows)
- Shared fixtures in `tests/conftest.py`

## Test Data

- Small inline JSON strings for unit tests (no external fixture files)
- `examples/sample_traces.json` for integration/CLI tests only
- Build `TraceData` and `Interaction` objects directly in renderer tests

## What to Test Thoroughly

- Parser: all JSON-RPC message types (request, response, error, streaming)
- Parser: both input formats (JSON array, NDJSON)
- Parser: edge cases (missing fields, empty arrays, malformed JSON)
- Renderer: Mermaid syntax correctness (participants, arrows, notes)
- Renderer: error styling (--x arrows for errors)
- CLI: via `typer.testing.CliRunner` — test exit codes and output

## What NOT to Test

- Private methods directly (test them through public API)
- Mermaid.js rendering (that's the viewer's job)
- Simple data classes with no logic

## Test Quality Checklist

Before considering tests complete:
- [ ] Happy path covered
- [ ] Edge cases covered (empty input, single interaction, all errors)
- [ ] CLI exit codes verified (0 for success, 1 for errors)
- [ ] No flaky tests (no external dependencies, no temp files left behind)
- [ ] Tests run in isolation (no shared mutable state between tests)
