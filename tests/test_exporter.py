"""Testes unitários para o módulo StudyExporter (study_agent/core/exporter.py)."""

from pathlib import Path
import pytest

from study_agent.core.evaluator import Evaluator
from study_agent.core.exporter import StudyExporter
from study_agent.models.curriculum import (
    ActiveRecallEvaluation,
    ActiveRecallQuestion,
    Curriculum,
    RecallRecord,
    Topic,
    TopicStatus,
)
from study_agent.models.student import KnowledgeLevel, StudentProfile


@pytest.fixture
def exporter_student() -> StudentProfile:
    return StudentProfile(
        id="std_exp",
        name="João Silva",
        target_subject="Programação Assíncrona & FastAPI",
        current_level=KnowledgeLevel.INTERMEDIATE,
        target_level=KnowledgeLevel.ADVANCED,
    )


@pytest.fixture
def exporter_curriculum(exporter_student: StudentProfile) -> Curriculum:
    return Curriculum(
        id="curr_exp",
        student_id=exporter_student.id,
        subject="Programação Assíncrona & FastAPI",
        overview="Domínio de corrotinas, event loop e endpoints não-bloqueantes.",
        topics=[
            Topic(
                id="t1",
                title="Event Loop & Corrotinas",
                description="Como o Python agenda tarefas I/O sem bloquear threads",
                status=TopicStatus.MASTERED,
                mastery_score=92.0,
                review_count=2,
                completed_lab_steps=3,
                key_takeaways=[
                    "await suspende a corrotina atual e devolve controle ao Event Loop",
                    "Operações CPU-bound bloqueiam o loop se não usarem ProcessPool",
                ],
                recall_history=[
                    RecallRecord(
                        question="O que acontece se chamarmos time.sleep(5) dentro de async def?",
                        student_answer="Bloqueia todo o event loop por 5 segundos.",
                        expected_concepts=["Bloqueio da thread única", "Usar asyncio.sleep"],
                        feedback="Exato! Para não travar outras requisições, use await asyncio.sleep(5).",
                        score=92.0,
                    )
                ],
            ),
            Topic(
                id="t2",
                title="Injeção de Dependências com Depends",
                description="Gerenciamento de sessão de banco e autenticação",
                status=TopicStatus.IN_PROGRESS,
                mastery_score=60.0,
                review_count=1,
                key_takeaways=["Depends permite reutilizar lógica e facilitar mocks em testes"],
            ),
            Topic(
                id="t3",
                title="WebSockets em Tempo Real",
                description="Comunicação bidirecional persistente",
                status=TopicStatus.LOCKED,
                prerequisites=["t2"],
            ),
        ],
    )


def test_slugify_handles_accents_and_special_chars():
    assert StudyExporter.slugify("Programação Assíncrona & FastAPI!") == "programacao_assincrona_fastapi"
    assert StudyExporter.slugify("   ") == "estudo"


def test_render_markdown_summary_includes_frontmatter_mermaid_and_details(
    exporter_student: StudentProfile,
    exporter_curriculum: Curriculum,
):
    exporter = StudyExporter()
    md = exporter.render_markdown_summary(exporter_student, exporter_curriculum)

    assert 'title: "Resumo de Estudos — Programação Assíncrona & FastAPI"' in md
    assert "```mermaid" in md
    assert "### 1. Event Loop & Corrotinas" in md
    assert "Missões de Lab:" in md
    assert "<details>" in md
    assert "time.sleep(5)" in md
    # Tópico IN_PROGRESS aparece no mapa geral Mermaid, mas não entra como seção de tópico consolidado
    assert "### 2. Injeção de Dependências com Depends" not in md


def test_render_anki_deck_headers_and_tsv_columns(exporter_curriculum: Curriculum):
    exporter = StudyExporter()
    # Injeta caracteres especiais (<tag>, tab e quebra de linha) para testar sanitização TSV
    exporter_curriculum.topics[0].recall_history[0].student_answer = "Usa <coroutine>\tcom\nawait"

    deck_txt = exporter.render_anki_deck(exporter_curriculum)
    lines = deck_txt.strip().splitlines()

    assert lines[0] == "#separator:tab"
    assert lines[1] == "#html:true"
    assert lines[2] == "#deck:AI Study Agent::Programação Assíncrona & FastAPI"
    assert lines[3] == "#tags column:3"

    card_lines = lines[4:]
    assert len(card_lines) == 2  # 1 card de Active Recall + 1 card de Key Takeaways
    for line in card_lines:
        cols = line.split("\t")
        assert len(cols) == 3
        assert "&lt;coroutine&gt;" in cols[1] or "Pontos-chave" in cols[1]


def test_export_session_formats_and_filtering(
    tmp_path: Path,
    exporter_student: StudentProfile,
    exporter_curriculum: Curriculum,
):
    exporter = StudyExporter(base_dir=tmp_path)

    # Exporta apenas MASTERED em ambos formatos
    res_both = exporter.export_session(exporter_student, exporter_curriculum, fmt="both")
    assert res_both.topics_exported == 1
    assert res_both.flashcards_generated == 2
    assert res_both.markdown_path is not None and res_both.markdown_path.exists()
    assert res_both.anki_path is not None and res_both.anki_path.exists()

    # Exporta incluindo IN_PROGRESS apenas para Anki
    res_in_prog = exporter.export_session(
        exporter_student,
        exporter_curriculum,
        fmt="anki",
        include_in_progress=True,
    )
    assert res_in_prog.topics_exported == 2
    assert res_in_prog.markdown_path is None
    assert res_in_prog.anki_path is not None and res_in_prog.anki_path.exists()
    assert res_in_prog.flashcards_generated == 3


def test_export_session_validations(
    tmp_path: Path,
    exporter_student: StudentProfile,
    exporter_curriculum: Curriculum,
):
    exporter = StudyExporter(base_dir=tmp_path)

    with pytest.raises(ValueError, match="Formato inválido"):
        exporter.export_session(exporter_student, exporter_curriculum, fmt="docx")

    locked_only = Curriculum(
        student_id=exporter_student.id,
        subject="Go",
        overview="Trilha vazia de concluídos",
        topics=[Topic(id="t1", title="Goroutines", description="Desc", status=TopicStatus.AVAILABLE)],
    )
    with pytest.raises(ValueError, match="Não há tópicos elegíveis"):
        exporter.export_session(exporter_student, locked_only)


def test_evaluator_records_recall_history_when_question_passed():
    evaluator = Evaluator(llm_client=None)  # update_topic_mastery é determinístico
    topic = Topic(id="t1", title="Indices B-Tree", description="Banco de dados")
    question = ActiveRecallQuestion(
        id="q1",
        question="Por que índices B-Tree aceleram buscas por faixa (range queries)?",
        expected_concepts=["Folhas ordenadas", "Complexidade O(log N)"],
    )
    evaluation = ActiveRecallEvaluation(
        question_id="q1",
        student_answer="Porque mantém chaves ordenadas nas folhas ligadas.",
        score=88.0,
        understood_concepts=["Folhas ordenadas"],
        missing_or_confused_concepts=[],
        feedback="Excelente!",
        is_passing=True,
    )

    evaluator.update_topic_mastery(topic, evaluation, question=question)

    assert topic.status == TopicStatus.MASTERED
    assert len(topic.recall_history) == 1
    assert topic.recall_history[0].question == question.question
    assert topic.recall_history[0].score == 88.0
