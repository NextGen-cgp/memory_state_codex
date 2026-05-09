---
name: curated-memory-plus
description: Persistent curated memory plus mandatory session/message traceability for Codex using a global SQLite database. Use when Codex needs to initialize, inspect, search, add, update, or delete durable memory across sessions and projects; when a user asks to remember facts, preferences, decisions, constraints, or prior work; or when starting substantial work that must log sessions and messages for searchable history.
---

# Curated Memory Plus

Use `scripts/memory.py` to store and retrieve durable, curated memory plus searchable session/message history in a global SQLite database.

The database path resolves in this order:

1. `CODEX_MEMORY_DB`
2. `$CODEX_HOME/memories/memory_state.db`
3. `~/.codex/memories/memory_state.db`

The database is global to Codex and independent from project databases. Do not store application secrets, credentials, API keys, private tokens, raw `.env` values, or unnecessary personal data.

## Workflow

1. Run `init` before first use or when repairing the schema.
2. Start a session with `start-session` before substantive work.
3. Log the user's substantive request and assistant outcomes with `add-message`.
4. Search memory before substantial work, usually with `--include-messages`.
5. Save durable, useful facts with `remember` after they are confirmed or strongly implied by completed work.
6. Link curated memories to their provenance. `remember` requires `--session-id`; add `--message-id` when the memory is grounded in a specific logged message.
7. End the session with `end-session`.

## Commands

Initialize:

```bash
python ~/.codex/skills/curated-memory-plus/scripts/memory.py init
```

Start a session:

```bash
python ~/.codex/skills/curated-memory-plus/scripts/memory.py start-session --title "Implement API change" --project-path "/path/to/project"
```

Log a message:

```bash
python ~/.codex/skills/curated-memory-plus/scripts/memory.py add-message --session-id "ses_..." --role user --content "Change the API envelope."
```

Search:

```bash
python ~/.codex/skills/curated-memory-plus/scripts/memory.py search "API contract" --scope project --project-path "/path/to/project" --include-messages
```

Search uses normal FTS5 first, trigram FTS as a complement/fallback, and `LIKE` as the final fallback. Message search joins through `sessions` and applies project filters via `sessions.project_path` so `--include-messages` can scale by project. Use `--substring` when looking for fragments inside identifiers, paths, compound names, or text without clear word boundaries. Query retries are enabled by default: when the original query has no results, the CLI retries with derived significant terms up to `--max-retries` (default `5`) and reports `search_attempts`.

If deterministic retries return no useful context, perform up to 3 semantic retry searches before concluding there is no memory. Rewrite the query using likely synonyms, project-specific nouns, session titles, filenames, feature names, API names, or broader concepts from the user's request. Use `search_attempts` to choose whether to broaden or narrow the next retry.

```bash
python ~/.codex/skills/curated-memory-plus/scripts/memory.py search "velope" --scope project --project-path "/path/to/project" --include-messages --substring
```

Remember:

```bash
python ~/.codex/skills/curated-memory-plus/scripts/memory.py remember --scope project --project-path "/path/to/project" --kind decision --key "api-envelope" --content "API routes return JSON envelopes shaped as { data, error }." --session-id "ses_..." --message-id "msg_..."
```

Use `--allow-unlinked` only for exceptional imported/global memories that genuinely have no session provenance.

List:

```bash
python ~/.codex/skills/curated-memory-plus/scripts/memory.py list --scope project --project-path "/path/to/project"
```

Forget:

```bash
python ~/.codex/skills/curated-memory-plus/scripts/memory.py forget --id "<memory-id>"
```

PLUS mode requires session logging for substantive work. Keep logged messages concise, user-visible, and free of secrets or hidden chain-of-thought.
