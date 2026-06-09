# HyperSpace-AGI v5.9 - Vector Stub (v5.8 compat)
from __future__ import annotations
from shared.domain.models import MemoryRecord


class VectorStub:
    """Stub no-op per vector search. Compatibile v5.8."""

    async def add(self, record: MemoryRecord) -> None:
        pass

    async def search(self, query: str, k: int = 3) -> list[MemoryRecord]:
        return []

    async def delete(self, memory_id: str) -> None:
        pass
