# HyperSpace-AGI v6.0 - Model Catalog con tier RAM
# ram_required_gb usato per auto-selezione modello al boot
from __future__ import annotations
from shared.domain.models import ModelProfile, ModelCatalogEntry


MODEL_CATALOG: list[ModelCatalogEntry] = [

    # ------------------------------------------------------------------
    # SMALL: Phi-3.5 Mini 3.8B - routing/classificazione ultra-veloce
    # RAM: 2.8GB | Adatto a nodi con 4-8GB RAM
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

    # ------------------------------------------------------------------
    # AGENT: Qwen 2.5 7B - standard agent, planning, tool calling
    # RAM: 5.5GB | Adatto a nodi con 8-16GB RAM
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
    # RAM: 5.5GB | Adatto a nodi con 8-16GB RAM
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
    # REASONER std: Gemma 4 12B Q4 - deep reasoning, 256K ctx
    # RAM: 6.9GB | Adatto a nodi con 12-16GB RAM
    # ------------------------------------------------------------------
    ModelCatalogEntry(
        profile=ModelProfile(
            model_id='gemma4:12b',
            family='gemma',
            size_class='9b',
            quantization='Q4_K_M',
            ram_required_gb=6.9,
            disk_size_gb=6.9,
            supports_json_schema=True,
            supports_tools=True,
            max_context_tokens=262144,
            reasoning_score=94,
            coding_score=82,
            speed_score=68,
        ),
        ollama_tag='batiai/gemma4-12b:q4',
        role='reasoner',
        priority=10,
    ),

    # ------------------------------------------------------------------
    # REASONER large: Gemma 4 27B Q4 - massima qualità, nodi potenti
    # RAM: 18GB | Adatto a nodi con 24-32GB RAM (es. Ubuntu 32GB DDR5)
    # ------------------------------------------------------------------
    ModelCatalogEntry(
        profile=ModelProfile(
            model_id='gemma4:27b',
            family='gemma',
            size_class='27b',
            quantization='Q4_K_M',
            ram_required_gb=18.0,
            disk_size_gb=17.0,
            supports_json_schema=True,
            supports_tools=True,
            max_context_tokens=131072,
            reasoning_score=98,
            coding_score=90,
            speed_score=45,
        ),
        ollama_tag='gemma4:27b',
        role='reasoner_large',
        priority=10,
    ),

    # ------------------------------------------------------------------
    # AGENT large: Qwen 2.5 32B - agent di alta qualità
    # RAM: 20GB | Adatto a nodi con 24-32GB RAM
    # ------------------------------------------------------------------
    ModelCatalogEntry(
        profile=ModelProfile(
            model_id='qwen2.5:32b',
            family='qwen',
            size_class='32b',
            quantization='Q4_K_M',
            ram_required_gb=20.0,
            disk_size_gb=19.0,
            supports_json_schema=True,
            supports_tools=True,
            max_context_tokens=32768,
            reasoning_score=88,
            coding_score=85,
            speed_score=42,
        ),
        ollama_tag='qwen2.5:32b',
        role='agent_large',
        priority=9,
    ),
]


def get_catalog() -> list[ModelCatalogEntry]:
    return [e for e in MODEL_CATALOG if e.is_available]


def get_by_role(role: str) -> list[ModelCatalogEntry]:
    return sorted(
        [e for e in get_catalog() if e.role == role],
        key=lambda e: e.priority,
        reverse=True,
    )


def get_by_id(model_id: str) -> ModelCatalogEntry | None:
    return next((e for e in MODEL_CATALOG if e.profile.model_id == model_id), None)


def mark_unavailable(model_id: str) -> None:
    entry = get_by_id(model_id)
    if entry:
        entry.is_available = False


def get_ollama_tags() -> list[str]:
    return [e.ollama_tag for e in MODEL_CATALOG]


def get_models_for_ram(ram_gb: float) -> list[ModelCatalogEntry]:
    """
    Restituisce tutti i modelli che entrano nella RAM disponibile,
    ordinati per priorità decrescente.
    Lascia un margine del 15% per OS e overhead.
    """
    usable_ram = ram_gb * 0.85
    fitting = [
        e for e in MODEL_CATALOG
        if e.profile.ram_required_gb <= usable_ram
    ]
    return sorted(fitting, key=lambda e: e.priority, reverse=True)


def get_best_model_for_role_and_ram(role: str, ram_gb: float) -> ModelCatalogEntry | None:
    """Miglior modello per un ruolo dato che entra nella RAM disponibile."""
    usable_ram = ram_gb * 0.85
    candidates = [
        e for e in MODEL_CATALOG
        if e.role == role and e.profile.ram_required_gb <= usable_ram
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda e: e.priority)
