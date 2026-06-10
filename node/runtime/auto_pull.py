# HyperSpace-AGI v6.0 - AutoPull
# Al boot, seleziona e scarica automaticamente i modelli adatti alla RAM del nodo.
from __future__ import annotations
import asyncio
import logging
import os
import httpx

logger = logging.getLogger('auto_pull')

OLLAMA_URL  = os.getenv('OLLAMA_BASE_URL', 'http://ollama:11434')
NODE_RAM_GB = float(os.getenv('NODE_RAM_GB', '0'))  # 0 = disabilitato
AUTHORITY   = os.getenv('AUTHORITY_URL', 'http://authority:8766')

# Ruoli da garantire sul nodo, in ordine di priorità
TARGET_ROLES = ['agent', 'coder', 'reasoner', 'reasoner_large', 'agent_large', 'small']


async def get_installed_models() -> set[str]:
    """Restituisce i tag dei modelli già installati su Ollama."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(f'{OLLAMA_URL}/api/tags')
            if r.status_code == 200:
                return {m['name'] for m in r.json().get('models', [])}
    except Exception as e:
        logger.warning(f'AutoPull: impossibile leggere modelli installati: {e}')
    return set()


async def pull_model(tag: str) -> bool:
    """Scarica un modello da Ollama. Restituisce True se completato."""
    logger.info(f'AutoPull: inizio pull {tag}')
    try:
        async with httpx.AsyncClient(timeout=1800.0) as client:  # 30min max
            async with client.stream('POST', f'{OLLAMA_URL}/api/pull',
                                     json={'name': tag}) as resp:
                async for line in resp.aiter_lines():
                    if '"status":"success"' in line:
                        logger.info(f'AutoPull: {tag} completato ✅')
                        return True
        return False
    except Exception as e:
        logger.error(f'AutoPull: errore pull {tag}: {e}')
        return False


async def run_auto_pull() -> dict:
    """
    Punto di ingresso principale.
    - Legge NODE_RAM_GB dall'env
    - Chiede al catalog di Authority i modelli adatti
    - Scarica solo quelli mancanti
    """
    if NODE_RAM_GB <= 0:
        logger.info('AutoPull: NODE_RAM_GB non impostato, skip')
        return {'status': 'skipped', 'reason': 'NODE_RAM_GB not set'}

    logger.info(f'AutoPull: RAM disponibile = {NODE_RAM_GB}GB')

    # chiedi al catalog quali modelli entrano nella RAM
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            r = await client.get(f'{AUTHORITY}/catalog/ram/{NODE_RAM_GB}')
            if r.status_code != 200:
                logger.warning('AutoPull: catalog non raggiungibile')
                return {'status': 'error', 'reason': 'catalog unreachable'}
            catalog_models = r.json().get('models', [])
    except Exception as e:
        logger.warning(f'AutoPull: Authority non raggiungibile: {e}')
        return {'status': 'error', 'reason': str(e)}

    installed = await get_installed_models()
    to_pull   = [
        m for m in catalog_models
        if m['ollama_tag'] not in installed
    ]

    if not to_pull:
        logger.info('AutoPull: tutti i modelli già installati ✅')
        return {'status': 'ok', 'pulled': [], 'already_installed': len(installed)}

    logger.info(f'AutoPull: {len(to_pull)} modelli da scaricare: '
                f'{[m["ollama_tag"] for m in to_pull]}')

    pulled, failed = [], []
    for m in to_pull:
        ok = await pull_model(m['ollama_tag'])
        (pulled if ok else failed).append(m['ollama_tag'])

    return {
        'status':    'ok',
        'ram_gb':    NODE_RAM_GB,
        'pulled':    pulled,
        'failed':    failed,
        'installed': list(installed),
    }
