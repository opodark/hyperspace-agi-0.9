# HyperSpace-AGI v5.9 - Tiered Memory Store
# Evolution from v5.8 TieredMemoryStore
# v5.9 additions: ContestStatus, TTL pruning, update(), list_contested()
from __future__ import annotations
import sqlite3
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from shared.domain.models import MemoryRecord, MemoryTier, ContestStatus


CREATE_MEMORY = """
CREATE TABLE IF NOT EXISTS memory_records (
    memory_id          TEXT PRIMARY KEY,
    session_id         TEXT NOT NULL,
    role               TEXT NOT NULL,
    content            TEXT NOT NULL,
    tier               TEXT NOT NULL,
    score              REAL NOT NULL DEFAULT 0.5,
    source_task_id     TEXT,
    validation_status  TEXT NOT NULL DEFAULT 'none',
    validation_notes   TEXT,
    contest_status     TEXT NOT NULL DEFAULT 'none',
    contest_opened_at  TEXT,
    ttl_expires_at     TEXT
);
CREATE TABLE IF NOT EXISTS memory_edges (
    edge_id            TEXT PRIMARY KEY,
    source_memory_id   TEXT NOT NULL,
    target_memory_id   TEXT NOT NULL,
    relation           TEXT NOT NULL,
    weight             REAL NOT NULL DEFAULT 0.5,
    created_by         TEXT NOT NULL DEFAULT 'dream_validator'
);
CREATE TABLE IF NOT EXISTS quarantine (
    memory_id          TEXT PRIMARY KEY,
    session_id         TEXT NOT NULL,
    role               TEXT NOT NULL,
    content            TEXT NOT NULL,
    tier               TEXT NOT NULL,
    score              REAL NOT NULL DEFAULT 0.5,
    source_task_id     TEXT,
    validation_status  TEXT NOT NULL DEFAULT 'quarantined',
    validation_notes   TEXT,
    contest_status     TEXT NOT NULL DEFAULT 'open',
    contest_opened_at  TEXT,
    ttl_expires_at     TEXT
);
CREATE INDEX IF NOT EXISTS idx_mem_session ON memory_records(session_id);
CREATE INDEX IF NOT EXISTS idx_mem_tier    ON memory_records(tier);
CREATE INDEX IF NOT EXISTS idx_mem_contest ON memory_records(contest_status);
"""

_MEM_COLS = (
    'memory_id,session_id,role,content,tier,score,'
    'source_task_id,validation_status,validation_notes,'
    'contest_status,contest_opened_at,ttl_expires_at'
)


def _row_to_record(row: tuple) -> MemoryRecord:
    return MemoryRecord(
        memory_id=row[0], session_id=row[1], role=row[2], content=row[3],
        tier=MemoryTier(row[4]), score=row[5], source_task_id=row[6],
        validation_status=row[7], validation_notes=row[8],
        contest_status=ContestStatus(row[9]) if row[9] else ContestStatus.NONE,
        contest_opened_at=row[10], ttl_expires_at=row[11],
    )


class TieredMemoryStore:
    """SQLite tiered memory store - v5.8 compat + v5.9 extensions."""

    def __init__(self, state_dir: str = '/node/shared/memory') -> None:
        path = Path(state_dir) / 'memory.db'
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path), check_same_thread=False)
        self.conn.executescript(CREATE_MEMORY)
        self.conn.commit()

    async def add(self, record: MemoryRecord) -> None:
        self.conn.execute(
            f'INSERT OR REPLACE INTO memory_records ({_MEM_COLS}) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
            (record.memory_id, record.session_id, record.role, record.content,
             record.tier.value, record.score, record.source_task_id,
             record.validation_status, record.validation_notes,
             record.contest_status.value, record.contest_opened_at, record.ttl_expires_at),
        )
        self.conn.commit()

    async def update(self, record: MemoryRecord) -> None:
        """v5.9: aggiorna una MemoryRecord esistente."""
        self.conn.execute(
            'UPDATE memory_records SET tier=?,score=?,validation_status=?,validation_notes=?,'
            'contest_status=?,contest_opened_at=?,ttl_expires_at=? WHERE memory_id=?',
            (record.tier.value, record.score, record.validation_status, record.validation_notes,
             record.contest_status.value, record.contest_opened_at, record.ttl_expires_at,
             record.memory_id),
        )
        self.conn.commit()

    async def add_edge(self, source_memory_id: str, target_memory_id: str, relation: str,
                       weight: float = 0.5, created_by: str = 'dream_validator') -> None:
        self.conn.execute(
            'INSERT OR REPLACE INTO memory_edges VALUES (?,?,?,?,?,?)',
            (str(uuid.uuid4()), source_memory_id, target_memory_id, relation, weight, created_by),
        )
        self.conn.commit()

    async def quarantine_record(self, record: MemoryRecord, notes: str) -> None:
        record.validation_status = 'quarantined'
        record.validation_notes = notes
        record.contest_status = ContestStatus.OPEN
        record.contest_opened_at = datetime.utcnow().isoformat()
        self.conn.execute(
            f'INSERT OR REPLACE INTO quarantine ({_MEM_COLS}) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
            (record.memory_id, record.session_id, record.role, record.content,
             record.tier.value, record.score, record.source_task_id,
             record.validation_status, record.validation_notes,
             record.contest_status.value, record.contest_opened_at, record.ttl_expires_at),
        )
        self.conn.commit()

    async def promote(self, memory_id: str) -> MemoryRecord | None:
        """v5.8 preserved: promuove da quarantine a SEMANTIC."""
        row = self.conn.execute(
            f'SELECT {_MEM_COLS} FROM quarantine WHERE memory_id=?', (memory_id,)
        ).fetchone()
        if not row:
            return None
        self.conn.execute('DELETE FROM quarantine WHERE memory_id=?', (memory_id,))
        self.conn.commit()
        rec = MemoryRecord(
            memory_id=row[0], session_id=row[1], role=row[2], content=row[3],
            tier=MemoryTier.SEMANTIC, score=min(row[5] + 0.25, 1.0),
            source_task_id=row[6], validation_status='promoted', validation_notes=row[8],
            contest_status=ContestStatus.RESOLVED_CONFIRM,
        )
        await self.add(rec)
        await self.add_edge(row[0], rec.memory_id, 'promotes_to', 0.9)
        return rec

    async def search(self, session_id: str, query: str, k: int = 3,
                     tiers: tuple[MemoryTier, ...] = (MemoryTier.SEMANTIC, MemoryTier.EPISODIC)) -> list[MemoryRecord]:
        """Keyword overlap search (v5.8 preserved)."""
        rows = self.conn.execute(
            f'SELECT {_MEM_COLS} FROM memory_records WHERE session_id=?', (session_id,)
        ).fetchall()
        query_words = set(query.lower().split())
        scored: list[tuple[float, MemoryRecord]] = []
        for row in rows:
            if MemoryTier(row[4]) not in tiers:
                continue
            overlap = len(query_words.intersection(set(row[3].lower().split())))
            if overlap:
                scored.append((overlap + float(row[5]), _row_to_record(row)))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [r for _, r in scored[:k]]

    async def list_session(self, session_id: str) -> list[MemoryRecord]:
        rows = self.conn.execute(
            f'SELECT {_MEM_COLS} FROM memory_records WHERE session_id=? ORDER BY rowid ASC',
            (session_id,),
        ).fetchall()
        return [_row_to_record(r) for r in rows]

    async def list_quarantine(self, session_id: str) -> list[MemoryRecord]:
        rows = self.conn.execute(
            f'SELECT {_MEM_COLS} FROM quarantine WHERE session_id=? ORDER BY rowid ASC',
            (session_id,),
        ).fetchall()
        return [_row_to_record(r) for r in rows]

    async def list_edges(self, session_id: str) -> list[dict]:
        rows = self.conn.execute(
            'SELECT e.edge_id,e.source_memory_id,e.target_memory_id,e.relation,e.weight,e.created_by '
            'FROM memory_edges e JOIN memory_records r ON r.memory_id=e.source_memory_id '
            'WHERE r.session_id=?', (session_id,),
        ).fetchall()
        return [{'edge_id': r[0], 'source_memory_id': r[1], 'target_memory_id': r[2],
                 'relation': r[3], 'weight': r[4], 'created_by': r[5]} for r in rows]

    async def list_recent_by_tier(self, tier: MemoryTier, limit: int = 50) -> list[MemoryRecord]:
        rows = self.conn.execute(
            f'SELECT {_MEM_COLS} FROM memory_records WHERE tier=? ORDER BY rowid DESC LIMIT ?',
            (tier.value, limit),
        ).fetchall()
        return [_row_to_record(r) for r in rows]

    async def list_contested(self) -> list[MemoryRecord]:
        """v5.9: lista memorie con contest_status=OPEN."""
        rows = self.conn.execute(
            f'SELECT {_MEM_COLS} FROM memory_records WHERE contest_status=? ORDER BY rowid DESC',
            (ContestStatus.OPEN.value,),
        ).fetchall()
        return [_row_to_record(r) for r in rows]

    async def prune_low_score_speculative(self, threshold: float = 0.25) -> int:
        """v5.8 preserved."""
        cur = self.conn.execute(
            'DELETE FROM memory_records WHERE tier=? AND score<?',
            (MemoryTier.SPECULATIVE.value, threshold),
        )
        self.conn.commit()
        return cur.rowcount

    async def prune_expired_ttl(self) -> int:
        """v5.9: elimina memorie speculative scadute per TTL."""
        now = datetime.utcnow().isoformat()
        cur = self.conn.execute(
            'DELETE FROM memory_records WHERE tier=? AND ttl_expires_at IS NOT NULL AND ttl_expires_at<?',
            (MemoryTier.SPECULATIVE.value, now),
        )
        self.conn.commit()
        return cur.rowcount

    def set_ttl(self, memory_id: str, seconds: int) -> None:
        """v5.9: imposta TTL su una memoria speculativa."""
        expires = (datetime.utcnow() + timedelta(seconds=seconds)).isoformat()
        self.conn.execute(
            'UPDATE memory_records SET ttl_expires_at=? WHERE memory_id=?', (expires, memory_id)
        )
        self.conn.commit()
