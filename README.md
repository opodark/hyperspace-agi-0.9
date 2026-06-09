# HyperSpace-AGI v5.9

**Swarm di agenti IA distribuiti su Docker + Ollama** con modelli locali quantizzati 7B-14B.

## Obiettivo v5.9

- Modelli locali quantizzati: Qwen 3.5 7B/9B, Qwen Coder 9B/14B, Gemma 4, DeepSeek-R1 14B
- Hardware target: MacBook Air M5 (limitazione 14B)
- Docker + Ollama: container isolati, inferenza locale
- Memoria cognitiva: stati che cambiano, challenging, replay, revalidazione
- Policy Engine v1: Pydantic models + scoring + placement automatico
- Smart Routing 4-levels: agent → coder → reasoner → specialized workers

## Architettura

```
Open WebUI (8080)
     |
Control Plane (8768) - Smart Routing 4-levels
  |         |         |
Authority  Node    Worker
(8766)    (8765)   (8767)
Policy    Qwen3.5  Dream
Engine    Agent    Validator
     \      |      /
      Ollama (11434)
   Qwen3.5 | Coder | DeepSeek
```

## Quick Start

```bash
# 1. Pull modelli
ollama pull qwen3.5:7b
ollama pull qwen-coder:14b
ollama pull deepseek-r1:14b

# 2. Avvia
docker compose up -d --build

# 3. Accesso
# Open WebUI:     http://localhost:8080
# Control Plane:  http://localhost:8768
# Node API:       http://localhost:8765
# Authority API:  http://localhost:8766
# Worker API:     http://localhost:8767
# Ollama API:     http://localhost:11434
```

## Novità v5.9 vs v5.8

| Componente | v5.8 | v5.9 |
|---|---|---|
| Modelli | Phi Mini | Qwen 3.5 7B/9B, Coder 14B, DeepSeek 14B |
| Routing | Statico | Smart 4-levels |
| Memoria | RAG classico | Cognitiva (stati, replay, contested) |
| Policy Engine | None | Pydantic v1 + scoring + placement |
| Dream Voting | None | Validation Vote Store |
| Dream Replay | None | Replay store + revalidazione |
| Docker | Macchine fisiche | Container isolati |

## License

MIT
