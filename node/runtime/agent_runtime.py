# HyperSpace-AGI v5.9 - Agent Runtime
# Memory injection + control-plane /v1/chat/completions
from __future__ import annotations
import httpx
from datetime import datetime
from shared.domain.models import (
    ChatMessage, UserRequest, RequestFeatures, MemoryRecord, MemoryTier,
)
from shared.settings import settings
from node.memory.tiered_store import TieredMemoryStore


class AgentRuntime:
    """
    Runtime principale node v5.9.
    Flow: memory search -> system prompt injection -> control-plane -> save EPISODIC
    """

    def __init__(self, memory_store: TieredMemoryStore | None = None,
                 control_plane_url: str | None = None) -> None:
        self.memory = memory_store or TieredMemoryStore()
        self.cp_url = control_plane_url or f'http://control-plane:{settings.control_plane_api_port}'

    async def run(self, session_id: str, user_message: str,
                  model_alias: str = 'auto', system_prompt: str | None = None) -> str:
        """Esegue un turn conversazionale con memory injection."""
        context_records = await self.memory.search(
            session_id=session_id, query=user_message, k=5,
            tiers=(MemoryTier.SEMANTIC, MemoryTier.EPISODIC),
        )
        mem_context = '\n'.join(
            f'[{r.tier.value}] {r.role}: {r.content}' for r in context_records
        )
        base_system = system_prompt or 'You are a helpful HyperSpace-AGI agent.'
        full_system = (
            f'{base_system}\n\n## Memory Context\n{mem_context}' if mem_context else base_system
        )
        messages = [
            ChatMessage(role='system', content=full_system),
            ChatMessage(role='user', content=user_message),
        ]
        response_text = await self._call_control_plane(
            UserRequest(model_alias=model_alias, messages=messages, features=RequestFeatures())
        )
        await self.memory.add(MemoryRecord(
            session_id=session_id, role='user', content=user_message, tier=MemoryTier.EPISODIC, score=0.5,
        ))
        await self.memory.add(MemoryRecord(
            session_id=session_id, role='assistant', content=response_text, tier=MemoryTier.EPISODIC, score=0.5,
        ))
        return response_text

    async def _call_control_plane(self, request: UserRequest) -> str:
        payload = {
            'model': request.model_alias,
            'messages': [m.model_dump() for m in request.messages],
            'stream': False,
        }
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(f'{self.cp_url}/v1/chat/completions', json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data.get('message', {}).get('content', data.get('response', ''))
