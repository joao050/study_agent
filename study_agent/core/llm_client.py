"""Cliente unificado de LLM usando LiteLLM com suporte a Structured Outputs e resiliência."""

import json
import random
import re
import time
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar

import litellm
from pydantic import BaseModel, ValidationError

from study_agent.config import Settings, get_settings

T = TypeVar("T", bound=BaseModel)

MAX_BACKOFF_DELAY_SECONDS = 30.0


class LLMClientError(Exception):
    """Exceção base para falhas de comunicação ou execução do LLM."""

    pass


class LLMConnectionError(LLMClientError):
    """Exceção levantada após esgotar retentativas em falhas transitórias (503, 429, timeout, rede)."""

    def __init__(
        self,
        message: str,
        attempts: int = 1,
        status_code: Optional[int] = None,
        is_rate_limit: bool = False,
    ) -> None:
        super().__init__(message)
        self.attempts = attempts
        self.status_code = status_code
        self.is_rate_limit = is_rate_limit


class LLMAuthenticationError(LLMClientError):
    """Exceção levantada quando credenciais/chaves de API estão ausentes ou inválidas (401/403)."""

    pass


class LLMResponseValidationError(LLMClientError):
    """Exceção levantada quando a resposta do LLM não respeita o schema Pydantic esperado."""

    pass


class LLMClient:
    """Cliente unificado para múltiplos provedores (Gemini, OpenAI, Claude, Ollama) via LiteLLM."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        on_retry: Optional[Callable[[int, int, float, Exception], None]] = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.on_retry = on_retry
        self._configure_litellm()

    def _configure_litellm(self) -> None:
        """Ajusta configurações e chaves de provedor para a biblioteca LiteLLM."""
        litellm.telemetry = False
        litellm.suppress_debug_info = True

        if self.settings.gemini_api_key:
            litellm.api_key = self.settings.gemini_api_key

    def _build_kwargs(
        self,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Constrói os parâmetros adicionais de chamada conforme o provedor ativo."""
        kwargs: Dict[str, Any] = {
            "model": model or self.settings.llm_model,
            "temperature": temperature if temperature is not None else self.settings.temperature,
            "max_tokens": max_tokens or self.settings.max_tokens,
            "timeout": self.settings.llm_timeout,
        }

        # Injeção de credenciais específicas por provedor
        provider = self.settings.llm_provider.lower()
        if "gemini" in provider and self.settings.gemini_api_key:
            kwargs["api_key"] = self.settings.gemini_api_key
        elif "openai" in provider and self.settings.openai_api_key:
            kwargs["api_key"] = self.settings.openai_api_key
        elif "anthropic" in provider and self.settings.anthropic_api_key:
            kwargs["api_key"] = self.settings.anthropic_api_key
        elif "ollama" in provider and self.settings.ollama_api_base:
            kwargs["api_base"] = self.settings.ollama_api_base

        return kwargs

    @staticmethod
    def _is_authentication_error(exc: Exception) -> bool:
        """Identifica erros permanentes de autenticação ou chave de API inválida."""
        if isinstance(exc, litellm.AuthenticationError):
            return True
        status_code = getattr(exc, "status_code", None)
        if status_code in (401, 403):
            return True
        msg = str(exc).lower()
        auth_markers = (
            "api_key_invalid",
            "invalid api key",
            "authenticationerror",
            "unauthorized",
            "invalid x-api-key",
        )
        return any(marker in msg for marker in auth_markers)

    @classmethod
    def _is_retryable_error(cls, exc: Exception) -> bool:
        """Identifica falhas transitórias elegíveis para retry com backoff exponencial."""
        if cls._is_authentication_error(exc):
            return False

        if isinstance(
            exc,
            (
                litellm.ServiceUnavailableError,
                litellm.RateLimitError,
                litellm.Timeout,
                litellm.InternalServerError,
                litellm.APIConnectionError,
                TimeoutError,
                ConnectionError,
            ),
        ):
            return True

        status_code = getattr(exc, "status_code", None)
        if status_code in (408, 429, 500, 502, 503, 504):
            return True

        msg = str(exc).lower()
        transient_markers = (
            "503",
            "429",
            "502",
            "504",
            "service unavailable",
            "unavailable",
            "overloaded",
            "rate limit",
            "ratelimit",
            "resource_exhausted",
            "timed out",
            "timeout",
        )
        return any(marker in msg for marker in transient_markers)

    def _completion_with_retry(
        self,
        messages: List[Dict[str, str]],
        error_prefix: str = "Falha ao chamar o LLM",
        **kwargs: Any,
    ) -> Any:
        """Executa chamada ao LiteLLM com política de retry, backoff exponencial e jitter."""
        max_retries = max(0, self.settings.llm_num_retries)
        base_delay = max(0.0, self.settings.llm_retry_base_delay)

        for attempt in range(max_retries + 1):
            try:
                return litellm.completion(messages=messages, **kwargs)
            except Exception as exc:
                if self._is_authentication_error(exc):
                    raise LLMAuthenticationError(
                        f"{error_prefix}: credenciais ou chave de API inválidas ({exc})"
                    ) from exc

                if self._is_retryable_error(exc):
                    if attempt < max_retries:
                        backoff = base_delay * (2**attempt)
                        jitter = random.uniform(0.0, 0.25 * base_delay) if base_delay > 0 else 0.0
                        delay = min(backoff + jitter, MAX_BACKOFF_DELAY_SECONDS)
                        if self.on_retry:
                            self.on_retry(attempt + 1, max_retries, delay, exc)
                        time.sleep(delay)
                        continue

                    status_code = getattr(exc, "status_code", None)
                    msg_lower = str(exc).lower()
                    is_rate_limit = (
                        isinstance(exc, litellm.RateLimitError)
                        or status_code == 429
                        or "429" in msg_lower
                        or "rate limit" in msg_lower
                        or "resource_exhausted" in msg_lower
                    )
                    total_attempts = max_retries + 1
                    raise LLMConnectionError(
                        f"{error_prefix} após {total_attempts} tentativa(s): {exc}",
                        attempts=total_attempts,
                        status_code=status_code,
                        is_rate_limit=is_rate_limit,
                    ) from exc

                raise LLMClientError(f"{error_prefix}: {exc}") from exc

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Gera resposta em texto livre a partir de um prompt."""
        messages: List[Dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        kwargs = self._build_kwargs(model=model, temperature=temperature, max_tokens=max_tokens)
        response = self._completion_with_retry(
            messages=messages,
            error_prefix="Falha ao chamar o LLM",
            **kwargs,
        )
        return response.choices[0].message.content or ""

    def generate_structured(
        self,
        prompt: str,
        response_model: Type[T],
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> T:
        """Gera resposta no formato JSON estruturado e valida com o modelo Pydantic fornecido.

        Adiciona instruções de schema ao prompt do sistema e extrai o JSON puro da resposta,
        garantindo compatibilidade com provedores que não suportam JSON Schema nativo.
        """
        schema_json = json.dumps(response_model.model_json_schema(), indent=2, ensure_ascii=False)

        instruction = (
            f"\n\nATENÇÃO: Você DEVE responder OBRIGATORIAMENTE em formato JSON válido, "
            f"seguindo estritamente este JSON Schema Pydantic:\n{schema_json}\n"
            f"Não inclua nenhum texto adicional, saudações ou comentários fora do JSON."
        )

        full_system_prompt = (
            f"{system_prompt}{instruction}" if system_prompt else instruction.strip()
        )

        messages: List[Dict[str, str]] = [
            {"role": "system", "content": full_system_prompt},
            {"role": "user", "content": prompt},
        ]

        kwargs = self._build_kwargs(model=model, temperature=temperature, max_tokens=max_tokens)

        # Habilita json_object se o modelo suportar
        kwargs["response_format"] = {"type": "json_object"}

        try:
            response = self._completion_with_retry(
                messages=messages,
                error_prefix="Falha ao chamar o LLM para saída estruturada",
                **kwargs,
            )
            raw_text = response.choices[0].message.content or ""
        except (LLMConnectionError, LLMAuthenticationError):
            # Erros de rede/sobrecarga (já retentados) ou de autenticação propagam diretamente
            raise
        except LLMClientError:
            # Tenta sem response_format caso o provedor/modelo não suporte a flag json_object
            kwargs.pop("response_format", None)
            response = self._completion_with_retry(
                messages=messages,
                error_prefix="Falha ao chamar o LLM para saída estruturada",
                **kwargs,
            )
            raw_text = response.choices[0].message.content or ""

        cleaned_json = self._extract_clean_json(raw_text)

        try:
            return response_model.model_validate_json(cleaned_json)
        except ValidationError as exc:
            raise LLMResponseValidationError(
                f"A resposta gerada pelo LLM violou o schema '{response_model.__name__}': {str(exc)}\nJSON recebido: {cleaned_json}"
            ) from exc
        except Exception as exc:
            raise LLMResponseValidationError(
                f"Erro ao converter resposta em JSON para '{response_model.__name__}': {str(exc)}\nTexto bruto: {raw_text}"
            ) from exc

    @staticmethod
    def _extract_clean_json(raw_text: str) -> str:
        """Extrai o bloco JSON puro de uma resposta em texto, limpando eventuais marcações markdown."""
        text = raw_text.strip()

        # Remove blocos de código markdown ```json ... ``` ou ``` ... ```
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        if match:
            text = match.group(1).strip()

        # Busca pelo primeiro caractere de abertura ({ ou [) e o último de fechamento (} ou ])
        start_brace = text.find("{")
        start_bracket = text.find("[")

        if start_brace != -1 and (start_bracket == -1 or start_brace < start_bracket):
            end_brace = text.rfind("}")
            if end_brace != -1:
                return text[start_brace : end_brace + 1]
        elif start_bracket != -1:
            end_bracket = text.rfind("]")
            if end_bracket != -1:
                return text[start_bracket : end_bracket + 1]

        return text
