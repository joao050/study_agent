"""Modelos de dados Pydantic para a trilha pedagógica, tópicos e avaliações."""

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class TopicStatus(str, Enum):
    """Estado de progresso de um tópico na trilha."""
    LOCKED = "locked"           # Bloqueado por haver pré-requisitos pendentes
    AVAILABLE = "available"     # Desbloqueado e pronto para estudo
    IN_PROGRESS = "in_progress" # Sessão iniciada, ainda sem domínio consolidado
    MASTERED = "mastered"       # Concluído com nota de domínio atingida (>= 70%)


class ExplanationStyle(str, Enum):
    """Estilo pedagógico adotado pelo tutor durante a explicação."""
    FEYNMAN = "feynman"     # Analogias simples, linguagem do cotidiano, foco no conceito nuclear
    TECHNICAL = "technical" # Rigor formal, terminologia exata e detalhes de baixo nível
    PRACTICAL = "practical" # Foco 'mão na massa', exemplos práticos de código e casos de uso reais


class ActiveRecallQuestion(BaseModel):
    """Pergunta formulada para checagem ativa de absorção (Active Recall)."""
    id: str = Field(default_factory=lambda: str(uuid4())[:8])
    question: str = Field(description="Pergunta aberta para testar raciocínio e retenção")
    expected_concepts: List[str] = Field(
        default_factory=list,
        description="Conceitos-chave que uma resposta exemplar deve contemplar"
    )
    hint: Optional[str] = Field(
        default=None,
        description="Dica sutil caso o estudante encontre dificuldades"
    )


class ActiveRecallEvaluation(BaseModel):
    """Resultado da correção de uma resposta de Active Recall pelo avaliador."""
    question_id: str
    student_answer: str
    score: float = Field(ge=0.0, le=100.0, description="Nota de 0 a 100")
    understood_concepts: List[str] = Field(
        default_factory=list,
        description="Pontos e ideias que o aluno demonstrou dominar bem"
    )
    missing_or_confused_concepts: List[str] = Field(
        default_factory=list,
        description="Lacunas conceituais ou equívocos identificados"
    )
    feedback: str = Field(description="Retorno pedagógico construtivo")
    is_passing: bool = Field(
        description="True se o estudante atingiu a nota mínima para progredir"
    )


class Topic(BaseModel):
    """Unidade atômica de aprendizado dentro de uma trilha."""
    id: str = Field(description="Identificador único (ex: 'mod1_topico01' ou uuid)")
    title: str = Field(description="Título direto e claro do tópico")
    description: str = Field(description="Breve síntese do que será aprendido")
    estimated_minutes: int = Field(
        default=30,
        ge=5,
        description="Tempo estimado em minutos para absorver e praticar"
    )
    prerequisites: List[str] = Field(
        default_factory=list,
        description="Lista de IDs de tópicos que devem ser dominados antes deste"
    )
    status: TopicStatus = Field(
        default=TopicStatus.LOCKED,
        description="Estado atual do tópico na trilha"
    )
    mastery_score: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
        description="Nota de retenção atual (0 a 100)"
    )
    review_count: int = Field(
        default=0,
        ge=0,
        description="Quantas vezes o tópico foi revisado ou testado"
    )
    last_reviewed_at: Optional[datetime] = None
    key_takeaways: List[str] = Field(
        default_factory=list,
        description="Pontos centrais e resumos salvos após as sessões"
    )


class Curriculum(BaseModel):
    """Trilha completa de aprendizado personalizada para o estudante."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    student_id: str = Field(description="ID do estudante proprietário desta trilha")
    subject: str = Field(description="Assunto geral da trilha")
    overview: str = Field(description="Descrição panorâmica do percurso de aprendizado")
    topics: List[Topic] = Field(
        default_factory=list,
        description="Lista ordenada de tópicos a serem cursados"
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def get_topic(self, topic_id: str) -> Optional[Topic]:
        """Recupera um tópico pelo seu identificador."""
        for topic in self.topics:
            if topic.id == topic_id:
                return topic
        return None

    def update_topic_statuses(self) -> None:
        """
        Atualiza automaticamente o status de cada tópico com base nos pré-requisitos:
        - Se não tiver pré-requisitos ou todos estiverem MASTERED, e o tópico estiver LOCKED,
          torna-o AVAILABLE.
        """
        mastered_ids = {t.id for t in self.topics if t.status == TopicStatus.MASTERED}
        for topic in self.topics:
            if topic.status == TopicStatus.LOCKED:
                if not topic.prerequisites or all(prereq in mastered_ids for prereq in topic.prerequisites):
                    topic.status = TopicStatus.AVAILABLE

    def calculate_overall_progress(self) -> float:
        """Calcula o percentual (0.0 a 100.0) de tópicos dominados na trilha."""
        if not self.topics:
            return 0.0
        mastered_count = sum(1 for t in self.topics if t.status == TopicStatus.MASTERED)
        return round((mastered_count / len(self.topics)) * 100.0, 2)
