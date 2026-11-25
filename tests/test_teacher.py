"""Testes unitários para o módulo Teacher (core/teacher.py)."""

from unittest.mock import MagicMock
import pytest

from study_agent.core.llm_client import LLMClient
from study_agent.core.teacher import GuidedLabPayload, KeyTakeawaysPayload, Teacher
from study_agent.models.curriculum import (
    ErrorDebugResolution,
    ExplanationStyle,
    LabMission,
    Topic,
    TopicStatus,
)
from study_agent.models.student import KnowledgeLevel, StudentProfile


@pytest.fixture
def mock_llm_client() -> MagicMock:
    """Fixture que provê um LLMClient mockado."""
    return MagicMock(spec=LLMClient)


@pytest.fixture
def teacher(mock_llm_client: MagicMock) -> Teacher:
    """Fixture que provê uma instância do Teacher com mock injetado."""
    return Teacher(llm_client=mock_llm_client)


@pytest.fixture
def sample_topic() -> Topic:
    """Fixture de tópico de exemplo."""
    return Topic(
        id="mod1_async",
        title="Asyncio e Programação Assíncrona",
        description="Fundamentos de Event Loop, corrotinas, async e await",
        estimated_minutes=35,
        prerequisites=["mod1_funcoes"],
        status=TopicStatus.AVAILABLE,
    )


def test_explain_topic_feynman_style(teacher: Teacher, mock_llm_client: MagicMock, sample_topic: Topic):
    """Verifica se a explicação no estilo Feynman envia as diretrizes corretas de analogias."""
    mock_llm_client.generate.return_value = "Imagine um garçom atendendo várias mesas..."

    explanation = teacher.explain_topic(sample_topic, style=ExplanationStyle.FEYNMAN)

    assert "garçom" in explanation
    mock_llm_client.generate.assert_called_once()
    call_prompt = mock_llm_client.generate.call_args.kwargs["prompt"]
    assert "Técnica de Feynman" in call_prompt
    assert "Asyncio e Programação Assíncrona" in call_prompt
    assert "mod1_funcoes" in call_prompt


def test_explain_topic_technical_style(teacher: Teacher, mock_llm_client: MagicMock, sample_topic: Topic):
    """Verifica envio das diretrizes técnicas formais."""
    mock_llm_client.generate.return_value = "O event loop gerencia tarefas cooperativas em thread única..."

    teacher.explain_topic(sample_topic, style=ExplanationStyle.TECHNICAL)

    call_prompt = mock_llm_client.generate.call_args.kwargs["prompt"]
    assert "Técnica e Formal" in call_prompt


def test_explain_topic_practical_style(teacher: Teacher, mock_llm_client: MagicMock, sample_topic: Topic):
    """Verifica envio das diretrizes práticas de código."""
    mock_llm_client.generate.return_value = "```python\nimport asyncio\n```"

    teacher.explain_topic(sample_topic, style=ExplanationStyle.PRACTICAL)

    call_prompt = mock_llm_client.generate.call_args.kwargs["prompt"]
    assert "Prática (Hands-on)" in call_prompt


def test_explain_topic_validation_empty_title(teacher: Teacher):
    """Garante que tópico sem título gera erro."""
    invalid_topic = Topic(id="t1", title="   ", description="desc")
    with pytest.raises(ValueError, match="título válido"):
        teacher.explain_topic(invalid_topic)


def test_answer_doubt_success(teacher: Teacher, mock_llm_client: MagicMock, sample_topic: Topic):
    """Testa resposta contextualizada a uma dúvida do aluno."""
    mock_llm_client.generate.return_value = "A diferença entre thread e corrotina é..."

    answer = teacher.answer_doubt(
        sample_topic,
        student_question="Qual a diferença entre uma thread do SO e uma corrotina?",
        previous_explanation="Explicamos o event loop antes.",
    )

    assert "diferença entre thread e corrotina" in answer
    call_prompt = mock_llm_client.generate.call_args.kwargs["prompt"]
    assert "Qual a diferença" in call_prompt
    assert "Explicamos o event loop antes" in call_prompt


def test_answer_doubt_empty_question(teacher: Teacher, sample_topic: Topic):
    """Garante validação para perguntas vazias."""
    with pytest.raises(ValueError, match="não pode ser vazia"):
        teacher.answer_doubt(sample_topic, "   ")


def test_summarize_key_takeaways(teacher: Teacher, mock_llm_client: MagicMock, sample_topic: Topic):
    """Testa extração estruturada de pontos-chave de uma aula."""
    mock_llm_client.generate_structured.return_value = KeyTakeawaysPayload(
        takeaways=[
            "Corrotinas suspendem execução com await",
            "Event loop coordena I/O sem bloquear a thread principal",
            "Asyncio é ideal para tarefas I/O bound",
        ]
    )

    takeaways = teacher.summarize_key_takeaways(sample_topic, "Texto longo da aula...")

    assert len(takeaways) == 3
    assert "Event loop" in takeaways[1]
    mock_llm_client.generate_structured.assert_called_once()


def test_summarize_key_takeaways_empty_explanation(teacher: Teacher, sample_topic: Topic):
    """Garante fallback seguro caso a explicação esteja vazia."""
    takeaways = teacher.summarize_key_takeaways(sample_topic, "")
    assert takeaways == [sample_topic.title]


def test_generate_guided_lab_success_and_step_normalization(
    teacher: Teacher, mock_llm_client: MagicMock, sample_topic: Topic
):
    """Verifica geração de laboratório guiado com normalização sequencial de passos."""
    student = StudentProfile(
        name="João",
        target_subject="Python Assíncrono",
        current_level=KnowledgeLevel.BEGINNER,
    )
    mock_llm_client.generate_structured.return_value = GuidedLabPayload(
        intro_brief="Vamos criar nossa primeira corrotina prática.",
        prerequisites_check="python --version",
        missions=[
            LabMission(
                step_number=9,  # propositalmente fora de ordem para testar normalização
                title="Criar script async",
                instruction="Crie um arquivo ola_async.py",
                command_or_code="python -c \"import asyncio; asyncio.run(asyncio.sleep(0.1))\"",
                expected_outcome="Executa sem erros em ~0.1s",
            ),
            LabMission(
                step_number=10,
                title="Executar duas tarefas concorrentes",
                instruction="Use asyncio.gather",
                command_or_code="python ola_async.py",
                expected_outcome="Ambas finalizam juntas",
            ),
        ],
    )

    lab = teacher.generate_guided_lab(
        topic=sample_topic,
        student=student,
        mission_count=2,
        os_context="Windows",
    )

    assert lab.topic_id == sample_topic.id
    assert len(lab.missions) == 2
    assert lab.missions[0].step_number == 1
    assert lab.missions[1].step_number == 2

    call_kwargs = mock_llm_client.generate_structured.call_args.kwargs
    assert "Windows" in call_kwargs["prompt"]
    assert "beginner" in call_kwargs["prompt"]


def test_generate_guided_lab_empty_topic_raises_error(teacher: Teacher):
    """Garante validação de título vazio ao gerar laboratório."""
    invalid_topic = Topic(id="t_empty", title="  ", description="desc")
    with pytest.raises(ValueError, match="título válido"):
        teacher.generate_guided_lab(invalid_topic)


def test_debug_error_success(
    teacher: Teacher, mock_llm_client: MagicMock, sample_topic: Topic
):
    """Testa decodificação pedagógica de stack trace pelo método debug_error."""
    student = StudentProfile(
        name="João",
        target_subject="Python Assíncrono",
        current_level=KnowledgeLevel.BEGINNER,
    )
    expected_resolution = ErrorDebugResolution(
        error_summary="Você chamou uma função async sem usar await ou asyncio.run().",
        root_cause="Corrotinas em Python não executam sozinhas apenas com parênteses.",
        fix_instructions=[
            "Importe o módulo asyncio",
            "Envolva a chamada principal com asyncio.run(main())",
        ],
        corrected_command_or_code="python -c \"import asyncio; asyncio.run(main())\"",
        prevention_tip="RuntimeWarning: coroutine was never awaited sempre indica falta de await/asyncio.run.",
    )
    mock_llm_client.generate_structured.return_value = expected_resolution

    res = teacher.debug_error(
        student=student,
        topic=sample_topic,
        command_attempted="python app.py",
        error_output="RuntimeWarning: coroutine 'main' was never awaited",
        os_context="Windows",
    )

    assert res.corrected_command_or_code == expected_resolution.corrected_command_or_code
    call_kwargs = mock_llm_client.generate_structured.call_args.kwargs
    assert "RuntimeWarning: coroutine 'main' was never awaited" in call_kwargs["prompt"]
    assert "python app.py" in call_kwargs["prompt"]
    assert "Windows" in call_kwargs["prompt"]


def test_debug_error_empty_output_raises_error(teacher: Teacher, sample_topic: Topic):
    """Garante que saída de erro vazia levanta ValueError."""
    with pytest.raises(ValueError, match="não pode ser vazia"):
        teacher.debug_error(
            student=None,
            topic=sample_topic,
            command_attempted="python app.py",
            error_output="   ",
        )
