# HyperSpace-AGI v6.0 - Node Server con P2P + Shared Dreams
from __future__ import annotations
import os
import uuid
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from shared.settings import settings
from node.memory.tiered_store import TieredMemoryStore
from node.runtime.agent_runtime import AgentRuntime
from node.runtime.gossip_service import GossipService, PeerInfo
from node.runtime.node_state import NodeStateManager, DreamEntry

NODE_ID   = os.getenv('NODE_ID', 'node-default')
NODE_HOST = os.getenv('NODE_HOST', NODE_ID)
NODE_PORT = int(os.getenv('NODE_API_PORT', '8765'))
MODELS    = os.getenv('DEFAULT_AGENT_MODEL', 'qwen2.5:7b').split(',')

_self_info = PeerInfo.from_env(node_id=NODE_ID, host=NODE_HOST, port=NODE_PORT, models=MODELS)
_gossip    = GossipService(self_info=_self_info)
_memory    = TieredMemoryStore()
_agent     = AgentRuntime(memory_store=_memory)
_state     = NodeStateManager(node_id=NODE_ID)


async def _propagate_dream(dream: DreamEntry) -> None:
    """Propaga un dream a tutti i peer attivi via gossip."""
    import httpx
    peers = _gossip.get_peers()
    for peer in peers:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(
                    f'{peer.url}/dreams/receive',
                    json=dream.to_dict()
                )
        except Exception:
            pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    await _gossip.start()
    yield
    await _gossip.stop()


app = FastAPI(
    title=f'HyperSpace-AGI Node [{_self_info.display_name()}]',
    version='6.0.0',
    lifespan=lifespan
)


@app.get('/health')
async def health() -> dict:
    return {
        'status':   'ok', 'service': 'node', 'version': '6.0.0',
        'node_id':  NODE_ID, 'nickname': _self_info.nickname,
        'location': _self_info.location,
        **_state.get_status(),
    }


class ChatRequest(BaseModel):
    session_id: str
    message: str
    model_alias: str = 'auto'
    system_prompt: str | None = None


@app.post('/chat')
async def chat(req: ChatRequest) -> dict:
    _state.record_request()
    _gossip.update_self_state('active', load=min(_state._request_count / 100, 1.0))
    try:
        response = await _agent.run(
            session_id=req.session_id, user_message=req.message,
            model_alias=req.model_alias, system_prompt=req.system_prompt,
        )
        return {'session_id': req.session_id, 'response': response}
    except Exception as e:
        return JSONResponse(status_code=500, content={'error': str(e)})


@app.get('/memory/{session_id}')
async def list_memory(session_id: str) -> dict:
    records = await _memory.list_session(session_id)
    return {'session_id': session_id, 'count': len(records), 'records': [r.model_dump() for r in records]}


@app.get('/memory/{session_id}/quarantine')
async def list_quarantine(session_id: str) -> dict:
    records = await _memory.list_quarantine(session_id)
    return {'session_id': session_id, 'quarantined': [r.model_dump() for r in records]}


@app.get('/memory/contested')
async def list_contested() -> dict:
    records = await _memory.list_contested()
    return {'count': len(records), 'contested': [r.model_dump() for r in records]}


@app.post('/memory/prune')
async def prune_memory(threshold: float = 0.25) -> dict:
    pruned_score = await _memory.prune_low_score_speculative(threshold)
    pruned_ttl   = await _memory.prune_expired_ttl()
    return {'pruned_low_score': pruned_score, 'pruned_ttl': pruned_ttl}


# ── Gossip ────────────────────────────────────────────────────────────────────────

@app.post('/gossip/heartbeat')
async def gossip_heartbeat(peer: dict) -> dict:
    _gossip.register_peer(peer)
    return {
        'node_id':  NODE_ID, 'nickname': _self_info.nickname,
        'state':    _state.state, 'load': _state.load,
        'peers':    [p.to_dict() for p in _gossip.get_peers()],
    }


@app.get('/gossip/peers')
async def list_peers() -> dict:
    return {
        'self':        _gossip.self_to_dict(),
        'peers':       [p.to_dict() for p in _gossip.get_all_peers()],
        'alive_count': len(_gossip.get_peers()),
        'total':       len(_gossip.get_all_peers()),
    }


# ── Dreams (shared P2P) ────────────────────────────────────────────────────────────

@app.get('/dreams')
async def list_dreams() -> dict:
    return _state.get_status()


@app.post('/dreams/add')
async def add_dream(content: str, score: float = 0.75) -> dict:
    """Crea un dream e lo propaga a tutti i peer."""
    dream = DreamEntry(
        dream_id    = str(uuid.uuid4())[:8],
        content     = content,
        score       = score,
        origin_node = NODE_ID,
    )
    _state.add_dream(dream)
    _gossip.update_self_state('dreaming')
    # propaga ai peer in background
    import asyncio
    asyncio.create_task(_propagate_dream(dream))
    return dream.to_dict()


@app.post('/dreams/receive')
async def receive_dream(data: dict) -> dict:
    """Riceve un dream propagato da un peer."""
    dream = _state.receive_dream(data)
    if dream is None:
        return {'status': 'already_known', 'dream_id': data.get('dream_id')}
    return {'status': 'received', **dream.to_dict()}


@app.post('/dreams/{dream_id}/vote')
async def vote_dream(dream_id: str) -> dict:
    result = _state.vote_dream(dream_id, voter_node=NODE_ID)
    if result is None:
        return JSONResponse(status_code=404, content={'error': 'dream not found'})
    # propaga il voto aggiornato ai peer
    import asyncio
    asyncio.create_task(_propagate_dream(result))
    return result.to_dict()


@app.post('/dreams/{dream_id}/retract')
async def retract_dream(dream_id: str) -> dict:
    result = _state.resolve_dream(dream_id, 'retracted')
    if result is None:
        return JSONResponse(status_code=404, content={'error': 'dream not found'})
    _gossip.update_self_state('active')
    return result.to_dict()


if __name__ == '__main__':
    uvicorn.run('node.server:app', host='0.0.0.0', port=NODE_PORT, reload=False)
