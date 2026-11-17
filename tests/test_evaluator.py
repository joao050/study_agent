"""Testes unitários para o módulo Evaluator (core/evaluator.py)."""

from unittest.mock import MagicMock
import pytest

from study_agent.core.evaluator import ActiveRecallEvaluationPayload, Evaluator
from study_agent.core.llm_client import LLMClient
from study_agent.models.curriculum import (
    ActiveRecallEvaluation,
    ActiveRecallQuestion,
    Topic,
    TopicStatus,
)


@pytest.fixture
def mock_llm_client() -> MagicMock:
    """Fixture que provê um LLMClient mockado."""
    return MagicMock(spec=LLMClient)


@pytest.fixture
def evaluator(mock_llm_client: MagicMock) -> Evaluator:
    """Fixture com instância do Evaluator e mock injetado."""
    return Evaluator(llm_client=mock_llm_client)


@pytest.fixture
def sample_topic() -> Topic:
    """Fixture de tópico padrão."""
    return Topic(
        id="mod1_pydantic",
        title="Validação de Dados com Pydantic",
        description="Schemas, BaseModel, Field e serialização",
        estimated_minutes=30,
        status=TopicStatus.AVAILABLE,
    )


@pytest.fixture
def sample_question() -> ActiveRecallQuestion:
    """Fixture de questão de active recall."""
    return ActiveRecallQuestion(
        id="q_pydantic_01",
        question="Por que usamos BaseModel no Pydantic em vez de dicts normais?",
        expected_concepts=["Validação de tipos em tempo de execução", "Coerção automática", "Imutabilidade/Schema rígido"],
        hint="Pense no que acontece quando um dado com tipo errado chega na API.",
    )


def test_generate_active_recall_question(evaluator: Evaluator, mock_llm_client: MagicMock, sample_topic: Topic):
    """Testa geração estruturada de pergunta de Active Recall."""
    mock_question = ActiveRecallQuestion(
        id="q_gen",
        question="Explique a diferença entre BaseModel e dataclass.",
        expected_concepts=["Validação em runtime", "Serialização"],
        hint="Pydantic valida os dados de entrada.",
    )
    mock_llm_client.generate_structured.return_value = mock_question

    question = evaluator.generate_active_recall_question(sample_topic, key_takeaways=["Schemas", "Runtime validation"])

    assert question.id == "q_gen"
    assert "BaseModel" in question.question
    mock_llm_client.generate_structured.assert_called_once()
    call_prompt = mock_llm_client.generate_structured.call_args.kwargs["prompt"]
    assert "Validação de Dados com Pydantic" in call_prompt
    assert "Runtime validation" in call_prompt


def test_generate_active_recall_empty_topic_title(evaluator: Evaluator):
    """Garante validação para tópicos com títulos inválidos."""
    invalid_topic = Topic(id="t1", title="   ", description="desc")
    with pytest.raises(ValueError, match="título válido"):
        evaluator.generate_active_recall_question(invalid_topic)


def test_evaluate_active_recall_empty_answer(evaluator: Evaluator, sample_question: ActiveRecallQuestion):
    """Testa resposta vazia ou desistência do aluno sem acionar o LLM."""
    evaluation = evaluator.evaluate_active_recall(sample_question, "   ")

    assert evaluation.score == 0.0
    assert evaluation.is_passing is False
    assert evaluation.question_id == sample_question.id
    assert "Nenhuma resposta fornecida" in evaluation.feedback


def test_evaluate_active_recall_passing(evaluator: Evaluator, mock_llm_client: MagicMock, sample_question: ActiveRecallQuestion):
    """Testa resposta aprovada (score >= 70)."""
    mock_payload = ActiveRecallEvaluationPayload(
        score=85.0,
        understood_concepts=["Validação de tipos", "Coerção automática"],
        missing_or_confused_concepts=[],
        feedback="Excelente resposta, demonstrou clareza nos benefícios do Pydantic.",
    )
    mock_llm_client.generate_structured.return_value = mock_payload

    evaluation = evaluator.evaluate_active_recall(
        sample_question,
        "Usamos BaseModel para garantir tipagem e validação automática dos dados quando a requisição chega.",
    )

    assert evaluation.score == 85.0
    assert evaluation.is_passing is True
    assert len(evaluation.understood_concepts) == 2
    assert "Excelente" in evaluation.feedback


def test_evaluate_active_recall_failing(evaluator: Evaluator, mock_llm_client: MagicMock, sample_question: ActiveRecallQuestion):
    """Testa resposta reprovada (score < 70)."""
    mock_payload = ActiveRecallEvaluationPayload(
        score=45.0,
        understood_concepts=["Mencionou dict"],
        missing_or_confused_concepts=["Validação de tipos", "Coerção automática"],
        feedback="Faltou explicar como o Pydantic protege contra dados inválidos.",
    )
    mock_llm_client.generate_structured.return_value = mock_payload

    evaluation = evaluator.evaluate_active_recall(
        sample_question,
        "Acho que é só um jeito diferente de escrever um dicionário.",
    )

    assert evaluation.score == 45.0
    assert evaluation.is_passing is False
    assert len(evaluation.missing_or_confused_concepts) == 2


def test_update_topic_mastery_promotes_to_mastered(evaluator: Evaluator, sample_topic: Topic):
    """Verifica transição de status para MASTERED quando o estudante passa na avaliação."""
    evaluation = ActiveRecallEvaluation(
        question_id="q1",
        student_answer="resp",
        score=80.0,
        understood_concepts=["conceito"],
        missing_or_confused_concepts=[],
        feedback="Parabéns!",
        is_passing=True,
    )

    updated = evaluator.update_topic_mastery(sample_topic, evaluation)

    assert updated.status == TopicStatus.MASTERED
    assert updated.mastery_score == 80.0
    assert updated.review_count == 1
    assert updated.last_reviewed_at is not None


def test_update_topic_mastery_sets_in_progress_when_failing(evaluator: Evaluator, sample_topic: Topic):
    """Verifica transição para IN_PROGRESS e retenção da maior nota quando reprovado."""
    evaluation = ActiveRecallEvaluation(
        question_id="q1",
        student_answer="resp",
        score=50.0,
        understood_concepts=[],
        missing_or_confused_concepts=["conceito"],
        feedback="Precisa revisar.",
        is_passing=False,
    )

    updated = evaluator.update_topic_mastery(sample_topic, evaluation)

    assert updated.status == TopicStatus.IN_PROGRESS
    assert updated.mastery_score == 50.0
    assert updated.review_count == 1


def test_update_topic_mastery_weighted_average(evaluator: Evaluator, sample_topic: Topic):
    """Verifica o recálculo ponderado quando o tópico já possuía pontuação prévia."""
    sample_topic.mastery_score = 70.0
    sample_topic.status = TopicStatus.MASTERED

    evaluation = ActiveRecallEvaluation(
        question_id="q1",
        student_answer="resp",
        score=90.0,
        understood_concepts=["tudo"],
        missing_or_confused_concepts=[],
        feedback="Perfeito!",
        is_passing=True,
    )

    updated = evaluator.update_topic_mastery(sample_topic, evaluation)

    # 70 * 0.3 + 90 * 0.7 = 21 + 63 = 84.0
    assert updated.mastery_score == 84.0
    assert updated.status == TopicStatus.MASTERED
    assert updated.review_count == 1
