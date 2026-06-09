# HyperSpace-AGI v5.9 - Ollama Pull Service
# Esegue materialmente il pull di un modello via Ollama API
# POST /api/pull con streaming progress — attende {"status": "success"}
from __future__ import annotations
import asyncio
import httpx
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

logger = logging.getLogger('ollama_pull_service')


class PullStatus(str, Enum):
    PENDING    = 'pending'
    PULLING    = 'pulling'
    SUCCESS    = 'success'
    FAILED     = 'failed'
    ALREADY_HOT = 'already_hot'


@dataclass
class PullProgress:
    model_id: str
    status: PullStatus = PullStatus.PENDING
    completed_bytes: int = 0
    total_bytes: int = 0
    last_status_msg: str = ''
    started_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    finished_at: str | None = None
    error: str | None = None

    @property
    def percent(self) -> float:
        if self.total_bytes == 0:
            return 0.0
        return round(self.completed_bytes / self.total_bytes * 100, 1)


class OllamaPullService:
    """
    Servizio async per il pull di modelli Ollama.
    Chiama POST /api/pull con streaming JSON lines e attende completamento.
    Gestisce:
      - progress tracking (byte completati / totali)
      - timeout configurabile
      - retry su errore transitorio
      - check pre-pull se il modello e gia HOT (skip pull)
    """

    def __init__(
        self,
        ollama_url: str = 'http://ollama:11434',
        timeout_seconds: int = 600,
        max_retries: int = 2,
    ) -> None:
        self.ollama_url = ollama_url.rstrip('/')
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        # Cache locale degli ultimi pull completati: model_id -> PullProgress
        self._pull_cache: dict[str, PullProgress] = {}

    async def is_hot(self, model_id: str) -> bool:
        """
        Controlla se il modello e gia disponibile localmente via GET /api/tags.
        Evita pull inutili.
        """
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f'{self.ollama_url}/api/tags')
                resp.raise_for_status()
                models = resp.json().get('models', [])
                return any(m.get('name', '').startswith(model_id.split(':')[0]) for m in models)
        except Exception:
            return False

    async def pull(self, model_id: str, force: bool = False) -> PullProgress:
        """
        Pull principale. Se il modello e gia HOT e force=False, skip.
        Ritorna PullProgress con status finale.
        """
        # Check cache
        cached = self._pull_cache.get(model_id)
        if cached and cached.status == PullStatus.SUCCESS and not force:
            logger.info(f'[pull] {model_id} gia in cache pull SUCCESS — skip')
            cached.status = PullStatus.ALREADY_HOT
            return cached

        # Check Ollama locale
        if not force and await self.is_hot(model_id):
            progress = PullProgress(model_id=model_id, status=PullStatus.ALREADY_HOT,
                                    last_status_msg='model already present locally')
            self._pull_cache[model_id] = progress
            logger.info(f'[pull] {model_id} gia presente in Ollama — skip pull')
            return progress

        progress = PullProgress(model_id=model_id, status=PullStatus.PULLING)
        self._pull_cache[model_id] = progress

        for attempt in range(1, self.max_retries + 2):
            try:
                logger.info(f'[pull] {model_id} tentativo {attempt}/{self.max_retries + 1}')
                await self._stream_pull(model_id, progress)
                if progress.status == PullStatus.SUCCESS:
                    break
            except Exception as exc:
                progress.error = str(exc)
                logger.warning(f'[pull] {model_id} tentativo {attempt} fallito: {exc}')
                if attempt <= self.max_retries:
                    await asyncio.sleep(2 ** attempt)  # backoff esponenziale
                else:
                    progress.status = PullStatus.FAILED
                    progress.finished_at = datetime.utcnow().isoformat()

        return progress

    async def _stream_pull(self, model_id: str, progress: PullProgress) -> None:
        """
        Stream POST /api/pull, parsa ogni JSON line.
        Aggiorna progress in-place.
        Considera SUCCESS quando riceve {"status": "success"}.
        """
        payload = {'name': model_id, 'stream': True}
        timeout = httpx.Timeout(connect=10.0, read=self.timeout_seconds, write=30.0, pool=10.0)

        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream('POST', f'{self.ollama_url}/api/pull', json=payload) as resp:
                resp.raise_for_status()
                async for raw_line in resp.aiter_lines():
                    if not raw_line.strip():
                        continue
                    try:
                        event = json.loads(raw_line)
                    except json.JSONDecodeError:
                        continue

                    status_msg = event.get('status', '')
                    progress.last_status_msg = status_msg

                    # Progress bytes
                    if 'completed' in event:
                        progress.completed_bytes = int(event['completed'])
                    if 'total' in event:
                        progress.total_bytes = int(event['total'])

                    logger.debug(
                        f'[pull] {model_id} | {status_msg} | '
                        f'{progress.percent:.1f}% ({progress.completed_bytes}/{progress.total_bytes})'
                    )

                    if status_msg == 'success':
                        progress.status = PullStatus.SUCCESS
                        progress.finished_at = datetime.utcnow().isoformat()
                        logger.info(f'[pull] {model_id} COMPLETATO ✓')
                        return

                    # Errore esplicito dal server
                    if 'error' in event:
                        raise RuntimeError(f'Ollama pull error: {event["error"]}')

        # Se lo stream termina senza success esplicito
        raise RuntimeError(f'Stream terminato senza status=success per {model_id}')

    def get_progress(self, model_id: str) -> PullProgress | None:
        """Stato corrente di un pull in corso o completato."""
        return self._pull_cache.get(model_id)

    def all_progress(self) -> list[PullProgress]:
        """Lista tutti i pull registrati."""
        return list(self._pull_cache.values())
