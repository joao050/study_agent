"""Módulo de modelos de dados estruturados do AI Study Agent."""

from study_agent.models.curriculum import (
    ActiveRecallEvaluation,
    ActiveRecallQuestion,
    Curriculum,
    ErrorDebugResolution,
    ExplanationStyle,
    GuidedLab,
    LabMission,
    Topic,
    TopicStatus,
)
from study_agent.models.student import (
    DiagnosticAnswer,
    DiagnosticQuestion,
    KnowledgeLevel,
    StudentProfile,
    StudyPace,
)

__all__ = [
    "KnowledgeLevel",
    "StudyPace",
    "DiagnosticQuestion",
    "DiagnosticAnswer",
    "StudentProfile",
    "TopicStatus",
    "ExplanationStyle",
    "LabMission",
    "GuidedLab",
    "ErrorDebugResolution",
    "ActiveRecallQuestion",
    "ActiveRecallEvaluation",
    "Topic",
    "Curriculum",
]
