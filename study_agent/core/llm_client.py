"""Cliente unificado de LLM usando LiteLLM com suporte a Structured Outputs."""

import json
import re
from typing import Any, Dict, List, Optional, Type, TypeVar

import litellm
from pydantic import BaseModel, ValidationError

from study_agent.config import Settings, get_settings

T = TypeVar("T", bound=BaseModel)


class LLMClientError(Exception):
    """Exceção base para falhas de comunicação ou execução do LLM."""

    pass


class LLMResponseValidationError(LLMClientError):
    """Exceção levantada quando a resposta do LLM não respeita o schema Pydantic esperado."""

    pass


class LLMClient:
    """Cliente unificado para múltiplos provedores (Gemini, OpenAI, Claude, Ollama) via LiteLLM."""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()
        self._configure_litellm()

    def _configure_litellm(self) -> None:
        """Ajusta configurações e chaves de provedor para a biblioteca LiteLLM."""
        litellm.telemetry = False

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

        try:
            response = litellm.completion(messages=messages, **kwargs)
            return response.choices[0].message.content or ""
        except Exception as exc:
            raise LLMClientError(f"Falha ao chamar o LLM: {str(exc)}") from exc

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
            response = litellm.completion(messages=messages, **kwargs)
            raw_text = response.choices[0].message.content or ""
        except Exception as exc:
            # Tenta sem response_format caso o provedor/modelo não suporte a flag
            try:
                kwargs.pop("response_format", None)
                response = litellm.completion(messages=messages, **kwargs)
                raw_text = response.choices[0].message.content or ""
            except Exception as inner_exc:
                raise LLMClientError(f"Falha ao chamar o LLM para saída estruturada: {str(inner_exc)}") from inner_exc

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
