# HyperSpace-AGI v5.9 - Dream Store (evolved from v5.8)
# v5.8: DreamStateStore con SQLite base
# v5.9: aggiunge replay_count, vote_tally (JSON), last_replayed_at
from __future__ import annotations
import sqlite3
import json
from pathlib import Path
from shared.domain.models import DreamState, DreamStatus


CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS dream_states (
    dream_id          TEXT PRIMARY KEY,
    node_id           TEXT NOT NULL,
    status            TEXT NOT NULL,
    summary           TEXT,
    speculative_count INTEGER DEFAULT 0,
    semantic_updates  INTEGER DEFAULT 0,
    coherence_score   REAL    DEFAULT 0.0,
    novelty_score     REAL    DEFAULT 0.0,
    support_score     REAL    DEFAULT 0.0,
    contradiction_score REAL  DEFAULT 0.0,
    replay_count      INTEGER DEFAULT 0,
    last_replayed_at  TEXT,
    vote_tally        TEXT    DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_dream_node ON dream_states(node_id);
"""


class DreamStateStore:
    """SQLite store per DreamState - v5.8 compat + v5.9 extensions."""

    def __init__(self, state_dir: str = '/worker/runtime/dreams') -> None:
        path = Path(state_dir) / 'dreams.db'
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path), check_same_thread=False)
        self.conn.executescript(CREATE_TABLE)
        self.conn.commit()

    async def upsert(self, dream: DreamState) -> None:
        """Inserisce o aggiorna un DreamState."""
        self.conn.execute(
            'INSERT OR REPLACE INTO dream_states VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',
            (
                dream.dream_id,
                dream.node_id,
                dream.status.value,
                dream.summary,
                dream.speculative_count,
                dream.semantic_updates,
                dream.coherence_score,
                dream.novelty_score,
                dream.support_score,
                dream.contradiction_score,
                dream.replay_count,
                dream.last_replayed_at,
                json.dumps(dream.vote_tally),
            ),
        )
        self.conn.commit()

    async def latest_for_node(self, node_id: str) -> DreamState | None:
        """Ultimo dream per node_id."""
        row = self.conn.execute(
            'SELECT dream_id,node_id,status,summary,speculative_count,semantic_updates,'
            'coherence_score,novelty_score,support_score,contradiction_score,'
            'replay_count,last_replayed_at,vote_tally '
            'FROM dream_states WHERE node_id=? ORDER BY rowid DESC LIMIT 1',
            (node_id,),
        ).fetchone()
        if not row:
            return None
        return self._row_to_dream(row)

    async def get(self, dream_id: str) -> DreamState | None:
        """Recupera un dream per dream_id."""
        row = self.conn.execute(
            'SELECT dream_id,node_id,status,summary,speculative_count,semantic_updates,'
            'coherence_score,novelty_score,support_score,contradiction_score,'
            'replay_count,last_replayed_at,vote_tally '
            'FROM dream_states WHERE dream_id=?',
            (dream_id,),
        ).fetchone()
        return self._row_to_dream(row) if row else None

    async def list_by_status(self, status: DreamStatus) -> list[DreamState]:
        """Lista dream per status."""
        rows = self.conn.execute(
            'SELECT dream_id,node_id,status,summary,speculative_count,semantic_updates,'
            'coherence_score,novelty_score,support_score,contradiction_score,'
            'replay_count,last_replayed_at,vote_tally '
            'FROM dream_states WHERE status=? ORDER BY rowid DESC',
            (status.value,),
        ).fetchall()
        return [self._row_to_dream(r) for r in rows]

    @staticmethod
    def _row_to_dream(row: tuple) -> DreamState:
        return DreamState(
            dream_id=row[0],
            node_id=row[1],
            status=DreamStatus(row[2]),
            summary=row[3],
            speculative_count=row[4],
            semantic_updates=row[5],
            coherence_score=row[6],
            novelty_score=row[7],
            support_score=row[8],
            contradiction_score=row[9],
            replay_count=row[10],
            last_replayed_at=row[11],
            vote_tally=json.loads(row[12]) if row[12] else {},
        )
