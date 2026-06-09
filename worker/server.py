# HyperSpace-AGI v5.9 - Worker Server
# FastAPI su porta 8767
# Espone: /health, /votes/{memory_id}, /votes/tally/{memory_id}, /dreams/{dream_id}, /replay
from __future__ import annotations
import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from shared.domain.models import ValidationVote
from shared.settings import settings
from worker.dream_store import DreamStateStore
from worker.validation_vote_store import ValidationVoteStore
from worker.dream_replay import DreamReplayEngine
from worker.dream_validator import DreamValidatorV2

app = FastAPI(
    title='HyperSpace-AGI Worker',
    description='Dream Validator v2 + Validation Vote Store + Dream Replay',
    version='0.9.0',
)

# Dependency singletons
_dream_store = DreamStateStore()
_vote_store = ValidationVoteStore()
_validator = DreamValidatorV2(memory_store=None, vote_store=_vote_store)
_replay_engine = DreamReplayEngine(
    dream_store=_dream_store,
    vote_store=_vote_store,
    validator=_validator,
)


@app.get('/health')
async def health() -> dict:
    return {'status': 'ok', 'service': 'worker', 'version': '0.9.0'}


@app.get('/votes/{memory_id}')
async def get_votes(memory_id: str) -> dict:
    """Lista tutti i voti per una memoria."""
    votes = _vote_store.votes_for_memory(memory_id)
    return {'memory_id': memory_id, 'votes': [v.model_dump() for v in votes]}


@app.get('/votes/tally/{memory_id}')
async def get_tally(memory_id: str) -> dict:
    """Tally voti per una memoria (con quorum check)."""
    tally = _vote_store.tally(memory_id)
    return tally.model_dump()


@app.get('/dreams/{dream_id}')
async def get_dream(dream_id: str) -> dict:
    """Stato di un dream."""
    dream = await _dream_store.get(dream_id)
    if not dream:
        return JSONResponse(status_code=404, content={'error': f'dream not found: {dream_id}'})
    return dream.model_dump()


@app.post('/replay')
async def trigger_replay(dream_id: str, replay_model_id: str, trigger: str = 'manual') -> dict:
    """Avvia un dream replay su un modello specifico."""
    try:
        record = await _replay_engine.replay(
            dream_id=dream_id,
            replay_model_id=replay_model_id,
            trigger=trigger,
        )
        return record.model_dump()
    except ValueError as e:
        return JSONResponse(status_code=404, content={'error': str(e)})


@app.get('/contested/{memory_id}/resolve')
async def resolve_contest(memory_id: str) -> dict:
    """Risolve una contestazione aperta su una memoria."""
    status = await _replay_engine.resolve_contested(memory_id)
    return {'memory_id': memory_id, 'resolution': status.value}


if __name__ == '__main__':
    uvicorn.run(
        'worker.server:app',
        host='0.0.0.0',
        port=settings.worker_api_port,
        reload=False,
    )
