"""Testes automatizados de integração para a Interface Web FastAPI (tests/test_web.py)."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from study_agent.core.diagnostician import DiagnosticReport
from study_agent.core.exporter import StudyExporter
from study_agent.core.llm_client import LLMAuthenticationError, LLMConnectionError
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
    DiagnosticQuestion,
    KnowledgeLevel,
    StudentProfile,
)
from study_agent.storage.session_store import SessionStore
from study_agent.web.app import create_app


@pytest.fixture
def temp_store(tmp_path) -> SessionStore:
    return SessionStore(base_dir=tmp_path / "data")


@pytest.fixture
def mock_services():
    teacher = MagicMock()
    evaluator = MagicMock()
    diag = MagicMock()
    curr_gen = MagicMock()
    return {
        "teacher": teacher,
        "evaluator": evaluator,
        "diag": diag,
        "curr_gen": curr_gen,
    }


@pytest.fixture
def web_client(temp_store: SessionStore, mock_services, tmp_path) -> TestClient:
    exporter = StudyExporter(base_dir=tmp_path / "exports")
    app = create_app(
        store_factory=lambda: temp_store,
        teacher_factory=lambda: mock_services["teacher"],
        evaluator_factory=lambda: mock_services["evaluator"],
        diagnostician_factory=lambda: mock_services["diag"],
        curriculum_gen_factory=lambda: mock_services["curr_gen"],
        exporter_factory=lambda: exporter,
    )
    return TestClient(app)


def test_spa_index_static_assets_and_health(web_client: TestClient):
    """Verifica entrega do HTML principal, arquivos estáticos e health check."""
    res_html = web_client.get("/")
    assert res_html.status_code == 200
    assert "AI Study Agent" in res_html.text
    assert "/static/app.js" in res_html.text

    res_js = web_client.get("/static/app.js")
    assert res_js.status_code == 200
    assert "initApp" in res_js.text

    res_css = web_client.get("/static/styles.css")
    assert res_css.status_code == 200

    res_health = web_client.get("/api/health")
    assert res_health.status_code == 200
    assert res_health.json()["status"] == "ok"


def test_dashboard_empty_and_full_onboarding_shared_with_cli_store(
    web_client: TestClient,
    temp_store: SessionStore,
    mock_services,
):
    """Testa dashboard vazio e criação de trilha via Web persistindo no mesmo SessionStore da CLI."""
    empty_dash = web_client.get("/api/dashboard").json()
    assert empty_dash["has_active_session"] is False
    assert len(empty_dash["badges"]) == 17

    q_list = [
        DiagnosticQuestion(id="q1", question="O que é FastAPI?", topic_focus="Intro", difficulty=KnowledgeLevel.BEGINNER),
        DiagnosticQuestion(id="q2", question="O que faz Depends?", topic_focus="DI", difficulty=KnowledgeLevel.INTERMEDIATE),
        DiagnosticQuestion(id="q3", question="Como funciona ASGI?", topic_focus="Async", difficulty=KnowledgeLevel.ADVANCED),
    ]
    mock_services["diag"].generate_questions.return_value = q_list
    mock_services["diag"].evaluate_answers.return_value = DiagnosticReport(
        target_subject="FastAPI",
        assessed_level=KnowledgeLevel.INTERMEDIATE,
        overall_score=72.0,
        answers=[],
        summary_feedback="Boa base assíncrona.",
        strengths=["Rotas"],
        learning_gaps=[" Lifespan"],
    )

    def _fake_gen(student_profile: StudentProfile, diagnostic_report=None):
        c = Curriculum(
            id="curr_web_1",
            student_id=student_profile.id,
            subject=student_profile.target_subject,
            overview="Trilha Web FastAPI",
            topics=[
                Topic(id="t1", title='Rotas "Async"', description="Endpoints", status=TopicStatus.AVAILABLE),
                Topic(id="t2", title="Depends", description="DI", status=TopicStatus.LOCKED, prerequisites=["t1"]),
            ],
        )
        return c

    mock_services["curr_gen"].generate.side_effect = _fake_gen

    res_q = web_client.post("/api/onboarding/questions", json={"target_subject": "FastAPI"})
    assert res_q.status_code == 200
    assert len(res_q.json()["questions"]) == 3

    res_done = web_client.post(
        "/api/onboarding/complete",
        json={
            "name": "Beatriz",
            "target_subject": "FastAPI",
            "target_level": "advanced",
            "pace": "regular",
            "daily_available_minutes": 45,
            "questions": [q.model_dump(mode="json") for q in q_list],
            "answers": ["Framework web", "Injeta dependências", "Protocolo async"],
            "target_days": 7,
            "goal_label": "Sprint API",
        },
    )
    assert res_done.status_code == 200
    body = res_done.json()
    assert body["dashboard"]["has_active_session"] is True
    assert body["dashboard"]["goal_status"]["target_days"] == 7
    assert "flowchart TD" in body["dashboard"]["mermaid_code"]

    # Confirma compartilhamento direto com SessionStore usado pela CLI
    cli_student, cli_curr = temp_store.load_active_session()
    assert cli_student is not None and cli_student.name == "Beatriz"
    assert cli_student.has_badge("adquirindo_conhecimento")
    assert cli_curr is not None and cli_curr.goal_label == "Sprint API"


def test_study_lab_debug_recall_srs_goal_and_export_flow(
    web_client: TestClient,
    temp_store: SessionStore,
    mock_services,
):
    """Exercita o ciclo completo na Web: aula, lab (+XP), debug, Active Recall, fila SRS, metas e export."""
    student = StudentProfile(id="s1", name="Helena", target_subject="Docker")
    curr = Curriculum(
        id="c1",
        student_id="s1",
        subject="Docker",
        overview="Containers na prática",
        topics=[
            Topic(id="t1", title="Imagens", description="Camadas", status=TopicStatus.AVAILABLE),
            Topic(id="t2", title="Volumes", description="Dados", status=TopicStatus.LOCKED, prerequisites=["t1"]),
        ],
    )
    temp_store.save_student(student)
    temp_store.save_curriculum(curr)
    temp_store.set_current_session(student.id, curr.id)

    # Tópico bloqueado deve retornar 400
    res_locked = web_client.post("/api/study/explain", json={"topic_id": "t2", "style": "feynman"})
    assert res_locked.status_code == 400

    # 1. Explicação + Takeaways
    mock_services["teacher"].explain_topic.return_value = "## Imagens Docker\nCamadas imutáveis."
    mock_services["teacher"].summarize_key_takeaways.return_value = ["UnionFS", "Cache de build"]
    res_exp = web_client.post("/api/study/explain", json={"topic_id": "t1", "style": "feynman"})
    assert res_exp.status_code == 200
    assert res_exp.json()["key_takeaways"] == ["UnionFS", "Cache de build"]

    # 2. Tira-dúvidas
    mock_services["teacher"].answer_doubt.return_value = "Cada instrução RUN cria uma nova camada."
    res_doubt = web_client.post("/api/study/doubt", json={"topic_id": "t1", "question": "O que cria camadas?"})
    assert res_doubt.status_code == 200
    assert "camada" in res_doubt.json()["answer"]

    # 3. Laboratório Guiado + Checkpoints (+15 XP por missão inédita)
    mock_services["teacher"].generate_guided_lab.return_value = GuidedLab(
        topic_id="t1",
        intro_brief="Vamos inspecionar imagens.",
        missions=[
            LabMission(
                step_number=1,
                title="Baixar alpine",
                instruction="Faça pull da imagem",
                command_or_code="docker pull alpine",
                expected_outcome="Download concluído",
            )
        ],
    )
    res_lab = web_client.post("/api/study/lab", json={"topic_id": "t1"})
    assert res_lab.status_code == 200

    res_chk = web_client.post("/api/study/lab/checkpoint", json={"topic_id": "t1", "step_number": 1})
    assert res_chk.status_code == 200
    assert res_chk.json()["event"]["xp_gained"] == 15

    # Repetir o mesmo checkpoint não farma XP
    res_chk_dup = web_client.post("/api/study/lab/checkpoint", json={"topic_id": "t1", "step_number": 1})
    assert res_chk_dup.json()["event"]["xp_gained"] == 0

    # 4. Debugging de erro real
    mock_services["teacher"].debug_error.return_value = ErrorDebugResolution(
        error_summary="Daemon desligado.",
        root_cause="Serviço parado.",
        fix_instructions=["Inicie o Docker Desktop"],
        corrected_command_or_code="docker info",
    )
    res_dbg = web_client.post(
        "/api/study/debug",
        json={"topic_id": "t1", "command_attempted": "docker ps", "error_output": "Cannot connect to daemon"},
    )
    assert res_dbg.status_code == 200
    assert res_dbg.json()["resolution"]["corrected_command_or_code"] == "docker info"

    # 5. Active Recall (96% -> +100 + 25 = 125 XP, desbloqueia t2 e conquistas)
    q_obj = ActiveRecallQuestion(id="qr1", question="Como funciona o cache de camadas?", expected_concepts=["Ordem"])
    mock_services["evaluator"].generate_active_recall_question.return_value = q_obj
    mock_services["evaluator"].evaluate_active_recall.return_value = ActiveRecallEvaluation(
        question_id="qr1",
        student_answer="Reaproveita camadas inalteradas.",
        score=96.0,
        understood_concepts=["Cache"],
        missing_or_confused_concepts=[],
        feedback="Impecável!",
        is_passing=True,
    )
    # Usa o método real de update_topic_mastery para validar integração ponta a ponta
    from study_agent.core.evaluator import Evaluator as RealEvaluator

    mock_services["evaluator"].update_topic_mastery.side_effect = RealEvaluator(
        llm_client=MagicMock()
    ).update_topic_mastery

    res_rq = web_client.post("/api/study/recall/question", json={"topic_id": "t1"})
    assert res_rq.status_code == 200

    res_reval = web_client.post(
        "/api/study/recall/evaluate",
        json={
            "topic_id": "t1",
            "question": res_rq.json()["question"],
            "student_answer": "Reaproveita camadas inalteradas.",
        },
    )
    assert res_reval.status_code == 200
    reval_data = res_reval.json()
    assert reval_data["event"]["xp_gained"] == 125  # 100 + 25 (os 15 do lab já foram dados no checkpoint)
    assert reval_data["dashboard"]["student"]["xp"] == 140  # 15 + 125
    t2_after = next(t for t in reval_data["dashboard"]["curriculum"]["topics"] if t["id"] == "t2")
    assert t2_after["status"] == "available"

    unlocked_ids = {b["id"] for b in reval_data["dashboard"]["badges"] if b["unlocked"]}
    assert {"primeiro_dominio", "maestria_impecavel", "mao_na_massa", "cacador_de_bugs"}.issubset(unlocked_ids)

    # 6. Revisão Espaçada (SRS): força vencimento de t1 e revisa com 0 XP
    reloaded_curr = temp_store.load_curriculum(curr.id)
    assert reloaded_curr is not None
    reloaded_curr.topics[0].next_review_at = datetime.now(timezone.utc) - timedelta(hours=1)
    temp_store.save_curriculum(reloaded_curr)

    res_srs_q = web_client.post("/api/srs/question", json={"topic_id": "t1"})
    assert res_srs_q.status_code == 200

    res_srs_eval = web_client.post(
        "/api/srs/evaluate",
        json={
            "topic_id": "t1",
            "question": res_srs_q.json()["question"],
            "student_answer": "Camadas imutáveis empilhadas.",
        },
    )
    assert res_srs_eval.status_code == 200
    assert res_srs_eval.json()["event"]["xp_gained"] == 0
    assert res_srs_eval.json()["srs_result"]["is_retained"] is True

    # 7. Definir e remover Meta via Web
    res_goal = web_client.post("/api/goal", json={"target_days": 5, "goal_label": "Meta Web"})
    assert res_goal.status_code == 200
    assert res_goal.json()["goal_status"]["goal_label"] == "Meta Web"

    res_del_goal = web_client.delete("/api/goal")
    assert res_del_goal.status_code == 200
    assert res_del_goal.json()["goal_status"]["has_goal"] is False

    # 8. Exportação Markdown & Anki via Web
    res_export = web_client.post("/api/export", json={"format": "both", "include_in_progress": False})
    assert res_export.status_code == 200
    exp_json = res_export.json()
    assert exp_json["topics_exported"] == 1
    assert "#separator:tab" in exp_json["anki_content"]
    assert "Imagens" in exp_json["markdown_content"]


def test_web_llm_exception_handlers_return_friendly_http_codes(
    web_client: TestClient,
    mock_services,
):
    """Verifica tradução limpa de falhas 401 e 503/429 da IA em respostas JSON amigáveis."""
    mock_services["diag"].generate_questions.side_effect = LLMAuthenticationError("Invalid API key")
    res_401 = web_client.post("/api/onboarding/questions", json={"target_subject": "Python"})
    assert res_401.status_code == 401
    assert ".env" in res_401.json()["detail"]

    mock_services["diag"].generate_questions.side_effect = LLMConnectionError(
        "Rate limit", attempts=4, status_code=429, is_rate_limit=True
    )
    res_429 = web_client.post("/api/onboarding/questions", json={"target_subject": "Python"})
    assert res_429.status_code == 429
    assert "4 tentativa(s)" in res_429.json()["detail"]
