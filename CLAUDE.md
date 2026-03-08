# A2A-Mermaid-Tracer

CLI tool to generate Mermaid.js sequence diagrams from A2A protocol traces.

## Build & Test

```bash
pip install -e ".[dev]"
ruff check src/ tests/              # lint
ruff format src/ tests/              # format
pytest                               # run all tests
pytest tests/test_parser.py -v       # single file
pytest -k "test_name"                # single test
```

## Code Style

- Python 3.10+, use `from __future__ import annotations` in every module
- Line length: 100 chars (ruff enforced)
- Type hints on all public functions and method signatures
- Docstrings: Google style, required on all public classes and functions
- Imports: sorted by ruff (isort-compatible)

## Architecture

```
src/a2a_mermaid_tracer/
├── parser.py     # TraceParser — ingests JSON/NDJSON logs into Interaction dataclasses
├── renderer.py   # MermaidBuilder — generates Mermaid sequence diagram syntax
├── cli.py        # Typer CLI — generate command with --input/--output/--title/--strict/--group-by-task
└── __init__.py   # Public API exports
```

- **parser.py**: Pure data transformation, no I/O except file reading. Dataclasses for structured output.
- **renderer.py**: Pure text generation from TraceData. No I/O, no side effects.
- **cli.py**: Thin CLI layer using Typer. Wires parser → renderer → output.

## Key Dependencies

- `typer[all]`: CLI framework — keep CLI thin, logic in parser/renderer
- No other runtime dependencies (this is intentional — keep it lightweight)

## Testing Rules

- Every public method MUST have at least one test
- Parser tests: use inline JSON strings, not external fixture files (except for integration tests)
- Renderer tests: assert on specific Mermaid syntax fragments, not full diagram strings
- CLI tests: test via `typer.testing.CliRunner` for integration tests
- Test edge cases: empty traces, single interaction, all-error traces, missing fields

## Conventions

- No print statements — use `typer.echo` in CLI, return values elsewhere
- Parser and renderer are pure functions with no side effects
- Fail fast: raise `ValueError` on malformed input with descriptive messages
- Keep zero runtime dependencies beyond Typer — this is a lightweight tool
