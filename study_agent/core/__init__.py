"""Módulo core com inteligência pedagógica e cliente LLM do AI Study Agent."""

from study_agent.core.curriculum_gen import CurriculumGenerator
from study_agent.core.diagnostician import Diagnostician, DiagnosticReport
from study_agent.core.evaluator import Evaluator
from study_agent.core.exporter import AnkiCard, ExportResult, StudyExporter
from study_agent.core.llm_client import (
    LLMAuthenticationError,
    LLMClient,
    LLMClientError,
    LLMConnectionError,
    LLMResponseValidationError,
)
from study_agent.core.teacher import Teacher

__all__ = [
    "LLMClient",
    "LLMClientError",
    "LLMConnectionError",
    "LLMAuthenticationError",
    "LLMResponseValidationError",
    "Diagnostician",
    "DiagnosticReport",
    "CurriculumGenerator",
    "Teacher",
    "Evaluator",
    "AnkiCard",
    "ExportResult",
    "StudyExporter",
]
