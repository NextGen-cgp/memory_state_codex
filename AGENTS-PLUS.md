# Global Codex Instructions

## Persistent Curated Memory Plus

- Codex has access to a global curated memory store managed by the `curated-memory-plus` skill.
- PLUS mode requires explicit session and message traceability for substantive work.
- The default database path is resolved by the CLI in this order:
  - `CODEX_MEMORY_DB`, if set;
  - `$CODEX_HOME/memories/memory_state.db`, if `CODEX_HOME` is set;
  - `~/.codex/memories/memory_state.db`.
- The default skill script path is:
  - `$CODEX_HOME/skills/curated-memory-plus/scripts/memory.py`, if `CODEX_HOME` is set;
  - `~/.codex/skills/curated-memory-plus/scripts/memory.py`.
- Initialize or repair the database with:
  `python ~/.codex/skills/curated-memory-plus/scripts/memory.py init`

### Required Session Logging

- At the start of substantive work, create a session with `start-session`.
- Use the current repository path as `--project-path` when working inside a repo.
- Log the user's substantive request with `add-message --role user`.
- Log assistant outcomes as concise assistant messages. Do not store hidden chain-of-thought; store only user-visible summaries, decisions, and relevant implementation notes.
- Log important tool results as concise `tool` messages when they explain future-relevant decisions or failures.
- Set `--relevance` when logging messages:
  - `0`: routine message with little future value;
  - `1`: useful context;
  - `2`: important implementation detail, user preference, or tool result;
  - `3`: key decision, final session summary, verification result, or memory provenance anchor.
- End the session with `end-session` when the task is complete.
- For trivial one-off answers, session logging may be skipped only when the answer has no durable context value.

Example:

```bash
python ~/.codex/skills/curated-memory-plus/scripts/memory.py start-session --title "Implement auth fix" --project-path "/path/to/project"
python ~/.codex/skills/curated-memory-plus/scripts/memory.py add-message --session-id "ses_..." --role user --content "Fix the auth redirect bug." --relevance 1
python ~/.codex/skills/curated-memory-plus/scripts/memory.py add-message --session-id "ses_..." --role assistant --content "Fixed the auth redirect bug in middleware and verified the login flow." --relevance 3
python ~/.codex/skills/curated-memory-plus/scripts/memory.py end-session "ses_..."
```

### When To Search Memory

- Before substantive work in a repository, search project-scoped memory for the current project path and include global memory.
- In PLUS mode, include messages for context search when prior session details may matter.
- Search memory when the user references prior decisions, preferences, constraints, conventions, or work from earlier sessions.
- Do not block trivial tasks on memory search when local context is already sufficient.

Example:

```bash
python ~/.codex/skills/curated-memory-plus/scripts/memory.py search "API contract" --scope project --project-path "/path/to/project" --include-messages
```

### Search Behavior

- The `search` command uses normal FTS5 first, trigram FTS as a complement or fallback, and SQL `LIKE` as the final fallback.
- `memory_items` are searched by curated-memory scope.
- `messages` are searched through their `sessions`, so project filters scale by joining `messages -> sessions` and applying `sessions.project_path`.
- Message search returns `relevance` and uses it to promote important messages after textual rank, and as the primary ordering signal for `LIKE` fallback matches.
- Use `--substring` when looking for fragments inside identifiers, file paths, compound names, or text without clear word boundaries.
- Query retries are enabled by default. If the original query returns no results, the CLI retries with derived significant terms up to `--max-retries` (default `5`).
- Results include `match_type` with one of: `fulltext`, `trigram`, or `like`.
- Results include `search_attempts` so the agent can see which query variant produced matches.
- If deterministic retries return no useful context, the agent should perform up to 3 semantic retry searches before concluding there is no memory. Rewrite the query using likely synonyms, project-specific nouns, session titles, filenames, feature names, API names, or broader concepts from the user's request.
- Prefer broad-to-specific semantic retries: first the project/product name, then the feature/domain term, then the suspected file/API/decision term. Avoid repeating failed query wording.
- Use `search_attempts` to decide the next retry. If only generic terms matched, issue a more specific semantic query; if nothing matched, broaden the query.

Example:

```bash
python ~/.codex/skills/curated-memory-plus/scripts/memory.py search "velope" --scope project --project-path "/path/to/project" --include-messages --substring
```

### What To Store As Curated Memory

- Store durable, curated, reusable memory with `remember`:
  - confirmed technical decisions;
  - stable user preferences;
  - security, API, data, or workflow constraints;
  - project-specific conventions;
  - facts that will prevent repeated investigation in future sessions.
- Prefer short, specific, actionable memory items.
- Use `scope=project` for repository-specific knowledge and `scope=global` for user or tooling preferences.
- Use a stable `key` when the memory represents a rule or decision that should be updated instead of duplicated.
- Set `--confidence` when storing memory:
  - `1.0`: directly verified fact, explicit user preference, or confirmed project contract;
  - `0.8`: reliable working conclusion from completed work;
  - `0.5`: reasonable inference that has not been directly verified;
  - `0.2`: weak/provisional note that should be treated cautiously.
- Prefer `0.8` when unsure. Use values below `0.8` only when the memory text clearly signals uncertainty.
- `remember` requires `--session-id` in PLUS mode. Pass `--message-id` when the memory is grounded in a specific logged message.
- Use `--allow-unlinked` only for exceptional imported/global memories that genuinely have no session provenance.

Example:

```bash
python ~/.codex/skills/curated-memory-plus/scripts/memory.py remember --scope project --project-path "/path/to/project" --kind decision --key "api-envelope" --content "API routes return JSON envelopes shaped as { data, error }." --confidence 1.0 --session-id "ses_..." --message-id "msg_..."
```

### What Not To Store

- Do not store secrets, credentials, tokens, API keys, cookies, raw `.env` values, or unnecessary personal data.
- Do not store hidden reasoning or chain-of-thought.
- Do not store fragile guesses as facts. If an inference may change or is not confirmed, either say so in the memory content or do not persist it.
- Do not use this database as a substitute for project documentation, migrations, tests, or versioned contracts.

### Maintenance

- If a memory becomes obsolete, update it with the same `key` or mark it deleted with `forget`.
- The global memory does not override local project contracts. If a rule belongs in a repository, update that repository's `AGENTS.md` or documentation when appropriate.
