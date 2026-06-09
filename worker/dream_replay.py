# HyperSpace-AGI v5.9 - Dream Replay
# NUOVO: riprocessa dream completati con modelli aggiornati o dopo contest risolto
# Trigger: scheduled | contest_resolved | model_upgraded | manual
from __future__ import annotations
from datetime import datetime
from shared.domain.models import (
    DreamState, DreamStatus, DreamReplayRecord,
    MemoryRecord, MemoryTier, ContestStatus,
)
from worker.dream_store import DreamStateStore
from worker.validation_vote_store import ValidationVoteStore
from worker.dream_validator import DreamValidatorV2


class DreamReplayEngine:
    """
    Riprocessa un dream completato:
    1. Carica il dream dal store
    2. Rilancia la validazione con un modello aggiornato
    3. Aggiorna i voti e risolve le contestazioni aperte
    4. Persiste il DreamReplayRecord
    """

    def __init__(
        self,
        dream_store: DreamStateStore,
        vote_store: ValidationVoteStore,
        validator: DreamValidatorV2,
    ) -> None:
        self.dream_store = dream_store
        self.vote_store = vote_store
        self.validator = validator

    async def replay(
        self,
        dream_id: str,
        replay_model_id: str,
        trigger: str = 'manual',
        memories: list[MemoryRecord] | None = None,
    ) -> DreamReplayRecord:
        """
        Entry point principale.
        - memories: lista di MemoryRecord da rivalidare
          (se None, usa lo store del validator)
        """
        dream = await self.dream_store.get(dream_id)
        if not dream:
            raise ValueError(f'dream not found: {dream_id}')

        record = DreamReplayRecord(
            dream_id=dream_id,
            trigger=trigger,
            replay_model_id=replay_model_id,
            started_at=datetime.utcnow().isoformat(),
        )

        if not memories:
            # Nessuna memoria passata: noop replay (struttura pronta per estensione)
            record.success = True
            record.completed_at = datetime.utcnow().isoformat()
            return record

        # Ri-valida ogni memoria
        neighborhood = memories  # usa tutte come contesto
        for mem in memories:
            updated_mem, vote = await self.validator.evaluate_with_contest(
                memory=mem,
                neighborhood=[m for m in neighborhood if m.memory_id != mem.memory_id],
                dream_id=dream_id,
                voter_model_id=replay_model_id,
            )
            self.vote_store.cast(vote)
            record.votes_cast += 1
            record.memories_revalidated += 1

            # Conta retractions e promotions
            if vote.vote == 'retract':
                record.retractions += 1
            elif vote.vote == 'confirm' and mem.tier == MemoryTier.SPECULATIVE:
                record.promotions += 1

        # Aggiorna dream con nuovo replay_count
        dream.replay_count += 1
        dream.last_replayed_at = datetime.utcnow().isoformat()
        await self.dream_store.upsert(dream)

        record.success = True
        record.completed_at = datetime.utcnow().isoformat()
        return record

    async def resolve_contested(
        self,
        memory_id: str,
    ) -> ContestStatus:
        """
        Controlla il tally dei voti per una memoria contestata
        e restituisce il ContestStatus risolto.
        """
        tally = self.vote_store.tally(memory_id)
        return tally.resolution
