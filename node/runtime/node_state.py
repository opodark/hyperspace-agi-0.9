# HyperSpace-AGI v6.0 - NodeState
# Stato globale del nodo: dreaming/sleeping/active + metriche
from __future__ import annotations
import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DreamEntry:
    dream_id:   str
    content:    str
    score:      float
    votes:      int   = 0
    votes_needed: int = 3
    status:     str   = 'pending'   # pending | promoted | retracted | contested
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            'dream_id':     self.dream_id,
            'content':      self.content[:80] + '...' if len(self.content) > 80 else self.content,
            'score':        round(self.score, 3),
            'votes':        self.votes,
            'votes_needed': self.votes_needed,
            'status':       self.status,
            'age_sec':      round(time.time() - self.created_at),
        }


class NodeStateManager:
    """
    Traccia lo stato operativo del nodo:
    - active:   elabora richieste
    - sleeping: idle, memoria in consolidamento
    - dreaming: DreamReplayEngine attivo
    """

    def __init__(self, node_id: str):
        self.node_id        = node_id
        self.state          = 'active'
        self.load           = 0.0
        self.active_dreams: dict[str, DreamEntry] = {}
        self.dream_history: list[DreamEntry]      = []
        self._request_count = 0
        self._last_request  = time.time()

    def record_request(self) -> None:
        self._request_count += 1
        self._last_request = time.time()
        self._update_state()

    def add_dream(self, dream: DreamEntry) -> None:
        self.active_dreams[dream.dream_id] = dream
        self.state = 'dreaming'

    def resolve_dream(self, dream_id: str, status: str) -> Optional[DreamEntry]:
        dream = self.active_dreams.pop(dream_id, None)
        if dream:
            dream.status = status
            self.dream_history.append(dream)
        if not self.active_dreams:
            self._update_state()
        return dream

    def vote_dream(self, dream_id: str) -> Optional[DreamEntry]:
        dream = self.active_dreams.get(dream_id)
        if dream:
            dream.votes += 1
            if dream.votes >= dream.votes_needed:
                return self.resolve_dream(dream_id, 'promoted')
        return dream

    def _update_state(self) -> None:
        idle_sec = time.time() - self._last_request
        if self.active_dreams:
            self.state = 'dreaming'
        elif idle_sec > 120:
            self.state = 'sleeping'
        else:
            self.state = 'active'

    def get_status(self) -> dict:
        self._update_state()
        return {
            'node_id':       self.node_id,
            'state':         self.state,
            'load':          round(self.load, 2),
            'request_count': self._request_count,
            'active_dreams': [d.to_dict() for d in self.active_dreams.values()],
            'dream_history': [d.to_dict() for d in self.dream_history[-10:]],
        }
