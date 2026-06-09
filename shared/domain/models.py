# HyperSpace-AGI v5.9 - Domain Models
# Evolution from v5.8: adds ContestStatus, ReasoningTier, ValidationVote,
# ReasoningTrace, ModelCatalogEntry, RoutingContext, DreamReplayRecord
from __future__ import annotations
from enum import StrEnum
from typing import Literal, Any
from uuid import uuid4
from datetime import datetime
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums (v5.8 preserved + v5.9 additions)
# ---------------------------------------------------------------------------

class WorkloadType(StrEnum):
    FAST_CHAT = 'fast_chat'
    STRUCTURED_EXTRACTION = 'structured_extraction'
    TOOL_CALLING = 'tool_calling'
    CODING_ASSISTANT = 'coding_assistant'
    DEEP_REASONING = 'deep_reasoning'
    LONG_CONTEXT_ANALYSIS = 'long_context_analysis'

class ServiceTier(StrEnum):
    INTERACTIVE = 'interactive'
    BALANCED = 'balanced'
    QUALITY = 'quality'
    MAX_QUALITY = 'max_quality'

class ModelResidency(StrEnum):
    HOT = 'hot'
    WARM = 'warm'
    COLD = 'cold'

class PullDecisionType(StrEnum):
    NO = 'no'
    YES = 'yes'
    DELEGATE = 'delegate'
    DOWNGRADE = 'downgrade'
    REJECT = 'reject'

class TaskStatus(StrEnum):
    PENDING = 'pending'
    CLAIMED = 'claimed'
    RUNNING = 'running'
    COMPLETED = 'completed'
    FAILED = 'failed'
    CANCELED = 'canceled'
    TIMEOUT = 'timeout'

class NodeStatus(StrEnum):
    ACTIVE = 'active'
    DRAINING = 'draining'
    DREAMING = 'dreaming'
    OFFLINE = 'offline'

class MemoryTier(StrEnum):
    EPISODIC = 'episodic'
    SEMANTIC = 'semantic'
    SPECULATIVE = 'speculative'
    QUARANTINED = 'quarantined'
    CONTESTED = 'contested'

class DreamStatus(StrEnum):
    IDLE = 'idle'
    RUNNING = 'running'
    COMPLETED = 'completed'
    FAILED = 'failed'
    REPLAYING = 'replaying'

class ContestStatus(StrEnum):
    NONE = 'none'
    OPEN = 'open'
    RESOLVED_CONFIRM = 'confirmed'
    RESOLVED_RETRACT = 'retracted'
    ESCALATED = 'escalated'

class ReasoningTier(StrEnum):
    SHALLOW = 'shallow'
    STANDARD = 'standard'
    DEEP = 'deep'
    BOUNDED = 'bounded'


# ---------------------------------------------------------------------------
# v5.8 Models (preserved as-is for backward compat)
# ---------------------------------------------------------------------------

class RequestFeatures(BaseModel):
    requires_json_schema: bool = False
    requires_tools: bool = False
    requires_code_quality: bool = False
    requires_long_context: bool = False
    estimated_context_tokens: int = 4096
    user_priority: ServiceTier = ServiceTier.BALANCED

class ChatMessage(BaseModel):
    role: Literal['system', 'user', 'assistant']
    content: str

class UserRequest(BaseModel):
    request_id: str = Field(default_factory=lambda: str(uuid4()))
    model_alias: str
    messages: list[ChatMessage]
    features: RequestFeatures = Field(default_factory=RequestFeatures)

class WorkloadProfile(BaseModel):
    workload_type: WorkloadType
    complexity_score: float = Field(ge=0, le=1)
    latency_target_ms: int
    min_quality_score: int
    preferred_size_classes: list[str]
    disallowed_size_classes: list[str] = Field(default_factory=list)

class ModelProfile(BaseModel):
    model_id: str
    family: str
    # FIX v5.9: aggiunto '12b' per Gemma 4 12B (batiai/gemma4-12b:q4)
    size_class: Literal['4b', '7b', '9b', '12b', '14b']
    quantization: str
    ram_required_gb: float
    disk_size_gb: float
    supports_json_schema: bool = False
    supports_tools: bool = False
    max_context_tokens: int = 8192
    reasoning_score: int = Field(ge=0, le=100)
    coding_score: int = Field(ge=0, le=100)
    speed_score: int = Field(ge=0, le=100)

class InstalledModelState(BaseModel):
    model_id: str
    residency: ModelResidency

class NodeCapability(BaseModel):
    node_id: str
    ram_total_gb: float
    ram_free_gb: float
    cpu_count: int = 4
    disk_free_gb: float = 100.0
    current_load: float = Field(ge=0, le=1, default=0.0)
    installed_models: list[InstalledModelState] = Field(default_factory=list)
    max_parallel_generations: int = 1
    active_generations: int = 0

class NodeRecord(BaseModel):
    node_id: str
    node_name: str
    base_url: str
    status: NodeStatus = NodeStatus.ACTIVE
    last_heartbeat: str | None = None
    completed_tasks: int = 0
    last_task_at: str | None = None
    last_dream_at: str | None = None

class PlacementCandidate(BaseModel):
    node_id: str
    model_id: str
    residency: ModelResidency
    fit_score: float
    resource_score: float
    warmness_score: float
    pull_cost_score: float
    load_penalty: float
    final_score: float
    needs_pull: bool = False

class PullDecision(BaseModel):
    decision: PullDecisionType
    node_id: str | None = None
    model_id: str | None = None
    fallback_model_id: str | None = None
    reason: str

class ExecutionPlan(BaseModel):
    request_id: str
    workload: WorkloadProfile
    selected_node_id: str | None = None
    selected_model_id: str | None = None
    pull_decision: PullDecision
    placement_candidates: list[PlacementCandidate] = Field(default_factory=list)

class MemoryRecord(BaseModel):
    memory_id: str = Field(default_factory=lambda: str(uuid4()))
    session_id: str
    role: str
    content: str
    tier: MemoryTier = MemoryTier.EPISODIC
    score: float = 0.5
    source_task_id: str | None = None
    validation_status: str = 'none'
    validation_notes: str | None = None
    contest_status: ContestStatus = ContestStatus.NONE
    contest_opened_at: str | None = None
    contest_resolved_at: str | None = None
    ttl_expires_at: str | None = None

class MemoryEdge(BaseModel):
    edge_id: str = Field(default_factory=lambda: str(uuid4()))
    source_memory_id: str
    target_memory_id: str
    relation: Literal['supports', 'contradicts', 'derived_from', 'promotes_to', 'contests']
    weight: float = 0.5
    created_by: str = 'dream_validator'

class WorkerInfo(BaseModel):
    worker_id: str
    container_id: str
    container_name: str
    worker_url: str
    model_id: str
    owner_node_id: str
    last_heartbeat: str | None = None
    busy: bool = False

class WorkerTask(BaseModel):
    task_id: str
    session_id: str
    model: str
    messages: list[ChatMessage]
    memory_context: list[str] = Field(default_factory=list)
    planner_system_prompt: str
    retry_count: int = 0

class TaskState(BaseModel):
    task_id: str
    session_id: str
    worker_id: str | None = None
    model_id: str
    status: TaskStatus
    output: str | None = None
    tool_result: dict[str, Any] | None = None
    retry_count: int = 0
    cancel_requested: bool = False
    claimed_by: str | None = None
    lease_until: str | None = None

class TaskEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    task_id: str
    type: str
    payload: dict[str, Any] = Field(default_factory=dict)

class QueuedTask(BaseModel):
    task_id: str
    session_id: str
    request: UserRequest
    selected_model_id: str

class DreamState(BaseModel):
    dream_id: str = Field(default_factory=lambda: str(uuid4()))
    node_id: str
    status: DreamStatus = DreamStatus.IDLE
    summary: str | None = None
    speculative_count: int = 0
    semantic_updates: int = 0
    coherence_score: float = 0.0
    novelty_score: float = 0.0
    support_score: float = 0.0
    contradiction_score: float = 0.0
    replay_count: int = 0
    last_replayed_at: str | None = None
    vote_tally: dict[str, int] = Field(default_factory=dict)

class ChatCompletionsRequest(BaseModel):
    model: str
    messages: list[ChatMessage]
    stream: bool = False
    async_mode: bool = False

class OpenAIModelCard(BaseModel):
    id: str
    object: str = 'model'
    owned_by: str = 'hyperspace'

class OpenAIModelsResponse(BaseModel):
    object: str = 'list'
    data: list[OpenAIModelCard]


# ---------------------------------------------------------------------------
# NEW v5.9 Models
# ---------------------------------------------------------------------------

class ValidationVote(BaseModel):
    """Singolo voto di validazione su una MemoryRecord."""
    vote_id: str = Field(default_factory=lambda: str(uuid4()))
    memory_id: str
    dream_id: str
    voter_model_id: str
    vote: Literal['confirm', 'retract', 'abstain']
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str | None = None
    voted_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

class ValidationVoteTally(BaseModel):
    """Aggregato voti per una memory."""
    memory_id: str
    confirm_count: int = 0
    retract_count: int = 0
    abstain_count: int = 0
    avg_confidence: float = 0.0
    quorum_reached: bool = False
    resolution: ContestStatus = ContestStatus.OPEN

class ReasoningTrace(BaseModel):
    """Trace del reasoning di un modello per un task."""
    trace_id: str = Field(default_factory=lambda: str(uuid4()))
    task_id: str
    model_id: str
    raw_trace: str
    tier: ReasoningTier = ReasoningTier.STANDARD
    token_count: int = 0
    was_truncated: bool = False
    categories: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

class ModelCatalogEntry(BaseModel):
    """Voce nel catalogo modelli v5.9."""
    profile: ModelProfile
    ollama_tag: str
    role: Literal['agent', 'coder', 'reasoner', 'small', 'specialized']
    priority: int = Field(ge=1, le=10, default=5)
    is_available: bool = True
    last_checked_at: str | None = None

class RoutingContext(BaseModel):
    """Contesto passato al Policy Engine per decidere il routing."""
    request_id: str
    workload: WorkloadProfile
    available_catalog: list[ModelCatalogEntry] = Field(default_factory=list)
    node_capabilities: list[NodeCapability] = Field(default_factory=list)
    routing_level: Literal[1, 2, 3, 4] = 1
    fallback_allowed: bool = True

class DreamReplayRecord(BaseModel):
    """Record di un dream replay."""
    replay_id: str = Field(default_factory=lambda: str(uuid4()))
    dream_id: str
    trigger: Literal['scheduled', 'contest_resolved', 'model_upgraded', 'manual']
    replay_model_id: str
    memories_revalidated: int = 0
    votes_cast: int = 0
    retractions: int = 0
    promotions: int = 0
    started_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    completed_at: str | None = None
    success: bool = False
