# HyperSpace-AGI v6.0

**Swarm di agenti IA distribuiti su Docker + Ollama** con modelli locali quantizzati 7B–32B.
Rete P2P multi-nodo con gossip protocol, Authority seed bootstrap, dream condivisi tra nodi e auto-selezione modelli in base alla RAM disponibile.

---

## Installazione

### macOS / Linux

```bash
git clone https://github.com/opodark/hyperspace-agi-0.9
cd hyperspace-agi-0.9
chmod +x setup.sh
./setup.sh
```

Lo script `setup.sh`:
- ✅ Verifica Docker e prerequisiti
- 🔨 Build delle immagini Docker con progress
- ⏳ Attende health check di ogni servizio
- 📥 Pull automatico del modello default (`qwen2.5:7b`)
- 🌐 Apre automaticamente Open WebUI nel browser

### Windows (PowerShell)

```powershell
git clone https://github.com/opodark/hyperspace-agi-0.9
cd hyperspace-agi-0.9
Set-ExecutionPolicy -Scope Process Bypass
.\setup.ps1
```

### Avvio manuale

```bash
git clone https://github.com/opodark/hyperspace-agi-0.9
cd hyperspace-agi-0.9
docker compose up -d --build
```

### Requisiti

| | Minimo | Consigliato | Nodo potente |
|---|---|---|---|
| RAM | 8 GB | 16 GB | 32 GB DDR5 |
| Storage | 15 GB | 40 GB | 80 GB |
| OS | macOS 13+, Ubuntu 22+, Win 10+ | macOS Apple Silicon | Ubuntu 24+ |
| Docker | 24+ | Docker Desktop | Docker Engine |

---

## Architettura v6.0

```
┌─────────────────────────────────────────────────────────────────────┐
│                         CLIENT / USER                               │
│               Open WebUI (8080)  •  REST API                        │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   CONTROL PLANE  :8768                              │
│   RequestClassifier ──▶ SmartRouter 4-level ──▶ LoadBalancer        │
│                                │                    │               │
│                                ▼                    ▼               │
│                         Authority :8766      nodo meno carico       │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
               ┌───────────────┴────────────────┐
               ▼                                ▼
┌──────────────────────┐          ┌──────────────────────┐
│   NODE A  :8765      │          │   NODE B  :8770      │
│   macbook-alberto    │◀────────▶│   ubuntu-server      │
│   16GB RAM           │  gossip  │   32GB DDR5          │
│   qwen2.5:7b         │  P2P     │   qwen2.5:32b        │
│   gemma4:12b Q4      │          │   gemma4:27b         │
└──────────┬───────────┘          └───────────┬──────────┘
           │                                  │
           └──────────────┬───────────────────┘
                          │  announce + heartbeat
                          ▼
            ┌─────────────────────────┐
            │   AUTHORITY  :8766      │
            │   NodeRegistry          │
            │   Model Catalog         │
            │   Policy Engine v1      │
            │   /catalog/ram/{gb}     │
            └─────────────────────────┘
                          │
                          ▼
            ┌─────────────────────────┐
            │     OLLAMA  :11434      │
            │  (condiviso tra nodi)   │
            └─────────────────────────┘
```

---

## P2P Network — come funziona

### Authority Seed Bootstrap

```
Boot nodo
  → POST authority:8766/peers/announce   ← si registra con nickname/tags/color/avatar
  ← [{peer-a}, {peer-b}, ...]            ← riceve lista peer attivi
  → gossip diretto con i peer ricevuti   ← da qui è tutto P2P
  → ogni 60s ri-annuncio a Authority     ← aggiorna last_seen
```

`NODE_PEERS` rimane come fallback statico se Authority non è raggiungibile al boot.

### Gossip Protocol

- Ogni **30s** ogni nodo pinga tutti i peer conosciuti via `POST /gossip/heartbeat`
- Ogni heartbeat propaga la lista dei peer conosciuti (**fan-out**)
- Peer non risponde per **90s** → rimosso automaticamente dal registry
- Stato (`active` / `dreaming` / `sleeping`) e `load` propagati ad ogni heartbeat

### Shared Dreams P2P

```
nodo-a crea dream  →  POST /dreams/add
  → propaga a tutti i peer  →  POST peer/dreams/receive
  → ogni peer può votare    →  POST /dreams/{id}/vote
  → quorum (3 voti)         →  dream promosso
```

---

## Auto-pull modelli per RAM

Impostando `NODE_RAM_GB` nell'env, al boot il nodo scarica automaticamente i modelli adatti:

```bash
# MacBook Air 16GB → scarica fino a 13.6GB usabili
NODE_RAM_GB=16   # qwen2.5:7b + qwen2.5-coder:7b + gemma4:12b

# Ubuntu 32GB DDR5 → scarica fino a 27.2GB usabili
NODE_RAM_GB=32   # + qwen2.5:32b + gemma4:27b
```

Logica: `Authority /catalog/ram/{gb}` → lista modelli che entrano → pull solo quelli mancanti.
Margine OS automatico: **15%** della RAM totale riservato.

---

## Modelli Supportati

| Modello | Tag Ollama | Ruolo | RAM | Ctx | Nodo target |
|---|---|---|---|---|---|
| Phi-3.5 Mini | `phi3.5` | small | 2.8 GB | 128K | qualsiasi |
| Qwen 2.5 7B | `qwen2.5:7b` | agent | 5.5 GB | 32K | 8GB+ |
| Qwen Coder 7B | `qwen2.5-coder:7b` | coder | 5.5 GB | 32K | 8GB+ |
| Gemma 4 12B Q4 | `batiai/gemma4-12b:q4` | reasoner | 6.9 GB | 256K | 12GB+ |
| Qwen 2.5 32B | `qwen2.5:32b` | agent_large | 20 GB | 32K | 24GB+ |
| Gemma 4 27B | `gemma4:27b` | reasoner_large | 18 GB | 128K | 24GB+ |

---

## Configurazione nodo

```yaml
environment:
  # identità
  - NODE_ID=node-a
  - NODE_NICKNAME=macbook-alberto
  - NODE_LOCATION=MacBook Air M2
  - NODE_TAGS=dev,macos,arm64
  - NODE_OWNER=alberto
  - NODE_COLOR=#7c3aed         # colore hex nella Peer Map
  - NODE_AVATAR_STYLE=bottts   # stile DiceBear (bottts, pixel-art, ...)

  # hardware
  - NODE_RAM_GB=16             # abilita auto-pull intelligente

  # rete P2P
  - AUTHORITY_URL=http://authority:8766
  - NODE_PEERS=node-b:8770     # fallback statico
  - GOSSIP_INTERVAL_SEC=30
  - ANNOUNCE_INTERVAL_SEC=60
```

**Nodo esterno** (Ubuntu su altra macchina):
```yaml
- AUTHORITY_URL=http://<IP-MacBook>:8766
- NODE_PEERS=   # vuoto, ci pensa l'Authority
- NODE_RAM_GB=32
```

---

## Endpoint

| Servizio | Porta | Endpoint chiave |
|---|---|---|
| Dashboard | 8769 | UI controllo completa |
| Open WebUI | 8080 | UI chat |
| Control Plane | 8768 | `/route`, `/v1/chat/completions`, `/stats` |
| Node | 8765/8770 | `/chat`, `/gossip/peers`, `/dreams`, `/dreams/add` |
| Authority | 8766 | `/peers`, `/peers/announce`, `/catalog`, `/catalog/ram/{gb}` |
| Worker | 8767 | `/votes/{id}`, `/replay`, `/contested/{id}/resolve` |
| Ollama | 11434 | `/api/chat`, `/api/pull`, `/api/tags` |

---

## Dashboard

Apri `http://localhost:8769`

- 🐳 **Container** — stato, restart/stop/start, log viewer
- 🕸️ **Peer Map** — nodi P2P con avatar DiceBear, stato, load, tags
- 🔍 **Authority** — NodeRegistry live + catalog modelli per RAM
- 🌙 **Dream Lab** — dream attivi, voti, stato promozione
- 🦙 **Modelli Ollama** — installati, pull nuovo modello con progress
- 📊 **Routing Stats** — decisioni smart router

Auto-refresh HTMX: container 10s · peer map 15s · authority 20s · dreams 8s.

---

## Struttura Repository

```
hyperspace-agi-0.9/
├── setup.sh / setup.ps1
├── docker-compose.yml
├── docker/                   # Dockerfile per ogni servizio
├── shared/
│   └── domain/models.py      # Domain models Pydantic v6.0
├── authority/
│   ├── server.py             # FastAPI + NodeRegistry + Catalog
│   ├── model_catalog.py      # 6 modelli 4b→32b con tier RAM
│   ├── node_registry.py      # Registry P2P con TTL
│   └── policy_engine.py      # Policy Engine v1
├── worker/
│   ├── dream_validator.py
│   ├── validation_vote_store.py
│   └── dream_replay.py
├── control-plane/
│   └── smart_router.py       # Router 4-level + load balancing
├── node/
│   ├── server.py             # FastAPI + gossip + shared dreams
│   ├── runtime/
│   │   ├── gossip_service.py # GossipService + PeerInfo + avatar
│   │   ├── node_state.py     # NodeStateManager + DreamEntry
│   │   └── auto_pull.py      # Auto-pull modelli per RAM
│   └── memory/
│       └── tiered_store.py
└── dashboard/
    ├── server.py
    └── templates/
        ├── index.html
        └── partials/         # status, peers, authority, dreams, models, stats
```

## License

MIT
