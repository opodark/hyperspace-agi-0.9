# HyperSpace-AGI v5.9 - Settings
# Configurazione centralizzata con model catalog e policy engine
from __future__ import annotations
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class HyperspaceSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,
        extra='ignore',
    )

    # Node identity
    node_id: str = Field(default='default-node', alias='NODE_ID')
    node_role: str = Field(default='orchestrator', alias='NODE_ROLE')
    node_api_port: int = Field(default=8765, alias='NODE_API_PORT')

    # Ollama
    ollama_base_url: str = Field(default='http://ollama:11434', alias='OLLAMA_BASE_URL')
    ollama_timeout_s: int = Field(default=120, alias='OLLAMA_TIMEOUT_S')

    # Model defaults v5.9 (upgrade da Phi Mini)
    default_agent_model: str = Field(default='qwen3.5:7b', alias='DEFAULT_AGENT_MODEL')
    default_coder_model: str = Field(default='qwen-coder:14b', alias='DEFAULT_CODER_MODEL')
    default_reasoner_model: str = Field(default='deepseek-r1:14b', alias='DEFAULT_REASONER_MODEL')
    default_small_model: str = Field(default='gemma4:7b', alias='DEFAULT_SMALL_MODEL')

    # Policy Engine v1
    policy_engine_version: int = Field(default=1, alias='POLICY_ENGINE_VERSION')
    routing_strategy: str = Field(default='smart-4level', alias='ROUTING_STRATEGY')
    routing_levels: int = Field(default=4, alias='ROUTING_LEVELS')
    model_catalog_enabled: bool = Field(default=True, alias='MODEL_CATALOG_ENABLED')

    # Memory & Dream
    dream_validator_enabled: bool = Field(default=True, alias='DREAM_VALIDATOR_ENABLED')
    validation_vote_store_enabled: bool = Field(default=True, alias='VALIDATION_VOTE_STORE_ENABLED')
    dream_replay_enabled: bool = Field(default=True, alias='DREAM_REPLAY_ENABLED')
    contested_memory_enabled: bool = Field(default=True, alias='CONTESTED_MEMORY_ENABLED')
    memory_ttl_speculative_s: int = Field(default=3600, alias='MEMORY_TTL_SPECULATIVE_S')
    vote_quorum: int = Field(default=3, alias='VOTE_QUORUM')  # voti minimi per risolvere

    # Reasoning Trace
    reasoning_trace_max_tokens: int = Field(default=8192, alias='REASONING_TRACE_MAX_TOKENS')
    reasoning_trace_truncate: bool = Field(default=True, alias='REASONING_TRACE_TRUNCATE')

    # API
    control_plane_api_port: int = Field(default=8768, alias='CONTROL_PLANE_API_PORT')
    authority_api_port: int = Field(default=8766, alias='AUTHORITY_API_PORT')
    worker_api_port: int = Field(default=8767, alias='WORKER_API_PORT')


settings = HyperspaceSettings()
