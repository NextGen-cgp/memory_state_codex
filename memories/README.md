# Empty Memory Database Template

`memory_state.db` is an empty SQLite database with the curated-memory schema already initialized.

It contains tables and FTS indexes, but no memories, messages, or sessions.

To install it, copy it to your Codex memories directory:

```bash
mkdir -p ~/.codex/memories
cp memories/memory_state.db ~/.codex/memories/memory_state.db
```

On Windows PowerShell:

```powershell
$codexHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $HOME ".codex" }
New-Item -ItemType Directory -Force -Path (Join-Path $codexHome "memories") | Out-Null
Copy-Item .\memories\memory_state.db (Join-Path $codexHome "memories\memory_state.db") -Force
```

You may also skip this file and let the CLI create or repair the database:

```bash
python ~/.codex/skills/curated-memory/scripts/memory.py init
```
