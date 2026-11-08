"""Testes unitários para o módulo Diagnosticador (core/diagnostician.py)."""

from unittest.mock import MagicMock
import pytest

from study_agent.core.diagnostician import (
    Diagnostician,
    DiagnosticEvaluationPayload,
    DiagnosticQuestionsContainer,
    SingleEvaluationItem,
)
from study_agent.core.llm_client import LLMClient
from study_agent.models.student import (
    DiagnosticAnswer,
    DiagnosticQuestion,
    KnowledgeLevel,
)


@pytest.fixture
def mock_llm_client() -> MagicMock:
    """Fixture que provê um LLMClient mockado."""
    return MagicMock(spec=LLMClient)


@pytest.fixture
def diagnostician(mock_llm_client: MagicMock) -> Diagnostician:
    """Fixture que provê uma instância do Diagnostician com mock injetado."""
    return Diagnostician(llm_client=mock_llm_client)


def test_calculate_level_rules():
    """Valida as regras de negócio para cálculo do nível consolidado."""
    # Lista vazia
    assert Diagnostician.calculate_level([]) == KnowledgeLevel.BEGINNER

    # Beginner (< 50)
    ans_beginner = [
        DiagnosticAnswer(
            question_id="q1",
            student_answer="resp",
            assessed_level=KnowledgeLevel.BEGINNER,
            feedback="fb",
            score=30.0,
        ),
        DiagnosticAnswer(
            question_id="q2",
            student_answer="resp",
            assessed_level=KnowledgeLevel.BEGINNER,
            feedback="fb",
            score=45.0,
        ),
    ]
    assert Diagnostician.calculate_level(ans_beginner) == KnowledgeLevel.BEGINNER

    # Intermediate (>= 50 e < 80)
    ans_intermediate = [
        DiagnosticAnswer(
            question_id="q1",
            student_answer="resp",
            assessed_level=KnowledgeLevel.INTERMEDIATE,
            feedback="fb",
            score=70.0,
        ),
        DiagnosticAnswer(
            question_id="q2",
            student_answer="resp",
            assessed_level=KnowledgeLevel.BEGINNER,
            feedback="fb",
            score=60.0,
        ),
    ]
    assert Diagnostician.calculate_level(ans_intermediate) == KnowledgeLevel.INTERMEDIATE

    # Advanced (>= 80)
    ans_advanced = [
        DiagnosticAnswer(
            question_id="q1",
            student_answer="resp",
            assessed_level=KnowledgeLevel.ADVANCED,
            feedback="fb",
            score=85.0,
        ),
        DiagnosticAnswer(
            question_id="q2",
            student_answer="resp",
            assessed_level=KnowledgeLevel.ADVANCED,
            feedback="fb",
            score=95.0,
        ),
    ]
    assert Diagnostician.calculate_level(ans_advanced) == KnowledgeLevel.ADVANCED


def test_generate_questions_validations(diagnostician: Diagnostician):
    """Garante que argumentos inválidos lançam exceção."""
    with pytest.raises(ValueError, match="não pode ser vazio"):
        diagnostician.generate_questions("   ")

    with pytest.raises(ValueError, match="no mínimo 1"):
        diagnostician.generate_questions("Python", count=0)


def test_generate_questions_success(
    diagnostician: Diagnostician, mock_llm_client: MagicMock
):
    """Testa geração bem-sucedida de perguntas usando resposta mockada do LLM."""
    mock_questions = [
        DiagnosticQuestion(
            id="q1",
            question="O que são tipos primitivos em Python?",
            topic_focus="Tipos e Variáveis",
            difficulty=KnowledgeLevel.BEGINNER,
        ),
        DiagnosticQuestion(
            id="q2",
            question="Como funciona uma list comprehension?",
            topic_focus="Iterações e Estruturas",
            difficulty=KnowledgeLevel.INTERMEDIATE,
        ),
        DiagnosticQuestion(
            id="q3",
            question="Explique a diferença entre threading e asyncio.",
            topic_focus="Concorrência",
            difficulty=KnowledgeLevel.ADVANCED,
        ),
    ]

    mock_llm_client.generate_structured.return_value = DiagnosticQuestionsContainer(
        questions=mock_questions
    )

    result = diagnostician.generate_questions("Python", count=3)

    assert len(result) == 3
    assert result[0].id == "q1"
    assert result[0].difficulty == KnowledgeLevel.BEGINNER
    assert result[1].difficulty == KnowledgeLevel.INTERMEDIATE
    assert result[2].difficulty == KnowledgeLevel.ADVANCED
    mock_llm_client.generate_structured.assert_called_once()


def test_evaluate_answers_validations(diagnostician: Diagnostician):
    """Testa validações de entrada para avaliação de respostas."""
    with pytest.raises(ValueError, match="não pode estar vazia"):
        diagnostician.evaluate_answers("Python", questions=[], student_answers=[])

    q = DiagnosticQuestion(
        id="q1",
        question="Teste?",
        topic_focus="Foco",
        difficulty=KnowledgeLevel.BEGINNER,
    )
    with pytest.raises(ValueError, match="difere do número de perguntas"):
        diagnostician.evaluate_answers("Python", questions=[q], student_answers=["a", "b"])


def test_evaluate_answers_success(
    diagnostician: Diagnostician, mock_llm_client: MagicMock
):
    """Testa o fluxo completo de avaliação e consolidação do relatório diagnóstico."""
    questions = [
        DiagnosticQuestion(
            id="q1",
            question="O que é FastAPI?",
            topic_focus="Framework",
            difficulty=KnowledgeLevel.BEGINNER,
        ),
        DiagnosticQuestion(
            id="q2",
            question="Como configurar injeção de dependência com Depends?",
            topic_focus="Injeção de Dependências",
            difficulty=KnowledgeLevel.INTERMEDIATE,
        ),
    ]
    student_answers = [
        "FastAPI é um framework moderno e rápido para APIs em Python baseado em Starlette e Pydantic.",
        "Não tenho certeza de como usar o Depends, nunca trabalhei com isso.",
    ]

    mock_payload = DiagnosticEvaluationPayload(
        evaluations=[
            SingleEvaluationItem(
                question_id="q1",
                assessed_level=KnowledgeLevel.INTERMEDIATE,
                feedback="Excelente definição, mencionou as bibliotecas base com clareza.",
                score=90.0,
            ),
            SingleEvaluationItem(
                question_id="q2",
                assessed_level=KnowledgeLevel.BEGINNER,
                feedback="Conceito ainda não conhecido pelo aluno, será coberto na trilha.",
                score=20.0,
            ),
        ],
        summary_feedback="O estudante compreende bem o panorama geral de FastAPI, mas precisa aprofundar injeção de dependência.",
        strengths=["Fundamentos do framework", "Ecossistema Starlette/Pydantic"],
        learning_gaps=["Injeção de dependência com Depends"],
    )

    mock_llm_client.generate_structured.return_value = mock_payload

    report = diagnostician.evaluate_answers("FastAPI", questions, student_answers)

    assert report.target_subject == "FastAPI"
    assert len(report.answers) == 2
    assert report.overall_score == 55.0  # (90 + 20) / 2
    assert report.assessed_level == KnowledgeLevel.INTERMEDIATE  # 55.0 está na faixa 50-80
    assert len(report.strengths) == 2
    assert len(report.learning_gaps) == 1
    assert "Depends" in report.learning_gaps[0]
    assert report.answers[0].score == 90.0
    assert report.answers[1].score == 20.0


def test_evaluate_answers_fallback_unmatched_id(
    diagnostician: Diagnostician, mock_llm_client: MagicMock
):
    """Testa a robustez caso o LLM retorne avaliações com IDs ausentes."""
    questions = [
        DiagnosticQuestion(
            id="q_esperado",
            question="Questão?",
            topic_focus="Foco",
            difficulty=KnowledgeLevel.BEGINNER,
        )
    ]
    student_answers = ["Minha resposta"]

    # Retorna payload com ID não coincidente
    mock_payload = DiagnosticEvaluationPayload(
        evaluations=[
            SingleEvaluationItem(
                question_id="outro_id_estranho",
                assessed_level=KnowledgeLevel.BEGINNER,
                feedback="Feedback",
                score=50.0,
            )
        ],
        summary_feedback="Geral",
        strengths=[],
        learning_gaps=[],
    )
    mock_llm_client.generate_structured.return_value = mock_payload

    report = diagnostician.evaluate_answers("Python", questions, student_answers)

    assert len(report.answers) == 1
    assert report.answers[0].question_id == "q_esperado"
    assert report.answers[0].assessed_level == KnowledgeLevel.BEGINNER
    assert report.answers[0].score == 50.0
