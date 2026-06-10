# Changelog — HyperSpace-AGI

Tutte le modifiche rilevanti al progetto sono documentate in questo file.
Formato: [Keep a Changelog](https://keepachangelog.com/it/1.0.0/)

---

## [6.0.0] — 2026-06-10

### ✨ Aggiunto

**P2P Network — Authority Seed Bootstrap**
- `authority/node_registry.py` — NodeRegistry con TTL (90s), cleanup automatico
- `POST /peers/announce` — nodo si registra e riceve lista peer attivi
- `GET /peers` — lista nodi registrati (filtro alive_only)
- Al boot ogni nodo annuncia sé stesso all'Authority e riceve i peer
- Re-annuncio automatico ogni 60s (`ANNOUNCE_INTERVAL_SEC`)
- `NODE_PEERS` mantenuto come fallback statico se Authority non raggiungibile

**P2P Network — Gossip Protocol**
- `node/runtime/gossip_service.py` — GossipService completo con fan-out
- Heartbeat ogni 30s tra nodi (`GOSSIP_INTERVAL_SEC`)
- Propagazione peer list ad ogni heartbeat
- Rimozione automatica peer scaduti (TTL 90s)
- `POST /gossip/heartbeat` su ogni nodo
- `GET /gossip/peers` — stato rete dal punto di vista del nodo

**Node Identity & Avatars**
- `PeerInfo` estesa: `nickname`, `location`, `tags`, `owner`, `color`, `avatar_style`
- Variabili env: `NODE_NICKNAME`, `NODE_LOCATION`, `NODE_TAGS`, `NODE_OWNER`, `NODE_COLOR`, `NODE_AVATAR_STYLE`
- Avatar deterministici via [DiceBear API](https://www.dicebear.com/) (stile `bottts`, seed = `node_id`)
- `avatar_url` property su `PeerInfo` — genera URL con background color coordinato

**Shared Dreams P2P**
- `node/runtime/node_state.py` — `NodeStateManager` + `DreamEntry`
- `POST /dreams/add` — crea dream e lo propaga a tutti i peer
- `POST /dreams/receive` — riceve dream da peer (idempotente)
- `POST /dreams/{id}/vote` — vota dream con propagazione aggiornamento
- `POST /dreams/{id}/retract` — ritira dream
- `GET /dreams` — stato dream attivi + history ultimi 10
- Quorum configurabile (`votes_needed`, default 3)
- Stato nodo aggiornato automaticamente: `active` → `dreaming` → `active`

**Auto-pull Modelli per RAM**
- `node/runtime/auto_pull.py` — `AutoPullService`
- `NODE_RAM_GB` env → al boot calcola RAM usabile (85%) e chiede ad Authority i modelli adatti
- `GET /catalog/ram/{ram_gb}` su Authority — ritorna modelli che entrano nella RAM
- `GET /catalog/best/{role}/{ram_gb}` — miglior modello per ruolo + RAM
- Pull solo dei modelli mancanti, skip automatico se già installati
- Streaming progress pull con timeout 30min

**Modelli Large (nodi 24-32GB)**
- `gemma4:27b` — reasoner_large, 18GB RAM, 128K ctx, reasoning_score 98
- `qwen2.5:32b` — agent_large, 20GB RAM, 32K ctx, reasoning_score 88
- `phi3.5` — small, 2.8GB RAM, 128K ctx (routing ultra-veloce)
- `node-b` (Ubuntu 32GB DDR5) configurato con modelli large

**Dashboard Authority Section**
- Nuova sezione `🔍 Authority — NodeRegistry` in dashboard
- Mostra nodi registrati con avatar, stato alive/dead, uptime
- Catalog modelli con RAM richiesta e ruolo
- Auto-refresh HTMX ogni 20s
- Partial `/partials/authority` — endpoint dedicato

**Dashboard — Peer Map migliorata**
- Card nodo con avatar DiceBear 48px + pallino stato sovrapposto
- Bordo colorato con `NODE_COLOR` del nodo
- Load bar inline
- Tags, location, owner, modelli visibili
- Hover scale animation

### 🔧 Modificato

- `shared/domain/models.py` — `ModelProfile.size_class` aggiunto `'27b'`, `'32b'`
- `shared/domain/models.py` — `ModelCatalogEntry.role` aggiunto `'reasoner_large'`, `'agent_large'`
- `authority/model_catalog.py` — aggiornato a 6 modelli (phi3.5 → gemma4:27b)
- `authority/server.py` — aggiunti endpoint `/catalog/ram/{gb}`, `/catalog/best/{role}/{gb}`
- `docker-compose.yml` — `NODE_RAM_GB` per node-a (16) e node-b (32)
- `dashboard/server.py` — aggiunta `get_authority_data()`, route `/partials/authority`
- `dashboard/templates/index.html` — aggiunta sezione Authority con auto-refresh

### 🐛 Fix

- `ModelProfile.size_class` Literal non includeva `'27b'` e `'32b'` → crash Authority al boot
- `ModelCatalogEntry.role` Literal non includeva `'reasoner_large'` e `'agent_large'`

---

## [5.9.0] — 2026-06-09

### ✨ Aggiunto
- Smart Router 4-level (L1 FAST_CHAT → L3 DEEP_REASONING)
- Pull automatico modelli via PullExecutor + OllamaPullService
- Memoria cognitiva: tier (episodic/semantic/speculative/quarantined/contested)
- TTL su memorie speculative, pruning automatico
- ValidationVoteStore (SQLite) + quorum(3)
- DreamReplayEngine: retraction e promotion memorie
- WorkloadType: aggiunto DEEP_REASONING e LONG_CONTEXT_ANALYSIS
- Gemma 4 12B Q4 come reasoner (batiai/gemma4-12b:q4, 256K ctx)
- Setup script automatico macOS/Linux/Windows

### 🔧 Modificato
- Reasoner passato da DeepSeek-R1 14B a Gemma 4 12B
- PolicyEngineV1 con scoring e placement candidates
- `size_class` Literal aggiornato con `'12b'`

---

## [5.8.0] — 2026-06-01

### ✨ Aggiunto
- Architettura base: Control Plane, Authority, Node, Worker, Ollama, Open WebUI
- Routing statico per workload type
- Memoria RAG classica
- Dream validator base
- Docker Compose multi-service

---

*Formato: [Keep a Changelog](https://keepachangelog.com/it/1.0.0/) — [SemVer](https://semver.org/)*
