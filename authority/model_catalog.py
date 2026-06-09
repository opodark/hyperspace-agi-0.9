# HyperSpace-AGI v5.9 - Model Catalog
# Modelli verificati su Ollama registry, max 9-12B per Mac M-series 16GB
# gemma4:12b -> tag: batiai/gemma4-12b:q4 (6.9GB RAM, 256K ctx, richiede Ollama 0.30.4+)
from __future__ import annotations
from shared.domain.models import ModelProfile, ModelCatalogEntry


MODEL_CATALOG: list[ModelCatalogEntry] = [

    # ------------------------------------------------------------------
    # AGENT: Qwen 2.5 7B - standard agent, planning, tool calling
    # Tag Ollama: qwen2.5:7b | 5.5GB RAM | 32K ctx
    # ------------------------------------------------------------------
    ModelCatalogEntry(
        profile=ModelProfile(
            model_id='qwen2.5:7b',
            family='qwen',
            size_class='7b',
            quantization='Q4_K_M',
            ram_required_gb=5.5,
            disk_size_gb=4.7,
            supports_json_schema=True,
            supports_tools=True,
            max_context_tokens=32768,
            reasoning_score=72,
            coding_score=70,
            speed_score=88,
        ),
        ollama_tag='qwen2.5:7b',
        role='agent',
        priority=8,
    ),

    # ------------------------------------------------------------------
    # CODER: Qwen 2.5 Coder 7B - code generation, refactoring
    # Tag Ollama: qwen2.5-coder:7b | 5.5GB RAM | 32K ctx
    # ------------------------------------------------------------------
    ModelCatalogEntry(
        profile=ModelProfile(
            model_id='qwen2.5-coder:7b',
            family='qwen-coder',
            size_class='7b',
            quantization='Q4_K_M',
            ram_required_gb=5.5,
            disk_size_gb=4.7,
            supports_json_schema=True,
            supports_tools=False,
            max_context_tokens=32768,
            reasoning_score=60,
            coding_score=92,
            speed_score=85,
        ),
        ollama_tag='qwen2.5-coder:7b',
        role='coder',
        priority=9,
    ),

    # ------------------------------------------------------------------
    # REASONER: Gemma 4 12B - deep reasoning, long context, multimodal
    # Tag Ollama: batiai/gemma4-12b:q4 | 6.9GB RAM | 256K ctx
    # Encoder-free multimodal (testo + immagini + audio + video)
    # Richiede: Ollama >= 0.30.4
    # ------------------------------------------------------------------
    ModelCatalogEntry(
        profile=ModelProfile(
            model_id='gemma4:12b',
            family='gemma',
            size_class='9b',  # size_class usa '9b' come proxy per 9-12b range
            quantization='Q4_K_M',
            ram_required_gb=6.9,
            disk_size_gb=6.9,
            supports_json_schema=True,
            supports_tools=True,
            max_context_tokens=262144,  # 256K
            reasoning_score=94,
            coding_score=82,
            speed_score=68,
        ),
        ollama_tag='batiai/gemma4-12b:q4',
        role='reasoner',
        priority=10,
    ),

    # ------------------------------------------------------------------
    # SMALL: Phi-3.5 Mini 3.8B - routing/classificazione ultra-veloce
    # Tag Ollama: phi3.5 | 2.8GB RAM | 128K ctx
    # ------------------------------------------------------------------
    ModelCatalogEntry(
        profile=ModelProfile(
            model_id='phi3.5',
            family='phi',
            size_class='4b',
            quantization='Q4_K_M',
            ram_required_gb=2.8,
            disk_size_gb=2.2,
            supports_json_schema=True,
            supports_tools=False,
            max_context_tokens=131072,
            reasoning_score=58,
            coding_score=52,
            speed_score=97,
        ),
        ollama_tag='phi3.5',
        role='small',
        priority=6,
    ),
]


def get_catalog() -> list[ModelCatalogEntry]:
    """Restituisce il catalogo completo dei modelli disponibili."""
    return [e for e in MODEL_CATALOG if e.is_available]


def get_by_role(role: str) -> list[ModelCatalogEntry]:
    """Filtra per ruolo, ordinato per priorità desc."""
    return sorted(
        [e for e in get_catalog() if e.role == role],
        key=lambda e: e.priority,
        reverse=True,
    )


def get_by_id(model_id: str) -> ModelCatalogEntry | None:
    """Trova una voce per model_id."""
    return next((e for e in MODEL_CATALOG if e.profile.model_id == model_id), None)


def mark_unavailable(model_id: str) -> None:
    """Segna un modello come non disponibile (es. non ancora pullato)."""
    entry = get_by_id(model_id)
    if entry:
        entry.is_available = False


def get_ollama_tags() -> list[str]:
    """Lista tutti gli Ollama tags nel catalogo."""
    return [e.ollama_tag for e in MODEL_CATALOG]
