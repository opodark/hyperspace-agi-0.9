# HyperSpace-AGI v5.9 - Model Catalog (updated: REASONER -> Gemma 4 12B)
# Catalogo modelli locali supportati con Ollama tags e scoring
# Target: MacBook Air M5 (16GB RAM, 14B+ limit con Q4)
# Gemma 4 12B: batiai/gemma4-12b:q4 | 256K ctx | multimodal | 6.9GB RAM
from __future__ import annotations
from shared.domain.models import ModelProfile, ModelCatalogEntry


MODEL_CATALOG: list[ModelCatalogEntry] = [

    # ------------------------------------------------------------------
    # AGENT: Qwen 3.5 7B - standard agent, planning, tool calling
    # ------------------------------------------------------------------
    ModelCatalogEntry(
        profile=ModelProfile(
            model_id='qwen3.5:7b',
            family='qwen',
            size_class='7b',
            quantization='Q4_K_M',
            ram_required_gb=5.5,
            disk_size_gb=4.8,
            supports_json_schema=True,
            supports_tools=True,
            max_context_tokens=32768,
            reasoning_score=72,
            coding_score=70,
            speed_score=88,
        ),
        ollama_tag='qwen3.5:7b',
        role='agent',
        priority=8,
    ),

    # ------------------------------------------------------------------
    # AGENT: Qwen 3.5 9B - agent potenziato, contesto lungo
    # ------------------------------------------------------------------
    ModelCatalogEntry(
        profile=ModelProfile(
            model_id='qwen3.5:9b',
            family='qwen',
            size_class='9b',
            quantization='Q4_K_M',
            ram_required_gb=7.0,
            disk_size_gb=6.0,
            supports_json_schema=True,
            supports_tools=True,
            max_context_tokens=32768,
            reasoning_score=78,
            coding_score=75,
            speed_score=80,
        ),
        ollama_tag='qwen3.5:9b',
        role='agent',
        priority=7,
    ),

    # ------------------------------------------------------------------
    # CODER: Qwen Coder 9B - code generation, refactoring
    # ------------------------------------------------------------------
    ModelCatalogEntry(
        profile=ModelProfile(
            model_id='qwen-coder:9b',
            family='qwen-coder',
            size_class='9b',
            quantization='Q4_K_M',
            ram_required_gb=7.0,
            disk_size_gb=6.0,
            supports_json_schema=True,
            supports_tools=False,
            max_context_tokens=32768,
            reasoning_score=65,
            coding_score=92,
            speed_score=78,
        ),
        ollama_tag='qwen2.5-coder:9b',
        role='coder',
        priority=9,
    ),

    # ------------------------------------------------------------------
    # CODER: Qwen Coder 14B - code generation heavy (M5 limit)
    # ------------------------------------------------------------------
    ModelCatalogEntry(
        profile=ModelProfile(
            model_id='qwen-coder:14b',
            family='qwen-coder',
            size_class='14b',
            quantization='Q4_K_M',
            ram_required_gb=10.5,
            disk_size_gb=9.0,
            supports_json_schema=True,
            supports_tools=False,
            max_context_tokens=32768,
            reasoning_score=72,
            coding_score=96,
            speed_score=60,
        ),
        ollama_tag='qwen2.5-coder:14b',
        role='coder',
        priority=8,
    ),

    # ------------------------------------------------------------------
    # REASONER: Gemma 4 12B - deep reasoning, long context, multimodal
    # Sostituisce DeepSeek-R1:14b a partire da v5.9
    # Ollama tag: batiai/gemma4-12b:q4 (Q4_K_M, ~6.9GB RAM, 256K ctx)
    # Rilasciato: giugno 2026 | multimodale: testo + immagini + audio + video
    # ------------------------------------------------------------------
    ModelCatalogEntry(
        profile=ModelProfile(
            model_id='gemma4:12b',
            family='gemma',
            size_class='12b',
            quantization='Q4_K_M',
            ram_required_gb=6.9,
            disk_size_gb=7.0,
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
    # SMALL: Gemma 3 9B - task veloci, classificazione, routing
    # ------------------------------------------------------------------
    ModelCatalogEntry(
        profile=ModelProfile(
            model_id='gemma3:9b',
            family='gemma',
            size_class='9b',
            quantization='Q4_K_M',
            ram_required_gb=5.0,
            disk_size_gb=4.5,
            supports_json_schema=True,
            supports_tools=False,
            max_context_tokens=8192,
            reasoning_score=60,
            coding_score=55,
            speed_score=95,
        ),
        ollama_tag='gemma3:9b',
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
