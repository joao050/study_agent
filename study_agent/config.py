"""Módulo de configuração e carregamento de variáveis de ambiente."""

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configurações da aplicação carregadas a partir de variáveis de ambiente ou arquivo .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Configuração padrão do LLM
    llm_provider: str = "gemini"
    llm_model: str = "gemini/gemini-flash-lite-latest"
    temperature: float = 0.7
    max_tokens: int = 2048

    # Resiliência e retentativas automáticas de conexão com LLM
    llm_num_retries: int = 3
    llm_retry_base_delay: float = 1.0
    llm_timeout: float = 60.0

    # Chaves de API de provedores suportados
    gemini_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None

    # Provedor local (Ollama)
    ollama_api_base: str = "http://localhost:11434"

    # Diretórios de persistência de dados e exportação
    data_dir: str = "data"
    exports_dir: str = "exports"


@lru_cache()
def get_settings() -> Settings:
    """Retorna uma instância única (singleton em cache) das configurações."""
    return Settings()
