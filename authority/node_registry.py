# HyperSpace-AGI v6.0 - NodeRegistry
# Store in-memory dei nodi annunciati, con TTL e cleanup automatico.
from __future__ import annotations
import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger('node_registry')

NODE_TTL_SEC     = 120   # nodo rimosso se non si riannuncia entro 120s
CLEANUP_INTERVAL = 60    # pulizia ogni 60s


@dataclass
class NodeEntry:
    node_id:   str
    host:      str
    port:      int
    nickname:  str       = ''
    location:  str       = ''
    tags:      list[str] = field(default_factory=list)
    owner:     str       = ''
    color:     str       = '#7c3aed'
    models:    list[str] = field(default_factory=list)
    load:      float     = 0.0
    state:     str       = 'active'
    announced_at: float  = field(default_factory=time.time)
    last_seen:    float  = field(default_factory=time.time)

    def is_alive(self) -> bool:
        return (time.time() - self.last_seen) < NODE_TTL_SEC

    def to_dict(self) -> dict:
        return {
            'node_id':      self.node_id,
            'host':         self.host,
            'port':         self.port,
            'nickname':     self.nickname,
            'location':     self.location,
            'tags':         self.tags,
            'owner':        self.owner,
            'color':        self.color,
            'models':       self.models,
            'load':         self.load,
            'state':        self.state,
            'last_seen':    self.last_seen,
            'alive':        self.is_alive(),
            'uptime_sec':   round(time.time() - self.announced_at),
        }


class NodeRegistry:
    """
    Registro centralizzato dei nodi della rete HyperSpace.
    Ogni nodo si annuncia al boot e periodicamente (heartbeat).
    L'Authority risponde con la peer table completa → bootstrap P2P.
    """

    def __init__(self):
        self._nodes: dict[str, NodeEntry] = {}
        self._task: Optional[asyncio.Task] = None

    def announce(self, data: dict) -> NodeEntry:
        """Registra o aggiorna un nodo. Restituisce l'entry aggiornata."""
        node_id = data.get('node_id', '').strip()
        if not node_id:
            raise ValueError('node_id mancante')

        existing = self._nodes.get(node_id)
        if existing:
            existing.host     = data.get('host', existing.host)
            existing.port     = int(data.get('port', existing.port))
            existing.nickname = data.get('nickname', existing.nickname)
            existing.location = data.get('location', existing.location)
            existing.tags     = data.get('tags', existing.tags)
            existing.owner    = data.get('owner', existing.owner)
            existing.color    = data.get('color', existing.color)
            existing.models   = data.get('models', existing.models)
            existing.load     = data.get('load', existing.load)
            existing.state    = data.get('state', existing.state)
            existing.last_seen = time.time()
            logger.debug(f'NodeRegistry: aggiornato {node_id}')
            return existing
        else:
            entry = NodeEntry(
                node_id  = node_id,
                host     = data.get('host', ''),
                port     = int(data.get('port', 8765)),
                nickname = data.get('nickname', ''),
                location = data.get('location', ''),
                tags     = data.get('tags', []),
                owner    = data.get('owner', ''),
                color    = data.get('color', '#7c3aed'),
                models   = data.get('models', []),
                load     = data.get('load', 0.0),
                state    = data.get('state', 'active'),
            )
            self._nodes[node_id] = entry
            logger.info(
                f'NodeRegistry: nuovo nodo "{entry.nickname or node_id}" '
                f'[{node_id}] @ {entry.host}:{entry.port}'
            )
            return entry

    def get_all(self, alive_only: bool = True) -> list[NodeEntry]:
        nodes = list(self._nodes.values())
        if alive_only:
            nodes = [n for n in nodes if n.is_alive()]
        return sorted(nodes, key=lambda n: n.last_seen, reverse=True)

    def get(self, node_id: str) -> Optional[NodeEntry]:
        return self._nodes.get(node_id)

    def remove(self, node_id: str) -> bool:
        if node_id in self._nodes:
            del self._nodes[node_id]
            logger.info(f'NodeRegistry: rimosso {node_id}')
            return True
        return False

    async def start_cleanup(self) -> None:
        self._task = asyncio.create_task(self._cleanup_loop())
        logger.info('NodeRegistry: cleanup task avviato')

    async def stop_cleanup(self) -> None:
        if self._task:
            self._task.cancel()

    async def _cleanup_loop(self) -> None:
        while True:
            await asyncio.sleep(CLEANUP_INTERVAL)
            dead = [nid for nid, n in self._nodes.items() if not n.is_alive()]
            for nid in dead:
                logger.info(f'NodeRegistry: TTL scaduto, rimosso {nid}')
                del self._nodes[nid]


# singleton
node_registry = NodeRegistry()
