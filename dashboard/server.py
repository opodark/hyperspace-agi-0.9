# HyperSpace-AGI v5.9 - Dashboard Server
# FastAPI + HTMX + TailwindCSS - porta 8769
from __future__ import annotations
import asyncio
import docker
import httpx
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os

app = FastAPI(title='HyperSpace Dashboard', version='1.0.0')
templates = Jinja2Templates(directory='/dashboard/templates')

DOCKER_CLIENT   = docker.from_env()
OLLAMA_URL      = os.getenv('OLLAMA_BASE_URL', 'http://ollama:11434')
CONTROL_PLANE   = os.getenv('CONTROL_PLANE_URL', 'http://control-plane:8768')
AUTHORITY_URL   = os.getenv('AUTHORITY_URL', 'http://authority:8766')

SERVICES = [
    {'name': 'hyperspace-ollama',        'label': 'Ollama',         'port': 11434, 'emoji': '🦙'},
    {'name': 'hyperspace-authority',     'label': 'Authority',      'port': 8766,  'emoji': '🔍'},
    {'name': 'hyperspace-node',          'label': 'Node',           'port': 8765,  'emoji': '🤖'},
    {'name': 'hyperspace-worker',        'label': 'Worker',         'port': 8767,  'emoji': '⚙️'},
    {'name': 'hyperspace-control-plane', 'label': 'Control Plane',  'port': 8768,  'emoji': '🧠'},
    {'name': 'hyperspace-webui',         'label': 'Open WebUI',     'port': 8080,  'emoji': '🌐'},
]


def get_container_status(name: str) -> dict:
    try:
        c = DOCKER_CLIENT.containers.get(name)
        health = c.attrs.get('State', {}).get('Health', {})
        health_status = health.get('Status', 'none') if health else 'none'
        return {
            'status': c.status,
            'health': health_status,
            'running': c.status == 'running',
        }
    except Exception:
        return {'status': 'not found', 'health': 'none', 'running': False}


async def get_ollama_models() -> list:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f'{OLLAMA_URL}/api/tags')
            models = r.json().get('models', [])
            return models
    except Exception:
        return []


async def get_routing_stats() -> dict:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f'{CONTROL_PLANE}/stats')
            return r.json()
    except Exception:
        return {}


async def get_catalog() -> list:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f'{AUTHORITY_URL}/catalog')
            return r.json()
    except Exception:
        return []


# --- Routes ---

@app.get('/', response_class=HTMLResponse)
async def index(request: Request):
    services = []
    for svc in SERVICES:
        info = get_container_status(svc['name'])
        services.append({**svc, **info})
    models  = await get_ollama_models()
    stats   = await get_routing_stats()
    catalog = await get_catalog()
    return templates.TemplateResponse('index.html', {
        'request': request,
        'services': services,
        'models': models,
        'stats': stats,
        'catalog': catalog,
    })


@app.get('/partials/status', response_class=HTMLResponse)
async def partial_status(request: Request):
    """HTMX partial: aggiorna solo la sezione container status."""
    services = []
    for svc in SERVICES:
        info = get_container_status(svc['name'])
        services.append({**svc, **info})
    return templates.TemplateResponse('partials/status.html', {
        'request': request,
        'services': services,
    })


@app.get('/partials/models', response_class=HTMLResponse)
async def partial_models(request: Request):
    """HTMX partial: aggiorna lista modelli Ollama."""
    models = await get_ollama_models()
    return templates.TemplateResponse('partials/models.html', {
        'request': request,
        'models': models,
    })


@app.get('/partials/stats', response_class=HTMLResponse)
async def partial_stats(request: Request):
    """HTMX partial: aggiorna routing stats."""
    stats = await get_routing_stats()
    return templates.TemplateResponse('partials/stats.html', {
        'request': request,
        'stats': stats,
    })


@app.post('/container/{name}/restart')
async def restart_container(name: str):
    try:
        c = DOCKER_CLIENT.containers.get(name)
        c.restart(timeout=10)
        return HTMLResponse(f'<span class="text-green-400">✓ {name} riavviato</span>')
    except Exception as e:
        return HTMLResponse(f'<span class="text-red-400">✗ {e}</span>')


@app.post('/container/{name}/stop')
async def stop_container(name: str):
    try:
        c = DOCKER_CLIENT.containers.get(name)
        c.stop(timeout=10)
        return HTMLResponse(f'<span class="text-yellow-400">⏹ {name} fermato</span>')
    except Exception as e:
        return HTMLResponse(f'<span class="text-red-400">✗ {e}</span>')


@app.post('/container/{name}/start')
async def start_container(name: str):
    try:
        c = DOCKER_CLIENT.containers.get(name)
        c.start()
        return HTMLResponse(f'<span class="text-green-400">▶ {name} avviato</span>')
    except Exception as e:
        return HTMLResponse(f'<span class="text-red-400">✗ {e}</span>')


@app.get('/logs/{name}')
async def get_logs(name: str, lines: int = 100):
    try:
        c = DOCKER_CLIENT.containers.get(name)
        logs = c.logs(tail=lines, timestamps=True).decode('utf-8', errors='replace')
        return HTMLResponse(
            f'<pre class="text-xs text-green-300 whitespace-pre-wrap font-mono">'
            f'{logs}</pre>'
        )
    except Exception as e:
        return HTMLResponse(f'<pre class="text-red-400">{e}</pre>')


@app.post('/ollama/pull')
async def pull_model(request: Request):
    """SSE stream del pull modello Ollama."""
    form = await request.form()
    model = form.get('model', '').strip()
    if not model:
        return HTMLResponse('<span class="text-red-400">Specifica un modello</span>')

    async def stream_pull():
        try:
            async with httpx.AsyncClient(timeout=600.0) as client:
                async with client.stream(
                    'POST',
                    f'{OLLAMA_URL}/api/pull',
                    json={'name': model}
                ) as resp:
                    async for line in resp.aiter_lines():
                        if not line:
                            continue
                        import json
                        try:
                            data = json.loads(line)
                            status = data.get('status', '')
                            total = data.get('total', 0)
                            completed = data.get('completed', 0)
                            if total > 0:
                                pct = int(completed * 100 / total)
                                mb = completed // 1_048_576
                                tot_mb = total // 1_048_576
                                bar = '█' * (pct // 5) + '░' * (20 - pct // 5)
                                msg = f'[{bar}] {pct}% ({mb}/{tot_mb} MB)'
                            else:
                                msg = status
                            yield f'data: <div class="font-mono text-xs text-green-300">{msg}</div>\n\n'
                            if status == 'success':
                                yield 'data: <div class="text-green-400 font-bold">✓ Pull completato!</div>\n\n'
                                return
                        except Exception:
                            pass
        except Exception as e:
            yield f'data: <div class="text-red-400">Errore: {e}</div>\n\n'

    return StreamingResponse(stream_pull(), media_type='text/event-stream')


@app.delete('/ollama/model/{name:path}')
async def delete_model(name: str):
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.delete(f'{OLLAMA_URL}/api/delete', json={'name': name})
            if r.status_code == 200:
                return HTMLResponse(f'<span class="text-green-400">✓ {name} eliminato</span>')
            return HTMLResponse(f'<span class="text-red-400">Errore {r.status_code}</span>')
    except Exception as e:
        return HTMLResponse(f'<span class="text-red-400">{e}</span>')


if __name__ == '__main__':
    import uvicorn
    uvicorn.run('server:app', host='0.0.0.0', port=8769, reload=False)
