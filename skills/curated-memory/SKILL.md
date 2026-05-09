---
name: curated-memory
description: Persistent curated memory for Codex using a global SQLite database. Use when Codex needs to initialize, inspect, search, add, update, or delete durable memory across sessions and projects; when a user asks to remember facts, preferences, decisions, constraints, or prior work; or when starting substantial work that may benefit from previously curated context.
---

# Curated Memory

Use `scripts/memory.py` to store and retrieve durable, curated memory in a global SQLite database.

The database path resolves in this order:

1. `CODEX_MEMORY_DB`
2. `$CODEX_HOME/memories/memory_state.db`
3. `~/.codex/memories/memory_state.db`

The database is global to Codex and independent from project databases. Do not store application secrets, credentials, API keys, private tokens, raw `.env` values, or unnecessary personal data.

## Workflow

1. Run `init` before first use or when repairing the schema.
2. Search memory before substantial work, especially when the user references previous decisions, preferences, project conventions, or cross-session context.
3. Save only durable, useful facts after they are confirmed or strongly implied by completed work.
4. Prefer short, specific memory items over long transcripts.
5. Use project scope for repo-specific knowledge and global scope for user/tooling preferences.

## Commands

Initialize:

```bash
python ~/.codex/skills/curated-memory/scripts/memory.py init
```

Search:

```bash
python ~/.codex/skills/curated-memory/scripts/memory.py search "API contract" --scope project --project-path "/path/to/project"
```

Search uses normal FTS5 first, trigram FTS as a complement/fallback, and `LIKE` as the final fallback. Use `--substring` when looking for fragments inside identifiers, paths, compound names, or text without clear word boundaries:

```bash
python ~/.codex/skills/curated-memory/scripts/memory.py search "velope" --scope project --project-path "/path/to/project" --substring
```

Remember:

```bash
python ~/.codex/skills/curated-memory/scripts/memory.py remember --scope project --project-path "/path/to/project" --kind decision --key "api-envelope" --content "API routes return JSON envelopes shaped as { data, error }."
```

List:

```bash
python ~/.codex/skills/curated-memory/scripts/memory.py list --scope project --project-path "/path/to/project"
```

Forget:

```bash
python ~/.codex/skills/curated-memory/scripts/memory.py forget --id "<memory-id>"
```

Session logging is optional and should stay concise. Use `start-session`, `add-message`, and `end-session` only when explicit session traceability is useful.
