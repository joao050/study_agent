"""Testes unitários e de integração para o motor de Repetição Espaçada (SRS / SM-2)."""

from datetime import date, datetime, timedelta, timezone
import pytest

from study_agent.core.evaluator import Evaluator
from study_agent.core.srs import SpacedRepetitionEngine
from study_agent.models.curriculum import (
    ActiveRecallEvaluation,
    ActiveRecallQuestion,
    Curriculum,
    Topic,
    TopicStatus,
)
from study_agent.models.student import StudentProfile


@pytest.fixture
def student() -> StudentProfile:
    return StudentProfile(
        id="std_srs",
        name="Rafael",
        target_subject="Arquitetura Limpa",
    )


@pytest.fixture
def mastered_topic() -> Topic:
    return Topic(
        id="t_solid",
        title="Princípio da Inversão de Dependência",
        description="Depender de abstrações e não de implementações",
        status=TopicStatus.MASTERED,
        mastery_score=85.0,
    )


def test_score_to_quality_mapping():
    """Valida mapeamento da nota (0..100) para escala discreta SM-2 (0..5)."""
    assert SpacedRepetitionEngine.score_to_quality(98.0) == 5
    assert SpacedRepetitionEngine.score_to_quality(95.0) == 5
    assert SpacedRepetitionEngine.score_to_quality(88.0) == 4
    assert SpacedRepetitionEngine.score_to_quality(70.0) == 3
    assert SpacedRepetitionEngine.score_to_quality(60.0) == 2
    assert SpacedRepetitionEngine.score_to_quality(30.0) == 1
    assert SpacedRepetitionEngine.score_to_quality(10.0) == 0


def test_sm2_interval_cadence_and_ef_bounds(mastered_topic: Topic):
    """Testa progressão clássica SM-2 (1d -> 6d -> round(I * EF)), teto e piso de EF >= 1.3."""
    t0 = datetime(2026, 11, 1, 10, 0, tzinfo=timezone.utc)

    # 1ª revisão com nota 90% (q=4 -> EF permanece 2.50, intervalo = 1d)
    r1 = SpacedRepetitionEngine.apply_sm2(mastered_topic, score=90.0, now=t0)
    assert r1.quality == 4
    assert r1.is_retained is True
    assert r1.new_interval_days == 1
    assert r1.new_ef == 2.5
    assert mastered_topic.srs_repetitions == 1
    assert mastered_topic.next_review_at == t0 + timedelta(days=1)

    # 2ª revisão com nota 96% (q=5 -> EF sobe para 2.60, intervalo = 6d)
    t1 = t0 + timedelta(days=1)
    r2 = SpacedRepetitionEngine.apply_sm2(mastered_topic, score=96.0, now=t1)
    assert r2.quality == 5
    assert r2.new_interval_days == 6
    assert r2.new_ef == 2.6
    assert mastered_topic.srs_repetitions == 2

    # 3ª revisão com nota 90% (q=4 -> EF mantém 2.60, intervalo = round(6 * 2.6) = 16d)
    t2 = t1 + timedelta(days=6)
    r3 = SpacedRepetitionEngine.apply_sm2(mastered_topic, score=90.0, now=t2)
    assert r3.new_interval_days == 16
    assert mastered_topic.srs_repetitions == 3

    # Sequência de lapsos severos (q=0) nunca reduz EF abaixo de 1.3 e não bloqueia o tópico
    for _ in range(5):
        SpacedRepetitionEngine.apply_sm2(mastered_topic, score=0.0, now=t2)

    assert mastered_topic.easiness_factor == 1.3
    assert mastered_topic.srs_repetitions == 0
    assert mastered_topic.interval_days == 1
    assert mastered_topic.status == TopicStatus.MASTERED


def test_due_queue_filtering_ordering_and_legacy_support(student: StudentProfile):
    """Garante ordenação por urgência, suporte a tópicos legados sem data e exclusão de não-MASTERED."""
    now = datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc)
    curr = Curriculum(
        id="c1",
        student_id=student.id,
        subject="Go",
        overview="Concorrência",
        topics=[
            Topic(
                id="t_future",
                title="Goroutines",
                description="Leves",
                status=TopicStatus.MASTERED,
                next_review_at=now + timedelta(days=3),
            ),
            Topic(
                id="t_overdue_recent",
                title="Channels",
                description="Comunicação",
                status=TopicStatus.MASTERED,
                next_review_at=now - timedelta(hours=5),
            ),
            Topic(
                id="t_legacy",
                title="Structs",
                description="Tipos",
                status=TopicStatus.MASTERED,
                next_review_at=None,  # Tópico legado de fases anteriores
            ),
            Topic(
                id="t_overdue_old",
                title="Interfaces",
                description="Contratos",
                status=TopicStatus.MASTERED,
                next_review_at=now - timedelta(days=2),
            ),
            Topic(
                id="t_in_progress",
                title="Context",
                description="Cancelamento",
                status=TopicStatus.IN_PROGRESS,
            ),
        ],
    )

    due = SpacedRepetitionEngine.get_due_topics(curr, now=now)
    assert [t.id for t in due] == ["t_legacy", "t_overdue_old", "t_overdue_recent"]

    summary = SpacedRepetitionEngine.get_queue_summary(curr, now=now)
    assert summary.total_mastered == 4
    assert summary.due_now_count == 3
    assert summary.scheduled_future_count == 1
    assert summary.next_upcoming_at == now + timedelta(days=3)


def test_evaluator_schedules_initial_srs_review_on_first_mastery():
    """Verifica que dominar um tópico no Evaluator agenda automaticamente a 1ª revisão (+1 dia)."""
    evaluator = Evaluator(llm_client=object())  # type: ignore[arg-type]
    topic = Topic(id="t1", title="Indices SQL", description="B-Tree", status=TopicStatus.AVAILABLE)
    eval_pass = ActiveRecallEvaluation(
        question_id="q1",
        student_answer="Busca logarítmica",
        score=85.0,
        understood_concepts=["B-Tree"],
        missing_or_confused_concepts=[],
        feedback="Correto!",
        is_passing=True,
    )

    evaluator.update_topic_mastery(topic, eval_pass)
    assert topic.status == TopicStatus.MASTERED
    assert topic.interval_days == 1
    assert topic.next_review_at is not None


def test_complete_review_session_maintains_streak_zero_xp_and_unlocks_badge(
    student: StudentProfile, mastered_topic: Topic
):
    """Verifica que 10 sessões SRS mantêm Streak, dão 0 XP, salvam RecallRecord e liberam Memória Blindada."""
    curr = Curriculum(
        id="c_srs",
        student_id=student.id,
        subject="Clean Arch",
        overview="Trilha",
        topics=[mastered_topic],
    )
    q = ActiveRecallQuestion(
        id="q_srs",
        question="Por que módulos de alto nível não devem importar detalhes de banco?",
        expected_concepts=["Desacoplamento"],
    )
    ev = ActiveRecallEvaluation(
        question_id="q_srs",
        student_answer="Para proteger as regras de negócio contra mudanças externas.",
        score=92.0,
        understood_concepts=["Desacoplamento"],
        missing_or_confused_concepts=[],
        feedback="Excelente!",
        is_passing=True,
    )

    base_day = date(2026, 11, 1)
    base_dt = datetime(2026, 11, 1, 9, 0, tzinfo=timezone.utc)

    for i in range(10):
        srs_res, gamif_ev = SpacedRepetitionEngine.complete_review_session(
            student=student,
            curriculum=curr,
            topic=mastered_topic,
            evaluation=ev,
            question=q,
            reference_date=base_day + timedelta(days=i),
            now=base_dt + timedelta(days=i),
        )
        assert gamif_ev.xp_gained == 0

    assert student.xp == 0
    assert student.current_streak == 10
    assert student.total_srs_reviews == 10
    assert student.has_badge("memoria_blindada")
    assert student.has_badge("foco_10_dias")
    assert len(mastered_topic.recall_history) == 10
    assert srs_res.srs_repetitions == 10
