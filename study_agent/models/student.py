"""Modelos de dados Pydantic para perfis de estudantes e diagnósticos de nível."""

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class KnowledgeLevel(str, Enum):
    """Nível de conhecimento do estudante."""
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class StudyPace(str, Enum):
    """Ritmo de estudo pretendido pelo estudante."""
    RELAXED = "relaxed"       # 15 a 30 minutos diários
    REGULAR = "regular"       # 45 a 60 minutos diários
    INTENSIVE = "intensive"   # 90+ minutos diários


class DiagnosticQuestion(BaseModel):
    """Pergunta elaborada pela IA para sondagem e nivelamento prévio."""
    id: str = Field(default_factory=lambda: str(uuid4())[:8])
    question: str = Field(description="Enunciado da pergunta de nivelamento")
    topic_focus: str = Field(description="Subtópico ou conceito testado por esta questão")
    difficulty: KnowledgeLevel = Field(
        default=KnowledgeLevel.BEGINNER,
        description="Nível de profundidade esperado para a questão"
    )


class DiagnosticAnswer(BaseModel):
    """Registro da resposta do estudante e a avaliação atribuída pelo diagnosticador."""
    question_id: str
    student_answer: str
    assessed_level: KnowledgeLevel
    feedback: str = Field(description="Comentário didático sobre os pontos fortes e lacunas")
    score: float = Field(ge=0.0, le=100.0, description="Nota de 0 a 100")


class StudentProfile(BaseModel):
    """Perfil completo e persistível do estudante."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str = Field(description="Nome do estudante")
    target_subject: str = Field(description="Assunto ou tecnologia que deseja aprender")
    current_level: KnowledgeLevel = Field(
        default=KnowledgeLevel.BEGINNER,
        description="Nível atual estimado pelo diagnóstico"
    )
    target_level: KnowledgeLevel = Field(
        default=KnowledgeLevel.ADVANCED,
        description="Nível de profundidade desejado ao concluir a trilha"
    )
    pace: StudyPace = Field(
        default=StudyPace.REGULAR,
        description="Ritmo diário de dedicação"
    )
    daily_available_minutes: int = Field(
        default=45,
        ge=10,
        le=480,
        description="Tempo diário disponível para estudo em minutos"
    )
    diagnostic_history: List[DiagnosticAnswer] = Field(
        default_factory=list,
        description="Histórico de respostas ao teste de nivelamento inicial"
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
