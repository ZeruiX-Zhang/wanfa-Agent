# Deprecated Entrypoints

Reality OS does not delete legacy projects. It marks replaced or wrapper-only entrypoints as deprecated documentation targets.

## Deprecated by Adapter

| Entrypoint | Status | Replacement |
|---|---|---|
| Direct formal knowledge writes from generated/reflection content | Deprecated | Pending review queue in `services/knowledge` |
| Browser extension business logic | Deprecated | Extension is input-only; server adapters own workflow logic |
| Ungated high-risk tool execution | Deprecated | `services/tool-gateway` dry-run and approval policy |

## Preserved

- `legacy/sou`
- `legacy/prompt-agent`
- `legacy/work`
- `legacy/study`
- `legacy/prompt-rag-backup`

No legacy directory is deleted or moved by this document.
