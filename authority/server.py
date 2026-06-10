# HyperSpace-AGI v6.0 - Authority Server
# Espone: /health, /catalog, /resolve, /peers/*
from __future__ import annotations
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from shared.domain.models import RoutingContext
from shared.settings import settings
from authority.model_catalog import get_catalog, get_by_role, get_by_id
from authority.policy_engine import policy_engine
from authority.node_registry import node_registry


@asynccontextmanager
async def lifespan(app: FastAPI):
    await node_registry.start_cleanup()
    yield
    await node_registry.stop_cleanup()


app = FastAPI(
    title='HyperSpace-AGI Authority',
    description='Policy Engine v1 + Model Catalog + NodeRegistry',
    version='6.0.0',
    lifespan=lifespan,
)


# ── Health ────────────────────────────────────────────────────────────────────

@app.get('/health')
async def health() -> dict:
    alive_nodes = node_registry.get_all(alive_only=True)
    return {
        'status':      'ok',
        'service':     'authority',
        'version':     '6.0.0',
        'nodes_alive': len(alive_nodes),
    }


# ── NodeRegistry (Seed / Bootstrap) ────────────────────────────────────────────

@app.post('/peers/announce')
async def announce_peer(data: dict) -> dict:
    """
    Un nodo si annuncia al boot e periodicamente.
    Risponde con la peer table completa → usata come bootstrap P2P.
    """
    try:
        entry  = node_registry.announce(data)
        peers  = node_registry.get_all(alive_only=True)
        # escludi il nodo che si è appena annunciato dalla lista peers
        others = [p.to_dict() for p in peers if p.node_id != entry.node_id]
        return {
            'status':  'registered',
            'node_id': entry.node_id,
            'peers':   others,
            'total':   len(others),
        }
    except ValueError as e:
        return JSONResponse(status_code=400, content={'error': str(e)})


@app.get('/peers')
async def list_peers(alive_only: bool = True) -> dict:
    """Lista tutti i nodi noti al registry."""
    nodes = node_registry.get_all(alive_only=alive_only)
    return {
        'total': len(nodes),
        'alive': sum(1 for n in nodes if n.is_alive()),
        'nodes': [n.to_dict() for n in nodes],
    }


@app.get('/peers/{node_id}')
async def get_peer(node_id: str) -> dict:
    """Dettaglio singolo nodo."""
    entry = node_registry.get(node_id)
    if not entry:
        return JSONResponse(status_code=404, content={'error': f'node not found: {node_id}'})
    return entry.to_dict()


@app.delete('/peers/{node_id}')
async def remove_peer(node_id: str) -> dict:
    """Rimuove manualmente un nodo dal registry."""
    removed = node_registry.remove(node_id)
    if not removed:
        return JSONResponse(status_code=404, content={'error': f'node not found: {node_id}'})
    return {'status': 'removed', 'node_id': node_id}


# ── Model Catalog ──────────────────────────────────────────────────────────────────

@app.get('/catalog')
async def list_catalog() -> dict:
    catalog = get_catalog()
    return {
        'total': len(catalog),
        'models': [
            {
                'model_id':       e.profile.model_id,
                'ollama_tag':     e.ollama_tag,
                'role':           e.role,
                'priority':       e.priority,
                'size_class':     e.profile.size_class,
                'ram_required_gb': e.profile.ram_required_gb,
                'is_available':   e.is_available,
            }
            for e in catalog
        ],
    }


@app.get('/catalog/role/{role}')
async def list_by_role(role: str) -> dict:
    entries = get_by_role(role)
    if not entries:
        return JSONResponse(status_code=404, content={'error': f'no models found for role: {role}'})
    return {'role': role, 'models': [e.model_dump() for e in entries]}


@app.get('/catalog/{model_id}')
async def get_model(model_id: str) -> dict:
    entry = get_by_id(model_id)
    if not entry:
        return JSONResponse(status_code=404, content={'error': f'model not found: {model_id}'})
    return entry.model_dump()


@app.post('/resolve')
async def resolve_routing(ctx: RoutingContext) -> dict:
    plan = policy_engine.resolve(ctx)
    return plan.model_dump()


if __name__ == '__main__':
    uvicorn.run(
        'authority.server:app',
        host='0.0.0.0',
        port=settings.authority_api_port,
        reload=False,
    )
