"""Testes unitários completos para o motor de gamificação, metas, streaks e conquistas."""

from datetime import date, datetime, timedelta, timezone
import pytest

from study_agent.core.gamification import (
    BADGE_BY_ID,
    BADGE_CATALOG,
    GamificationEngine,
)
from study_agent.models.curriculum import (
    ActiveRecallEvaluation,
    Curriculum,
    Topic,
    TopicStatus,
)
from study_agent.models.student import (
    BadgeCategory,
    KnowledgeLevel,
    StudentProfile,
)


@pytest.fixture
def student() -> StudentProfile:
    return StudentProfile(
        id="std_gamif",
        name="Marina",
        target_subject="FastAPI",
        current_level=KnowledgeLevel.BEGINNER,
        target_level=KnowledgeLevel.ADVANCED,
    )


@pytest.fixture
def curriculum(student: StudentProfile) -> Curriculum:
    return Curriculum(
        id="curr_gamif",
        student_id=student.id,
        subject="FastAPI",
        overview="Trilha prática de APIs assíncronas",
        topics=[
            Topic(
                id="t1",
                title="Rotas e Path Params",
                description="Fundamentos de endpoints",
                status=TopicStatus.AVAILABLE,
            ),
            Topic(
                id="t2",
                title="Injeção de Dependências",
                description="Depends e segurança",
                status=TopicStatus.LOCKED,
                prerequisites=["t1"],
            ),
        ],
    )


def _make_eval(score: float, passing: bool = True) -> ActiveRecallEvaluation:
    return ActiveRecallEvaluation(
        question_id="q1",
        student_answer="Resposta técnica completa",
        score=score,
        understood_concepts=["Conceito A"],
        missing_or_confused_concepts=[],
        feedback="Muito bom!",
        is_passing=passing,
    )


def test_badge_catalog_integrity_and_categories():
    """Garante unicidade dos IDs e cobertura das 6 categorias oficiais."""
    ids = [b.id for b in BADGE_CATALOG]
    assert len(ids) == len(set(ids))
    assert len(BADGE_CATALOG) == 17
    categories_present = {b.category for b in BADGE_CATALOG}
    assert categories_present == set(BadgeCategory)
    assert "adquirindo_conhecimento" in BADGE_BY_ID
    assert "memoria_blindada" in BADGE_BY_ID


def test_level_progression_and_titles():
    """Valida a curva de níveis e títulos de Iniciante até Mestre."""
    expected = [
        (0, 1, "Iniciante"),
        (149, 1, "Iniciante"),
        (150, 2, "Explorador"),
        (400, 3, "Praticante"),
        (800, 4, "Construtor"),
        (1400, 5, "Especialista"),
        (2200, 6, "Mestre"),
        (3250, 7, "Mestre"),
    ]
    for xp, expected_lvl, expected_title in expected:
        prog = GamificationEngine.calculate_level_progress(xp)
        assert prog.level == expected_lvl
        assert prog.title == expected_title
        assert 0.0 <= prog.progress_pct <= 100.0


def test_xp_economy_anti_farming_lab_and_mastery(student: StudentProfile, curriculum: Curriculum):
    """Garante ganho único por missão prática (+15), 1º domínio (+100) e excelência (+25)."""
    topic = curriculum.topics[0]
    topic.total_lab_missions = 3

    # Conclui 2 missões inéditas -> +30 XP
    topic.completed_lab_steps = 2
    ev_lab1 = GamificationEngine.award_lab_mission_xp(student, topic, curriculum)
    assert ev_lab1.xp_gained == 30
    assert student.xp == 30

    # Repetir chamada sem novas missões -> 0 XP (anti-farming)
    ev_lab_repeat = GamificationEngine.award_lab_mission_xp(student, topic, curriculum)
    assert ev_lab_repeat.xp_gained == 0
    assert student.xp == 30

    # Conclui 3ª missão (100% do Lab) -> +15 XP e conquista 'Mão na Massa'
    topic.completed_lab_steps = 3
    ev_lab2 = GamificationEngine.award_lab_mission_xp(student, topic, curriculum)
    assert ev_lab2.xp_gained == 15
    assert student.xp == 45
    assert student.has_badge("mao_na_massa")

    # Tentativa reprovada (< 70%) -> 0 XP
    ev_fail = GamificationEngine.process_topic_evaluation(
        student=student,
        curriculum=curriculum,
        topic=topic,
        evaluation=_make_eval(55.0, passing=False),
    )
    assert ev_fail.xp_gained == 0
    assert student.xp == 45

    # Domina pela 1ª vez com 80% -> +100 XP (sem bônus de 90%), salta +25 pts -> 'Salto de Domínio'
    topic.status = TopicStatus.MASTERED
    ev_pass = GamificationEngine.process_topic_evaluation(
        student=student,
        curriculum=curriculum,
        topic=topic,
        evaluation=_make_eval(80.0, passing=True),
        was_mastered_before=False,
        previous_score=55.0,
    )
    assert ev_pass.xp_gained == 100
    assert student.xp == 145
    assert student.has_badge("primeiro_dominio")
    assert student.has_badge("salto_de_dominio")
    assert not student.has_badge("maestria_impecavel")

    # Reavalia o mesmo tópico atingindo 96% -> ganha APENAS o bônus inédito (+25 XP), não ganha +100 de novo
    ev_excel = GamificationEngine.process_topic_evaluation(
        student=student,
        curriculum=curriculum,
        topic=topic,
        evaluation=_make_eval(96.0, passing=True),
        was_mastered_before=True,
        previous_score=80.0,
    )
    assert ev_excel.xp_gained == 25
    assert student.xp == 170
    assert ev_excel.leveled_up is True
    assert student.level == 2
    assert student.level_title == "Explorador"
    assert student.has_badge("maestria_impecavel")

    # Terceira avaliação com 98% no mesmo tópico -> 0 XP total
    ev_zero = GamificationEngine.process_topic_evaluation(
        student=student,
        curriculum=curriculum,
        topic=topic,
        evaluation=_make_eval(98.0, passing=True),
        was_mastered_before=True,
    )
    assert ev_zero.xp_gained == 0


def test_streak_mechanics_and_srs_habit_without_xp(student: StudentProfile):
    """Valida ofensiva diária consecutiva, mesmo dia, quebra de sequência e 0 XP em revisões SRS."""
    d0 = date(2026, 11, 1)

    # Dia 1
    assert GamificationEngine.update_streak(student, reference_date=d0) is True
    assert student.current_streak == 1

    # Mesmo dia -> não incrementa
    assert GamificationEngine.update_streak(student, reference_date=d0) is False
    assert student.current_streak == 1

    # Dias 2 e 3 via Revisão SRS -> mantém streak, 0 XP e desbloqueia 'Faísca Inicial' (3d)
    ev_srs1 = GamificationEngine.record_srs_review(student, reference_date=d0 + timedelta(days=1))
    ev_srs2 = GamificationEngine.record_srs_review(student, reference_date=d0 + timedelta(days=2))
    assert ev_srs1.xp_gained == 0
    assert ev_srs2.xp_gained == 0
    assert student.xp == 0
    assert student.current_streak == 3
    assert student.longest_streak == 3
    assert student.has_badge("faisca_inicial")

    # Passaram 3 dias sem estudar -> get_effective_streak exibe 0 sem apagar longest_streak
    d_gap = d0 + timedelta(days=5)
    assert GamificationEngine.get_effective_streak(student, reference_date=d_gap) == 0
    assert student.longest_streak == 3

    # Retoma estudo após pausa -> current_streak reinicia em 1, longest_streak permanece 3
    GamificationEngine.update_streak(student, reference_date=d_gap)
    assert student.current_streak == 1
    assert student.longest_streak == 3


def test_streak_milestones_10_50_100_days_and_srs_badge(student: StudentProfile):
    """Testa desbloqueio das conquistas de 10, 50 e 100 dias e Memória Blindada (10 SRS)."""
    start = date(2026, 1, 1)
    for offset in range(100):
        GamificationEngine.record_srs_review(student, reference_date=start + timedelta(days=offset))

    assert student.current_streak == 100
    assert student.total_srs_reviews == 100
    assert student.xp == 0  # Revisões nunca inflam XP
    assert student.has_badge("faisca_inicial")
    assert student.has_badge("foco_10_dias")
    assert student.has_badge("disciplina_50_dias")
    assert student.has_badge("lenda_100_dias")
    assert student.has_badge("memoria_blindada")


def test_scale_badges_1_5_10_25_topics(student: StudentProfile):
    """Verifica desbloqueio progressivo de escala de tópicos dominados."""
    student.total_topics_mastered = 25
    GamificationEngine.evaluate_badges(student)
    assert student.has_badge("primeiro_dominio")
    assert student.has_badge("base_solida")
    assert student.has_badge("mente_afiada")
    assert student.has_badge("erudito_pratico")


def test_bug_hunter_and_sprint_goal_badges(student: StudentProfile, curriculum: Curriculum):
    """Testa Caçador de Bugs, Sprint Vencida (<=10d), Missão Cumprida e Trilha Completa."""
    now = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)
    goal_status = GamificationEngine.set_goal(
        curriculum, target_days=7, goal_label="Sprint FastAPI", now=now
    )
    assert goal_status.has_goal is True
    assert goal_status.days_remaining >= 7

    # Tópico 1 já dominado
    curriculum.topics[0].status = TopicStatus.MASTERED

    # Tópico 2 usa debug assistant e é dominado antes do deadline (3 dias depois)
    t2 = curriculum.topics[1]
    GamificationEngine.record_debug_usage(t2)
    t2.status = TopicStatus.MASTERED

    finish_time = now + timedelta(days=3)
    ev = GamificationEngine.process_topic_evaluation(
        student=student,
        curriculum=curriculum,
        topic=t2,
        evaluation=_make_eval(92.0, passing=True),
        was_mastered_before=False,
        now=finish_time,
    )

    assert ev.xp_gained == 125  # 100 + 25 bônus
    assert student.has_badge("cacador_de_bugs")
    assert student.has_badge("trilha_completa")
    assert student.has_badge("missao_cumprida")
    assert student.has_badge("sprint_vencida")
    assert student.has_badge("salto_de_dominio")  # BEGINNER -> ADVANCED ao concluir trilha
    assert student.current_level == KnowledgeLevel.ADVANCED


def test_overdue_goal_unlocks_track_complete_but_not_mission_accomplished(
    student: StudentProfile, curriculum: Curriculum
):
    """Se concluir a trilha após o prazo, ganha Trilha Completa mas não Missão Cumprida."""
    now = datetime(2026, 11, 1, 10, 0, tzinfo=timezone.utc)
    GamificationEngine.set_goal(curriculum, target_days=5, now=now)

    overdue_check = GamificationEngine.get_goal_status(curriculum, now=now + timedelta(days=8))
    assert overdue_check.is_overdue is True
    assert "expirado" in overdue_check.status_label

    curriculum.topics[0].status = TopicStatus.MASTERED
    curriculum.topics[1].status = TopicStatus.MASTERED

    GamificationEngine.process_topic_evaluation(
        student=student,
        curriculum=curriculum,
        topic=curriculum.topics[1],
        evaluation=_make_eval(85.0, passing=True),
        was_mastered_before=False,
        now=now + timedelta(days=8),
    )

    assert student.has_badge("trilha_completa")
    assert not student.has_badge("missao_cumprida")
    assert not student.has_badge("sprint_vencida")
