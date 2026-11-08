"""Módulo core com inteligência pedagógica e cliente LLM do AI Study Agent."""

from study_agent.core.curriculum_gen import CurriculumGenerator
from study_agent.core.diagnostician import Diagnostician, DiagnosticReport
from study_agent.core.llm_client import (
    LLMClient,
    LLMClientError,
    LLMResponseValidationError,
)

__all__ = [
    "LLMClient",
    "LLMClientError",
    "LLMResponseValidationError",
    "Diagnostician",
    "DiagnosticReport",
    "CurriculumGenerator",
]
