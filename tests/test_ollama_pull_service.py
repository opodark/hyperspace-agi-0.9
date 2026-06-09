# HyperSpace-AGI v5.9 - Smoke tests: OllamaPullService
import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from node.ollama_pull_service import OllamaPullService, PullStatus


@pytest.fixture
def svc() -> OllamaPullService:
    return OllamaPullService(ollama_url='http://localhost:11434', timeout_seconds=30)


@pytest.mark.asyncio
async def test_already_hot_skip_pull(svc):
    """Se il modello e gia presente, non deve partire il pull."""
    with patch.object(svc, 'is_hot', new=AsyncMock(return_value=True)):
        progress = await svc.pull('qwen3.5:7b')
    assert progress.status == PullStatus.ALREADY_HOT


@pytest.mark.asyncio
async def test_pull_success(svc):
    """Simula uno stream pull con status=success."""
    # Mock stream con 3 linee: pulling + progress + success
    stream_lines = [
        '{"status": "pulling manifest"}',
        '{"status": "downloading", "completed": 500, "total": 1000}',
        '{"status": "success"}',
    ]

    async def fake_stream(*args, **kwargs):
        class FakeResponse:
            status_code = 200
            async def __aenter__(self): return self
            async def __aexit__(self, *a): pass
            def raise_for_status(self): pass
            async def aiter_lines(self):
                for line in stream_lines:
                    yield line
        return FakeResponse()

    with patch.object(svc, 'is_hot', new=AsyncMock(return_value=False)):
        with patch('httpx.AsyncClient.stream', new=fake_stream):
            progress = await svc.pull('batiai/gemma4-12b:q4')

    assert progress.status == PullStatus.SUCCESS
    assert progress.percent == 50.0
    assert progress.finished_at is not None


@pytest.mark.asyncio
async def test_pull_failed_max_retries(svc):
    """Simula errore persistente dopo max_retries."""
    svc.max_retries = 1

    with patch.object(svc, 'is_hot', new=AsyncMock(return_value=False)):
        with patch.object(svc, '_stream_pull', new=AsyncMock(side_effect=RuntimeError('network error'))):
            progress = await svc.pull('some-model:7b')

    assert progress.status == PullStatus.FAILED
    assert progress.error is not None


@pytest.mark.asyncio
async def test_get_progress_after_pull(svc):
    """Verifica che il progresso sia accessibile dopo il pull."""
    with patch.object(svc, 'is_hot', new=AsyncMock(return_value=True)):
        await svc.pull('qwen3.5:7b')
    prog = svc.get_progress('qwen3.5:7b')
    assert prog is not None
    assert prog.model_id == 'qwen3.5:7b'
