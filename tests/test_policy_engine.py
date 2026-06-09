# HyperSpace-AGI v5.9 - Smoke tests: Policy Engine v1
import pytest
from shared.domain.models import (
    WorkloadProfile, WorkloadType, NodeCapability,
    InstalledModelState, ModelResidency, RoutingContext, PullDecisionType,
)
from authority.policy_engine import PolicyEngineV1, PolicyConfig
from authority.model_catalog import get_catalog


@pytest.fixture
def node_with_qwen() -> NodeCapability:
    return NodeCapability(
        node_id='test-node', ram_total_gb=24.0, ram_free_gb=16.0,
        cpu_count=8, disk_free_gb=100.0, current_load=0.1,
        installed_models=[
            InstalledModelState(model_id='qwen3.5:7b', residency=ModelResidency.HOT),
            InstalledModelState(model_id='qwen-coder:14b', residency=ModelResidency.WARM),
        ],
    )


@pytest.fixture
def engine() -> PolicyEngineV1:
    return PolicyEngineV1(PolicyConfig())


def test_fast_chat_routes_to_agent(engine, node_with_qwen):
    workload = WorkloadProfile(
        workload_type=WorkloadType.FAST_CHAT, complexity_score=0.3,
        latency_target_ms=6000, min_quality_score=50, preferred_size_classes=['7b'],
    )
    ctx = RoutingContext(request_id='req-001', workload=workload, node_capabilities=[node_with_qwen])
    plan = engine.resolve(ctx)
    assert plan.pull_decision.decision != PullDecisionType.REJECT
    assert plan.selected_model_id is not None


def test_coding_routes_to_coder(engine, node_with_qwen):
    workload = WorkloadProfile(
        workload_type=WorkloadType.CODING_ASSISTANT, complexity_score=0.8,
        latency_target_ms=15000, min_quality_score=75,
        preferred_size_classes=['9b', '14b'], disallowed_size_classes=['4b'],
    )
    ctx = RoutingContext(request_id='req-002', workload=workload, node_capabilities=[node_with_qwen])
    plan = engine.resolve(ctx)
    assert plan.selected_model_id is not None
    assert 'coder' in (plan.selected_model_id or '')


def test_no_nodes_returns_reject_or_downgrade(engine):
    workload = WorkloadProfile(
        workload_type=WorkloadType.FAST_CHAT, complexity_score=0.3,
        latency_target_ms=6000, min_quality_score=50, preferred_size_classes=['7b'],
    )
    ctx = RoutingContext(request_id='req-003', workload=workload, node_capabilities=[])
    plan = engine.resolve(ctx)
    assert plan.pull_decision.decision in (PullDecisionType.REJECT, PullDecisionType.DOWNGRADE)


def test_catalog_has_all_roles():
    catalog = get_catalog()
    roles = {e.role for e in catalog}
    assert 'agent' in roles
    assert 'coder' in roles
    assert 'reasoner' in roles
