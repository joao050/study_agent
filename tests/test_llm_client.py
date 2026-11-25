"""Testes unitários para o cliente unificado de LLM (LLMClient)."""

from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel

from study_agent.config import Settings
from study_agent.core.llm_client import (
    LLMAuthenticationError,
    LLMClient,
    LLMClientError,
    LLMConnectionError,
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


@patch("study_agent.core.llm_client.time.sleep")
@patch("litellm.completion")
def test_retry_on_503_succeeds_with_exponential_backoff(mock_completion, mock_sleep):
    """Simula duas falhas 503 Service Unavailable seguidas de sucesso na 3ª tentativa."""
    mock_choice = MagicMock()
    mock_choice.message.content = "Resposta recuperada após oscilação!"
    success_response = MagicMock(choices=[mock_choice])

    mock_completion.side_effect = [
        RuntimeError("503 Service Unavailable - Model is overloaded"),
        RuntimeError("503 UNAVAILABLE"),
        success_response,
    ]

    retry_events = []
    settings = Settings(llm_num_retries=3, llm_retry_base_delay=1.0)
    client = LLMClient(
        settings=settings,
        on_retry=lambda attempt, max_r, delay, exc: retry_events.append((attempt, max_r, delay)),
    )

    result = client.generate(prompt="Explique redes")

    assert result == "Resposta recuperada após oscilação!"
    assert mock_completion.call_count == 3
    assert mock_sleep.call_count == 2
    assert len(retry_events) == 2
    assert retry_events[0][0] == 1 and retry_events[0][1] == 3
    assert retry_events[1][0] == 2 and retry_events[1][1] == 3
    # Verifica crescimento do backoff exponencial: tentativa 1 (~1s..1.25s) < tentativa 2 (~2s..2.25s)
    delay_1 = mock_sleep.call_args_list[0].args[0]
    delay_2 = mock_sleep.call_args_list[1].args[0]
    assert 1.0 <= delay_1 <= 1.25
    assert 2.0 <= delay_2 <= 2.25


@patch("study_agent.core.llm_client.time.sleep")
@patch("litellm.completion")
def test_retry_exhausted_raises_llm_connection_error(mock_completion, mock_sleep):
    """Verifica que esgotar todas as retentativas levanta LLMConnectionError com metadados."""
    mock_completion.side_effect = RuntimeError("503 Service Unavailable")

    settings = Settings(llm_num_retries=3, llm_retry_base_delay=0.5)
    client = LLMClient(settings=settings)

    with pytest.raises(LLMConnectionError, match="após 4 tentativa") as exc_info:
        client.generate(prompt="Teste 503 persistente")

    assert exc_info.value.attempts == 4
    assert exc_info.value.is_rate_limit is False
    assert mock_completion.call_count == 4
    assert mock_sleep.call_count == 3


@patch("study_agent.core.llm_client.time.sleep")
@patch("litellm.completion")
def test_rate_limit_429_sets_rate_limit_flag(mock_completion, mock_sleep):
    """Verifica detecção de erro 429 (Rate Limit / Resource Exhausted)."""
    mock_completion.side_effect = RuntimeError("429 RESOURCE_EXHAUSTED: Rate limit reached")

    settings = Settings(llm_num_retries=2, llm_retry_base_delay=0.5)
    client = LLMClient(settings=settings)

    with pytest.raises(LLMConnectionError) as exc_info:
        client.generate(prompt="Teste cota")

    assert exc_info.value.attempts == 3
    assert exc_info.value.is_rate_limit is True
    assert mock_completion.call_count == 3
    assert mock_sleep.call_count == 2


@patch("study_agent.core.llm_client.time.sleep")
@patch("litellm.completion")
def test_authentication_error_fails_immediately_without_retry(mock_completion, mock_sleep):
    """Garante que chaves de API inválidas (401/API_KEY_INVALID) falham na hora sem desperdiçar retries."""
    mock_completion.side_effect = RuntimeError("401 Unauthorized: API_KEY_INVALID")

    settings = Settings(llm_num_retries=3, llm_retry_base_delay=1.0)
    client = LLMClient(settings=settings)

    with pytest.raises(LLMAuthenticationError, match="credenciais ou chave de API inválidas"):
        client.generate(prompt="Teste chave inválida")

    assert mock_completion.call_count == 1
    assert mock_sleep.call_count == 0


@patch("study_agent.core.llm_client.time.sleep")
@patch("litellm.completion")
def test_generate_structured_503_does_not_double_retry(mock_completion, mock_sleep):
    """Garante que erro 503 em generate_structured não repete todo o ciclo sem response_format."""
    mock_completion.side_effect = RuntimeError("503 Service Unavailable")

    settings = Settings(llm_num_retries=2, llm_retry_base_delay=0.5)
    client = LLMClient(settings=settings)

    with pytest.raises(LLMConnectionError) as exc_info:
        client.generate_structured(prompt="Gere JSON", response_model=DummySampleModel)

    assert exc_info.value.attempts == 3
    assert mock_completion.call_count == 3
    assert mock_sleep.call_count == 2


@patch("study_agent.core.llm_client.time.sleep")
@patch("litellm.completion")
def test_generate_structured_fallback_when_response_format_unsupported(mock_completion, mock_sleep):
    """Garante fallback limpo sem sleep quando provedor não suporta response_format json_object."""
    mock_choice = MagicMock()
    mock_choice.message.content = '{"title": "Fallback OK", "score": 88}'
    mock_completion.side_effect = [
        ValueError("Unsupported param: response_format"),
        MagicMock(choices=[mock_choice]),
    ]

    client = LLMClient(settings=Settings(llm_num_retries=3))
    obj = client.generate_structured(prompt="Gere JSON", response_model=DummySampleModel)

    assert obj.title == "Fallback OK"
    assert obj.score == 88
    assert mock_completion.call_count == 2
    assert mock_sleep.call_count == 0
