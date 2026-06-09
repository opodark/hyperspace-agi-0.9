# HyperSpace-AGI v5.9 - Request Classifier
# Evolution from v5.8 RequestClassifier (orchestration/policy_engine.py)
# v5.8: classify() -> FAST_CHAT | CODING_ASSISTANT | TOOL_CALLING
# v5.9: aggiunge DEEP_REASONING e LONG_CONTEXT_ANALYSIS
from __future__ import annotations
from shared.domain.models import (
    UserRequest, WorkloadProfile, WorkloadType, ServiceTier,
)


# Keyword sets per ogni workload type (v5.8 keywords preserved)
_CODING_KEYWORDS = {
    'python', 'refactor', 'asyncio', 'docker', 'ollama', 'bug', 'test',
    'javascript', 'typescript', 'rust', 'golang', 'function', 'class',
    'api', 'sql', 'query', 'database', 'debug', 'implement', 'write code',
}
_REASONING_KEYWORDS = {
    'why', 'explain', 'analyze', 'reason', 'think', 'hypothesis',
    'because', 'therefore', 'deduce', 'infer', 'evaluate', 'compare',
    'pros and cons', 'tradeoff', 'decision', 'strategy', 'architecture',
}
_LONG_CONTEXT_KEYWORDS = {
    'summarize', 'summary', 'document', 'paper', 'article', 'read this',
    'analyze this', 'long', 'entire', 'full text', 'transcript', 'review',
}


class RequestClassifier:
    """
    Classifica una UserRequest in un WorkloadProfile.
    v5.8 logica preservata per CODING/TOOL_CALLING/FAST_CHAT.
    v5.9 aggiunge DEEP_REASONING e LONG_CONTEXT_ANALYSIS.
    Priorita classificazione (decrescente):
      1. CODING_ASSISTANT  (keyword coding o requires_code_quality)
      2. DEEP_REASONING    (keyword reasoning o MAX_QUALITY priority)
      3. LONG_CONTEXT_ANALYSIS (token context > 16k o keyword)
      4. TOOL_CALLING      (requires_tools o requires_json_schema)
      5. FAST_CHAT         (default)
    """

    def classify(self, request: UserRequest) -> WorkloadProfile:
        text = ' '.join(m.content for m in request.messages).lower()
        f = request.features
        token_estimate = f.estimated_context_tokens

        # 1. CODING
        if f.requires_code_quality or any(k in text for k in _CODING_KEYWORDS):
            return WorkloadProfile(
                workload_type=WorkloadType.CODING_ASSISTANT,
                complexity_score=0.80,
                latency_target_ms=15000,
                min_quality_score=75,
                preferred_size_classes=['9b', '14b'],
                disallowed_size_classes=['4b'],
            )

        # 2. DEEP_REASONING (v5.9)
        if (
            f.user_priority == ServiceTier.MAX_QUALITY
            or sum(1 for k in _REASONING_KEYWORDS if k in text) >= 2
        ):
            return WorkloadProfile(
                workload_type=WorkloadType.DEEP_REASONING,
                complexity_score=0.90,
                latency_target_ms=30000,
                min_quality_score=85,
                preferred_size_classes=['14b'],
                disallowed_size_classes=['4b', '7b'],
            )

        # 3. LONG_CONTEXT_ANALYSIS (v5.9)
        if token_estimate > 16000 or any(k in text for k in _LONG_CONTEXT_KEYWORDS):
            return WorkloadProfile(
                workload_type=WorkloadType.LONG_CONTEXT_ANALYSIS,
                complexity_score=0.75,
                latency_target_ms=20000,
                min_quality_score=70,
                preferred_size_classes=['9b', '14b'],
                disallowed_size_classes=['4b'],
            )

        # 4. TOOL_CALLING (v5.8 preserved)
        if f.requires_json_schema or f.requires_tools:
            return WorkloadProfile(
                workload_type=WorkloadType.TOOL_CALLING,
                complexity_score=0.65,
                latency_target_ms=10000,
                min_quality_score=65,
                preferred_size_classes=['7b', '9b'],
                disallowed_size_classes=['4b'],
            )

        # 5. FAST_CHAT default (v5.8 preserved)
        return WorkloadProfile(
            workload_type=WorkloadType.FAST_CHAT,
            complexity_score=0.35,
            latency_target_ms=6000,
            min_quality_score=50,
            preferred_size_classes=['4b', '7b'],
            disallowed_size_classes=[],
        )
