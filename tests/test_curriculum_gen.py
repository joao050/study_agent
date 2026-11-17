"""Testes unitários para o módulo Gerador de Trilha (core/curriculum_gen.py)."""

from unittest.mock import MagicMock
import pytest

from study_agent.core.curriculum_gen import (
    CurriculumGenerationPayload,
    CurriculumGenerator,
)
from study_agent.core.diagnostician import DiagnosticReport
from study_agent.core.llm_client import LLMClient
from study_agent.models.curriculum import Topic, TopicStatus
from study_agent.models.student import (
    KnowledgeLevel,
    StudentProfile,
    StudyPace,
)


@pytest.fixture
def mock_llm_client() -> MagicMock:
    """Fixture que provê um LLMClient mockado."""
    return MagicMock(spec=LLMClient)


@pytest.fixture
def curriculum_gen(mock_llm_client: MagicMock) -> CurriculumGenerator:
    """Fixture com gerador instanciado com mock."""
    return CurriculumGenerator(llm_client=mock_llm_client)


@pytest.fixture
def sample_profile() -> StudentProfile:
    """Fixture que provê um perfil padrão de estudante."""
    return StudentProfile(
        name="Carlos",
        target_subject="FastAPI com Docker",
        current_level=KnowledgeLevel.BEGINNER,
        target_level=KnowledgeLevel.ADVANCED,
        pace=StudyPace.REGULAR,
        daily_available_minutes=45,
    )


def test_resolve_topic_count(curriculum_gen: CurriculumGenerator):
    """Verifica contagens sugeridas de tópicos para cada ritmo de estudo."""
    assert curriculum_gen._resolve_topic_count(StudyPace.RELAXED) == 5
    assert curriculum_gen._resolve_topic_count(StudyPace.REGULAR) == 7
    assert curriculum_gen._resolve_topic_count(StudyPace.INTENSIVE) == 10


def test_generate_validation_empty_subject(curriculum_gen: CurriculumGenerator):
    """Garante que perfil sem target_subject dispara erro."""
    invalid_profile = StudentProfile(name="Ana", target_subject="   ")
    with pytest.raises(ValueError, match="target_subject válido"):
        curriculum_gen.generate(invalid_profile)


def test_sanitize_and_validate_topics(curriculum_gen: CurriculumGenerator):
    """Testa higienização contra IDs duplicados, auto-referência e pré-requisitos futuros/inválidos."""
    raw_topics = [
        Topic(
            id="t1",
            title="Tópico 1",
            description="Desc 1",
            prerequisites=["t1", "fantasma", "t2"],  # t1 é auto-referência, t2 é futuro
        ),
        Topic(
            id="t1",  # ID duplicado
            title="Tópico 2",
            description="Desc 2",
            prerequisites=["t1"],
        ),
    ]

    sanitized = curriculum_gen._sanitize_and_validate_topics(raw_topics)

    assert len(sanitized) == 2
    assert sanitized[0].id == "t1"
    # Auto-referência e futuro devem ter sido removidos
    assert sanitized[0].prerequisites == []

    # O segundo tópico teve seu id ajustado para não colidir
    assert sanitized[1].id == "t1_2"
    assert sanitized[1].prerequisites == ["t1"]


def test_sanitize_empty_topics_raises_error(curriculum_gen: CurriculumGenerator):
    """Garante que lista vazia de tópicos levantada pelo LLM gera erro."""
    with pytest.raises(ValueError, match="não retornou nenhum tópico"):
        curriculum_gen._sanitize_and_validate_topics([])


def test_generate_curriculum_success(
    curriculum_gen: CurriculumGenerator,
    mock_llm_client: MagicMock,
    sample_profile: StudentProfile,
):
    """Testa o fluxo completo de geração e desbloqueio inicial da trilha."""
    mock_topics = [
        Topic(
            id="mod1_intro",
            title="Introdução ao FastAPI",
            description="Estrutura básica de rotas e ASGI",
            estimated_minutes=30,
            prerequisites=[],
        ),
        Topic(
            id="mod1_pydantic",
            title="Modelos e Schemas Pydantic",
            description="Validação de dados e serialização",
            estimated_minutes=40,
            prerequisites=["mod1_intro"],
        ),
    ]

    mock_llm_client.generate_structured.return_value = CurriculumGenerationPayload(
        overview="Trilha completa para dominar FastAPI e empacotamento com Docker.",
        topics=mock_topics,
    )

    curriculum = curriculum_gen.generate(sample_profile)

    assert curriculum.student_id == sample_profile.id
    assert curriculum.subject == "FastAPI com Docker"
    assert len(curriculum.topics) == 2

    # O primeiro tópico sem pré-requisitos deve estar AVAILABLE
    assert curriculum.topics[0].status == TopicStatus.AVAILABLE

    # O segundo tópico com pré-requisito pendente deve estar LOCKED
    assert curriculum.topics[1].status == TopicStatus.LOCKED

    mock_llm_client.generate_structured.assert_called_once()


def test_generate_curriculum_with_diagnostic(
    curriculum_gen: CurriculumGenerator,
    mock_llm_client: MagicMock,
    sample_profile: StudentProfile,
):
    """Verifica se o prompt inclui dados do diagnóstico pedagógico quando fornecido."""
    mock_llm_client.generate_structured.return_value = CurriculumGenerationPayload(
        overview="Trilha sob medida.",
        topics=[
            Topic(id="t1", title="Base", description="D", estimated_minutes=20, prerequisites=[])
        ],
    )

    diagnostic = DiagnosticReport(
        target_subject="FastAPI com Docker",
        assessed_level=KnowledgeLevel.BEGINNER,
        overall_score=40.0,
        answers=[],
        summary_feedback="O aluno precisa focar em requisições assíncronas.",
        strengths=["Conhece sintaxe de funções Python"],
        learning_gaps=["Injeção de dependências", "Asyncio"],
    )

    curriculum = curriculum_gen.generate(sample_profile, diagnostic_report=diagnostic)

    # Inspeciona a chamada do prompt enviado ao LLM
    call_args = mock_llm_client.generate_structured.call_args
    prompt_sent = call_args.kwargs["prompt"]

    assert "Score de partida: 40.0/100" in prompt_sent
    assert "Conhece sintaxe de funções Python" in prompt_sent
    assert "Injeção de dependências" in prompt_sent
    assert curriculum.topics[0].status == TopicStatus.AVAILABLE


def test_format_ascii_tree(sample_profile: StudentProfile):
    """Testa a geração textual do mapa mental / árvore de tópicos."""
    mock_topics = [
        Topic(
            id="t1",
            title="Fundamentos",
            description="Conceitos chave",
            estimated_minutes=30,
            status=TopicStatus.AVAILABLE,
            prerequisites=[],
        ),
        Topic(
            id="t2",
            title="Avançado",
            description="Tópicos avançados",
            estimated_minutes=45,
            status=TopicStatus.LOCKED,
            prerequisites=["t1"],
        ),
    ]

    from study_agent.models.curriculum import Curriculum

    curriculum = Curriculum(
        student_id=sample_profile.id,
        subject="Python",
        overview="Visão geral do curso",
        topics=mock_topics,
    )

    tree = CurriculumGenerator.format_ascii_tree(curriculum)

    assert "Trilha de Aprendizado: Python" in tree
    assert "[Disponível]" in tree
    assert "[Bloqueado]" in tree
    assert "<- pré-req: t1" in tree


def test_generate_mermaid_graph(sample_profile: StudentProfile):
    """Testa a exportação da trilha no formato Mermaid."""
    mock_topics = [
        Topic(
            id="t1",
            title="Básico",
            description="D1",
            estimated_minutes=25,
            status=TopicStatus.MASTERED,
            prerequisites=[],
        ),
        Topic(
            id="t2",
            title="Intermediário",
            description="D2",
            estimated_minutes=35,
            status=TopicStatus.AVAILABLE,
            prerequisites=["t1"],
        ),
    ]

    from study_agent.models.curriculum import Curriculum

    curriculum = Curriculum(
        student_id=sample_profile.id,
        subject="Python",
        overview="Visão geral",
        topics=mock_topics,
    )

    mermaid_code = CurriculumGenerator.generate_mermaid_graph(curriculum)

    assert "flowchart TD" in mermaid_code
    assert 't1["Básico<br/>⏱️ 25m"]' in mermaid_code
    assert "t1 --> t2" in mermaid_code
    assert "style t1 fill:#d4edda" in mermaid_code
