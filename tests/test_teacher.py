"""Testes unitários para o módulo Teacher (core/teacher.py)."""

from unittest.mock import MagicMock
import pytest

from study_agent.core.llm_client import LLMClient
from study_agent.core.teacher import KeyTakeawaysPayload, Teacher
from study_agent.models.curriculum import ExplanationStyle, Topic, TopicStatus


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
