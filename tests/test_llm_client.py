"""Testes unitários para o cliente unificado de LLM (LLMClient)."""

from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel

from study_agent.config import Settings
from study_agent.core.llm_client import (
    LLMClient,
    LLMClientError,
    LLMResponseValidationError,
)


class DummySampleModel(BaseModel):
    title: str
    score: int


def test_llm_client_initialization():
    settings = Settings(
        llm_provider="gemini",
        llm_model="gemini/gemini-2.5-flash",
        gemini_api_key="test-gemini-key",
    )
    client = LLMClient(settings=settings)
    assert client.settings.llm_provider == "gemini"
    assert client.settings.gemini_api_key == "test-gemini-key"


def test_build_kwargs_provider_credentials():
    # Gemini
    gemini_client = LLMClient(
        settings=Settings(llm_provider="gemini", gemini_api_key="key-gem")
    )
    assert gemini_client._build_kwargs()["api_key"] == "key-gem"

    # OpenAI
    openai_client = LLMClient(
        settings=Settings(llm_provider="openai", openai_api_key="key-oai")
    )
    assert openai_client._build_kwargs()["api_key"] == "key-oai"

    # Anthropic
    anthropic_client = LLMClient(
        settings=Settings(llm_provider="anthropic", anthropic_api_key="key-ant")
    )
    assert anthropic_client._build_kwargs()["api_key"] == "key-ant"

    # Ollama
    ollama_client = LLMClient(
        settings=Settings(llm_provider="ollama", ollama_api_base="http://local-ollama:11434")
    )
    assert ollama_client._build_kwargs()["api_base"] == "http://local-ollama:11434"


@patch("litellm.completion")
def test_generate_text_success(mock_completion):
    mock_choice = MagicMock()
    mock_choice.message.content = "Olá, estudante!"
    mock_response = MagicMock(choices=[mock_choice])
    mock_completion.return_value = mock_response

    client = LLMClient(settings=Settings())
    result = client.generate(
        prompt="Diga olá",
        system_prompt="Você é um tutor",
        temperature=0.5,
    )

    assert result == "Olá, estudante!"
    mock_completion.assert_called_once()
    _, kwargs = mock_completion.call_args
    assert kwargs["temperature"] == 0.5
    assert len(kwargs["messages"]) == 2
    assert kwargs["messages"][0]["role"] == "system"
    assert kwargs["messages"][1]["role"] == "user"


@patch("litellm.completion")
def test_generate_text_failure_raises_llm_client_error(mock_completion):
    mock_completion.side_effect = RuntimeError("Erro de conexão na API")

    client = LLMClient(settings=Settings())
    with pytest.raises(LLMClientError, match="Falha ao chamar o LLM"):
        client.generate(prompt="Teste")


@patch("litellm.completion")
def test_generate_structured_success_with_json_markdown(mock_completion):
    mock_choice = MagicMock()
    # Simula resposta com blocos markdown ```json ... ```
    mock_choice.message.content = '```json\n{"title": "Matemática", "score": 95}\n```'
    mock_completion.return_value = MagicMock(choices=[mock_choice])

    client = LLMClient(settings=Settings())
    obj = client.generate_structured(
        prompt="Gere uma avaliação",
        response_model=DummySampleModel,
    )

    assert isinstance(obj, DummySampleModel)
    assert obj.title == "Matemática"
    assert obj.score == 95


@patch("litellm.completion")
def test_generate_structured_validation_error(mock_completion):
    mock_choice = MagicMock()
    # Resposta com tipo incorreto para o campo 'score' (espera int, envia string não numérica)
    mock_choice.message.content = '{"title": "História", "score": "nota_invalida"}'
    mock_completion.return_value = MagicMock(choices=[mock_choice])

    client = LLMClient(settings=Settings())
    with pytest.raises(LLMResponseValidationError, match="violou o schema"):
        client.generate_structured(
            prompt="Avalie",
            response_model=DummySampleModel,
        )


def test_extract_clean_json_variations():
    # JSON em bloco markdown com linguagem especificada
    raw1 = "```json\n{\"chave\": \"valor\"}\n```"
    assert LLMClient._extract_clean_json(raw1) == '{"chave": "valor"}'

    # JSON sem markdown, mas com texto antes e depois
    raw2 = "Aqui está a resposta:\n{\"numero\": 42}\nEspero que ajude!"
    assert LLMClient._extract_clean_json(raw2) == '{"numero": 42}'

    # Array JSON puro
    raw3 = "[1, 2, 3]"
    assert LLMClient._extract_clean_json(raw3) == '[1, 2, 3]'
