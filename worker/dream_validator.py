# HyperSpace-AGI v5.9 - Dream Validator v2
# Evolution from v5.8: aggiunge ValidationVote, ContestStatus, quorum logic
# v5.8 base: score_memory() + evaluate() -> preserve + extend
from __future__ import annotations
from datetime import datetime
from shared.domain.models import (
    MemoryRecord, MemoryTier, ContestStatus,
    ValidationVote, ValidationVoteTally, DreamState,
)
from shared.settings import settings


class DreamValidatorV2:
    """
    Evoluzione del DreamValidator v5.8.
    Nuove features v5.9:
    - Emette ValidationVote invece di semplice string outcome
    - Supporta contested memory con ContestStatus
    - Quorum logic configurabile via settings.vote_quorum
    - Integrazione con ValidationVoteStore
    """

    def __init__(self, memory_store, vote_store: 'ValidationVoteStore') -> None:
        self.memory_store = memory_store
        self.vote_store = vote_store

    # ------------------------------------------------------------------
    # Score logic (v5.8 preserved, invariata)
    # ------------------------------------------------------------------

    async def score_memory(
        self,
        memory: MemoryRecord,
        neighborhood: list[MemoryRecord],
    ) -> dict:
        """Calcola support/contradiction/novelty/coherence scores."""
        support = sum(
            1 for x in neighborhood
            if any(w in x.content.lower() for w in memory.content.lower().split()[:6])
        ) / max(len(neighborhood), 1)

        contradiction = sum(
            1 for x in neighborhood
            if ('not ' in x.content.lower() and x.session_id == memory.session_id)
        ) / max(len(neighborhood), 1)

        novelty = min(1.0, max(0.1, 1.0 - support * 0.5))
        coherence = max(0.0, 1.0 - contradiction * 0.6)
        final = (
            0.45 * coherence
            + 0.30 * support
            + 0.25 * novelty
            - 0.35 * contradiction
        )
        return {
            'support_score': round(support, 3),
            'contradiction_score': round(contradiction, 3),
            'novelty_score': round(novelty, 3),
            'coherence_score': round(coherence, 3),
            'final_score': round(final, 3),
        }

    # ------------------------------------------------------------------
    # v5.9: emit ValidationVote
    # ------------------------------------------------------------------

    async def cast_vote(
        self,
        memory: MemoryRecord,
        neighborhood: list[MemoryRecord],
        dream_id: str,
        voter_model_id: str,
    ) -> ValidationVote:
        """Emette un ValidationVote basato sullo scoring."""
        scores = await self.score_memory(memory, neighborhood)
        final = scores['final_score']
        contradiction = scores['contradiction_score']

        if contradiction >= 0.45:
            vote = 'retract'
            confidence = round(contradiction, 3)
        elif final >= settings.validation_threshold if hasattr(settings, 'validation_threshold') else 0.55:
            vote = 'confirm'
            confidence = round(final, 3)
        else:
            vote = 'abstain'
            confidence = 0.5

        return ValidationVote(
            memory_id=memory.memory_id,
            dream_id=dream_id,
            voter_model_id=voter_model_id,
            vote=vote,
            confidence=confidence,
            reasoning=f"scores={scores}",
        )

    # ------------------------------------------------------------------
    # v5.9: evaluate con ContestStatus
    # ------------------------------------------------------------------

    async def evaluate_with_contest(
        self,
        memory: MemoryRecord,
        neighborhood: list[MemoryRecord],
        dream_id: str,
        voter_model_id: str,
    ) -> tuple[MemoryRecord, ValidationVote]:
        """
        Evoluzione di evaluate():
        - Emette voto
        - Aggiorna contest_status sulla MemoryRecord
        - Gestisce transizione tier: SPECULATIVE -> SEMANTIC | CONTESTED | QUARANTINED
        """
        vote = await self.cast_vote(memory, neighborhood, dream_id, voter_model_id)

        updated = memory.model_copy(deep=True)
        now = datetime.utcnow().isoformat()

        if vote.vote == 'retract':
            updated.tier = MemoryTier.QUARANTINED
            updated.contest_status = ContestStatus.OPEN
            updated.contest_opened_at = now
            updated.validation_status = 'contested'
        elif vote.vote == 'confirm':
            if updated.tier == MemoryTier.SPECULATIVE:
                updated.tier = MemoryTier.SEMANTIC
            updated.contest_status = ContestStatus.NONE
            updated.validation_status = 'confirmed'
            updated.validation_notes = f"confirmed by {voter_model_id}"
        else:  # abstain
            updated.validation_status = 'abstained'

        return updated, vote

    # ------------------------------------------------------------------
    # v5.8 compat: evaluate() legacy
    # ------------------------------------------------------------------

    async def evaluate(
        self,
        memory: MemoryRecord,
        neighborhood: list[MemoryRecord],
    ) -> tuple[str, dict]:
        """Backward compat con v5.8. Restituisce (outcome_str, scores_dict)."""
        scores = await self.score_memory(memory, neighborhood)
        if scores['contradiction_score'] >= 0.45:
            return 'reject', scores
        threshold = 0.55
        if scores['final_score'] >= threshold:
            return 'promote', scores
        return 'quarantine', scores
