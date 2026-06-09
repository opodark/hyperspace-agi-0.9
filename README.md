# HyperSpace-AGI v5.9

**Swarm di agenti IA distribuiti su Docker + Ollama** con modelli locali quantizzati 7B–12B.
Pull automatico dei modelli, routing intelligente 4 livelli, memoria cognitiva contestabile.

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
              │  qwen3.5:7b          │  ◀ AGENT (L1)
              │  qwen3.5:9b          │  ◀ AGENT (L1+)
              │  qwen2.5-coder:9b    │  ◀ CODER (L2)
              │  qwen2.5-coder:14b   │  ◀ CODER (L2+)
              │  batiai/gemma4-12b   │  ◀ REASONER (L3) 256K ctx
              │  gemma3:9b           │  ◀ SMALL routing
              └───────────────────────┘
```

---

## Flow: Pull Automatico dei Modelli

Da v5.9 **non è necessario fare `ollama pull` manualmente**.
Il sistema gestisce il pull in autonomia:

```
UserRequest
  → RequestClassifier   (es. DEEP_REASONING → gemma4:12b)
  → authority /resolve  (PullDecision = YES se modello COLD)
  → PullExecutor
      → OllamaPullService.is_hot()   ← skip se già presente
      → POST ollama/api/pull          ← streaming progress
      → attende {"status": "success"}
  → ExecutionPlan (modello ora HOT)
  → /v1/chat/completions → Ollama
```

Se il pull fallisce → **fallback automatico** a `qwen3.5:7b`.

---

## Quick Start

```bash
git clone https://github.com/opodark/hyperspace-agi-0.9
cd hyperspace-agi-0.9

# Avvia tutto (i modelli vengono pullati automaticamente al primo uso)
docker compose up -d --build

# Oppure pre-pull opzionale per velocizzare il primo avvio
ollama pull qwen3.5:7b          # agent  — sempre richiesto
ollama pull qwen2.5-coder:9b    # coder
ollama pull batiai/gemma4-12b:q4 # reasoner (256K ctx, multimodal)
ollama pull gemma3:9b           # small/routing

# Smoke tests
pytest tests/ -v
```

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
| Qwen 3.5 7B | `qwen3.5:7b` | agent | 5.5GB | 32K | default, tool calling |
| Qwen 3.5 9B | `qwen3.5:9b` | agent | 7.0GB | 32K | agent potenziato |
| Qwen Coder 9B | `qwen2.5-coder:9b` | coder | 7.0GB | 32K | coding L2 |
| Qwen Coder 14B | `qwen2.5-coder:14b` | coder | 10.5GB | 32K | coding pesante |
| **Gemma 4 12B** | `batiai/gemma4-12b:q4` | reasoner | 6.9GB | **256K** | multimodal, nuovo giugno 2026 |
| Gemma 3 9B | `gemma3:9b` | small | 5.0GB | 8K | routing/classificazione |

---

## Novità v5.9 vs v5.8

| Componente | v5.8 | v5.9 |
|---|---|---|
| Routing | Statico | Smart 4-levels (L1→L3) |
| Pull modelli | **Manuale** (`ollama pull`) | **Automatico** (PullExecutor + OllamaPullService) |
| Reasoner | DeepSeek-R1 14B | **Gemma 4 12B** (256K ctx, multimodal) |
| Memoria | RAG classico | Cognitiva (tier, TTL, contest, replay) |
| Policy Engine | None | PolicyEngineV1 + scoring + placement |
| Dream Voting | None | ValidationVoteStore + quorum(3) |
| Dream Replay | None | DreamReplayEngine + retraction/promotion |
| Workload types | 3 (chat/code/tool) | 5 (+DEEP_REASONING, +LONG_CONTEXT_ANALYSIS) |
| Context max | 65K (DeepSeek) | **256K** (Gemma 4 12B) |

---

## Struttura Repository

```
hyperspace-agi-0.9/
├── docker/                  # Dockerfile per ogni servizio
├── docker-compose.yml
├── shared/                  # Domain models, settings, trace splitter
├── authority/               # Policy Engine v1, model catalog
├── worker/                  # Dream validator, vote store, replay engine
├── control-plane/           # Smart Router, Request Classifier, Pull Executor
├── node/                    # Agent Runtime, Tiered Memory Store
└── tests/                   # Smoke tests (pytest)
```

## License

MIT
