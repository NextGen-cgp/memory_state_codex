#!/usr/bin/env python3
"""Curated persistent memory for Claude Code."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sqlite3
import sys
import uuid
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "1"
STOP_WORDS = {
    "a",
    "al",
    "and",
    "are",
    "as",
    "con",
    "de",
    "del",
    "el",
    "en",
    "for",
    "he",
    "in",
    "is",
    "la",
    "las",
    "lo",
    "los",
    "me",
    "mi",
    "mis",
    "of",
    "on",
    "or",
    "por",
    "project",
    "proyecto",
    "que",
    "the",
    "to",
    "un",
    "una",
    "y",
}


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def default_db_path() -> Path:
    override = os.environ.get("CLAUDE_MEMORY_DB")
    if override:
        return Path(override).expanduser()

    claude_home = os.environ.get("CLAUDE_HOME")
    base = Path(claude_home).expanduser() if claude_home else Path.home() / ".claude"
    return base / "memories" / "memory_state.db"


def project_path(value: str | None, scope: str | None = None) -> str | None:
    if scope and scope != "project":
        return None
    path = Path(value).expanduser() if value else Path.cwd()
    return str(path.resolve())


def read_json(value: str | None, field: str) -> str | None:
    if not value:
        return None
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"{field} must be valid JSON: {exc}") from exc
    return json.dumps(parsed, ensure_ascii=True, sort_keys=True)


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("PRAGMA journal_mode = WAL")
    return con


def init_db(con: sqlite3.Connection) -> dict[str, Any]:
    con.executescript(
        """
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            source TEXT NOT NULL DEFAULT 'claude',
            model TEXT,
            project_path TEXT,
            started_at TEXT NOT NULL,
            ended_at TEXT,
            title TEXT,
            parent_session_id TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            input_tokens INTEGER NOT NULL DEFAULT 0,
            output_tokens INTEGER NOT NULL DEFAULT 0,
            cost_usd REAL NOT NULL DEFAULT 0,
            metadata_json TEXT,
            FOREIGN KEY(parent_session_id) REFERENCES sessions(id)
        );

        CREATE INDEX IF NOT EXISTS idx_sessions_project_started
            ON sessions(project_path, started_at DESC);

        CREATE INDEX IF NOT EXISTS idx_sessions_project_id
            ON sessions(project_path, id);

        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            tool_name TEXT,
            tool_calls_json TEXT,
            reasoning TEXT,
            relevance INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            metadata_json TEXT,
            FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_messages_session_created
            ON messages(session_id, created_at);

        CREATE INDEX IF NOT EXISTS idx_messages_session_relevance_created
            ON messages(session_id, relevance DESC, created_at DESC);

        CREATE TABLE IF NOT EXISTS memory_items (
            id TEXT PRIMARY KEY,
            scope TEXT NOT NULL CHECK(scope IN ('global', 'project', 'user')),
            project_path TEXT,
            kind TEXT NOT NULL DEFAULT 'fact',
            key TEXT,
            content TEXT NOT NULL,
            confidence REAL NOT NULL DEFAULT 0.8,
            status TEXT NOT NULL DEFAULT 'active'
                CHECK(status IN ('active', 'superseded', 'deleted')),
            source_session_id TEXT,
            source_message_id TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            last_used_at TEXT,
            metadata_json TEXT,
            FOREIGN KEY(source_session_id) REFERENCES sessions(id) ON DELETE SET NULL,
            FOREIGN KEY(source_message_id) REFERENCES messages(id) ON DELETE SET NULL
        );

        CREATE UNIQUE INDEX IF NOT EXISTS idx_memory_key
            ON memory_items(scope, COALESCE(project_path, ''), key)
            WHERE key IS NOT NULL;

        CREATE INDEX IF NOT EXISTS idx_memory_scope_project_status
            ON memory_items(scope, project_path, status, updated_at DESC);

        CREATE TABLE IF NOT EXISTS memory_events (
            id TEXT PRIMARY KEY,
            memory_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            detail TEXT,
            session_id TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(memory_id) REFERENCES memory_items(id) ON DELETE CASCADE,
            FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE SET NULL
        );

        CREATE INDEX IF NOT EXISTS idx_memory_events_memory_created
            ON memory_events(memory_id, created_at);

        CREATE TABLE IF NOT EXISTS state_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
            message_id UNINDEXED,
            session_id UNINDEXED,
            role UNINDEXED,
            content,
            reasoning,
            tokenize='unicode61'
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS memory_items_fts USING fts5(
            memory_id UNINDEXED,
            scope UNINDEXED,
            project_path UNINDEXED,
            kind UNINDEXED,
            key,
            content,
            tokenize='unicode61'
        );
        """
    )
    trigram_enabled = True
    try:
        con.executescript(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts_trigram USING fts5(
                message_id UNINDEXED,
                session_id UNINDEXED,
                content,
                tokenize='trigram'
            );

            CREATE VIRTUAL TABLE IF NOT EXISTS memory_items_fts_trigram USING fts5(
                memory_id UNINDEXED,
                scope UNINDEXED,
                project_path UNINDEXED,
                content,
                tokenize='trigram'
            );
            """
        )
    except sqlite3.OperationalError:
        trigram_enabled = False

    con.execute(
        """
        INSERT INTO state_meta(key, value, updated_at)
        VALUES('schema_version', ?, ?)
        ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at
        """,
        (SCHEMA_VERSION, now()),
    )
    con.commit()
    return {"schema_version": SCHEMA_VERSION, "trigram_enabled": trigram_enabled}


def emit(payload: Any) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {key: row[key] for key in row.keys()}


def ensure_initialized(con: sqlite3.Connection) -> None:
    init_db(con)


def start_session(args: argparse.Namespace, con: sqlite3.Connection) -> None:
    ensure_initialized(con)
    session_id = args.id or new_id("ses")
    ts = now()
    con.execute(
        """
        INSERT INTO sessions(
            id, source, model, project_path, started_at, title,
            parent_session_id, metadata_json
        )
        VALUES(?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            session_id,
            args.source,
            args.model,
            project_path(args.project_path, "project"),
            ts,
            args.title,
            args.parent_session_id,
            read_json(args.metadata_json, "--metadata-json"),
        ),
    )
    con.commit()
    emit({"id": session_id, "started_at": ts})


def end_session(args: argparse.Namespace, con: sqlite3.Connection) -> None:
    ensure_initialized(con)
    ts = now()
    cur = con.execute(
        """
        UPDATE sessions
        SET ended_at = ?, status = 'ended',
            input_tokens = COALESCE(?, input_tokens),
            output_tokens = COALESCE(?, output_tokens),
            cost_usd = COALESCE(?, cost_usd)
        WHERE id = ?
        """,
        (ts, args.input_tokens, args.output_tokens, args.cost_usd, args.session_id),
    )
    con.commit()
    emit({"updated": cur.rowcount, "ended_at": ts})


def add_message(args: argparse.Namespace, con: sqlite3.Connection) -> None:
    ensure_initialized(con)
    message_id = args.id or new_id("msg")
    ts = now()
    tool_calls_json = read_json(args.tool_calls_json, "--tool-calls-json")
    metadata_json = read_json(args.metadata_json, "--metadata-json")
    con.execute(
        """
        INSERT INTO messages(
            id, session_id, role, content, tool_name, tool_calls_json,
            reasoning, relevance, created_at, metadata_json
        )
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            message_id,
            args.session_id,
            args.role,
            args.content,
            args.tool_name,
            tool_calls_json,
            args.reasoning,
            args.relevance,
            ts,
            metadata_json,
        ),
    )
    con.execute(
        """
        INSERT INTO messages_fts(message_id, session_id, role, content, reasoning)
        VALUES(?, ?, ?, ?, ?)
        """,
        (message_id, args.session_id, args.role, args.content, args.reasoning),
    )
    insert_optional_fts(
        con,
        "messages_fts_trigram",
        "message_id, session_id, content",
        (message_id, args.session_id, args.content),
    )
    con.commit()
    emit({"id": message_id, "created_at": ts})


def insert_optional_fts(
    con: sqlite3.Connection, table: str, columns: str, values: tuple[Any, ...]
) -> None:
    placeholders = ", ".join("?" for _ in values)
    try:
        con.execute(f"INSERT INTO {table}({columns}) VALUES({placeholders})", values)
    except sqlite3.OperationalError:
        return


def remember(args: argparse.Namespace, con: sqlite3.Connection) -> None:
    ensure_initialized(con)
    validate_memory_provenance(args, con)
    ts = now()
    scope = args.scope
    ppath = project_path(args.project_path, scope)
    metadata_json = read_json(args.metadata_json, "--metadata-json")

    existing = None
    if args.key:
        existing = con.execute(
            """
            SELECT * FROM memory_items
            WHERE scope = ? AND COALESCE(project_path, '') = COALESCE(?, '') AND key = ?
            """,
            (scope, ppath, args.key),
        ).fetchone()

    if existing:
        memory_id = existing["id"]
        con.execute(
            """
            UPDATE memory_items
            SET kind = ?, content = ?, confidence = ?, status = 'active',
                source_session_id = COALESCE(?, source_session_id),
                source_message_id = COALESCE(?, source_message_id),
                updated_at = ?, metadata_json = COALESCE(?, metadata_json)
            WHERE id = ?
            """,
            (
                args.kind,
                args.content,
                args.confidence,
                args.session_id,
                args.message_id,
                ts,
                metadata_json,
                memory_id,
            ),
        )
        event_type = "updated"
    else:
        memory_id = args.id or new_id("mem")
        con.execute(
            """
            INSERT INTO memory_items(
                id, scope, project_path, kind, key, content, confidence,
                status, source_session_id, source_message_id, created_at,
                updated_at, metadata_json
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?, ?, ?)
            """,
            (
                memory_id,
                scope,
                ppath,
                args.kind,
                args.key,
                args.content,
                args.confidence,
                args.session_id,
                args.message_id,
                ts,
                ts,
                metadata_json,
            ),
        )
        event_type = "created"

    refresh_memory_fts(con, memory_id)
    con.execute(
        """
        INSERT INTO memory_events(id, memory_id, event_type, detail, session_id, created_at)
        VALUES(?, ?, ?, ?, ?, ?)
        """,
        (new_id("evt"), memory_id, event_type, args.event_detail, args.session_id, ts),
    )
    con.commit()
    emit({"id": memory_id, "event": event_type, "updated_at": ts})


def validate_memory_provenance(args: argparse.Namespace, con: sqlite3.Connection) -> None:
    if args.allow_unlinked:
        return

    if not args.session_id:
        raise SystemExit(
            "curated-memory-plus requires --session-id for remember. "
            "Use --allow-unlinked only for exceptional imported/global memories."
        )

    session = con.execute(
        "SELECT id FROM sessions WHERE id = ?",
        (args.session_id,),
    ).fetchone()
    if not session:
        raise SystemExit(f"session not found for --session-id: {args.session_id}")

    if args.message_id:
        message = con.execute(
            "SELECT id FROM messages WHERE id = ? AND session_id = ?",
            (args.message_id, args.session_id),
        ).fetchone()
        if not message:
            raise SystemExit(
                "--message-id must reference a message that belongs to --session-id"
            )


def refresh_memory_fts(con: sqlite3.Connection, memory_id: str) -> None:
    row = con.execute("SELECT * FROM memory_items WHERE id = ?", (memory_id,)).fetchone()
    if not row:
        return
    con.execute("DELETE FROM memory_items_fts WHERE memory_id = ?", (memory_id,))
    try:
        con.execute("DELETE FROM memory_items_fts_trigram WHERE memory_id = ?", (memory_id,))
    except sqlite3.OperationalError:
        pass
    if row["status"] != "active":
        return
    con.execute(
        """
        INSERT INTO memory_items_fts(memory_id, scope, project_path, kind, key, content)
        VALUES(?, ?, ?, ?, ?, ?)
        """,
        (
            row["id"],
            row["scope"],
            row["project_path"],
            row["kind"],
            row["key"],
            row["content"],
        ),
    )
    insert_optional_fts(
        con,
        "memory_items_fts_trigram",
        "memory_id, scope, project_path, content",
        (row["id"], row["scope"], row["project_path"], row["content"]),
    )


def list_memory(args: argparse.Namespace, con: sqlite3.Connection) -> None:
    ensure_initialized(con)
    filters = ["status = ?"]
    values: list[Any] = [args.status]
    if args.scope:
        filters.append("scope = ?")
        values.append(args.scope)
    if args.project_path or args.scope == "project":
        filters.append("project_path = ?")
        values.append(project_path(args.project_path, "project"))
    sql = f"""
        SELECT id, scope, project_path, kind, key, content, confidence,
               status, updated_at, last_used_at
        FROM memory_items
        WHERE {' AND '.join(filters)}
        ORDER BY updated_at DESC
        LIMIT ?
    """
    values.append(args.limit)
    rows = [row_to_dict(row) for row in con.execute(sql, values)]
    emit({"items": rows})


def search(args: argparse.Namespace, con: sqlite3.Connection) -> None:
    ensure_initialized(con)
    ppath = (
        project_path(args.project_path, "project")
        if args.project_path or args.scope == "project"
        else None
    )
    attempts = build_query_attempts(args.query, args.max_retries if args.retry_queries else 0)
    memories: list[dict[str, Any]] = []
    messages: list[dict[str, Any]] = []
    used_attempts: list[dict[str, Any]] = []

    for index, attempt in enumerate(attempts, start=1):
        attempt_memories = search_memory(
            con,
            attempt,
            args.limit,
            args.scope,
            ppath,
            args.include_global,
            args.substring,
            args.trigram,
        )
        attempt_messages: list[dict[str, Any]] = []
        if args.include_messages:
            attempt_messages = search_messages(
                con,
                attempt,
                args.limit,
                args.scope,
                ppath,
                args.include_global,
                args.substring,
                args.trigram,
            )
        used_attempts.append(
            {
                "index": index,
                "query": attempt,
                "memory_items": len(attempt_memories),
                "messages": len(attempt_messages),
            }
        )
        memories = merge_results(memories, attempt_memories, args.limit)
        messages = merge_results(messages, attempt_messages, args.limit)
        if memories or messages:
            break

    ts = now()
    for item in memories:
        con.execute("UPDATE memory_items SET last_used_at = ? WHERE id = ?", (ts, item["id"]))
    con.commit()
    emit({"memory_items": memories, "messages": messages, "search_attempts": used_attempts})


def build_query_attempts(query: str, max_retries: int) -> list[str]:
    attempts = [query]
    if max_retries <= 0:
        return attempts

    terms = extract_query_terms(query)
    candidates: list[str] = []
    if terms:
        candidates.extend(terms)
        if len(terms) > 1:
            candidates.append(" OR ".join(terms))

    for candidate in candidates:
        if candidate not in attempts:
            attempts.append(candidate)
        if len(attempts) >= max_retries + 1:
            break
    return attempts


def extract_query_terms(query: str) -> list[str]:
    raw_terms = re.findall(r"[\w.-]+", query, flags=re.UNICODE)
    terms: list[str] = []
    for term in raw_terms:
        normalized = term.strip("_-.").lower()
        if len(normalized) < 3 or normalized in STOP_WORDS:
            continue
        if normalized not in terms:
            terms.append(normalized)
    terms.sort(key=len, reverse=True)
    return terms


def search_memory(
    con: sqlite3.Connection,
    query: str,
    limit: int,
    scope: str | None,
    ppath: str | None,
    include_global: bool,
    substring: bool,
    trigram: bool,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    if not substring:
        results = fulltext_search_memory(con, query, limit, scope, ppath, include_global)

    if trigram and should_try_trigram(query) and (substring or len(results) < limit):
        results = merge_results(
            results,
            trigram_search_memory(con, query, limit, scope, ppath, include_global),
            limit,
        )

    if len(results) < limit:
        results = merge_results(
            results,
            like_search_memory(con, query, limit, scope, ppath, include_global),
            limit,
        )
    return results


def should_try_trigram(query: str) -> bool:
    compact = "".join(ch for ch in query if not ch.isspace())
    return len(compact) >= 3


def merge_results(
    current: list[dict[str, Any]],
    extra: list[dict[str, Any]],
    limit: int,
) -> list[dict[str, Any]]:
    seen = {item["id"] for item in current}
    merged = list(current)
    for item in extra:
        if item["id"] in seen:
            continue
        seen.add(item["id"])
        merged.append(item)
        if len(merged) >= limit:
            break
    return merged


def memory_filter_sql(
    alias: str,
    scope: str | None,
    ppath: str | None,
    include_global: bool,
) -> tuple[str, list[Any]]:
    filters = [f"{alias}.status = 'active'"]
    values: list[Any] = []
    if scope:
        if scope == "project" and include_global and ppath:
            filters.append(f"({alias}.scope = 'project' OR {alias}.scope = 'global')")
        else:
            filters.append(f"{alias}.scope = ?")
            values.append(scope)
    if ppath:
        if include_global and scope != "global":
            filters.append(f"({alias}.project_path = ? OR {alias}.scope = 'global')")
        else:
            filters.append(f"{alias}.project_path = ?")
        values.append(ppath)
    return " AND ".join(filters), values


def fulltext_search_memory(
    con: sqlite3.Connection,
    query: str,
    limit: int,
    scope: str | None,
    ppath: str | None,
    include_global: bool,
) -> list[dict[str, Any]]:
    filter_sql, filter_values = memory_filter_sql("m", scope, ppath, include_global)
    values: list[Any] = [query, *filter_values, limit]
    sql = f"""
        SELECT m.id, m.scope, m.project_path, m.kind, m.key, m.content,
               m.confidence, m.updated_at, bm25(memory_items_fts) AS rank,
               'fulltext' AS match_type
        FROM memory_items_fts
        JOIN memory_items m ON m.id = memory_items_fts.memory_id
        WHERE memory_items_fts MATCH ? AND {filter_sql}
        ORDER BY rank, m.confidence DESC, m.updated_at DESC
        LIMIT ?
    """
    try:
        return [row_to_dict(row) for row in con.execute(sql, values)]
    except sqlite3.OperationalError:
        return []


def trigram_search_memory(
    con: sqlite3.Connection,
    query: str,
    limit: int,
    scope: str | None,
    ppath: str | None,
    include_global: bool,
) -> list[dict[str, Any]]:
    filter_sql, filter_values = memory_filter_sql("m", scope, ppath, include_global)
    values: list[Any] = [query, *filter_values, limit]
    sql = f"""
        SELECT m.id, m.scope, m.project_path, m.kind, m.key, m.content,
               m.confidence, m.updated_at, bm25(memory_items_fts_trigram) AS rank,
               'trigram' AS match_type
        FROM memory_items_fts_trigram
        JOIN memory_items m ON m.id = memory_items_fts_trigram.memory_id
        WHERE memory_items_fts_trigram MATCH ? AND {filter_sql}
        ORDER BY rank, m.confidence DESC, m.updated_at DESC
        LIMIT ?
    """
    try:
        return [row_to_dict(row) for row in con.execute(sql, values)]
    except sqlite3.OperationalError:
        return []


def like_search_memory(
    con: sqlite3.Connection,
    query: str,
    limit: int,
    scope: str | None,
    ppath: str | None,
    include_global: bool,
) -> list[dict[str, Any]]:
    filters = ["status = 'active'", "(content LIKE ? OR key LIKE ?)"]
    pattern = f"%{query}%"
    values: list[Any] = [pattern, pattern]
    if scope:
        if scope == "project" and include_global and ppath:
            filters.append("(scope = 'project' OR scope = 'global')")
        else:
            filters.append("scope = ?")
            values.append(scope)
    if ppath:
        if include_global and scope != "global":
            filters.append("(project_path = ? OR scope = 'global')")
        else:
            filters.append("project_path = ?")
        values.append(ppath)
    values.append(limit)
    rows = con.execute(
        f"""
        SELECT id, scope, project_path, kind, key, content,
               confidence, updated_at, 0 AS rank, 'like' AS match_type
        FROM memory_items
        WHERE {' AND '.join(filters)}
        ORDER BY confidence DESC, updated_at DESC
        LIMIT ?
        """,
        values,
    )
    return [row_to_dict(row) for row in rows]


def search_messages(
    con: sqlite3.Connection,
    query: str,
    limit: int,
    scope: str | None,
    ppath: str | None,
    include_global: bool,
    substring: bool,
    trigram: bool,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    if not substring:
        results = fulltext_search_messages(con, query, limit, scope, ppath, include_global)
    if trigram and should_try_trigram(query) and (substring or len(results) < limit):
        results = merge_results(
            results,
            trigram_search_messages(con, query, limit, scope, ppath, include_global),
            limit,
        )
    if len(results) < limit:
        results = merge_results(
            results,
            like_search_messages(con, query, limit, scope, ppath, include_global),
            limit,
        )
    return results


def message_filter_sql(
    scope: str | None,
    ppath: str | None,
    include_global: bool,
) -> tuple[str, list[Any]]:
    filters: list[str] = []
    values: list[Any] = []
    if scope == "global":
        filters.append("s.project_path IS NULL")
    elif ppath:
        if include_global:
            filters.append("(s.project_path = ? OR s.project_path IS NULL)")
        else:
            filters.append("s.project_path = ?")
        values.append(ppath)
    return (" AND ".join(filters) if filters else "1 = 1"), values


def fulltext_search_messages(
    con: sqlite3.Connection,
    query: str,
    limit: int,
    scope: str | None,
    ppath: str | None,
    include_global: bool,
) -> list[dict[str, Any]]:
    filter_sql, filter_values = message_filter_sql(scope, ppath, include_global)
    values: list[Any] = [query, *filter_values, limit]
    try:
        rows = con.execute(
            f"""
            SELECT msg.id, msg.session_id, s.title AS session_title,
                   s.project_path, msg.role, msg.content, msg.relevance, msg.created_at,
                   bm25(messages_fts) AS rank, 'fulltext' AS match_type
            FROM messages_fts
            JOIN messages msg ON msg.id = messages_fts.message_id
            JOIN sessions s ON s.id = msg.session_id
            WHERE messages_fts MATCH ? AND {filter_sql}
            ORDER BY rank, msg.relevance DESC, msg.created_at DESC
            LIMIT ?
            """,
            values,
        )
        return [row_to_dict(row) for row in rows]
    except sqlite3.OperationalError:
        return []


def trigram_search_messages(
    con: sqlite3.Connection,
    query: str,
    limit: int,
    scope: str | None,
    ppath: str | None,
    include_global: bool,
) -> list[dict[str, Any]]:
    filter_sql, filter_values = message_filter_sql(scope, ppath, include_global)
    values: list[Any] = [query, *filter_values, limit]
    try:
        rows = con.execute(
            f"""
            SELECT msg.id, msg.session_id, s.title AS session_title,
                   s.project_path, msg.role, msg.content, msg.relevance, msg.created_at,
                   bm25(messages_fts_trigram) AS rank, 'trigram' AS match_type
            FROM messages_fts_trigram
            JOIN messages msg ON msg.id = messages_fts_trigram.message_id
            JOIN sessions s ON s.id = msg.session_id
            WHERE messages_fts_trigram MATCH ? AND {filter_sql}
            ORDER BY rank, msg.relevance DESC, msg.created_at DESC
            LIMIT ?
            """,
            values,
        )
        return [row_to_dict(row) for row in rows]
    except sqlite3.OperationalError:
        return []


def like_search_messages(
    con: sqlite3.Connection,
    query: str,
    limit: int,
    scope: str | None,
    ppath: str | None,
    include_global: bool,
) -> list[dict[str, Any]]:
    filter_sql, filter_values = message_filter_sql(scope, ppath, include_global)
    values: list[Any] = [f"%{query}%", *filter_values, limit]
    rows = con.execute(
        f"""
        SELECT msg.id, msg.session_id, s.title AS session_title,
               s.project_path, msg.role, msg.content, msg.relevance, msg.created_at,
               0 AS rank, 'like' AS match_type
        FROM messages msg
        JOIN sessions s ON s.id = msg.session_id
        WHERE msg.content LIKE ? AND {filter_sql}
        ORDER BY msg.relevance DESC, msg.created_at DESC
        LIMIT ?
        """,
        values,
    )
    return [row_to_dict(row) for row in rows]


def forget(args: argparse.Namespace, con: sqlite3.Connection) -> None:
    ensure_initialized(con)
    if not args.id and not args.key:
        raise SystemExit("forget requires --id or --key")
    ts = now()
    values: list[Any]
    if args.id:
        where = "id = ?"
        values = [args.id]
    else:
        where = "scope = ? AND COALESCE(project_path, '') = COALESCE(?, '') AND key = ?"
        values = [args.scope, project_path(args.project_path, args.scope), args.key]
    rows = con.execute(f"SELECT id FROM memory_items WHERE {where}", values).fetchall()
    for row in rows:
        memory_id = row["id"]
        con.execute(
            "UPDATE memory_items SET status = 'deleted', updated_at = ? WHERE id = ?",
            (ts, memory_id),
        )
        refresh_memory_fts(con, memory_id)
        con.execute(
            """
            INSERT INTO memory_events(id, memory_id, event_type, detail, session_id, created_at)
            VALUES(?, ?, 'deleted', ?, ?, ?)
            """,
            (new_id("evt"), memory_id, args.reason, args.session_id, ts),
        )
    con.commit()
    emit({"deleted": len(rows), "updated_at": ts})


def inspect_db(args: argparse.Namespace, con: sqlite3.Connection) -> None:
    ensure_initialized(con)
    tables = [
        row["name"]
        for row in con.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type IN ('table', 'view') AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        )
    ]
    counts = {}
    for table in ("sessions", "messages", "memory_items", "memory_events"):
        counts[table] = con.execute(f"SELECT COUNT(*) AS c FROM {table}").fetchone()["c"]
    emit({"db_path": str(args.db), "tables": tables, "counts": counts})


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Claude Code curated memory store")
    parser.add_argument("--db", type=Path, default=default_db_path())
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init")
    sub.add_parser("inspect")

    p = sub.add_parser("start-session")
    p.add_argument("--id")
    p.add_argument("--source", default="claude")
    p.add_argument("--model")
    p.add_argument("--title")
    p.add_argument("--project-path")
    p.add_argument("--parent-session-id")
    p.add_argument("--metadata-json")

    p = sub.add_parser("end-session")
    p.add_argument("session_id")
    p.add_argument("--input-tokens", type=int)
    p.add_argument("--output-tokens", type=int)
    p.add_argument("--cost-usd", type=float)

    p = sub.add_parser("add-message")
    p.add_argument("--id")
    p.add_argument("--session-id", required=True)
    p.add_argument("--role", required=True, choices=["system", "user", "assistant", "tool"])
    p.add_argument("--content", required=True)
    p.add_argument("--tool-name")
    p.add_argument("--tool-calls-json")
    p.add_argument("--reasoning")
    p.add_argument("--relevance", type=int, default=0)
    p.add_argument("--metadata-json")

    p = sub.add_parser("remember")
    p.add_argument("--id")
    p.add_argument("--scope", default="project", choices=["global", "project", "user"])
    p.add_argument("--project-path")
    p.add_argument("--kind", default="fact")
    p.add_argument("--key")
    p.add_argument("--content", required=True)
    p.add_argument("--confidence", type=float, default=0.8)
    p.add_argument("--session-id")
    p.add_argument("--message-id")
    p.add_argument(
        "--allow-unlinked",
        action="store_true",
        help="Allow remember without --session-id for exceptional imported/global memories.",
    )
    p.add_argument("--metadata-json")
    p.add_argument("--event-detail")

    p = sub.add_parser("search")
    p.add_argument("query")
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--scope", choices=["global", "project", "user"])
    p.add_argument("--project-path")
    p.add_argument("--include-global", action="store_true", default=True)
    p.add_argument("--no-include-global", dest="include_global", action="store_false")
    p.add_argument("--include-messages", action="store_true")
    p.add_argument(
        "--substring",
        action="store_true",
        help="Prefer trigram substring search before normal full-text search.",
    )
    p.add_argument(
        "--trigram",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Use trigram FTS as a complement/fallback when available.",
    )
    p.add_argument(
        "--retry-queries",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Retry with derived query terms when the original query has no results.",
    )
    p.add_argument(
        "--max-retries",
        type=int,
        default=5,
        help="Maximum derived query retries after the original query.",
    )

    p = sub.add_parser("list")
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--scope", choices=["global", "project", "user"])
    p.add_argument("--project-path")
    p.add_argument("--status", default="active", choices=["active", "superseded", "deleted"])

    p = sub.add_parser("forget")
    p.add_argument("--id")
    p.add_argument("--key")
    p.add_argument("--scope", default="project", choices=["global", "project", "user"])
    p.add_argument("--project-path")
    p.add_argument("--session-id")
    p.add_argument("--reason")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    args.db = args.db.expanduser()

    with connect(args.db) as con:
        if args.command == "init":
            emit({"db_path": str(args.db), **init_db(con)})
        elif args.command == "inspect":
            inspect_db(args, con)
        elif args.command == "start-session":
            start_session(args, con)
        elif args.command == "end-session":
            end_session(args, con)
        elif args.command == "add-message":
            add_message(args, con)
        elif args.command == "remember":
            remember(args, con)
        elif args.command == "search":
            search(args, con)
        elif args.command == "list":
            list_memory(args, con)
        elif args.command == "forget":
            forget(args, con)
        else:
            parser.error(f"unknown command: {args.command}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
