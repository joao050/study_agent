"""Testes automatizados para a interface de linha de comando CLI (tests/test_cli.py)."""

from unittest.mock import MagicMock, patch
import pytest
from typer.testing import CliRunner

from study_agent import __version__
from study_agent.cli import app
from study_agent.core.diagnostician import DiagnosticReport
from study_agent.models.curriculum import (
    ActiveRecallEvaluation,
    ActiveRecallQuestion,
    Curriculum,
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

runner = CliRunner()


@pytest.fixture
def sample_student() -> StudentProfile:
    return StudentProfile(
        id="std_123",
        name="Lucas",
        target_subject="Docker para Desenvolvedores",
        current_level=KnowledgeLevel.BEGINNER,
        target_level=KnowledgeLevel.ADVANCED,
        pace=StudyPace.REGULAR,
        daily_available_minutes=45,
    )


@pytest.fixture
def sample_curriculum(sample_student: StudentProfile) -> Curriculum:
    return Curriculum(
        id="curr_123",
        student_id=sample_student.id,
        subject="Docker para Desenvolvedores",
        overview="Trilha completa de containers.",
        topics=[
            Topic(
                id="t1",
                title="Containers vs VMs",
                description="Conceitos de isolamento de processos",
                estimated_minutes=25,
                status=TopicStatus.AVAILABLE,
                prerequisites=[],
            ),
            Topic(
                id="t2",
                title="Dockerfile e Camadas",
                description="Construção de imagens otimizadas",
                estimated_minutes=35,
                status=TopicStatus.LOCKED,
                prerequisites=["t1"],
            ),
        ],
    )


def test_cli_version():
    """Verifica comando version."""
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "AI Study Agent" in result.output
    assert __version__ in result.output


def test_cli_status_no_session():
    """Verifica mensagem amigável ao pedir status sem sessão ativa."""
    with patch("study_agent.cli.get_store") as mock_get_store:
        mock_store = MagicMock()
        mock_store.load_active_session.return_value = (None, None)
        mock_get_store.return_value = mock_store

        result = runner.invoke(app, ["status"])
        assert result.exit_code == 0
        assert "Nenhuma sessão ativa encontrada" in result.output


def test_cli_status_with_session(sample_student: StudentProfile, sample_curriculum: Curriculum):
    """Verifica painel e tabela de status para sessão ativa."""
    with patch("study_agent.cli.get_store") as mock_get_store:
        mock_store = MagicMock()
        mock_store.load_active_session.return_value = (sample_student, sample_curriculum)
        mock_get_store.return_value = mock_store

        result = runner.invoke(app, ["status"])
        assert result.exit_code == 0
        assert "Lucas" in result.output
        assert "Docker para Desenvolvedores" in result.output
        assert "Containers vs VMs" in result.output
        assert "Disponível" in result.output


def test_cli_map_ascii_and_mermaid(sample_student: StudentProfile, sample_curriculum: Curriculum):
    """Testa renderização de mapa conceitual padrão e flag --mermaid."""
    with patch("study_agent.cli.get_store") as mock_get_store:
        mock_store = MagicMock()
        mock_store.load_active_session.return_value = (sample_student, sample_curriculum)
        mock_get_store.return_value = mock_store

        # Teste mapa ASCII
        res_ascii = runner.invoke(app, ["map"])
        assert res_ascii.exit_code == 0
        assert "Trilha de Aprendizado" in res_ascii.output

        # Teste flag Mermaid
        res_mermaid = runner.invoke(app, ["map", "--mermaid"])
        assert res_mermaid.exit_code == 0
        assert "flowchart TD" in res_mermaid.output
        assert "t1 --> t2" in res_mermaid.output


def test_cli_students_listing_and_switch(sample_student: StudentProfile, sample_curriculum: Curriculum):
    """Testa listagem de estudantes e alternância de sessão ativa."""
    with patch("study_agent.cli.get_store") as mock_get_store:
        mock_store = MagicMock()
        mock_store.list_students.return_value = [sample_student]
        mock_store.get_current_session.return_value = (sample_student.id, sample_curriculum.id)
        mock_store.load_student.return_value = sample_student
        mock_store.load_curriculum_by_student.return_value = sample_curriculum
        mock_get_store.return_value = mock_store

        # Listagem
        res_list = runner.invoke(app, ["students"])
        assert res_list.exit_code == 0
        assert "Lucas" in res_list.output
        assert "Estudantes Cadastrados" in res_list.output

        # Alternar estudante
        res_switch = runner.invoke(app, ["students", "--switch", sample_student.id])
        assert res_switch.exit_code == 0
        assert "Sessão alternada com sucesso" in res_switch.output
        mock_store.set_current_session.assert_called_once_with(sample_student.id, sample_curriculum.id)


def test_cli_study_all_mastered(sample_student: StudentProfile):
    """Verifica mensagem de conclusão quando todos os tópicos estão dominados."""
    completed_curriculum = Curriculum(
        student_id=sample_student.id,
        subject="Python",
        overview="Feito",
        topics=[
            Topic(
                id="t1",
                title="Tópico Único",
                description="Desc",
                status=TopicStatus.MASTERED,
                mastery_score=95.0,
            )
        ],
    )

    with patch("study_agent.cli.get_store") as mock_get_store:
        mock_store = MagicMock()
        mock_store.load_active_session.return_value = (sample_student, completed_curriculum)
        mock_get_store.return_value = mock_store

        result = runner.invoke(app, ["study"])
        assert result.exit_code == 0
        assert "Parabéns! Todos os tópicos da sua trilha foram dominados!" in result.output


@patch("study_agent.cli.get_store")
@patch("study_agent.cli.Diagnostician")
@patch("study_agent.cli.CurriculumGenerator")
def test_cli_init_full_flow(
    mock_curriculum_gen_cls,
    mock_diagnostician_cls,
    mock_get_store,
    sample_student: StudentProfile,
    sample_curriculum: Curriculum,
):
    """Testa o fluxo completo do comando init com inputs simulados."""
    mock_store = MagicMock()
    mock_get_store.return_value = mock_store

    # Mock diagnostician
    mock_diag = MagicMock()
    mock_diag.generate_questions.return_value = [
        DiagnosticQuestion(id="q1", question="O que é container?", topic_focus="Conceito", difficulty=KnowledgeLevel.BEGINNER),
        DiagnosticQuestion(id="q2", question="Como criar Dockerfile?", topic_focus="Build", difficulty=KnowledgeLevel.INTERMEDIATE),
        DiagnosticQuestion(id="q3", question="O que é multi-stage build?", topic_focus="Otimização", difficulty=KnowledgeLevel.ADVANCED),
    ]
    mock_diag.evaluate_answers.return_value = DiagnosticReport(
        target_subject="Docker",
        assessed_level=KnowledgeLevel.INTERMEDIATE,
        overall_score=75.0,
        answers=[],
        summary_feedback="Bom conhecimento prévio.",
        strengths=["Conceito de imagens"],
        learning_gaps=["Multi-stage"],
    )
    mock_diagnostician_cls.return_value = mock_diag

    # Mock curriculum generator
    mock_gen = MagicMock()
    mock_gen.generate.return_value = sample_curriculum
    mock_curriculum_gen_cls.return_value = mock_gen

    # Entradas do usuário no console:
    # Nome, Assunto, Nível (3), Ritmo (2), Minutos (45), Respostas Q1, Q2, Q3
    user_inputs = "\n".join([
        "Renata",
        "Docker",
        "3",
        "2",
        "45",
        "Isolamento a nível de kernel",
        "FROM, COPY, RUN, CMD",
        "Builds em estágios para reduzir tamanho",
    ])

    result = runner.invoke(app, ["init"], input=user_inputs)
    assert result.exit_code == 0
    assert "Trilha criada com sucesso para Renata!" in result.output
    mock_store.save_student.assert_called_once()
    mock_store.save_curriculum.assert_called_once()
    mock_store.set_current_session.assert_called_once()


@patch("study_agent.cli.get_store")
@patch("study_agent.cli.Teacher")
@patch("study_agent.cli.Evaluator")
def test_cli_study_full_flow(
    mock_evaluator_cls,
    mock_teacher_cls,
    mock_get_store,
    sample_student: StudentProfile,
    sample_curriculum: Curriculum,
):
    """Testa o fluxo interativo do comando study: aula, dúvidas e active recall."""
    mock_store = MagicMock()
    mock_store.load_active_session.return_value = (sample_student, sample_curriculum)
    mock_get_store.return_value = mock_store

    # Mock Teacher
    mock_teacher = MagicMock()
    mock_teacher.explain_topic.return_value = "# Containers vs VMs\n\nAnalogia: casas vs apartamentos."
    mock_teacher.summarize_key_takeaways.return_value = ["Compartilha kernel", "Mais leve"]
    mock_teacher.answer_doubt.return_value = "O kernel Linux usa namespaces e cgroups."
    mock_teacher_cls.return_value = mock_teacher

    # Mock Evaluator
    mock_evaluator = MagicMock()
    mock_evaluator.generate_active_recall_question.return_value = ActiveRecallQuestion(
        id="q_recall_01",
        question="Por que containers sobem mais rápido que VMs?",
        expected_concepts=["Não inicializa SO completo", "Usa mesmo kernel"],
        hint="Pense no boot do sistema operacional.",
    )
    mock_evaluator.evaluate_active_recall.return_value = ActiveRecallEvaluation(
        question_id="q_recall_01",
        student_answer="Porque não precisa dar boot em outro SO convidado.",
        score=85.0,
        understood_concepts=["Boot rápido", "Sem guest OS"],
        missing_or_confused_concepts=[],
        feedback="Resposta precisa e correta!",
        is_passing=True,
    )
    mock_evaluator_cls.return_value = mock_evaluator

    # Entradas do console:
    # Estilo de explicação: 1 (Feynman)
    # Tem dúvida? 'y' (sim)
    # Pergunta da dúvida: 'Como funciona no Windows?'
    # Tem mais dúvida? 'n' (não)
    # Resposta da questão Active Recall: 'Não precisa de boot completo do SO'
    user_inputs = "\n".join([
        "1",
        "y",
        "Como funciona no Windows?",
        "n",
        "Não precisa de boot completo do SO",
    ])

    result = runner.invoke(app, ["study"], input=user_inputs)
    assert result.exit_code == 0
    assert "Tópico Dominado!" in result.output
    assert "O próximo tópico da trilha foi desbloqueado" in result.output
    mock_store.save_curriculum.assert_called_once()
