# HyperSpace-AGI v5.9 - Policy Engine v1
# Pydantic-based policy engine: scoring function + smart routing 4 livelli
# Flow: Request -> WorkloadProfile -> ModelCandidates -> Placement -> PullDecision
from __future__ import annotations
from pydantic import BaseModel, Field
from shared.domain.models import (
    WorkloadType, WorkloadProfile, ModelCatalogEntry,
    NodeCapability, PlacementCandidate, PullDecision, PullDecisionType,
    ExecutionPlan, RoutingContext, ModelResidency,
)
from authority.model_catalog import get_by_role, get_catalog


# ---------------------------------------------------------------------------
# Policy Config v1
# ---------------------------------------------------------------------------

class PolicyConfig(BaseModel):
    """Configurazione runtime del Policy Engine."""
    max_ram_headroom_gb: float = Field(default=2.0)   # RAM libera minima da lasciare
    hot_bonus: float = Field(default=0.3)              # bonus residency HOT
    warm_bonus: float = Field(default=0.1)             # bonus residency WARM
    load_penalty_factor: float = Field(default=0.4)    # penalita carico nodo
    fallback_to_small: bool = Field(default=True)      # fallback a small se tutto occupato
    allow_downgrade: bool = Field(default=True)        # downgrade size_class se necessario


DEFAULT_POLICY = PolicyConfig()


# ---------------------------------------------------------------------------
# Workload -> Role mapping (routing level 1-4)
# ---------------------------------------------------------------------------

# Level 1: agent (default)
# Level 2: coder (coding workloads)
# Level 3: reasoner (deep reasoning, contested memory)
# Level 4: specialized (future: vision, audio, etc.)

WORKLOAD_TO_ROLE: dict[WorkloadType, str] = {
    WorkloadType.FAST_CHAT: 'agent',
    WorkloadType.STRUCTURED_EXTRACTION: 'agent',
    WorkloadType.TOOL_CALLING: 'agent',
    WorkloadType.CODING_ASSISTANT: 'coder',
    WorkloadType.DEEP_REASONING: 'reasoner',
    WorkloadType.LONG_CONTEXT_ANALYSIS: 'reasoner',
}

WORKLOAD_TO_LEVEL: dict[WorkloadType, int] = {
    WorkloadType.FAST_CHAT: 1,
    WorkloadType.STRUCTURED_EXTRACTION: 1,
    WorkloadType.TOOL_CALLING: 1,
    WorkloadType.CODING_ASSISTANT: 2,
    WorkloadType.DEEP_REASONING: 3,
    WorkloadType.LONG_CONTEXT_ANALYSIS: 3,
}


# ---------------------------------------------------------------------------
# Scoring functions
# ---------------------------------------------------------------------------

def _workload_fit_score(workload: WorkloadProfile, entry: ModelCatalogEntry) -> float:
    """
    Score 0-1 che misura quanto il modello e adatto al workload.
    Combina reasoning_score, coding_score, speed_score pesati per workload_type.
    """
    p = entry.profile
    wt = workload.workload_type

    if wt == WorkloadType.CODING_ASSISTANT:
        raw = p.coding_score * 0.7 + p.reasoning_score * 0.2 + p.speed_score * 0.1
    elif wt == WorkloadType.DEEP_REASONING:
        raw = p.reasoning_score * 0.8 + p.coding_score * 0.1 + p.speed_score * 0.1
    elif wt == WorkloadType.FAST_CHAT:
        raw = p.speed_score * 0.6 + p.reasoning_score * 0.3 + p.coding_score * 0.1
    elif wt == WorkloadType.LONG_CONTEXT_ANALYSIS:
        raw = p.reasoning_score * 0.6 + p.speed_score * 0.2 + p.coding_score * 0.2
    else:  # STRUCTURED_EXTRACTION, TOOL_CALLING
        raw = p.reasoning_score * 0.4 + p.speed_score * 0.4 + p.coding_score * 0.2

    # Feature gates
    if workload.workload_type == WorkloadType.TOOL_CALLING and not p.supports_tools:
        raw *= 0.3  # forte penalita se non supporta tools
    if workload.workload_type == WorkloadType.STRUCTURED_EXTRACTION and not p.supports_json_schema:
        raw *= 0.5

    return min(raw / 100.0, 1.0)


def _resource_score(node: NodeCapability, entry: ModelCatalogEntry, cfg: PolicyConfig) -> float:
    """
    Score 0-1 che misura se il nodo ha risorse sufficienti.
    Penalizza nodi con poca RAM libera.
    """
    needed = entry.profile.ram_required_gb + cfg.max_ram_headroom_gb
    if node.ram_free_gb < needed:
        return 0.0  # nodo non adatto
    ratio = min(node.ram_free_gb / max(needed, 1.0), 2.0) / 2.0
    return ratio


def _warmness_score(node: NodeCapability, model_id: str, cfg: PolicyConfig) -> tuple[float, ModelResidency]:
    """Score basato sulla residency del modello nel nodo."""
    for installed in node.installed_models:
        if installed.model_id == model_id:
            if installed.residency == ModelResidency.HOT:
                return 1.0 + cfg.hot_bonus, ModelResidency.HOT
            if installed.residency == ModelResidency.WARM:
                return 0.6 + cfg.warm_bonus, ModelResidency.WARM
            return 0.3, ModelResidency.COLD
    return 0.0, ModelResidency.COLD  # non installato -> needs pull


def _load_penalty(node: NodeCapability, cfg: PolicyConfig) -> float:
    """Penalita per carico corrente del nodo."""
    return node.current_load * cfg.load_penalty_factor


def score_candidate(
    node: NodeCapability,
    entry: ModelCatalogEntry,
    workload: WorkloadProfile,
    cfg: PolicyConfig = DEFAULT_POLICY,
) -> PlacementCandidate | None:
    """Costruisce un PlacementCandidate con scoring completo. None se nodo inadatto."""
    resource = _resource_score(node, entry, cfg)
    if resource == 0.0:
        return None  # nodo senza risorse sufficienti

    fit = _workload_fit_score(workload, entry)
    warmness, residency = _warmness_score(node, entry.profile.model_id, cfg)
    pull_cost = 1.0 - (entry.profile.disk_size_gb / 20.0)  # meno pesa, meno costa pullare
    load_pen = _load_penalty(node, cfg)
    needs_pull = residency == ModelResidency.COLD and warmness == 0.0

    final = (
        fit * 0.35
        + resource * 0.25
        + warmness * 0.25
        + pull_cost * 0.10
        - load_pen * 0.05
    )

    return PlacementCandidate(
        node_id=node.node_id,
        model_id=entry.profile.model_id,
        residency=residency,
        fit_score=fit,
        resource_score=resource,
        warmness_score=warmness,
        pull_cost_score=pull_cost,
        load_penalty=load_pen,
        final_score=round(final, 4),
        needs_pull=needs_pull,
    )


# ---------------------------------------------------------------------------
# Policy Engine v1 - main entry point
# ---------------------------------------------------------------------------

class PolicyEngineV1:
    """Smart routing 4-level basato su workload type e risorse disponibili."""

    def __init__(self, cfg: PolicyConfig = DEFAULT_POLICY):
        self.cfg = cfg

    def resolve(
        self,
        ctx: RoutingContext,
    ) -> ExecutionPlan:
        """
        Flow completo:
        1. Determina role/level dal workload type
        2. Filtra candidati dal catalogo per role
        3. Scorecard su tutti i nodi x modelli
        4. Seleziona best candidate
        5. Decide pull se necessario
        """
        workload = ctx.workload
        role = WORKLOAD_TO_ROLE.get(workload.workload_type, 'agent')
        level = WORKLOAD_TO_LEVEL.get(workload.workload_type, 1)

        # Step 1: candidati dal catalogo per role
        candidates_entries = (
            ctx.available_catalog
            if ctx.available_catalog
            else get_by_role(role)
        )

        if not candidates_entries:
            # fallback a small se nessun modello per questo role
            if self.cfg.fallback_to_small:
                candidates_entries = get_by_role('small')
            if not candidates_entries:
                return self._reject(ctx.request_id, workload, 'no models available for role: ' + role)

        # Step 2: scorecard su tutti i nodi
        scored: list[PlacementCandidate] = []
        for entry in candidates_entries:
            for node in ctx.node_capabilities:
                c = score_candidate(node, entry, workload, self.cfg)
                if c:
                    scored.append(c)

        # Nessun nodo disponibile
        if not scored:
            if self.cfg.allow_downgrade:
                return self._downgrade(ctx.request_id, workload, role)
            return self._reject(ctx.request_id, workload, 'no nodes with sufficient resources')

        # Step 3: seleziona best
        best = max(scored, key=lambda c: c.final_score)

        # Step 4: pull decision
        if best.needs_pull:
            pull = PullDecision(
                decision=PullDecisionType.YES,
                node_id=best.node_id,
                model_id=best.model_id,
                reason='model not installed, pull required',
            )
        else:
            pull = PullDecision(
                decision=PullDecisionType.NO,
                node_id=best.node_id,
                model_id=best.model_id,
                reason='model already available',
            )

        return ExecutionPlan(
            request_id=ctx.request_id,
            workload=workload,
            selected_node_id=best.node_id,
            selected_model_id=best.model_id,
            pull_decision=pull,
            placement_candidates=scored,
        )

    def _reject(self, request_id: str, workload: WorkloadProfile, reason: str) -> ExecutionPlan:
        return ExecutionPlan(
            request_id=request_id,
            workload=workload,
            pull_decision=PullDecision(decision=PullDecisionType.REJECT, reason=reason),
        )

    def _downgrade(self, request_id: str, workload: WorkloadProfile, original_role: str) -> ExecutionPlan:
        return ExecutionPlan(
            request_id=request_id,
            workload=workload,
            pull_decision=PullDecision(
                decision=PullDecisionType.DOWNGRADE,
                reason=f'downgrade from {original_role}: no suitable node found',
            ),
        )


# Singleton
policy_engine = PolicyEngineV1()
