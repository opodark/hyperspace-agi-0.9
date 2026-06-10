# HyperSpace-AGI v6.0 - NodeState + SharedDream propagation
from __future__ import annotations
import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DreamEntry:
    dream_id:     str
    content:      str
    score:        float
    origin_node:  str   = ''        # nodo che ha creato il dream
    votes:        int   = 0
    votes_needed: int   = 3
    status:       str   = 'pending' # pending|promoted|retracted|contested
    created_at:   float = field(default_factory=time.time)
    voters:       list  = field(default_factory=list)  # node_id che hanno votato

    def to_dict(self) -> dict:
        return {
            'dream_id':     self.dream_id,
            'content':      self.content[:80] + '...' if len(self.content) > 80 else self.content,
            'score':        round(self.score, 3),
            'origin_node':  self.origin_node,
            'votes':        self.votes,
            'votes_needed': self.votes_needed,
            'status':       self.status,
            'age_sec':      round(time.time() - self.created_at),
            'voters':       self.voters,
        }

    @classmethod
    def from_dict(cls, d: dict) -> 'DreamEntry':
        return cls(
            dream_id     = d.get('dream_id', ''),
            content      = d.get('content', ''),
            score        = d.get('score', 0.5),
            origin_node  = d.get('origin_node', ''),
            votes        = d.get('votes', 0),
            votes_needed = d.get('votes_needed', 3),
            status       = d.get('status', 'pending'),
            voters       = d.get('voters', []),
        )


class NodeStateManager:
    def __init__(self, node_id: str):
        self.node_id         = node_id
        self.state           = 'active'
        self.load            = 0.0
        self.active_dreams:  dict[str, DreamEntry] = {}
        self.dream_history:  list[DreamEntry]      = []
        self._request_count  = 0
        self._last_request   = time.time()

    def record_request(self) -> None:
        self._request_count += 1
        self._last_request = time.time()
        self._update_state()

    def add_dream(self, dream: DreamEntry) -> None:
        """Aggiunge un dream (locale o ricevuto da peer)."""
        if dream.dream_id not in self.active_dreams:
            if not dream.origin_node:
                dream.origin_node = self.node_id
            self.active_dreams[dream.dream_id] = dream
            if dream.origin_node == self.node_id:
                self.state = 'dreaming'

    def receive_dream(self, data: dict) -> Optional[DreamEntry]:
        """Riceve un dream da un peer via gossip. Restituisce None se già noto."""
        dream_id = data.get('dream_id', '')
        if dream_id in self.active_dreams:
            # aggiorna voti se il peer è più avanti
            existing = self.active_dreams[dream_id]
            if data.get('votes', 0) > existing.votes:
                existing.votes  = data['votes']
                existing.voters = data.get('voters', existing.voters)
            return None
        dream = DreamEntry.from_dict(data)
        self.active_dreams[dream_id] = dream
        return dream

    def vote_dream(self, dream_id: str, voter_node: str = '') -> Optional[DreamEntry]:
        dream = self.active_dreams.get(dream_id)
        if dream:
            if voter_node and voter_node in dream.voters:
                return dream  # già votato
            dream.votes += 1
            if voter_node:
                dream.voters.append(voter_node)
            if dream.votes >= dream.votes_needed:
                return self.resolve_dream(dream_id, 'promoted')
        return dream

    def resolve_dream(self, dream_id: str, status: str) -> Optional[DreamEntry]:
        dream = self.active_dreams.pop(dream_id, None)
        if dream:
            dream.status = status
            self.dream_history.append(dream)
        if not self.active_dreams:
            self._update_state()
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
