"""Motor de Repetição Espaçada (SRS) baseado na Curva de Ebbinghaus e no algoritmo SuperMemo SM-2."""

from datetime import date, datetime, timedelta, timezone
from typing import List, Optional, Tuple

from pydantic import BaseModel, Field

from study_agent.core.gamification import GamificationEngine, GamificationEvent
from study_agent.models.curriculum import (
    ActiveRecallEvaluation,
    ActiveRecallQuestion,
    Curriculum,
    RecallRecord,
    Topic,
    TopicStatus,
)
from study_agent.models.student import StudentProfile


class SRSReviewResult(BaseModel):
    """Resultado do recálculo de agendamento SM-2 após uma revisão rápida."""

    topic_id: str
    quality: int = Field(ge=0, le=5, description="Qualidade SM-2 de 0 a 5 derivada da nota")
    is_retained: bool = Field(description="True quando quality >= 3 (nota >= 70%)")
    previous_interval_days: int
    new_interval_days: int
    previous_ef: float
    new_ef: float
    srs_repetitions: int
    next_review_at: datetime


class SRSQueueSummary(BaseModel):
    """Resumo executivo da fila de repetição espaçada de uma trilha."""

    total_mastered: int = 0
    due_now_count: int = 0
    scheduled_future_count: int = 0
    due_topic_ids: List[str] = Field(default_factory=list)
    next_upcoming_at: Optional[datetime] = None


class SpacedRepetitionEngine:
    """Implementação do algoritmo SM-2 adaptado para revisões ativas de tópicos dominados."""

    MIN_EASINESS_FACTOR: float = 1.3
    MAX_EASINESS_FACTOR: float = 5.0
    DEFAULT_EASINESS_FACTOR: float = 2.5
    INITIAL_INTERVAL_DAYS: int = 1
    SECOND_INTERVAL_DAYS: int = 6

    @staticmethod
    def _utc_now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _ensure_utc(dt: datetime) -> datetime:
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    @staticmethod
    def score_to_quality(score: float) -> int:
        """
        Converte uma nota pedagógica (0 a 100) para a escala discreta SM-2 (0 a 5):
        - 5: >= 95 (lembrança impecável e fluida)
        - 4: 85..94.9 (correta com segurança)
        - 3: 70..84.9 (correta com esforço; limiar de retenção)
        - 2: 50..69.9 (incompleta, mas lembrou conceitos parciais)
        - 1: 25..49.9 (errada, vaga familiaridade)
        - 0: < 25 (esquecimento completo)
        """
        if score >= 95.0:
            return 5
        if score >= 85.0:
            return 4
        if score >= 70.0:
            return 3
        if score >= 50.0:
            return 2
        if score >= 25.0:
            return 1
        return 0

    @classmethod
    def schedule_initial_review(
        cls,
        topic: Topic,
        now: Optional[datetime] = None,
    ) -> Topic:
        """Agenda a primeira revisão espaçada (+1 dia) assim que o tópico atinge MASTERED."""
        ref_now = cls._ensure_utc(now) if now else cls._utc_now()
        if topic.next_review_at is None:
            topic.interval_days = cls.INITIAL_INTERVAL_DAYS
            topic.next_review_at = ref_now + timedelta(days=cls.INITIAL_INTERVAL_DAYS)
        return topic

    @classmethod
    def is_topic_due(
        cls,
        topic: Topic,
        now: Optional[datetime] = None,
    ) -> bool:
        """Verifica se um tópico MASTERED está vencido (ou sem data inicial) para revisão."""
        if topic.status != TopicStatus.MASTERED:
            return False
        if topic.next_review_at is None:
            return True
        ref_now = cls._ensure_utc(now) if now else cls._utc_now()
        return cls._ensure_utc(topic.next_review_at) <= ref_now

    @classmethod
    def get_due_topics(
        cls,
        curriculum: Curriculum,
        now: Optional[datetime] = None,
    ) -> List[Topic]:
        """Retorna todos os tópicos MASTERED pendentes de revisão, ordenados por maior urgência."""
        ref_now = cls._ensure_utc(now) if now else cls._utc_now()
        due = [t for t in curriculum.topics if cls.is_topic_due(t, now=ref_now)]
        epoch_min = datetime.min.replace(tzinfo=timezone.utc)
        due.sort(key=lambda t: cls._ensure_utc(t.next_review_at) if t.next_review_at else epoch_min)
        return due

    @classmethod
    def get_queue_summary(
        cls,
        curriculum: Curriculum,
        now: Optional[datetime] = None,
    ) -> SRSQueueSummary:
        """Gera panorama completo da fila SRS (vencidos agora vs agendados para o futuro)."""
        ref_now = cls._ensure_utc(now) if now else cls._utc_now()
        mastered = [t for t in curriculum.topics if t.status == TopicStatus.MASTERED]
        due = cls.get_due_topics(curriculum, now=ref_now)
        due_ids = {t.id for t in due}

        future_dates = [
            cls._ensure_utc(t.next_review_at)
            for t in mastered
            if t.id not in due_ids and t.next_review_at is not None
        ]
        next_upcoming = min(future_dates) if future_dates else None

        return SRSQueueSummary(
            total_mastered=len(mastered),
            due_now_count=len(due),
            scheduled_future_count=len(mastered) - len(due),
            due_topic_ids=[t.id for t in due],
            next_upcoming_at=next_upcoming,
        )

    @classmethod
    def apply_sm2(
        cls,
        topic: Topic,
        score: float,
        now: Optional[datetime] = None,
        question: Optional[ActiveRecallQuestion] = None,
        evaluation: Optional[ActiveRecallEvaluation] = None,
    ) -> SRSReviewResult:
        """
        Aplica a equação clássica SuperMemo SM-2 atualizando EF, intervalo e próxima revisão.
        Em caso de lapso (quality < 3), reinicia o intervalo para 1 dia sem bloquear a trilha.
        """
        ref_now = cls._ensure_utc(now) if now else cls._utc_now()
        quality = cls.score_to_quality(score)
        prev_ef = topic.easiness_factor
        prev_interval = topic.interval_days
        prev_reps = topic.srs_repetitions

        # Fórmula SM-2: EF' = EF + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
        ef_delta = 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)
        new_ef = round(
            min(cls.MAX_EASINESS_FACTOR, max(cls.MIN_EASINESS_FACTOR, prev_ef + ef_delta)),
            2,
        )

        is_retained = quality >= 3
        if is_retained:
            if prev_reps == 0:
                new_interval = cls.INITIAL_INTERVAL_DAYS
            elif prev_reps == 1:
                new_interval = cls.SECOND_INTERVAL_DAYS
            else:
                base_days = max(1, prev_interval)
                new_interval = max(1, round(base_days * new_ef))
            new_reps = prev_reps + 1
            if topic.mastery_score > 0:
                topic.mastery_score = round((topic.mastery_score * 0.4) + (score * 0.6), 2)
            else:
                topic.mastery_score = round(score, 2)
        else:
            # Lapso de memória: reinicia cadeia de repetições e agenda reforço para amanhã (1d)
            new_reps = 0
            new_interval = cls.INITIAL_INTERVAL_DAYS
            if topic.mastery_score > 0:
                topic.mastery_score = round((topic.mastery_score * 0.7) + (score * 0.3), 2)

        next_dt = ref_now + timedelta(days=new_interval)

        topic.easiness_factor = new_ef
        topic.interval_days = new_interval
        topic.srs_repetitions = new_reps
        topic.review_count += 1
        topic.last_reviewed_at = ref_now
        topic.next_review_at = next_dt

        if question is not None and evaluation is not None:
            topic.recall_history.append(
                RecallRecord(
                    question=question.question,
                    student_answer=evaluation.student_answer,
                    expected_concepts=list(question.expected_concepts),
                    feedback=evaluation.feedback,
                    score=evaluation.score,
                    recorded_at=ref_now,
                )
            )

        return SRSReviewResult(
            topic_id=topic.id,
            quality=quality,
            is_retained=is_retained,
            previous_interval_days=prev_interval,
            new_interval_days=new_interval,
            previous_ef=prev_ef,
            new_ef=new_ef,
            srs_repetitions=new_reps,
            next_review_at=next_dt,
        )

    @classmethod
    def complete_review_session(
        cls,
        student: StudentProfile,
        curriculum: Curriculum,
        topic: Topic,
        evaluation: ActiveRecallEvaluation,
        question: Optional[ActiveRecallQuestion] = None,
        reference_date: Optional[date] = None,
        now: Optional[datetime] = None,
    ) -> Tuple[SRSReviewResult, GamificationEvent]:
        """
        Orquestra o fim de uma revisão SRS:
        1. Atualiza parâmetros SM-2 do tópico;
        2. Mantém a ofensiva diária (Streak) concedendo 0 XP e contabilizando 'Memória Blindada'.
        """
        srs_result = cls.apply_sm2(
            topic=topic,
            score=evaluation.score,
            now=now,
            question=question,
            evaluation=evaluation,
        )
        gamif_event = GamificationEngine.record_srs_review(
            student=student,
            curriculum=curriculum,
            reference_date=reference_date,
            now=now,
        )
        return srs_result, gamif_event
