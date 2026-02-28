# Mermaid Sequence Diagram Conventions

## Syntax Reference

- Diagram starts with `sequenceDiagram`
- Participants declared with `participant ID as Display Name`
- Participant IDs: alphanumeric + underscores only (sanitize agent names)

## Arrow Types

| Arrow | Meaning | When to use |
|-------|---------|-------------|
| `->>` | Solid arrow with arrowhead | Request (message/send, message/stream) |
| `-->>` | Dashed arrow with arrowhead | Response (JSON-RPC result) |
| `--x` | Dashed arrow with cross | Error (JSON-RPC error) |

## Labels

- Requests: `method_name (Task: short_id)`
- Responses: `Response (Task: short_id)`
- Errors: `ERROR (message_truncated_to_50_chars)`
- Task IDs truncated to 8 chars for readability

## Annotations

- Timestamps as `Note right of Sender: ISO_timestamp`
- Only on request messages (not responses) to avoid clutter

## Output Formats

- `.md` files: wrap diagram in ` ```mermaid ` code block
- `.mmd` files: raw Mermaid syntax (no wrapper)
- stdout: raw Mermaid syntax
