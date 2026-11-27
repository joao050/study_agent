"""Modelos de dados Pydantic para perfis de estudantes e diagnósticos de nível."""

from datetime import date, datetime, timezone
from enum import Enum
from typing import List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class BadgeCategory(str, Enum):
    """Categorias temáticas do catálogo de conquistas (badges)."""
    ONBOARDING = "onboarding"
    SCALE = "scale"
    PRACTICE = "practice"
    STREAK = "streak"
    GOALS = "goals"
    RETENTION = "retention"


class UnlockedBadge(BaseModel):
    """Registro persistido de uma conquista desbloqueada pelo estudante."""
    badge_id: str = Field(description="Identificador único da conquista no catálogo")
    unlocked_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    curriculum_id: Optional[str] = Field(
        default=None,
        description="ID da trilha em que a conquista foi obtida, quando aplicável",
    )


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
    xp: int = Field(
        default=0,
        ge=0,
        description="Total acumulado de pontos de experiência prática (XP)",
    )
    level: int = Field(
        default=1,
        ge=1,
        description="Nível atual calculado pela progressão de XP",
    )
    level_title: str = Field(
        default="Iniciante",
        description="Título correspondente ao nível atual do estudante",
    )
    current_streak: int = Field(
        default=0,
        ge=0,
        description="Ofensiva atual em dias consecutivos de estudo ou revisão",
    )
    longest_streak: int = Field(
        default=0,
        ge=0,
        description="Maior ofensiva histórica atingida em dias consecutivos",
    )
    last_study_date: Optional[date] = Field(
        default=None,
        description="Última data local em que o estudante realizou estudo ou revisão",
    )
    total_topics_mastered: int = Field(
        default=0,
        ge=0,
        description="Total acumulado de tópicos dominados pelo estudante",
    )
    total_srs_reviews: int = Field(
        default=0,
        ge=0,
        description="Total acumulado de revisões espaçadas (SRS) concluídas",
    )
    unlocked_badges: List[UnlockedBadge] = Field(
        default_factory=list,
        description="Conquistas (badges) desbloqueadas pelo estudante",
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def has_badge(self, badge_id: str) -> bool:
        """Verifica se o estudante já desbloqueou uma conquista específica."""
        return any(b.badge_id == badge_id for b in self.unlocked_badges)
