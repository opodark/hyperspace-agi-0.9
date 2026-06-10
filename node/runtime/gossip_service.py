# HyperSpace-AGI v6.0 - GossipService con seed bootstrap via Authority
from __future__ import annotations
import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Optional
import httpx

logger = logging.getLogger('gossip')

GOSSIP_INTERVAL  = int(os.getenv('GOSSIP_INTERVAL_SEC', '30'))
ANNOUNCE_INTERVAL = int(os.getenv('ANNOUNCE_INTERVAL_SEC', '60'))  # ri-annuncio all'Authority
GOSSIP_TIMEOUT   = 5.0
PEER_TTL_SEC     = 90
AUTHORITY_URL    = os.getenv('AUTHORITY_URL', 'http://authority:8766')


@dataclass
class PeerInfo:
    node_id:   str
    host:      str
    port:      int
    nickname:  str        = ''
    location:  str        = ''
    tags:      list[str]  = field(default_factory=list)
    owner:     str        = ''
    color:     str        = '#7c3aed'
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
            node_id   = d.get('node_id', ''),
            host      = d.get('host', ''),
            port      = int(d.get('port', 8765)),
            nickname  = d.get('nickname', ''),
            location  = d.get('location', ''),
            tags      = d.get('tags', []),
            owner     = d.get('owner', ''),
            color     = d.get('color', '#7c3aed'),
            models    = d.get('models', []),
            load      = d.get('load', 0.0),
            state     = d.get('state', 'active'),
            last_seen = time.time(),
        )

    @classmethod
    def from_env(cls, node_id: str, host: str, port: int, models: list[str]) -> 'PeerInfo':
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
        self.self_info  = self_info
        self._peers: dict[str, PeerInfo] = {}
        self._task_gossip:   Optional[asyncio.Task] = None
        self._task_announce: Optional[asyncio.Task] = None
        self._load_static_peers()

    def _load_static_peers(self) -> None:
        """Bootstrap statico da NODE_PEERS (fallback se Authority non raggiungibile)."""
        raw = os.getenv('NODE_PEERS', '')
        if not raw:
            return
        for entry in raw.split(','):
            entry = entry.strip()
            if not entry:
                continue
            try:
                host, port_s = entry.rsplit(':', 1)
                port   = int(port_s)
                tmp_id = f'__bootstrap_{host}:{port}'
                self._peers[tmp_id] = PeerInfo(node_id=tmp_id, host=host, port=port)
                logger.info(f'Gossip: bootstrap statico {host}:{port}')
            except ValueError:
                logger.warning(f'Gossip: entry non valida: {entry}')

    # ── Authority seed bootstrap ────────────────────────────────────────────────

    async def announce_to_authority(self) -> bool:
        """
        Annuncia sé stesso all'Authority e ottiene la peer table.
        Chiamato al boot e ogni ANNOUNCE_INTERVAL secondi.
        Restituisce True se il seed ha risposto.
        """
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                r = await client.post(
                    f'{AUTHORITY_URL}/peers/announce',
                    json=self.self_to_dict()
                )
                if r.status_code == 200:
                    data = r.json()
                    peers_from_seed = data.get('peers', [])
                    for p in peers_from_seed:
                        self.register_peer(p)
                    logger.info(
                        f'Gossip: annunciato a Authority — '
                        f'ricevuti {len(peers_from_seed)} peer dal seed'
                    )
                    return True
        except Exception as e:
            logger.warning(f'Gossip: Authority non raggiungibile: {e}')
        return False

    # ── Peer management ───────────────────────────────────────────────────────────

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

        bootstrap_key = f'__bootstrap_{host}:{port}'
        if bootstrap_key in self._peers:
            del self._peers[bootstrap_key]

        existing = self._peers.get(node_id)
        if existing:
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
            logger.info(
                f'Gossip: nuovo peer "{info.get("nickname") or node_id}" '
                f'[{node_id}] @ {host}:{port}'
            )

    def update_self_state(self, state: str, load: float = 0.0) -> None:
        self.self_info.state = state
        self.self_info.load  = load

    def self_to_dict(self) -> dict:
        d = self.self_info.to_dict()
        d['last_seen'] = time.time()
        d['alive']     = True
        return d

    # ── Gossip loop ───────────────────────────────────────────────────────────────────

    async def _ping_peer(self, peer: PeerInfo) -> bool:
        try:
            async with httpx.AsyncClient(timeout=GOSSIP_TIMEOUT) as client:
                r = await client.post(
                    f'{peer.url}/gossip/heartbeat',
                    json=self.self_to_dict()
                )
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

    # ── Lifecycle ──────────────────────────────────────────────────────────────────────

    async def start(self) -> None:
        logger.info(
            f'GossipService avviato — '
            f'{self.self_info.node_id} '
            f'("{self.self_info.display_name()}")'
        )
        # 1. annuncio immediato all'Authority per il bootstrap
        await self.announce_to_authority()
        # 2. primo round gossip subito dopo
        await self._gossip_round()
        # 3. loop gossip periodico
        self._task_gossip   = asyncio.create_task(self._gossip_loop())
        # 4. loop ri-annuncio periodico all'Authority
        self._task_announce = asyncio.create_task(self._announce_loop())

    async def _gossip_loop(self) -> None:
        while True:
            await asyncio.sleep(GOSSIP_INTERVAL)
            try:
                await self._gossip_round()
            except Exception as e:
                logger.error(f'Gossip loop error: {e}')

    async def _announce_loop(self) -> None:
        while True:
            await asyncio.sleep(ANNOUNCE_INTERVAL)
            try:
                await self.announce_to_authority()
            except Exception as e:
                logger.error(f'Announce loop error: {e}')

    async def stop(self) -> None:
        for task in [self._task_gossip, self._task_announce]:
            if task:
                task.cancel()
