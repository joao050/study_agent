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
    llm_model: str = "gemini/gemini-2.5-flash"
    temperature: float = 0.7
    max_tokens: int = 2048

    # Chaves de API de provedores suportados
    gemini_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None

    # Provedor local (Ollama)
    ollama_api_base: str = "http://localhost:11434"


@lru_cache()
def get_settings() -> Settings:
    """Retorna uma instância única (singleton em cache) das configurações."""
    return Settings()
