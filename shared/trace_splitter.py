# HyperSpace-AGI v5.9 - Trace Splitter
# Split e categorizzazione del reasoning trace per tier
from __future__ import annotations
from shared.domain.models import ReasoningTrace, ReasoningTier


# Soglie token per tier
_TIER_THRESHOLDS = {
    ReasoningTier.SHALLOW: (0, 512),
    ReasoningTier.STANDARD: (512, 2048),
    ReasoningTier.DEEP: (2048, 8192),
}

# Pattern keyword per categorizzazione automatica
_CATEGORY_PATTERNS: dict[str, list[str]] = {
    'planning': ['plan', 'step', 'first', 'then', 'next', 'finally', 'goal'],
    'tool_call': ['tool', 'function', 'call', 'invoke', 'search', 'fetch', 'execute'],
    'memory_ref': ['remember', 'recall', 'memory', 'previously', 'earlier', 'stored'],
    'code_gen': ['```python', '```javascript', '```bash', 'def ', 'class ', 'import '],
    'reasoning': ['because', 'therefore', 'thus', 'conclude', 'hypothesis', 'deduce'],
    'contested': ['contradict', 'disagree', 'conflict', 'however', 'but wait', 'incorrect'],
}


def estimate_tokens(text: str) -> int:
    """Stima token count da char count (approx 4 char/token)."""
    return max(1, len(text) // 4)


def classify_tier(token_count: int, max_tokens: int) -> tuple[ReasoningTier, bool]:
    """Restituisce (tier, was_truncated)."""
    was_truncated = token_count >= max_tokens
    if was_truncated:
        return ReasoningTier.BOUNDED, True
    for tier, (low, high) in _TIER_THRESHOLDS.items():
        if low <= token_count < high:
            return tier, False
    return ReasoningTier.DEEP, False


def extract_categories(text: str) -> list[str]:
    """Identifica le categorie presenti nel trace."""
    text_lower = text.lower()
    return [
        cat
        for cat, keywords in _CATEGORY_PATTERNS.items()
        if any(kw in text_lower for kw in keywords)
    ]


def truncate_trace(text: str, max_tokens: int) -> str:
    """Tronca il trace al limite massimo di token (approx)."""
    max_chars = max_tokens * 4
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + '\n[TRACE TRUNCATED — bounded at max_tokens=' + str(max_tokens) + ']'


def split_trace(
    task_id: str,
    model_id: str,
    raw_trace: str,
    max_tokens: int = 8192,
) -> ReasoningTrace:
    """
    Entry point principale.
    Prende un raw trace e restituisce un ReasoningTrace annotato con:
    - tier (SHALLOW / STANDARD / DEEP / BOUNDED)
    - token_count stimato
    - was_truncated
    - categories rilevate
    """
    # Tronca se necessario
    processed = truncate_trace(raw_trace, max_tokens)
    token_count = estimate_tokens(processed)
    tier, was_truncated = classify_tier(token_count, max_tokens)
    categories = extract_categories(processed)

    return ReasoningTrace(
        task_id=task_id,
        model_id=model_id,
        raw_trace=processed,
        tier=tier,
        token_count=token_count,
        was_truncated=was_truncated,
        categories=categories,
    )


def split_trace_segments(
    raw_trace: str,
    segment_separator: str = '<think>',
) -> list[str]:
    """
    Separa il trace in segmenti logici basandosi su marcatori del modello.
    Utile per DeepSeek-R1 e Qwen che usano <think>...</think>.
    """
    if segment_separator not in raw_trace:
        return [raw_trace]
    parts = raw_trace.split(segment_separator)
    return [p.strip() for p in parts if p.strip()]
