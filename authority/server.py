# HyperSpace-AGI v5.9 - Authority Server
# FastAPI server su porta 8766
# Espone: /health, /catalog, /resolve
from __future__ import annotations
import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from shared.domain.models import RoutingContext
from shared.settings import settings
from authority.model_catalog import get_catalog, get_by_role, get_by_id
from authority.policy_engine import policy_engine

app = FastAPI(
    title='HyperSpace-AGI Authority',
    description='Policy Engine v1 + Model Catalog',
    version='0.9.0',
)


@app.get('/health')
async def health() -> dict:
    return {'status': 'ok', 'service': 'authority', 'version': '0.9.0'}


@app.get('/catalog')
async def list_catalog() -> dict:
    """Lista tutti i modelli disponibili nel catalogo."""
    catalog = get_catalog()
    return {
        'total': len(catalog),
        'models': [
            {
                'model_id': e.profile.model_id,
                'ollama_tag': e.ollama_tag,
                'role': e.role,
                'priority': e.priority,
                'size_class': e.profile.size_class,
                'ram_required_gb': e.profile.ram_required_gb,
                'is_available': e.is_available,
            }
            for e in catalog
        ],
    }


@app.get('/catalog/role/{role}')
async def list_by_role(role: str) -> dict:
    """Filtra catalogo per ruolo (agent, coder, reasoner, small)."""
    entries = get_by_role(role)
    if not entries:
        return JSONResponse(status_code=404, content={'error': f'no models found for role: {role}'})
    return {'role': role, 'models': [e.model_dump() for e in entries]}


@app.get('/catalog/{model_id}')
async def get_model(model_id: str) -> dict:
    """Dettaglio singolo modello."""
    entry = get_by_id(model_id)
    if not entry:
        return JSONResponse(status_code=404, content={'error': f'model not found: {model_id}'})
    return entry.model_dump()


@app.post('/resolve')
async def resolve_routing(ctx: RoutingContext) -> dict:
    """Chiama il Policy Engine v1 e restituisce l\'ExecutionPlan."""
    plan = policy_engine.resolve(ctx)
    return plan.model_dump()


if __name__ == '__main__':
    uvicorn.run(
        'authority.server:app',
        host='0.0.0.0',
        port=settings.authority_api_port,
        reload=False,
    )
