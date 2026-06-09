# HyperSpace-AGI v5.9 - Smart Router 4-level (updated: PullExecutor integration)
# Flow: Classifier -> RoutingContext -> authority/resolve -> PullExecutor -> ExecutionPlan
from __future__ import annotations
import httpx
from shared.domain.models import (
    UserRequest, ExecutionPlan, WorkloadProfile,
    NodeCapability, RoutingContext,
    WorkloadType, PullDecision, PullDecisionType,
)
from shared.settings import settings
from control_plane.request_classifier import RequestClassifier
from control_plane.pull_executor import PullExecutor
from node.ollama_pull_service import OllamaPullService

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
    Smart routing 4-level v5.9.
    Novita vs versione precedente:
      - dopo authority/resolve, chiama PullExecutor.maybe_pull()
      - se pull_decision=YES, il modello viene pullato prima dell'inferenza
      - se pull fallisce, fallback automatico a default_agent_model
    """

    def __init__(
        self,
        authority_url: str | None = None,
        node_capabilities: list[NodeCapability] | None = None,
        ollama_url: str | None = None,
    ) -> None:
        self.authority_url = authority_url or f'http://authority:{settings.authority_api_port}'
        self.classifier = RequestClassifier()
        self._node_capabilities: list[NodeCapability] = node_capabilities or []
        _ollama = OllamaPullService(
            ollama_url=ollama_url or settings.ollama_base_url,
            timeout_seconds=settings.pull_timeout_seconds,
        )
        self._pull_executor = PullExecutor(
            pull_service=_ollama,
            fallback_model_id=settings.default_agent_model,
        )

    def update_nodes(self, nodes: list[NodeCapability]) -> None:
        self._node_capabilities = nodes

    async def route(self, request: UserRequest) -> ExecutionPlan:
        """
        Flow completo:
        1. Classifica workload
        2. Costruisce RoutingContext
        3. Chiama authority /resolve
        4. PullExecutor: se pull_decision=YES, esegue pull
        5. Ritorna ExecutionPlan con modello pronto
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
            plan = self._local_fallback(request.request_id, workload, str(exc))

        # --- NUOVO v5.9: esegui pull se necessario ---
        plan = await self._pull_executor.maybe_pull(plan)

        return plan

    async def _call_authority(self, ctx: RoutingContext) -> ExecutionPlan:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f'{self.authority_url}/resolve',
                json=ctx.model_dump(),
            )
            resp.raise_for_status()
            return ExecutionPlan.model_validate(resp.json())

    def _local_fallback(
        self, request_id: str, workload: WorkloadProfile, reason: str,
    ) -> ExecutionPlan:
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
