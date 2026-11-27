"""Testes unitários para os modelos Pydantic de Student e Curriculum."""

import pytest
from pydantic import ValidationError

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


def test_guided_lab_and_error_debug_models():
    """Valida os schemas Pydantic de laboratório guiado e diagnóstico de erros."""
    assert ExplanationStyle.GUIDED_LAB == "guided_lab"

    mission = LabMission(
        step_number=1,
        title="Verificar instalação do Docker",
        instruction="Confira se o cliente Docker está acessível no terminal.",
        command_or_code="docker --version",
        expected_outcome="Exibe a versão instalada, ex: Docker version 27.x",
        verification_hint="No Windows, abra o Docker Desktop antes.",
    )
    lab = GuidedLab(
        topic_id="t1",
        intro_brief="Containers isolam processos usando recursos do kernel.",
        prerequisites_check="Docker Desktop instalado",
        missions=[mission],
    )
    assert lab.topic_id == "t1"
    assert len(lab.missions) == 1
    assert lab.missions[0].step_number == 1

    with pytest.raises(ValidationError):
        GuidedLab(topic_id="t1", intro_brief="Sem missões", missions=[])

    resolution = ErrorDebugResolution(
        error_summary="O cliente Docker não conseguiu conectar ao motor (daemon).",
        root_cause="O serviço do Docker Desktop está fechado ou parado.",
        fix_instructions=["Abra o aplicativo Docker Desktop", "Aguarde o ícone ficar verde"],
        corrected_command_or_code="docker ps",
        prevention_tip="Sempre verifique se o motor está ativo antes de rodar containers.",
    )
    assert len(resolution.fix_instructions) == 2
    assert resolution.corrected_command_or_code == "docker ps"

    topic = Topic(id="t_lab", title="Volumes", description="Persistência")
    assert topic.completed_lab_steps == 0
    assert topic.rewarded_lab_steps == 0
    assert topic.used_debug_assistant is False


def test_legacy_json_retrocompatibility_for_gamification_fields():
    """Garante que JSONs salvos nas Fases 1/2 (sem campos da Fase 3) carregam sem erro."""
    legacy_student_json = '{"id": "old_1", "name": "João", "target_subject": "Python"}'
    student = StudentProfile.model_validate_json(legacy_student_json)
    assert student.xp == 0
    assert student.level == 1
    assert student.level_title == "Iniciante"
    assert student.current_streak == 0
    assert student.unlocked_badges == []

    legacy_curr_json = (
        '{"id": "c_old", "student_id": "old_1", "subject": "Python", '
        '"overview": "Base", "topics": [{"id": "t1", "title": "Intro", "description": "Desc"}]}'
    )
    curr = Curriculum.model_validate_json(legacy_curr_json)
    assert curr.target_days is None
    assert curr.deadline_at is None
    assert curr.topics[0].mastery_xp_awarded is False
