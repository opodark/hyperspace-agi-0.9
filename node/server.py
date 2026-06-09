# HyperSpace-AGI v5.9 - Node Server (porta 8765)
from __future__ import annotations
import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from shared.settings import settings
from node.memory.tiered_store import TieredMemoryStore
from node.runtime.agent_runtime import AgentRuntime

app = FastAPI(title='HyperSpace-AGI Node', version='0.9.0')

_memory = TieredMemoryStore()
_agent = AgentRuntime(memory_store=_memory)


class ChatRequest(BaseModel):
    session_id: str
    message: str
    model_alias: str = 'auto'
    system_prompt: str | None = None


@app.get('/health')
async def health() -> dict:
    return {'status': 'ok', 'service': 'node', 'version': '0.9.0'}


@app.post('/chat')
async def chat(req: ChatRequest) -> dict:
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
    pruned_ttl = await _memory.prune_expired_ttl()
    return {'pruned_low_score': pruned_score, 'pruned_ttl': pruned_ttl}


if __name__ == '__main__':
    uvicorn.run('node.server:app', host='0.0.0.0', port=settings.node_api_port, reload=False)
