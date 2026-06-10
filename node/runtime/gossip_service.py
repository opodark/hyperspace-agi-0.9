# HyperSpace-AGI v6.0 - GossipService
# Fix: self.alive, peer dedup normalizzato su node_id
from __future__ import annotations
import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Optional
import httpx

logger = logging.getLogger('gossip')

GOSSIP_INTERVAL = int(os.getenv('GOSSIP_INTERVAL_SEC', '30'))
GOSSIP_TIMEOUT  = 5.0
PEER_TTL_SEC    = 90


@dataclass
class PeerInfo:
    node_id:   str
    host:      str
    port:      int
    models:    list[str] = field(default_factory=list)
    load:      float     = 0.0
    state:     str       = 'active'
    last_seen: float     = field(default_factory=time.time)

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
    def __init__(self, self_info: PeerInfo):
        self.self_info = self_info
        self._peers: dict[str, PeerInfo] = {}
        self._task: Optional[asyncio.Task] = None
        self._load_initial_peers()

    def _load_initial_peers(self) -> None:
        """Carica peer da NODE_PEERS=host:port,host:port
        Nota: il node_id reale arriva al primo heartbeat.
        Usiamo host:port come chiave temporanea.
        """
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
                # chiave temporanea = host:port, verrà sostituita al primo heartbeat
                tmp_id = f'__bootstrap_{host}:{port}'
                self._peers[tmp_id] = PeerInfo(
                    node_id=tmp_id, host=host, port=port
                )
                logger.info(f'Gossip: bootstrap peer {host}:{port}')
            except ValueError:
                logger.warning(f'Gossip: entry peer non valida: {entry}')

    def get_peers(self) -> list[PeerInfo]:
        return [p for p in self._peers.values() if p.is_alive()]

    def get_all_peers(self) -> list[PeerInfo]:
        return list(self._peers.values())

    def register_peer(self, info: dict) -> None:
        """Registra/aggiorna peer usando node_id come chiave canonica.
        Rimuove eventuali entry bootstrap duplicate (host:port).
        """
        node_id = info.get('node_id', '').strip()
        if not node_id or node_id == self.self_info.node_id:
            return

        host = info.get('host', '')
        port = int(info.get('port', 8765))

        # rimuovi entry bootstrap per questo host:port se esiste
        bootstrap_key = f'__bootstrap_{host}:{port}'
        if bootstrap_key in self._peers:
            del self._peers[bootstrap_key]
            logger.debug(f'Gossip: rimossa entry bootstrap {bootstrap_key}')

        existing = self._peers.get(node_id)
        if existing:
            existing.host      = host or existing.host
            existing.port      = port or existing.port
            existing.models    = info.get('models', existing.models)
            existing.load      = info.get('load', existing.load)
            existing.state     = info.get('state', existing.state)
            existing.last_seen = time.time()
        else:
            self._peers[node_id] = PeerInfo(
                node_id   = node_id,
                host      = host,
                port      = port,
                models    = info.get('models', []),
                load      = info.get('load', 0.0),
                state     = info.get('state', 'active'),
                last_seen = time.time(),
            )
            logger.info(f'Gossip: nuovo peer {node_id} @ {host}:{port}')

    def update_self_state(self, state: str, load: float = 0.0) -> None:
        self.self_info.state = state
        self.self_info.load  = load

    def self_to_dict(self) -> dict:
        """Serializza self con alive=True sempre (non passa per is_alive)."""
        return {
            'node_id':   self.self_info.node_id,
            'host':      self.self_info.host,
            'port':      self.self_info.port,
            'models':    self.self_info.models,
            'load':      self.self_info.load,
            'state':     self.self_info.state,
            'last_seen': time.time(),
            'alive':     True,
        }

    async def _ping_peer(self, peer: PeerInfo) -> bool:
        try:
            async with httpx.AsyncClient(timeout=GOSSIP_TIMEOUT) as client:
                payload = self.self_to_dict()
                r = await client.post(f'{peer.url}/gossip/heartbeat', json=payload)
                if r.status_code == 200:
                    data = r.json()
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
        dead = [nid for nid, p in self._peers.items() if not p.is_alive()]
        for nid in dead:
            logger.info(f'Gossip: peer scaduto rimosso {nid}')
            del self._peers[nid]

    async def start(self) -> None:
        logger.info(f'GossipService avviato — node_id={self.self_info.node_id}')
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
