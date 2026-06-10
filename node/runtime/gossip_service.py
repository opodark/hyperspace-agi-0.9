# HyperSpace-AGI v6.0 - GossipService con naming completo
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
    # --- identità tecnica ---
    node_id:   str
    host:      str
    port:      int
    # --- naming / metadati ---
    nickname:  str        = ''
    location:  str        = ''
    tags:      list[str]  = field(default_factory=list)
    owner:     str        = ''
    color:     str        = '#7c3aed'   # hex, usato nella UI
    # --- runtime ---
    models:    list[str]  = field(default_factory=list)
    load:      float      = 0.0
    state:     str        = 'active'
    last_seen: float      = field(default_factory=time.time)

    @property
    def url(self) -> str:
        return f'http://{self.host}:{self.port}'

    def is_alive(self) -> bool:
        return (time.time() - self.last_seen) < PEER_TTL_SEC

    def display_name(self) -> str:
        return self.nickname if self.nickname else self.node_id

    def to_dict(self) -> dict:
        return {
            'node_id':   self.node_id,
            'host':      self.host,
            'port':      self.port,
            'nickname':  self.nickname,
            'location':  self.location,
            'tags':      self.tags,
            'owner':     self.owner,
            'color':     self.color,
            'models':    self.models,
            'load':      self.load,
            'state':     self.state,
            'last_seen': self.last_seen,
            'alive':     self.is_alive(),
        }

    @classmethod
    def from_dict(cls, d: dict) -> 'PeerInfo':
        return cls(
            node_id  = d.get('node_id', ''),
            host     = d.get('host', ''),
            port     = int(d.get('port', 8765)),
            nickname = d.get('nickname', ''),
            location = d.get('location', ''),
            tags     = d.get('tags', []),
            owner    = d.get('owner', ''),
            color    = d.get('color', '#7c3aed'),
            models   = d.get('models', []),
            load     = d.get('load', 0.0),
            state    = d.get('state', 'active'),
            last_seen= time.time(),
        )

    @classmethod
    def from_env(cls, node_id: str, host: str, port: int, models: list[str]) -> 'PeerInfo':
        """Costruisce PeerInfo leggendo le env di naming."""
        raw_tags = os.getenv('NODE_TAGS', '')
        tags = [t.strip() for t in raw_tags.split(',') if t.strip()]
        return cls(
            node_id  = node_id,
            host     = host,
            port     = port,
            models   = models,
            nickname = os.getenv('NODE_NICKNAME', ''),
            location = os.getenv('NODE_LOCATION', ''),
            tags     = tags,
            owner    = os.getenv('NODE_OWNER', ''),
            color    = os.getenv('NODE_COLOR', '#7c3aed'),
        )


class GossipService:
    def __init__(self, self_info: PeerInfo):
        self.self_info = self_info
        self._peers: dict[str, PeerInfo] = {}
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
                tmp_id = f'__bootstrap_{host}:{port}'
                self._peers[tmp_id] = PeerInfo(
                    node_id=tmp_id, host=host, port=port
                )
                logger.info(f'Gossip: bootstrap peer {host}:{port}')
            except ValueError:
                logger.warning(f'Gossip: entry non valida: {entry}')

    def get_peers(self) -> list[PeerInfo]:
        return [p for p in self._peers.values() if p.is_alive()]

    def get_all_peers(self) -> list[PeerInfo]:
        return list(self._peers.values())

    def register_peer(self, info: dict) -> None:
        node_id = info.get('node_id', '').strip()
        if not node_id or node_id == self.self_info.node_id:
            return

        host = info.get('host', '')
        port = int(info.get('port', 8765))

        # rimuovi entry bootstrap per questo host:port
        bootstrap_key = f'__bootstrap_{host}:{port}'
        if bootstrap_key in self._peers:
            del self._peers[bootstrap_key]

        existing = self._peers.get(node_id)
        if existing:
            # aggiorna tutti i campi inclusi naming
            existing.host      = host or existing.host
            existing.port      = port or existing.port
            existing.nickname  = info.get('nickname', existing.nickname)
            existing.location  = info.get('location', existing.location)
            existing.tags      = info.get('tags', existing.tags)
            existing.owner     = info.get('owner', existing.owner)
            existing.color     = info.get('color', existing.color)
            existing.models    = info.get('models', existing.models)
            existing.load      = info.get('load', existing.load)
            existing.state     = info.get('state', existing.state)
            existing.last_seen = time.time()
        else:
            self._peers[node_id] = PeerInfo.from_dict(info)
            logger.info(f'Gossip: nuovo peer "{info.get("nickname") or node_id}" [{node_id}] @ {host}:{port}')

    def update_self_state(self, state: str, load: float = 0.0) -> None:
        self.self_info.state = state
        self.self_info.load  = load

    def self_to_dict(self) -> dict:
        d = self.self_info.to_dict()
        d['last_seen'] = time.time()
        d['alive']     = True
        return d

    async def _ping_peer(self, peer: PeerInfo) -> bool:
        try:
            async with httpx.AsyncClient(timeout=GOSSIP_TIMEOUT) as client:
                r = await client.post(f'{peer.url}/gossip/heartbeat', json=self.self_to_dict())
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
        logger.debug(f'Gossip round: {alive}/{len(peers)} alive')
        dead = [nid for nid, p in self._peers.items() if not p.is_alive()]
        for nid in dead:
            logger.info(f'Gossip: peer scaduto rimosso {nid}')
            del self._peers[nid]

    async def start(self) -> None:
        logger.info(
            f'GossipService avviato — '
            f'node_id={self.self_info.node_id} '
            f'nickname="{self.self_info.nickname}" '
            f'owner={self.self_info.owner}'
        )
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
