# HyperSpace-AGI v5.9 - Validation Vote Store
# NUOVO: SQLite store per voti di validazione su MemoryRecord
# Supporta: cast, tally, quorum check, list per dream
from __future__ import annotations
import sqlite3
from pathlib import Path
from datetime import datetime
from shared.domain.models import ValidationVote, ValidationVoteTally, ContestStatus
from shared.settings import settings


CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS validation_votes (
    vote_id        TEXT PRIMARY KEY,
    memory_id      TEXT NOT NULL,
    dream_id       TEXT NOT NULL,
    voter_model_id TEXT NOT NULL,
    vote           TEXT NOT NULL,
    confidence     REAL NOT NULL,
    reasoning      TEXT,
    voted_at       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_votes_memory ON validation_votes(memory_id);
CREATE INDEX IF NOT EXISTS idx_votes_dream  ON validation_votes(dream_id);
"""


class ValidationVoteStore:
    """SQLite-backed store per i voti di validazione."""

    def __init__(self, state_dir: str = '/worker/worker/votes') -> None:
        path = Path(state_dir) / 'votes.db'
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path), check_same_thread=False)
        self.conn.executescript(CREATE_TABLE)
        self.conn.commit()

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def cast(self, vote: ValidationVote) -> None:
        """Persiste un voto."""
        self.conn.execute(
            'INSERT OR REPLACE INTO validation_votes VALUES (?,?,?,?,?,?,?,?)',
            (
                vote.vote_id,
                vote.memory_id,
                vote.dream_id,
                vote.voter_model_id,
                vote.vote,
                vote.confidence,
                vote.reasoning,
                vote.voted_at,
            ),
        )
        self.conn.commit()

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def votes_for_memory(self, memory_id: str) -> list[ValidationVote]:
        """Tutti i voti per una memory."""
        rows = self.conn.execute(
            'SELECT vote_id,memory_id,dream_id,voter_model_id,vote,confidence,reasoning,voted_at '
            'FROM validation_votes WHERE memory_id=? ORDER BY voted_at',
            (memory_id,),
        ).fetchall()
        return [self._row_to_vote(r) for r in rows]

    def votes_for_dream(self, dream_id: str) -> list[ValidationVote]:
        """Tutti i voti per un dream."""
        rows = self.conn.execute(
            'SELECT vote_id,memory_id,dream_id,voter_model_id,vote,confidence,reasoning,voted_at '
            'FROM validation_votes WHERE dream_id=? ORDER BY voted_at',
            (dream_id,),
        ).fetchall()
        return [self._row_to_vote(r) for r in rows]

    # ------------------------------------------------------------------
    # Tally + Quorum
    # ------------------------------------------------------------------

    def tally(self, memory_id: str) -> ValidationVoteTally:
        """Calcola il tally per una memory."""
        votes = self.votes_for_memory(memory_id)
        if not votes:
            return ValidationVoteTally(memory_id=memory_id)

        confirms  = [v for v in votes if v.vote == 'confirm']
        retracts  = [v for v in votes if v.vote == 'retract']
        abstains  = [v for v in votes if v.vote == 'abstain']
        avg_conf  = sum(v.confidence for v in votes) / len(votes)
        quorum    = len(votes) >= settings.vote_quorum

        # Risoluzione: maggioranza tra confirm/retract
        resolution = ContestStatus.OPEN
        if quorum:
            if len(confirms) > len(retracts):
                resolution = ContestStatus.RESOLVED_CONFIRM
            elif len(retracts) >= len(confirms):
                resolution = ContestStatus.RESOLVED_RETRACT

        return ValidationVoteTally(
            memory_id=memory_id,
            confirm_count=len(confirms),
            retract_count=len(retracts),
            abstain_count=len(abstains),
            avg_confidence=round(avg_conf, 3),
            quorum_reached=quorum,
            resolution=resolution,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_vote(row: tuple) -> ValidationVote:
        return ValidationVote(
            vote_id=row[0],
            memory_id=row[1],
            dream_id=row[2],
            voter_model_id=row[3],
            vote=row[4],
            confidence=row[5],
            reasoning=row[6],
            voted_at=row[7],
        )
