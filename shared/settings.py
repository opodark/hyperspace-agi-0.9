# HyperSpace-AGI v5.9 - Settings
# Pydantic-settings: legge da env / .env file
from __future__ import annotations
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    # --- Ollama ---
    ollama_base_url: str = Field('http://ollama:11434', env='OLLAMA_BASE_URL')
    pull_timeout_seconds: int = Field(600, env='PULL_TIMEOUT_SECONDS')

    # --- Default models per workload type ---
    default_agent_model: str = Field('qwen3.5:7b', env='DEFAULT_AGENT_MODEL')
    default_coder_model: str = Field('qwen2.5-coder:9b', env='DEFAULT_CODER_MODEL')
    # v5.9: gemma4:12b sostituisce deepseek-r1:14b come reasoner default
    default_reasoner_model: str = Field('batiai/gemma4-12b:q4', env='DEFAULT_REASONER_MODEL')
    default_small_model: str = Field('gemma3:9b', env='DEFAULT_SMALL_MODEL')

    # --- Service ports ---
    authority_api_port: int = Field(8766, env='AUTHORITY_API_PORT')
    worker_api_port: int = Field(8767, env='WORKER_API_PORT')
    control_plane_api_port: int = Field(8768, env='CONTROL_PLANE_API_PORT')
    node_api_port: int = Field(8765, env='NODE_API_PORT')

    # --- Auth ---
    authority_token: str = Field('changeme', env='AUTHORITY_TOKEN')

    # --- Memory ---
    memory_state_dir: str = Field('/node/shared/memory', env='MEMORY_STATE_DIR')
    speculative_ttl_seconds: int = Field(3600, env='SPECULATIVE_TTL_SECONDS')

    # --- Dream / Validation ---
    validation_quorum: int = Field(3, env='VALIDATION_QUORUM')
    dream_replay_trigger: str = Field('auto', env='DREAM_REPLAY_TRIGGER')

    class Config:
        env_file = '.env'
        env_file_encoding = 'utf-8'
        case_sensitive = False


settings = Settings()
