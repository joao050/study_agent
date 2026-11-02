"""Testes unitários para os modelos Pydantic de Student e Curriculum."""

import pytest
from pydantic import ValidationError

from study_agent.models.curriculum import (
    ActiveRecallEvaluation,
    ActiveRecallQuestion,
    Curriculum,
    ExplanationStyle,
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


def test_student_profile_defaults_and_serialization():
    """Valida a criação com defaults e serialização bidirecional em JSON."""
    profile = StudentProfile(
        name="Carlos Silva",
        target_subject="Estruturas de Dados em Python"
    )

    assert profile.name == "Carlos Silva"
    assert profile.target_subject == "Estruturas de Dados em Python"
    assert profile.current_level == KnowledgeLevel.BEGINNER
    assert profile.target_level == KnowledgeLevel.ADVANCED
    assert profile.pace == StudyPace.REGULAR
    assert profile.daily_available_minutes == 45
    assert len(profile.diagnostic_history) == 0

    # Teste de serialização e desserialização JSON (Pydantic v2)
    json_data = profile.model_dump_json()
    reloaded = StudentProfile.model_validate_json(json_data)
    assert reloaded.id == profile.id
    assert reloaded.name == profile.name


def test_student_profile_score_boundaries():
    """Valida que notas fora do intervalo [0.0, 100.0] disparam erro de validação."""
    with pytest.raises(ValidationError):
        DiagnosticAnswer(
            question_id="q1",
            student_answer="Minha resposta",
            assessed_level=KnowledgeLevel.BEGINNER,
            feedback="Feedback",
            score=105.0  # Inválido: > 100
        )

    with pytest.raises(ValidationError):
        DiagnosticAnswer(
            question_id="q1",
            student_answer="Minha resposta",
            assessed_level=KnowledgeLevel.BEGINNER,
            feedback="Feedback",
            score=-5.0  # Inválido: < 0
        )


def test_curriculum_methods_and_status_transitions():
    """Testa busca de tópicos, atualização de pré-requisitos e cálculo de progresso."""
    topic1 = Topic(
        id="topico_01",
        title="Variáveis e Tipos Básicos",
        description="Fundamentos de tipagem em Python",
        status=TopicStatus.LOCKED,
        prerequisites=[]
    )
    topic2 = Topic(
        id="topico_02",
        title="Listas e Dicionários",
        description="Coleções de dados",
        status=TopicStatus.LOCKED,
        prerequisites=["topico_01"]
    )
    topic3 = Topic(
        id="topico_03",
        title="Árvores Binárias",
        description="Estruturas hierárquicas",
        status=TopicStatus.LOCKED,
        prerequisites=["topico_02"]
    )

    curriculum = Curriculum(
        student_id="student_123",
        subject="Python",
        overview="Trilha do zero ao avançado em Python",
        topics=[topic1, topic2, topic3]
    )

    # 1. Teste de busca por ID
    assert curriculum.get_topic("topico_01") is topic1
    assert curriculum.get_topic("topico_inexistente") is None

    # 2. Inicialmente 0% de progresso
    assert curriculum.calculate_overall_progress() == 0.0

    # 3. Atualizar status: topico_01 não tem pré-requisitos, deve se tornar AVAILABLE
    curriculum.update_topic_statuses()
    assert topic1.status == TopicStatus.AVAILABLE
    assert topic2.status == TopicStatus.LOCKED
    assert topic3.status == TopicStatus.LOCKED

    # 4. Conclui topico_01 e atualiza status: topico_02 deve virar AVAILABLE
    topic1.status = TopicStatus.MASTERED
    topic1.mastery_score = 85.0
    curriculum.update_topic_statuses()
    assert topic2.status == TopicStatus.AVAILABLE
    assert topic3.status == TopicStatus.LOCKED

    # 1 de 3 tópicos dominados = 33.33%
    assert curriculum.calculate_overall_progress() == 33.33

    # 5. Conclui todos os tópicos restantes
    topic2.status = TopicStatus.MASTERED
    curriculum.update_topic_statuses()
    assert topic3.status == TopicStatus.AVAILABLE

    topic3.status = TopicStatus.MASTERED
    assert curriculum.calculate_overall_progress() == 100.0


def test_active_recall_evaluation_validation():
    """Valida o modelo de retorno de avaliação de Active Recall."""
    eval_result = ActiveRecallEvaluation(
        question_id="ar_01",
        student_answer="Uma lista é mutável e ordenada.",
        score=90.0,
        understood_concepts=["mutabilidade", "ordenação"],
        missing_or_confused_concepts=[],
        feedback="Excelente síntese dos dois atributos principais.",
        is_passing=True
    )
    assert eval_result.is_passing is True
    assert eval_result.score == 90.0
