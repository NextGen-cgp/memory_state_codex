# Codex and Claude Curated Memory

Portable persistent memory for Codex and Claude Code agents, backed by SQLite.

This repository packages reusable global profiles for Codex and Claude Code, agent-specific skill folders, an empty SQLite database template, and an npm installer for both providers. The goal is to give agents a durable, searchable memory layer without coupling it to any project database.

## What It Provides

- Curated memory in `memory_items` for durable facts, decisions, preferences, and constraints.
- LITE mode with curated memory only by default.
- PLUS mode with required session/message traceability and project-filtered message search.
- FTS5 indexes for normal full-text search.
- Trigram FTS indexes for substring, identifiers, paths, compound names, and CJK-like text boundaries.
- A Python CLI with no third-party dependencies.
- Global `AGENTS.md` profiles that tell Codex when and how to use the memory store.
- Global `CLAUDE.md` profiles that tell Claude Code when and how to use the memory store.
- Separate `skills-codex/` and `skills-claude/` trees so each agent resolves its own global paths.
- A cross-platform npm installer for Codex and Claude Code on Windows, macOS, and Linux.

## Quick Install

After the package is published to npm:

Install the default LITE mode into both Codex and Claude Code:

```bash
npx memory-state-codex
```

Install PLUS mode into both Codex and Claude Code:

```bash
npx memory-state-codex --plus
```

Install only one provider:

```bash
npx memory-state-codex --provider codex
npx memory-state-codex --provider claude
npx memory-state-codex --plus --provider claude
```

The installer resolves the Codex home directory in this order:

1. `--codex-home <path>` if passed.
2. `CODEX_HOME` if set.
3. `~/.codex`.

It resolves the Claude Code home directory in this order:

1. `--claude-home <path>` if passed.
2. `CLAUDE_HOME` if set.
3. `~/.claude`.

It installs:

- `AGENTS-LITE.md` or `AGENTS-PLUS.md` instructions into the global Codex `AGENTS.md`.
- `skills-codex/curated-memory` or `skills-codex/curated-memory-plus` into the global Codex skills directory.
- `CLAUDE-LITE.md` or `CLAUDE-PLUS.md` instructions into the global Claude Code `CLAUDE.md`.
- `skills-claude/curated-memory` or `skills-claude/curated-memory-plus` into the global Claude Code skills directory.
- `memories/memory_state.db` into each selected provider's memories directory, only if no database exists yet.

The installer is idempotent. It replaces the managed memory block in `AGENTS.md` and/or `CLAUDE.md`, refreshes selected provider skill files, and leaves existing memory databases untouched unless `--force-db` is used.

```bash
npx memory-state-codex --provider both
npx memory-state-codex --codex-home ~/.codex
npx memory-state-codex --claude-home ~/.claude
npx memory-state-codex --provider codex --codex-home ~/.codex
npx memory-state-codex --provider claude --claude-home ~/.claude
npx memory-state-codex --plus
npx memory-state-codex --dry-run
npx memory-state-codex --force-db
```

On Windows PowerShell:

```powershell
npx memory-state-codex
npx memory-state-codex --codex-home "$HOME\.codex"
npx memory-state-codex --claude-home "$HOME\.claude"
npx memory-state-codex --provider codex
npx memory-state-codex --provider claude
```

## Repository Layout

```text
.
|-- AGENTS-LITE.md
|-- AGENTS-PLUS.md
|-- CLAUDE-LITE.md
|-- CLAUDE-PLUS.md
|-- LICENSE
|-- README.md
|-- package.json
|-- bin/
|   `-- install.js
|-- memories/
|   |-- README.md
|   `-- memory_state.db
|-- skills-codex/
|   |-- curated-memory/
|   |   |-- SKILL.md
|   |   |-- agents/
|   |   |   `-- openai.yaml
|   |   `-- scripts/
|   |       `-- memory.py
|   `-- curated-memory-plus/
|       |-- SKILL.md
|       |-- agents/
|       |   `-- openai.yaml
|       `-- scripts/
|           `-- memory.py
`-- skills-claude/
    |-- curated-memory/
    |   |-- SKILL.md
    |   |-- agents/
    |   |   `-- openai.yaml
    |   `-- scripts/
    |       `-- memory.py
    `-- curated-memory-plus/
        |-- SKILL.md
        |-- agents/
        |   `-- openai.yaml
        `-- scripts/
            `-- memory.py
```

## Manual Install For Codex

Pick your Codex home directory:

- If `CODEX_HOME` is set, use that.
- Otherwise use `~/.codex` on macOS/Linux.
- On Windows, `~` usually resolves to `%USERPROFILE%`, so the default is `%USERPROFILE%\.codex`.

### PowerShell

```powershell
$codexHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $HOME ".codex" }
New-Item -ItemType Directory -Force -Path $codexHome | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $codexHome "skills") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $codexHome "memories") | Out-Null

Copy-Item .\AGENTS-LITE.md (Join-Path $codexHome "AGENTS.md") -Force
Copy-Item .\skills-codex\curated-memory (Join-Path $codexHome "skills\curated-memory") -Recurse -Force
Copy-Item .\memories\memory_state.db (Join-Path $codexHome "memories\memory_state.db") -Force
```

### macOS/Linux

```bash
CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
mkdir -p "$CODEX_HOME/skills" "$CODEX_HOME/memories"

cp AGENTS-LITE.md "$CODEX_HOME/AGENTS.md"
cp -R skills-codex/curated-memory "$CODEX_HOME/skills/curated-memory"
cp memories/memory_state.db "$CODEX_HOME/memories/memory_state.db"
```

You can skip copying `memory_state.db` and run `init`; the CLI will create the same schema.

For PLUS manual install, copy `AGENTS-PLUS.md` to `AGENTS.md` and copy `skills-codex/curated-memory-plus` instead.

## Manual Install For Claude Code

Pick your Claude home directory:

- If `CLAUDE_HOME` is set, use that.
- Otherwise use `~/.claude` on macOS/Linux.
- On Windows, `~` usually resolves to `%USERPROFILE%`, so the default is `%USERPROFILE%\.claude`.

### PowerShell

```powershell
$claudeHome = if ($env:CLAUDE_HOME) { $env:CLAUDE_HOME } else { Join-Path $HOME ".claude" }
New-Item -ItemType Directory -Force -Path $claudeHome | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $claudeHome "skills") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $claudeHome "memories") | Out-Null

Copy-Item .\CLAUDE-LITE.md (Join-Path $claudeHome "CLAUDE.md") -Force
Copy-Item .\skills-claude\curated-memory (Join-Path $claudeHome "skills\curated-memory") -Recurse -Force
Copy-Item .\memories\memory_state.db (Join-Path $claudeHome "memories\memory_state.db") -Force
```

### macOS/Linux

```bash
CLAUDE_HOME="${CLAUDE_HOME:-$HOME/.claude}"
mkdir -p "$CLAUDE_HOME/skills" "$CLAUDE_HOME/memories"

cp CLAUDE-LITE.md "$CLAUDE_HOME/CLAUDE.md"
cp -R skills-claude/curated-memory "$CLAUDE_HOME/skills/curated-memory"
cp memories/memory_state.db "$CLAUDE_HOME/memories/memory_state.db"
```

For PLUS manual install, copy `CLAUDE-PLUS.md` to `CLAUDE.md` and copy `skills-claude/curated-memory-plus` instead.

## Initialize Or Repair

```bash
python ~/.codex/skills/curated-memory/scripts/memory.py init
```

You can override the database location:

```bash
CODEX_MEMORY_DB=/path/to/memory_state.db python ~/.codex/skills/curated-memory/scripts/memory.py init
```

For Claude Code, use `CLAUDE_MEMORY_DB` and the equivalent `~/.claude/skills/...` script path.

## Common Commands

Remember a project-specific decision:

```bash
python ~/.codex/skills/curated-memory/scripts/memory.py remember \
  --scope project \
  --project-path "/path/to/project" \
  --kind decision \
  --key "api-error-envelope" \
  --content "API routes return errors as { data: null, error: { code, message } }." \
  --confidence 1.0
```

Search project memory, including global memory by default:

```bash
python ~/.codex/skills/curated-memory/scripts/memory.py search \
  "api envelope" \
  --scope project \
  --project-path "/path/to/project"
```

Search by substring:

```bash
python ~/.codex/skills/curated-memory/scripts/memory.py search \
  "velope" \
  --scope project \
  --project-path "/path/to/project" \
  --substring
```

List memories:

```bash
python ~/.codex/skills/curated-memory/scripts/memory.py list \
  --scope project \
  --project-path "/path/to/project"
```

Forget a memory:

```bash
python ~/.codex/skills/curated-memory/scripts/memory.py forget --id "mem_..."
```

Inspect the database:

```bash
python ~/.codex/skills/curated-memory/scripts/memory.py inspect
```

## Search Strategy

The CLI searches in this order:

1. FTS5 `unicode61` for normal word-based full-text search.
2. FTS5 `trigram` as a complement or fallback, and first when `--substring` is used.
3. SQL `LIKE` as the final fallback.

Results include `match_type`, which can be `fulltext`, `trigram`, or `like`.

Search returns `confidence` for `memory_items` and uses it to promote reliable memories after textual rank. For `LIKE` fallback matches, confidence is the primary ordering signal before recency.

In PLUS mode, `--include-messages` searches `messages` through `sessions` and applies project filters through `sessions.project_path`, so message history can scale by repository instead of searching every saved message globally.

Both LITE and PLUS enable query retries by default. If the original natural-language query returns no results, the CLI retries with derived significant terms up to `--max-retries` (default `5`) and returns a `search_attempts` audit list. Disable this with `--no-retry-queries`.

The AGENTS and CLAUDE profiles add a second semantic retry layer for the AI agent. If deterministic retries return no useful context, the agent should run up to 3 additional searches with rewritten queries based on synonyms, project-specific nouns, filenames, feature names, API names, session titles in PLUS, or broader concepts from the user's request.

## Data Model

- `memory_items`: curated durable memories.
- `memory_events`: audit trail for memory creation, updates, and deletion.
- `sessions`: optional session metadata.
- `messages`: optional message traceability.
- `messages_fts` and `memory_items_fts`: normal FTS5 indexes.
- `messages_fts_trigram` and `memory_items_fts_trigram`: substring-oriented indexes.
- `state_meta`: schema metadata.

The LITE workflow stores curated memories directly in `memory_items`. Session and message logging is optional.

The PLUS workflow requires `start-session`, `add-message`, and `end-session` for substantive work. In PLUS mode, `remember` requires `--session-id`; `--message-id` is verified against that session when provided. Use `--allow-unlinked` only for exceptional imported/global memories that genuinely have no session provenance.

Use `--confidence` when storing memory:

- `1.0`: directly verified fact, explicit user preference, or confirmed project contract.
- `0.8`: reliable working conclusion from completed work.
- `0.5`: reasonable inference that has not been directly verified.
- `0.2`: weak/provisional note that should be treated cautiously.

Prefer `0.8` when unsure. Use values below `0.8` only when the memory text clearly signals uncertainty.

PLUS message logging supports `--relevance`:

- `0`: routine message with little future value.
- `1`: useful context.
- `2`: important implementation detail, user preference, or tool result.
- `3`: key decision, final session summary, verification result, or memory provenance anchor.

Message search returns `relevance` and uses it to promote important messages after textual rank. For `LIKE` fallback matches, relevance is the primary ordering signal before recency.

## Privacy

Do not store secrets, credentials, tokens, API keys, cookies, raw `.env` values, or unnecessary personal data. This system is intended for durable working context, not private secret storage.

## Requirements

- Node.js 18 or newer for the npm installer.
- Python 3.10 or newer for the memory CLI.
- SQLite with FTS5. Trigram FTS is optional; the CLI falls back gracefully if unavailable.

## Publishing To npm

1. Create or log into an npm account.
2. Run `npm login`.
3. Check the package contents with `npm pack --dry-run`.
4. Publish with `npm publish --access public`.

If the package name `memory-state-codex` is already taken, change `name` in `package.json` before publishing, for example to a scoped name such as `@your-npm-user/memory-state-codex`.
