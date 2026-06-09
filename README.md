# HyperSpace-AGI v5.9

**Swarm di agenti IA distribuiti su Docker + Ollama** con modelli locali quantizzati 7B–12B.
Pull automatico dei modelli, routing intelligente 4 livelli, memoria cognitiva contestabile.

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
- ⏳ Attende health check di ogni servizio con barra avanzamento
- 📥 Pull automatico del modello default (`qwen2.5:7b`) con progress MB/%
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

# Avvia stack (pull modelli automatico al primo uso)
docker compose up -d --build

# Pre-pull opzionale per velocizzare il primo avvio
docker exec -it hyperspace-ollama ollama pull qwen2.5:7b
docker exec -it hyperspace-ollama ollama pull qwen2.5-coder:7b
docker exec -it hyperspace-ollama ollama pull gemma3:9b
```

### Requisiti

| | Minimo | Consigliato |
|---|---|---|
| RAM | 8 GB | 16 GB |
| Storage | 10 GB | 30 GB |
| OS | macOS 13+, Ubuntu 22+, Windows 10+ | macOS Apple Silicon |
| Docker | 24+ | Docker Desktop |

---

## Architettura

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLIENT / USER                            │
│              Open WebUI (8080)  •  REST API                     │
└────────────────────────────┬────────────────────────────────────┘
                             │  POST /v1/chat/completions
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                  CONTROL PLANE  :8768                           │
│                                                                 │
│  RequestClassifier ──▶ SmartRouter 4-level                      │
│    FAST_CHAT  (L1)       │                                      │
│    TOOL_CALL  (L1)       │  POST /resolve                       │
│    CODING     (L2)       ▼                                      │
│    REASONING  (L3)  ┌──────────┐   PullDecision(YES)?          │
│    LONG_CTX   (L3)  │Authority │──▶ PullExecutor                │
│                     │  :8766   │       │                        │
│                     └──────────┘       │ POST /api/pull         │
│  RuntimeStore (SQLite)  ◀──────────────▼                        │
│  audit trail routing        Ollama  :11434                      │
└──────────┬──────────────────────────────────────────────────────┘
           │  ExecutionPlan (model pronto)
           ▼
┌──────────────────────┐     ┌──────────────────────────────────┐
│    NODE  :8765       │     │        WORKER  :8767             │
│                      │     │                                  │
│  AgentRuntime        │     │  DreamValidator v2               │
│  TieredMemoryStore   │     │  ValidationVoteStore (SQLite)    │
│  ┌────────────────┐  │     │  DreamStore (SQLite)             │
│  │  EPISODIC      │  │     │  DreamReplayEngine               │
│  │  SEMANTIC      │  │     │  ┌──────────────────────────┐   │
│  │  SPECULATIVE   │  │     │  │  Dream → Vote → Tally    │   │
│  │  (TTL, score)  │  │     │  │  Quorum(3) → Resolve     │   │
│  └────────────────┘  │     │  └──────────────────────────┘   │
└──────────┬───────────┘     └────────────────┬─────────────────┘
           │                                  │
           └──────────────┬───────────────────┘
                          ▼
              ┌───────────────────────┐
              │     OLLAMA  :11434    │
              │                      │
              │  qwen2.5:7b          │  ◀ AGENT (L1)  default
              │  qwen2.5:14b         │  ◀ AGENT (L1+)
              │  qwen2.5-coder:7b    │  ◀ CODER (L2)
              │  qwen2.5-coder:14b   │  ◀ CODER (L2+)
              │  gemma3:12b          │  ◀ REASONER (L3)
              │  gemma3:9b           │  ◀ SMALL routing
              └───────────────────────┘
```

---

## Flow: Pull Automatico dei Modelli

Da v5.9 **non è necessario fare `ollama pull` manualmente**.
Il sistema gestisce il pull in autonomia:

```
UserRequest
  → RequestClassifier   (es. DEEP_REASONING → gemma3:12b)
  → authority /resolve  (PullDecision = YES se modello COLD)
  → PullExecutor
      → OllamaPullService.is_hot()   ← skip se già presente
      → POST ollama/api/pull          ← streaming progress
      → attende {"status": "success"}
  → ExecutionPlan (modello ora HOT)
  → /v1/chat/completions → Ollama
```

Se il pull fallisce → **fallback automatico** a `qwen2.5:7b`.

---

## Endpoint

| Servizio | Porta | Endpoint chiave |
|---|---|---|
| Open WebUI | 8080 | UI chat |
| Control Plane | 8768 | `/route`, `/v1/chat/completions`, `/stats`, `/decisions` |
| Node | 8765 | `/chat`, `/memory/{session_id}`, `/memory/contested`, `/memory/prune` |
| Authority | 8766 | `/resolve`, `/catalog`, `/catalog/role/{role}`, `/health` |
| Worker | 8767 | `/votes/{id}`, `/votes/tally/{id}`, `/replay`, `/contested/{id}/resolve` |
| Ollama | 11434 | `/api/chat`, `/api/pull`, `/api/tags` |

---

## Modelli Supportati

| Modello | Tag Ollama | Ruolo | RAM | Ctx | Note |
|---|---|---|---|---|---|
| Qwen 2.5 7B | `qwen2.5:7b` | agent | 5.5GB | 32K | default, tool calling |
| Qwen 2.5 14B | `qwen2.5:14b` | agent | 9.0GB | 32K | agent potenziato |
| Qwen Coder 7B | `qwen2.5-coder:7b` | coder | 5.5GB | 32K | coding L2 |
| Qwen Coder 14B | `qwen2.5-coder:14b` | coder | 10.5GB | 32K | coding pesante |
| Gemma 3 12B | `gemma3:12b` | reasoner | 8.0GB | 128K | reasoning L3 |
| Gemma 3 9B | `gemma3:9b` | small | 5.0GB | 8K | routing/classificazione |

---

## Novità v5.9 vs v5.8

| Componente | v5.8 | v5.9 |
|---|---|---|
| Routing | Statico | Smart 4-levels (L1→L3) |
| Pull modelli | **Manuale** (`ollama pull`) | **Automatico** (PullExecutor + OllamaPullService) |
| Reasoner | DeepSeek-R1 14B | **Gemma 3 12B** (128K ctx) |
| Memoria | RAG classico | Cognitiva (tier, TTL, contest, replay) |
| Policy Engine | None | PolicyEngineV1 + scoring + placement |
| Dream Voting | None | ValidationVoteStore + quorum(3) |
| Dream Replay | None | DreamReplayEngine + retraction/promotion |
| Workload types | 3 (chat/code/tool) | 5 (+DEEP_REASONING, +LONG_CONTEXT_ANALYSIS) |
| Setup | Manuale | **Script automatico** (macOS/Linux/Windows) |

---

## Struttura Repository

```
hyperspace-agi-0.9/
├── setup.sh                 # Installer macOS/Linux
├── setup.ps1                # Installer Windows
├── docker-compose.yml
├── docker/                  # Dockerfile per ogni servizio
├── shared/                  # Domain models, settings, trace splitter
├── authority/               # Policy Engine v1, model catalog
├── worker/                  # Dream validator, vote store, replay engine
├── control-plane/           # Smart Router, Request Classifier, Pull Executor
├── node/                    # Agent Runtime, Tiered Memory Store
└── tests/                   # Smoke tests (pytest)
```

## License

MIT
