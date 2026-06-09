# HyperSpace-AGI v5.9 - Smart Router 4-level
# Orchestra il routing: Classifier -> Authority/PolicyEngine -> ExecutionPlan
# Level 1: agent  | Level 2: coder  | Level 3: reasoner  | Level 4: specialized
from __future__ import annotations
import httpx
from shared.domain.models import (
    UserRequest, ExecutionPlan, WorkloadProfile,
    NodeCapability, RoutingContext,
    WorkloadType, PullDecision, PullDecisionType,
)
from shared.settings import settings
from control_plane.request_classifier import RequestClassifier

_WORKLOAD_TO_LEVEL: dict[WorkloadType, int] = {
    WorkloadType.FAST_CHAT: 1,
    WorkloadType.STRUCTURED_EXTRACTION: 1,
    WorkloadType.TOOL_CALLING: 1,
    WorkloadType.CODING_ASSISTANT: 2,
    WorkloadType.DEEP_REASONING: 3,
    WorkloadType.LONG_CONTEXT_ANALYSIS: 3,
}


class SmartRouter:
    """
    Smart routing 4-level:
    - Classifica la request in WorkloadProfile
    - Delega la placement decision al Authority service (/resolve)
    - Gestisce fallback locale se authority non raggiungibile
    """

    def __init__(
        self,
        authority_url: str | None = None,
        node_capabilities: list[NodeCapability] | None = None,
    ) -> None:
        self.authority_url = authority_url or f'http://authority:{settings.authority_api_port}'
        self.classifier = RequestClassifier()
        self._node_capabilities: list[NodeCapability] = node_capabilities or []

    def update_nodes(self, nodes: list[NodeCapability]) -> None:
        """Aggiorna la lista di nodi disponibili."""
        self._node_capabilities = nodes

    async def route(self, request: UserRequest) -> ExecutionPlan:
        """
        Flow principale:
        1. Classifica workload
        2. Costruisce RoutingContext
        3. Chiama authority /resolve
        4. Ritorna ExecutionPlan
        """
        workload = self.classifier.classify(request)
        level = _WORKLOAD_TO_LEVEL.get(workload.workload_type, 1)

        ctx = RoutingContext(
            request_id=request.request_id,
            workload=workload,
            node_capabilities=self._node_capabilities,
            routing_level=level,
        )

        try:
            plan = await self._call_authority(ctx)
        except Exception as exc:
            # Fallback locale se authority non disponibile
            plan = self._local_fallback(request.request_id, workload, str(exc))

        return plan

    async def _call_authority(self, ctx: RoutingContext) -> ExecutionPlan:
        """HTTP POST a authority/resolve."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f'{self.authority_url}/resolve',
                json=ctx.model_dump(),
            )
            resp.raise_for_status()
            return ExecutionPlan.model_validate(resp.json())

    def _local_fallback(
        self,
        request_id: str,
        workload: WorkloadProfile,
        reason: str,
    ) -> ExecutionPlan:
        """
        Fallback locale: usa il default model dal settings.
        Usato quando authority non e raggiungibile.
        """
        model_id = {
            WorkloadType.CODING_ASSISTANT: settings.default_coder_model,
            WorkloadType.DEEP_REASONING: settings.default_reasoner_model,
            WorkloadType.LONG_CONTEXT_ANALYSIS: settings.default_reasoner_model,
        }.get(workload.workload_type, settings.default_agent_model)

        return ExecutionPlan(
            request_id=request_id,
            workload=workload,
            selected_model_id=model_id,
            pull_decision=PullDecision(
                decision=PullDecisionType.NO,
                model_id=model_id,
                reason=f'local fallback (authority unavailable): {reason}',
            ),
        )
