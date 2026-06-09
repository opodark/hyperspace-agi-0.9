# HyperSpace-AGI v5.9 - Model Catalog
# Catalogo modelli locali supportati con Ollama tags e scoring
# Target: MacBook Air M5 (14B limit)
from __future__ import annotations
from shared.domain.models import ModelProfile, ModelCatalogEntry


# ---------------------------------------------------------------------------
# Catalogo modelli v5.9
# ---------------------------------------------------------------------------

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
    # REASONER: DeepSeek-R1 14B - deep reasoning, contested memory
    # ------------------------------------------------------------------
    ModelCatalogEntry(
        profile=ModelProfile(
            model_id='deepseek-r1:14b',
            family='deepseek',
            size_class='14b',
            quantization='Q4_K_M',
            ram_required_gb=10.5,
            disk_size_gb=9.0,
            supports_json_schema=False,
            supports_tools=False,
            max_context_tokens=65536,
            reasoning_score=96,
            coding_score=70,
            speed_score=45,
        ),
        ollama_tag='deepseek-r1:14b',
        role='reasoner',
        priority=9,
    ),

    # ------------------------------------------------------------------
    # SMALL: Gemma 4 7B - task veloci, classificazione, routing
    # ------------------------------------------------------------------
    ModelCatalogEntry(
        profile=ModelProfile(
            model_id='gemma4:7b',
            family='gemma',
            size_class='7b',
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
    """Restituisce il catalogo completo."""
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
