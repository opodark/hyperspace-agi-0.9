# HyperSpace-AGI v6.0 - GossipService
# Ciclo 30s: ogni nodo fa ping ai peer noti e propaga la peer_table
from __future__ import annotations
import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Optional
import httpx

logger = logging.getLogger('gossip')

GOSSIP_INTERVAL   = int(os.getenv('GOSSIP_INTERVAL_SEC', '30'))
GOSSIP_TIMEOUT    = 5.0
PEER_TTL_SEC      = 90   # nodo rimosso se silenzioso per 90s


@dataclass
class PeerInfo:
    node_id:    str
    host:       str
    port:       int
    models:     list[str]  = field(default_factory=list)
    load:       float      = 0.0          # 0.0 - 1.0
    state:      str        = 'active'     # active | sleeping | dreaming
    last_seen:  float      = field(default_factory=time.time)

    @property
    def url(self) -> str:
        return f'http://{self.host}:{self.port}'

    def is_alive(self) -> bool:
        return (time.time() - self.last_seen) < PEER_TTL_SEC

    def to_dict(self) -> dict:
        return {
            'node_id':   self.node_id,
            'host':      self.host,
            'port':      self.port,
            'models':    self.models,
            'load':      self.load,
            'state':     self.state,
            'last_seen': self.last_seen,
            'alive':     self.is_alive(),
        }


class GossipService:
    """
    Gestisce il discovery e la propagazione delle info di stato tra nodi.
    Ogni nodo conosce i suoi peer via env NODE_PEERS=host:port,host:port
    e li pinga ogni GOSSIP_INTERVAL secondi.
    """

    def __init__(self, self_info: PeerInfo):
        self.self_info = self_info
        self._peers: dict[str, PeerInfo] = {}   # node_id -> PeerInfo
        self._task: Optional[asyncio.Task] = None
        self._load_initial_peers()

    def _load_initial_peers(self) -> None:
        raw = os.getenv('NODE_PEERS', '')
        if not raw:
            return
        for entry in raw.split(','):
            entry = entry.strip()
            if not entry:
                continue
            try:
                host, port_s = entry.rsplit(':', 1)
                port = int(port_s)
                peer_id = f'{host}:{port}'
                self._peers[peer_id] = PeerInfo(
                    node_id=peer_id, host=host, port=port
                )
                logger.info(f'Gossip: peer iniziale registrato {peer_id}')
            except ValueError:
                logger.warning(f'Gossip: entry peer non valida: {entry}')

    def get_peers(self) -> list[PeerInfo]:
        return [p for p in self._peers.values() if p.is_alive()]

    def get_all_peers(self) -> list[PeerInfo]:
        return list(self._peers.values())

    def register_peer(self, info: dict) -> None:
        """Registra o aggiorna un peer dal suo heartbeat."""
        node_id = info.get('node_id')
        if not node_id or node_id == self.self_info.node_id:
            return
        existing = self._peers.get(node_id)
        if existing:
            existing.models    = info.get('models', existing.models)
            existing.load      = info.get('load', existing.load)
            existing.state     = info.get('state', existing.state)
            existing.last_seen = time.time()
        else:
            self._peers[node_id] = PeerInfo(
                node_id  = node_id,
                host     = info.get('host', ''),
                port     = int(info.get('port', 8765)),
                models   = info.get('models', []),
                load     = info.get('load', 0.0),
                state    = info.get('state', 'active'),
                last_seen= time.time(),
            )
            logger.info(f'Gossip: nuovo peer scoperto {node_id}')

    def update_self_state(self, state: str, load: float = 0.0) -> None:
        self.self_info.state = state
        self.self_info.load  = load

    async def _ping_peer(self, peer: PeerInfo) -> bool:
        try:
            async with httpx.AsyncClient(timeout=GOSSIP_TIMEOUT) as client:
                payload = self.self_info.to_dict()
                r = await client.post(f'{peer.url}/gossip/heartbeat', json=payload)
                if r.status_code == 200:
                    data = r.json()
                    # propaga i peer che il peer conosce
                    for p in data.get('peers', []):
                        self.register_peer(p)
                    peer.last_seen = time.time()
                    peer.state     = data.get('state', peer.state)
                    peer.load      = data.get('load', peer.load)
                    return True
        except Exception as e:
            logger.debug(f'Gossip: ping fallito {peer.node_id}: {e}')
        return False

    async def _gossip_round(self) -> None:
        peers = list(self._peers.values())
        if not peers:
            return
        results = await asyncio.gather(
            *[self._ping_peer(p) for p in peers],
            return_exceptions=True
        )
        alive = sum(1 for r in results if r is True)
        logger.debug(f'Gossip round: {alive}/{len(peers)} peer alive')
        # pulizia peer scaduti
        dead = [nid for nid, p in self._peers.items() if not p.is_alive()]
        for nid in dead:
            logger.info(f'Gossip: peer scaduto rimosso {nid}')
            del self._peers[nid]

    async def start(self) -> None:
        logger.info(f'GossipService avviato - node_id={self.self_info.node_id}')
        self._task = asyncio.create_task(self._loop())

    async def _loop(self) -> None:
        while True:
            try:
                await self._gossip_round()
            except Exception as e:
                logger.error(f'Gossip loop error: {e}')
            await asyncio.sleep(GOSSIP_INTERVAL)

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
