"""CLI for a2a-mermaid-tracer."""

from __future__ import annotations

from pathlib import Path

import typer

from a2a_mermaid_tracer.parser import TraceParser
from a2a_mermaid_tracer.renderer import MermaidBuilder

app = typer.Typer(
    name="a2a-mermaid-tracer",
    help="Generate Mermaid.js sequence diagrams from A2A protocol traces.",
    add_completion=False,
)


@app.command()
def generate(
    input: Path = typer.Option(
        ...,
        "--input",
        "-i",
        help="Path to the trace file (JSON array or NDJSON). Use '-' for stdin.",
    ),
    output: Path = typer.Option(
        None,
        "--output",
        "-o",
        help="Path to write the Mermaid diagram (default: stdout)",
    ),
    title: str = typer.Option(
        None,
        "--title",
        "-t",
        help="Optional title for the diagram",
    ),
    strict: bool = typer.Option(
        False,
        "--strict",
        help="Fail on malformed entries instead of skipping them",
    ),
    group_by_task: bool = typer.Option(
        False,
        "--group-by-task",
        help="Group interactions by task ID in rect blocks",
    ),
) -> None:
    """Parse A2A traces and generate a Mermaid sequence diagram."""
    parser = TraceParser(strict=strict)

    try:
        if str(input) == "-":
            trace = parser.parse_stdin()
        else:
            if not input.exists():
                typer.echo(f"File not found: {input}", err=True)
                raise typer.Exit(code=1)
            trace = parser.parse_file(input)
    except ValueError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)

    if not trace.interactions:
        typer.echo("No interactions found in the trace file.", err=True)
        raise typer.Exit(code=1)

    builder = MermaidBuilder(group_by_task=group_by_task)
    diagram = builder.render(trace, title=title)

    if output:
        # Wrap in markdown code block for .md files
        if output.suffix == ".md":
            content = f"```mermaid\n{diagram}```\n"
        else:
            content = diagram
        output.write_text(content, encoding="utf-8")
        typer.echo(f"Diagram written to {output}")
    else:
        typer.echo(diagram)

    typer.echo(
        f"Parsed {len(trace.interactions)} interactions between {len(trace.agents)} agents.",
        err=True,
    )


if __name__ == "__main__":
    app()
