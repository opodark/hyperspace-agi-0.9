# HyperSpace-AGI v5.9 - Control Plane Server
# FastAPI su porta 8768
# Espone: /health, /route, /catalog (proxy), /votes (proxy), /replay (proxy), /stats
from __future__ import annotations
import uvicorn
import httpx
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from shared.domain.models import UserRequest, ChatCompletionsRequest
from shared.settings import settings
from control_plane.request_classifier import RequestClassifier
from control_plane.smart_router import SmartRouter
from control_plane.runtime_store import ControlPlaneRuntimeStore

app = FastAPI(
    title='HyperSpace-AGI Control Plane',
    description='Smart Routing 4-level + Catalog + Votes + Replay proxy',
    version='0.9.0',
)

_classifier = RequestClassifier()
_router = SmartRouter()
_store = ControlPlaneRuntimeStore()

_AUTHORITY_URL = f'http://authority:{settings.authority_api_port}'
_WORKER_URL = f'http://worker:{settings.worker_api_port}'
_OLLAMA_URL = settings.ollama_base_url


@app.get('/health')
async def health() -> dict:
    return {'status': 'ok', 'service': 'control-plane', 'version': '0.9.0'}


@app.post('/route')
async def route_request(request: UserRequest) -> dict:
    """Classifica e ruota una UserRequest. Ritorna ExecutionPlan."""
    plan = await _router.route(request)
    workload_level = 1  # viene calcolato internamente al router
    fallback = 'local fallback' in (plan.pull_decision.reason or '')
    _store.record_decision(plan, routing_level=workload_level, fallback_used=fallback)
    return plan.model_dump()


@app.post('/v1/chat/completions')
async def openai_compat(req: ChatCompletionsRequest) -> dict:
    """
    Endpoint OpenAI-compatible: riceve una chat completions request,
    la ruota al modello corretto via Ollama.
    """
    user_request = UserRequest(
        model_alias=req.model,
        messages=req.messages,
    )
    plan = await _router.route(user_request)
    model_id = plan.selected_model_id or settings.default_agent_model

    ollama_payload = {
        'model': model_id,
        'messages': [m.model_dump() for m in req.messages],
        'stream': req.stream,
    }
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(f'{_OLLAMA_URL}/api/chat', json=ollama_payload)
        resp.raise_for_status()
        return resp.json()


# ------------------------------------------------------------------
# Proxy endpoints -> authority
# ------------------------------------------------------------------

@app.get('/catalog')
async def proxy_catalog() -> dict:
    """Proxy verso authority /catalog."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f'{_AUTHORITY_URL}/catalog')
        return resp.json()


@app.get('/catalog/role/{role}')
async def proxy_catalog_role(role: str) -> dict:
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f'{_AUTHORITY_URL}/catalog/role/{role}')
        return resp.json()


# ------------------------------------------------------------------
# Proxy endpoints -> worker
# ------------------------------------------------------------------

@app.get('/votes/{memory_id}')
async def proxy_votes(memory_id: str) -> dict:
    """Proxy verso worker /votes/{memory_id}."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f'{_WORKER_URL}/votes/{memory_id}')
        return resp.json()


@app.get('/votes/tally/{memory_id}')
async def proxy_tally(memory_id: str) -> dict:
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f'{_WORKER_URL}/votes/tally/{memory_id}')
        return resp.json()


@app.post('/replay')
async def proxy_replay(dream_id: str, replay_model_id: str, trigger: str = 'manual') -> dict:
    """Proxy verso worker /replay."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f'{_WORKER_URL}/replay',
            params={'dream_id': dream_id, 'replay_model_id': replay_model_id, 'trigger': trigger},
        )
        return resp.json()


# ------------------------------------------------------------------
# Metriche e audit
# ------------------------------------------------------------------

@app.get('/stats')
async def get_stats() -> dict:
    """Statistiche aggregate di routing."""
    return _store.stats()


@app.get('/decisions')
async def recent_decisions(limit: int = 20) -> dict:
    """Ultime N routing decisions."""
    return {'decisions': _store.recent_decisions(limit)}


if __name__ == '__main__':
    uvicorn.run(
        'control_plane.server:app',
        host='0.0.0.0',
        port=settings.control_plane_api_port,
        reload=False,
    )
