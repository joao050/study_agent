"""Módulo de modelos de dados estruturados do AI Study Agent."""

from study_agent.models.curriculum import (
    ActiveRecallEvaluation,
    ActiveRecallQuestion,
    Curriculum,
    ErrorDebugResolution,
    ExplanationStyle,
    GuidedLab,
    LabMission,
    RecallRecord,
    Topic,
    TopicStatus,
)
from study_agent.models.student import (
    BadgeCategory,
    DiagnosticAnswer,
    DiagnosticQuestion,
    KnowledgeLevel,
    StudentProfile,
    StudyPace,
    UnlockedBadge,
)

__all__ = [
    "BadgeCategory",
    "UnlockedBadge",
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
    "RecallRecord",
    "Topic",
    "Curriculum",
]
