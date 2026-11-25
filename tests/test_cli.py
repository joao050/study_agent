"""Testes automatizados para a interface de linha de comando CLI (tests/test_cli.py)."""

from unittest.mock import MagicMock, patch
import pytest
from typer.testing import CliRunner

from study_agent import __version__
from study_agent.cli import app
from study_agent.core.diagnostician import DiagnosticReport
from study_agent.core.llm_client import (
    LLMAuthenticationError,
    LLMConnectionError,
)
from study_agent.models.curriculum import (
    ActiveRecallEvaluation,
    ActiveRecallQuestion,
    Curriculum,
    ErrorDebugResolution,
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


@patch("study_agent.cli.Diagnostician")
def test_cli_init_handles_llm_connection_error_gracefully(mock_diagnostician_cls):
    """Verifica que falha 503 esgotada exibe painel amigável sem vazar stack trace bruto."""
    mock_diag = MagicMock()
    mock_diag.generate_questions.side_effect = LLMConnectionError(
        "Falha após 4 tentativas: 503 Service Unavailable",
        attempts=4,
        status_code=503,
        is_rate_limit=False,
    )
    mock_diagnostician_cls.return_value = mock_diag

    user_inputs = "\n".join(["Carlos", "Rust", "2", "2", "45"])
    result = runner.invoke(app, ["init"], input=user_inputs)

    assert result.exit_code == 1
    assert "Serviço de IA Temporariamente Indisponível" in result.output
    assert "4 tentativa(s)" in result.output
    assert "Traceback" not in result.output


@patch("study_agent.cli.Diagnostician")
def test_cli_init_handles_authentication_error_gracefully(mock_diagnostician_cls):
    """Verifica aviso claro de configuração .env quando a API Key é inválida."""
    mock_diag = MagicMock()
    mock_diag.generate_questions.side_effect = LLMAuthenticationError("API key invalid")
    mock_diagnostician_cls.return_value = mock_diag

    user_inputs = "\n".join(["Ana", "FastAPI", "1", "1", "25"])
    result = runner.invoke(app, ["init"], input=user_inputs)

    assert result.exit_code == 1
    assert "Erro de Credenciais / API Key" in result.output
    assert ".env" in result.output


@patch("study_agent.cli.get_store")
@patch("study_agent.cli.Teacher")
@patch("study_agent.cli.Evaluator")
def test_cli_study_doubt_error_recovers_without_aborting_lesson(
    mock_evaluator_cls,
    mock_teacher_cls,
    mock_get_store,
    sample_student: StudentProfile,
    sample_curriculum: Curriculum,
):
    """Verifica que erro 503 ao tirar uma dúvida exibe painel amigável e mantém a aula viva."""
    mock_store = MagicMock()
    mock_store.load_active_session.return_value = (sample_student, sample_curriculum)
    mock_get_store.return_value = mock_store

    mock_teacher = MagicMock()
    mock_teacher.explain_topic.return_value = "# Aula sobre Containers"
    mock_teacher.summarize_key_takeaways.return_value = ["Isolamento"]
    mock_teacher.answer_doubt.side_effect = LLMConnectionError(
        "503 Service Unavailable", attempts=4, is_rate_limit=True
    )
    mock_teacher_cls.return_value = mock_teacher

    mock_evaluator = MagicMock()
    mock_evaluator.generate_active_recall_question.return_value = ActiveRecallQuestion(
        id="q1", question="O que é um container?", expected_concepts=["Isolamento"]
    )
    mock_evaluator.evaluate_active_recall.return_value = ActiveRecallEvaluation(
        question_id="q1",
        student_answer="Processo isolado",
        score=90.0,
        understood_concepts=["Isolamento"],
        missing_or_confused_concepts=[],
        feedback="Muito bem!",
        is_passing=True,
    )
    mock_evaluator_cls.return_value = mock_evaluator

    user_inputs = "\n".join([
        "1",
        "y",
        "Dúvida durante pico de tráfego",
        "n",
        "Processo isolado",
    ])

    result = runner.invoke(app, ["study"], input=user_inputs)
    assert result.exit_code == 0
    assert "Serviço de IA Temporariamente Indisponível" in result.output
    assert "limite de requisições" in result.output
    assert "429" in result.output
    assert "Tópico Dominado!" in result.output


@patch("study_agent.cli.get_store")
@patch("study_agent.cli.Teacher")
@patch("study_agent.cli.Evaluator")
def test_cli_study_active_recall_error_saves_partial_progress(
    mock_evaluator_cls,
    mock_teacher_cls,
    mock_get_store,
    sample_student: StudentProfile,
    sample_curriculum: Curriculum,
):
    """Verifica que falha no Active Recall salva progresso parcial (IN_PROGRESS) antes de encerrar."""
    mock_store = MagicMock()
    mock_store.load_active_session.return_value = (sample_student, sample_curriculum)
    mock_get_store.return_value = mock_store

    mock_teacher = MagicMock()
    mock_teacher.explain_topic.return_value = "# Aula sobre Containers"
    mock_teacher.summarize_key_takeaways.return_value = ["Namespaces", "Cgroups"]
    mock_teacher_cls.return_value = mock_teacher

    mock_evaluator = MagicMock()
    mock_evaluator.generate_active_recall_question.side_effect = LLMConnectionError(
        "503 Unavailable", attempts=4
    )
    mock_evaluator_cls.return_value = mock_evaluator

    user_inputs = "\n".join(["1", "n"])
    result = runner.invoke(app, ["study"], input=user_inputs)

    assert result.exit_code == 1
    assert "Serviço de IA Temporariamente Indisponível" in result.output
    assert "progresso parcial neste tópico foi salvo" in result.output
    assert sample_curriculum.topics[0].status == TopicStatus.IN_PROGRESS
    assert sample_curriculum.topics[0].key_takeaways == ["Namespaces", "Cgroups"]
    mock_store.save_curriculum.assert_called_once_with(sample_curriculum)


@patch("study_agent.cli.get_store")
@patch("study_agent.cli.Teacher")
@patch("study_agent.cli.Evaluator")
def test_cli_study_report_terminal_error_option_e(
    mock_evaluator_cls,
    mock_teacher_cls,
    mock_get_store,
    sample_student: StudentProfile,
    sample_curriculum: Curriculum,
):
    """Testa opção [E] no menu de estudo colando stack trace multilinha e prosseguindo."""
    mock_store = MagicMock()
    mock_store.load_active_session.return_value = (sample_student, sample_curriculum)
    mock_get_store.return_value = mock_store

    mock_teacher = MagicMock()
    mock_teacher.explain_topic.return_value = "# Aula Prática de Docker"
    mock_teacher.summarize_key_takeaways.return_value = ["Daemon", "CLI"]
    mock_teacher.debug_error.return_value = ErrorDebugResolution(
        error_summary="O motor do Docker não está em execução.",
        root_cause="O serviço Docker Desktop está fechado no Windows.",
        fix_instructions=["Inicie o Docker Desktop", "Rode docker info para confirmar"],
        corrected_command_or_code="docker ps",
        prevention_tip="Confira o ícone da baleia na bandeja do sistema.",
    )
    mock_teacher_cls.return_value = mock_teacher

    mock_evaluator = MagicMock()
    mock_evaluator.generate_active_recall_question.return_value = ActiveRecallQuestion(
        id="q1", question="Qual papel do Docker daemon?", expected_concepts=["Gerenciar containers"]
    )
    mock_evaluator.evaluate_active_recall.return_value = ActiveRecallEvaluation(
        question_id="q1",
        student_answer="Gerencia os containers em background",
        score=92.0,
        understood_concepts=["Daemon"],
        missing_or_confused_concepts=[],
        feedback="Perfeito!",
        is_passing=True,
    )
    mock_evaluator_cls.return_value = mock_evaluator

    # Fluxo:
    # 3 -> Estilo Prático
    # E -> Reportar Erro / Colar Terminal
    # docker run hello-world -> comando tentado
    # 2 linhas de erro + linha vazia -> finaliza captura multilinha
    # C -> Concluir estudo e ir para Active Recall
    # Resposta do Active Recall
    user_inputs = "\n".join([
        "3",
        "E",
        "docker run hello-world",
        "docker: error during connect: open //./pipe/docker_engine",
        "The system cannot find the file specified.",
        "",
        "C",
        "Gerencia os containers em background",
    ])

    result = runner.invoke(app, ["study"], input=user_inputs)
    assert result.exit_code == 0
    assert "Assistente de Debugging em Tempo Real" in result.output
    assert "Docker Desktop" in result.output
    assert "Tópico Dominado!" in result.output

    mock_teacher.debug_error.assert_called_once()
    debug_kwargs = mock_teacher.debug_error.call_args.kwargs
    assert debug_kwargs["command_attempted"] == "docker run hello-world"
    assert "docker_engine" in debug_kwargs["error_output"]
    assert "cannot find the file" in debug_kwargs["error_output"]


@patch("study_agent.cli.get_store")
@patch("study_agent.cli.Teacher")
@patch("study_agent.cli.Evaluator")
def test_cli_study_guided_lab_mode_with_error_checkpoint(
    mock_evaluator_cls,
    mock_teacher_cls,
    mock_get_store,
    sample_student: StudentProfile,
    sample_curriculum: Curriculum,
):
    """Testa estilo [4] Laboratório Guiado Passo a Passo com erro na Missão 1 e conclusão."""
    mock_store = MagicMock()
    mock_store.load_active_session.return_value = (sample_student, sample_curriculum)
    mock_get_store.return_value = mock_store

    mock_teacher = MagicMock()
    mock_teacher.generate_guided_lab.return_value = GuidedLab(
        topic_id="t1",
        intro_brief="Vamos testar containers na prática.",
        prerequisites_check="Docker ativo",
        missions=[
            LabMission(
                step_number=1,
                title="Verificar versão",
                instruction="Valide o CLI do Docker",
                command_or_code="docker --version",
                expected_outcome="Mostra versão instalada",
            ),
            LabMission(
                step_number=2,
                title="Subir hello-world",
                instruction="Execute seu primeiro container",
                command_or_code="docker run --rm hello-world",
                expected_outcome="Imprime Hello from Docker!",
            ),
        ],
    )
    mock_teacher.debug_error.return_value = ErrorDebugResolution(
        error_summary="Flag digitada com apenas um hífen.",
        root_cause="Você digitou -version em vez de --version.",
        fix_instructions=["Use dois hífens: docker --version"],
        corrected_command_or_code="docker --version",
    )
    mock_teacher.summarize_key_takeaways.return_value = ["CLI", "Hello World"]
    mock_teacher_cls.return_value = mock_teacher

    mock_evaluator = MagicMock()
    mock_evaluator.generate_active_recall_question.return_value = ActiveRecallQuestion(
        id="q_lab", question="O que faz a flag --rm?", expected_concepts=["Remove container ao sair"]
    )
    mock_evaluator.evaluate_active_recall.return_value = ActiveRecallEvaluation(
        question_id="q_lab",
        student_answer="Remove o container assim que ele termina",
        score=95.0,
        understood_concepts=["Limpeza automática"],
        missing_or_confused_concepts=[],
        feedback="Excelente domínio prático!",
        is_passing=True,
    )
    mock_evaluator_cls.return_value = mock_evaluator

    # Fluxo:
    # 4 -> Laboratório Guiado Passo a Passo
    # E -> Na Missão 1, reporta erro
    # "" -> Aceita o default_command (docker --version)
    # "unknown shorthand flag: 'v' in -version" + "" -> envia erro multilinha
    # P -> Missão 1 funcionou!
    # P -> Missão 2 funcionou!
    # Resposta Active Recall
    user_inputs = "\n".join([
        "4",
        "E",
        "",
        "unknown shorthand flag: 'v' in -version",
        "",
        "P",
        "P",
        "Remove o container assim que ele termina",
    ])

    result = runner.invoke(app, ["study"], input=user_inputs)
    assert result.exit_code == 0
    assert "Missão 1/2: Verificar versão" in result.output
    assert "Missão 2/2: Subir hello-world" in result.output
    assert "Assistente de Debugging em Tempo Real" in result.output
    assert sample_curriculum.topics[0].completed_lab_steps == 2
    assert "Tópico Dominado!" in result.output


def test_cli_portable_command_hints_displayed(
    sample_student: StudentProfile, sample_curriculum: Curriculum
):
    """Verifica que as instruções da CLI sugerem o comando portátil python -m study_agent.cli."""
    with patch("study_agent.cli.get_store") as mock_get_store:
        mock_store = MagicMock()
        mock_store.load_active_session.return_value = (None, None)
        mock_store.list_students.return_value = [sample_student]
        mock_store.get_current_session.return_value = (sample_student.id, sample_curriculum.id)
        mock_get_store.return_value = mock_store

        for cmd in (["status"], ["map"], ["study"], ["students"]):
            res = runner.invoke(app, cmd)
            assert res.exit_code == 0
            assert "python -m study_agent.cli" in res.output


def test_windows_wrapper_and_packaging_entrypoints():
    """Valida existência e configuração de study-agent.bat, pyproject.toml, __main__.py e README.md."""
    from pathlib import Path
    import tomllib

    project_root = Path(__file__).resolve().parent.parent

    bat_file = project_root / "study-agent.bat"
    assert bat_file.exists()
    bat_content = bat_file.read_text(encoding="utf-8")
    assert "-m study_agent.cli %*" in bat_content
    assert ".venv\\Scripts\\python.exe" in bat_content

    main_file = project_root / "study_agent" / "__main__.py"
    assert main_file.exists()

    pyproject_file = project_root / "pyproject.toml"
    assert pyproject_file.exists()
    pyproject_data = tomllib.loads(pyproject_file.read_text(encoding="utf-8"))
    assert pyproject_data["project"]["scripts"]["study-agent"] == "study_agent.cli:app"

    readme_file = project_root / "README.md"
    assert readme_file.exists()
    readme_text = readme_file.read_text(encoding="utf-8")
    assert "Set-ExecutionPolicy" in readme_text
    assert "study-agent.bat" in readme_text or ".\\study-agent" in readme_text
