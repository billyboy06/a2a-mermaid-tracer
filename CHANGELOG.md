# Changelog

## [0.2.0] - Unreleased

### Added
- `--strict` mode: fail on malformed entries instead of silently skipping
- `--group-by-task` option: wrap interactions sharing a task ID in Mermaid `rect` blocks
- stdin support: use `--input -` to pipe trace data
- Fail-fast validation in parser (empty input, invalid JSON, missing required fields)
- CLI tests via `typer.testing.CliRunner`
- Edge case tests for parser and renderer
- NDJSON example file (`examples/sample_traces.ndjson`)
- GitHub Actions CI (lint + test on Python 3.10/3.11/3.12)
- PEP 561 `py.typed` marker

### Fixed
- Error arrows now point from responder back to requester (same direction as response arrows)
- Parser no longer silently uses the entire entry dict when `message` field is missing

## [0.1.0] - 2026-03-07

### Added
- Initial release
- Parse JSON-RPC 2.0 trace logs (JSON array or NDJSON)
- Generate Mermaid sequence diagrams (requests, responses, errors)
- Timestamp annotations on request arrows
- Task ID references (truncated to 8 chars)
- Output to stdout, `.md`, or `.mmd` files
- `--title` option for diagram titles
