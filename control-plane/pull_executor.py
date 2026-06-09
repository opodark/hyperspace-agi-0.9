# HyperSpace-AGI v5.9 - Pull Executor
# Intercetta PullDecision(YES) e chiama OllamaPullService prima dell'inferenza
# Integrato in SmartRouter.route()
from __future__ import annotations
import logging
from shared.domain.models import ExecutionPlan, PullDecisionType
from node.ollama_pull_service import OllamaPullService, PullStatus

logger = logging.getLogger('pull_executor')


class PullExecutor:
    """
    Esegue il pull di un modello se ExecutionPlan.pull_decision == YES.
    Se il pull fallisce, aggiorna il piano con un FALLBACK al modello default.
    """

    def __init__(
        self,
        pull_service: OllamaPullService | None = None,
        fallback_model_id: str = 'qwen3.5:7b',
    ) -> None:
        self.pull_service = pull_service or OllamaPullService()
        self.fallback_model_id = fallback_model_id

    async def maybe_pull(self, plan: ExecutionPlan) -> ExecutionPlan:
        """
        Se pull_decision == YES, esegue il pull e aggiorna il piano.
        Se pull_decision != YES, restituisce il piano invariato.
        Casi:
          - ALREADY_HOT / SUCCESS -> piano invariato, modello pronto
          - FAILED -> piano aggiornato con fallback_model_id + nota
        """
        if plan.pull_decision.decision != PullDecisionType.YES:
            return plan

        model_id = plan.pull_decision.model_id or plan.selected_model_id
        if not model_id:
            logger.warning('[pull_executor] PullDecision YES ma nessun model_id — skip')
            return plan

        logger.info(f'[pull_executor] Avvio pull per {model_id}')
        progress = await self.pull_service.pull(model_id)

        if progress.status in (PullStatus.SUCCESS, PullStatus.ALREADY_HOT):
            logger.info(f'[pull_executor] {model_id} pronto ({progress.status.value})')
            # Aggiorna reason nel piano
            plan.pull_decision.reason = (
                f'pull completed: {progress.status.value} | '
                f'{progress.percent:.1f}% | {progress.last_status_msg}'
            )
            return plan

        # Pull fallito — downgrade al fallback
        logger.error(
            f'[pull_executor] Pull fallito per {model_id}: {progress.error} — '
            f'fallback su {self.fallback_model_id}'
        )
        plan.selected_model_id = self.fallback_model_id
        plan.pull_decision.reason = (
            f'pull FAILED ({progress.error}) — fallback a {self.fallback_model_id}'
        )
        return plan
