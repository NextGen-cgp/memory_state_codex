# Global Codex Instructions

## Persistent Curated Memory

- Codex has access to a global curated memory store managed by the `curated-memory` skill.
- The default database path is resolved by the CLI in this order:
  - `CODEX_MEMORY_DB`, if set;
  - `$CODEX_HOME/memories/memory_state.db`, if `CODEX_HOME` is set;
  - `~/.codex/memories/memory_state.db`.
- The default skill script path is:
  - `$CODEX_HOME/skills/curated-memory/scripts/memory.py`, if `CODEX_HOME` is set;
  - `~/.codex/skills/curated-memory/scripts/memory.py`.
- Initialize or repair the database with:
  `python ~/.codex/skills/curated-memory/scripts/memory.py init`

### When To Search Memory

- Before substantial work in a repository, search project-scoped memory for the current project path and include global memory.
- Search memory when the user references prior decisions, preferences, constraints, conventions, or work from earlier sessions.
- Do not block trivial tasks on memory search when local context is already sufficient.

Example:

```bash
python ~/.codex/skills/curated-memory/scripts/memory.py search "API contract" --scope project --project-path "/path/to/project"
```

### Search Behavior

- The `search` command uses normal FTS5 first, trigram FTS as a complement or fallback, and SQL `LIKE` as the final fallback.
- Use `--substring` when looking for fragments inside identifiers, file paths, compound names, or text without clear word boundaries.
- Results include `match_type` with one of: `fulltext`, `trigram`, or `like`.
- Include `--include-messages` only when optional session/message traceability is relevant; the normal curated-memory workflow searches `memory_items`.

Example:

```bash
python ~/.codex/skills/curated-memory/scripts/memory.py search "velope" --scope project --project-path "/path/to/project" --substring
```

### What To Store

- Store only durable, curated, reusable memory:
  - confirmed technical decisions;
  - stable user preferences;
  - security, API, data, or workflow constraints;
  - project-specific conventions;
  - facts that will prevent repeated investigation in future sessions.
- Prefer short, specific, actionable memory items.
- Use `scope=project` for repository-specific knowledge and `scope=global` for user or tooling preferences.
- Use a stable `key` when the memory represents a rule or decision that should be updated instead of duplicated.

Example:

```bash
python ~/.codex/skills/curated-memory/scripts/memory.py remember --scope project --project-path "/path/to/project" --kind decision --key "api-envelope" --content "API routes return JSON envelopes shaped as { data, error }."
```

### What Not To Store

- Do not store secrets, credentials, tokens, API keys, cookies, raw `.env` values, or unnecessary personal data.
- Do not store long transcripts by default.
- Do not store fragile guesses as facts. If an inference may change or is not confirmed, either say so in the memory content or do not persist it.
- Do not use this database as a substitute for project documentation, migrations, tests, or versioned contracts.

### Maintenance

- If a memory becomes obsolete, update it with the same `key` or mark it deleted with `forget`.
- The global memory does not override local project contracts. If a rule belongs in a repository, update that repository's `AGENTS.md` or documentation when appropriate.
