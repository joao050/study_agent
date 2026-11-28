"""Servidor FastAPI integrado compartilhando core/ e SessionStore com a CLI."""

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from study_agent import __version__
from study_agent.core.curriculum_gen import CurriculumGenerator
from study_agent.core.diagnostician import Diagnostician
from study_agent.core.evaluator import Evaluator
from study_agent.core.exporter import StudyExporter
from study_agent.core.gamification import BADGE_CATALOG, GamificationEngine
from study_agent.core.llm_client import (
    LLMAuthenticationError,
    LLMClientError,
    LLMConnectionError,
    LLMResponseValidationError,
)
from study_agent.core.srs import SpacedRepetitionEngine
from study_agent.core.teacher import Teacher
from study_agent.models.curriculum import (
    ActiveRecallQuestion,
    Curriculum,
    ExplanationStyle,
    Topic,
    TopicStatus,
)
from study_agent.models.student import (
    DiagnosticQuestion,
    KnowledgeLevel,
    StudentProfile,
    StudyPace,
)
from study_agent.storage.session_store import SessionStore

WEB_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = WEB_DIR / "templates"
STATIC_DIR = WEB_DIR / "static"


# --- Payloads de Requisição da API REST ---


class SwitchStudentRequest(BaseModel):
    student_id: str


class OnboardingQuestionsRequest(BaseModel):
    target_subject: str = Field(min_length=1)


class OnboardingCompleteRequest(BaseModel):
    name: str = Field(min_length=1)
    target_subject: str = Field(min_length=1)
    target_level: KnowledgeLevel = KnowledgeLevel.ADVANCED
    pace: StudyPace = StudyPace.REGULAR
    daily_available_minutes: int = Field(default=45, ge=10, le=480)
    questions: List[DiagnosticQuestion]
    answers: List[str]
    target_days: Optional[int] = Field(default=None, ge=0, le=3650)
    goal_label: Optional[str] = None


class GoalUpdateRequest(BaseModel):
    target_days: int = Field(ge=1, le=3650)
    goal_label: Optional[str] = None


class ExplainTopicRequest(BaseModel):
    topic_id: str
    style: ExplanationStyle = ExplanationStyle.FEYNMAN


class DoubtRequest(BaseModel):
    topic_id: str
    question: str = Field(min_length=1)
    previous_explanation: Optional[str] = None


class LabRequest(BaseModel):
    topic_id: str


class LabCheckpointRequest(BaseModel):
    topic_id: str
    step_number: int = Field(ge=1)


class DebugErrorRequest(BaseModel):
    topic_id: str
    command_attempted: str = ""
    error_output: str = Field(min_length=1)


class RecallQuestionRequest(BaseModel):
    topic_id: str


class RecallEvaluateRequest(BaseModel):
    topic_id: str
    question: ActiveRecallQuestion
    student_answer: str


class ExportSessionRequest(BaseModel):
    format: str = "both"
    include_in_progress: bool = False


def build_interactive_mermaid(curriculum: Curriculum) -> str:
    """Gera grafo Mermaid estilizado para o tema visual Web com nós seguros contra aspas."""
    lines = ["flowchart TD"]
    status_styles = {
        TopicStatus.MASTERED: "fill:#064e3b,stroke:#10b981,stroke-width:2px,color:#ecfdf5",
        TopicStatus.IN_PROGRESS: "fill:#78350f,stroke:#f59e0b,stroke-width:2px,color:#fffbeb",
        TopicStatus.AVAILABLE: "fill:#1e3a8a,stroke:#38bdf8,stroke-width:2px,color:#eff6ff",
        TopicStatus.LOCKED: "fill:#1e293b,stroke:#475569,stroke-width:1px,color:#94a3b8",
    }
    status_icons = {
        TopicStatus.MASTERED: "✅",
        TopicStatus.IN_PROGRESS: "⏳",
        TopicStatus.AVAILABLE: "🔓",
        TopicStatus.LOCKED: "🔒",
    }

    for topic in curriculum.topics:
        safe_title = topic.title.replace('"', "'").replace("[", "(").replace("]", ")")
        icon = status_icons.get(topic.status, "•")
        score_txt = f" • {topic.mastery_score:.0f}%" if topic.mastery_score > 0 else ""
        lines.append(
            f'    {topic.id}["{icon} {safe_title}<br/><small>⏱️ {topic.estimated_minutes}m{score_txt}</small>"]'
        )
        for prereq in topic.prerequisites:
            lines.append(f"    {prereq} --> {topic.id}")
        style = status_styles.get(topic.status)
        if style:
            lines.append(f"    style {topic.id} {style}")

    return "\n".join(lines)


def _serialize_dashboard(store: SessionStore) -> Dict[str, Any]:
    """Constrói o snapshot completo do Dashboard Web para o frontend SPA."""
    student, curriculum = store.load_active_session()
    all_students = store.list_students()

    students_list = [
        {
            "id": s.id,
            "name": s.name,
            "target_subject": s.target_subject,
            "current_level": s.current_level.value,
            "level": s.level,
            "level_title": s.level_title,
            "xp": s.xp,
            "is_active": bool(student and s.id == student.id),
        }
        for s in all_students
    ]

    if not student or not curriculum:
        return {
            "has_active_session": False,
            "student": None,
            "curriculum": None,
            "overall_progress_pct": 0.0,
            "level_progress": None,
            "effective_streak": 0,
            "goal_status": None,
            "srs_summary": None,
            "due_topics": [],
            "badges": [
                {
                    **b.model_dump(mode="json"),
                    "unlocked": False,
                    "unlocked_at": None,
                }
                for b in BADGE_CATALOG
            ],
            "mermaid_code": "",
            "students": students_list,
        }

    curriculum.update_topic_statuses()
    level_prog = GamificationEngine.calculate_level_progress(student.xp)
    eff_streak = GamificationEngine.get_effective_streak(student)
    goal_status = GamificationEngine.get_goal_status(curriculum)
    srs_summary = SpacedRepetitionEngine.get_queue_summary(curriculum)
    due_topics = SpacedRepetitionEngine.get_due_topics(curriculum)

    unlocked_map = {b.badge_id: b.unlocked_at.isoformat() for b in student.unlocked_badges}
    badges_payload = [
        {
            **b.model_dump(mode="json"),
            "unlocked": b.id in unlocked_map,
            "unlocked_at": unlocked_map.get(b.id),
        }
        for b in BADGE_CATALOG
    ]

    return {
        "has_active_session": True,
        "student": student.model_dump(mode="json"),
        "curriculum": curriculum.model_dump(mode="json"),
        "overall_progress_pct": curriculum.calculate_overall_progress(),
        "level_progress": level_prog.model_dump(mode="json"),
        "effective_streak": eff_streak,
        "goal_status": goal_status.model_dump(mode="json"),
        "srs_summary": srs_summary.model_dump(mode="json"),
        "due_topics": [t.model_dump(mode="json") for t in due_topics],
        "badges": badges_payload,
        "mermaid_code": build_interactive_mermaid(curriculum),
        "students": students_list,
    }


def create_app(
    store_factory: Optional[Callable[[], SessionStore]] = None,
    teacher_factory: Optional[Callable[[], Teacher]] = None,
    evaluator_factory: Optional[Callable[[], Evaluator]] = None,
    diagnostician_factory: Optional[Callable[[], Diagnostician]] = None,
    curriculum_gen_factory: Optional[Callable[[], CurriculumGenerator]] = None,
    exporter_factory: Optional[Callable[[], StudyExporter]] = None,
) -> FastAPI:
    """Application Factory do servidor Web integrado (facilita injeção de mocks nos testes)."""
    get_store_fn = store_factory or SessionStore
    get_teacher_fn = teacher_factory or Teacher
    get_evaluator_fn = evaluator_factory or Evaluator
    get_diag_fn = diagnostician_factory or Diagnostician
    get_curr_gen_fn = curriculum_gen_factory or CurriculumGenerator
    get_exporter_fn = exporter_factory or StudyExporter

    web_app = FastAPI(
        title="AI Study Agent — Web App Integrado",
        version=__version__,
        description="Interface gráfica local integrada compartilhando core/ e SessionStore com a CLI.",
    )

    if STATIC_DIR.exists():
        web_app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @web_app.exception_handler(LLMClientError)
    async def handle_llm_errors(_request: Request, exc: LLMClientError) -> JSONResponse:
        if isinstance(exc, LLMAuthenticationError):
            return JSONResponse(
                status_code=401,
                content={
                    "error": "authentication_error",
                    "detail": (
                        "Falha de autenticação no provedor de IA. "
                        "Verifique sua API Key e LLM_PROVIDER no arquivo .env."
                    ),
                },
            )
        if isinstance(exc, LLMConnectionError):
            status_code = 429 if exc.is_rate_limit else 503
            return JSONResponse(
                status_code=status_code,
                content={
                    "error": "connection_error",
                    "detail": (
                        f"O serviço de IA não respondeu após {exc.attempts} tentativa(s) "
                        "(limite de taxa 429 ou oscilação 503). Aguarde alguns segundos e tente novamente."
                    ),
                },
            )
        if isinstance(exc, LLMResponseValidationError):
            return JSONResponse(
                status_code=502,
                content={
                    "error": "validation_error",
                    "detail": "O modelo retornou dados fora do formato estruturado esperado. Tente novamente.",
                },
            )
        return JSONResponse(
            status_code=502,
            content={"error": "llm_error", "detail": str(exc)},
        )

    def _require_active_session(store: SessionStore) -> tuple[StudentProfile, Curriculum]:
        student, curriculum = store.load_active_session()
        if not student or not curriculum:
            raise HTTPException(
                status_code=404,
                detail="Nenhuma sessão ativa encontrada. Crie ou selecione uma trilha primeiro.",
            )
        return student, curriculum

    def _require_topic(curriculum: Curriculum, topic_id: str, allow_locked: bool = False) -> Topic:
        topic = curriculum.get_topic(topic_id)
        if not topic:
            raise HTTPException(status_code=404, detail=f"Tópico '{topic_id}' não encontrado na trilha.")
        if not allow_locked and topic.status == TopicStatus.LOCKED:
            raise HTTPException(
                status_code=400,
                detail="Este tópico ainda está bloqueado. Domine os pré-requisitos anteriores primeiro.",
            )
        return topic

    @web_app.get("/", response_class=HTMLResponse)
    async def serve_spa() -> HTMLResponse:
        index_file = TEMPLATES_DIR / "index.html"
        if not index_file.exists():
            return HTMLResponse("<h1>AI Study Agent Web</h1><p>Template não encontrado.</p>", status_code=500)
        return HTMLResponse(index_file.read_text(encoding="utf-8"))

    @web_app.get("/api/health")
    async def health_check() -> Dict[str, str]:
        return {"status": "ok", "version": __version__}

    @web_app.get("/api/dashboard")
    async def get_dashboard() -> Dict[str, Any]:
        store = get_store_fn()
        return _serialize_dashboard(store)

    @web_app.post("/api/students/switch")
    async def switch_student(payload: SwitchStudentRequest) -> Dict[str, Any]:
        store = get_store_fn()
        student = store.load_student(payload.student_id)
        if not student:
            raise HTTPException(status_code=404, detail="Estudante não encontrado.")
        curriculum = store.load_curriculum_by_student(student.id)
        if not curriculum:
            raise HTTPException(status_code=404, detail="Nenhuma trilha encontrada para este estudante.")
        store.set_current_session(student.id, curriculum.id)
        return _serialize_dashboard(store)

    @web_app.post("/api/onboarding/questions")
    async def generate_onboarding_questions(payload: OnboardingQuestionsRequest) -> Dict[str, Any]:
        diag = get_diag_fn()
        questions = diag.generate_questions(target_subject=payload.target_subject.strip(), count=3)
        return {"questions": [q.model_dump(mode="json") for q in questions]}

    @web_app.post("/api/onboarding/complete")
    async def complete_onboarding(payload: OnboardingCompleteRequest) -> Dict[str, Any]:
        if len(payload.questions) != len(payload.answers):
            raise HTTPException(
                status_code=400,
                detail="A quantidade de respostas deve corresponder às perguntas diagnósticas.",
            )

        profile = StudentProfile(
            name=payload.name.strip(),
            target_subject=payload.target_subject.strip(),
            current_level=KnowledgeLevel.BEGINNER,
            target_level=payload.target_level,
            pace=payload.pace,
            daily_available_minutes=payload.daily_available_minutes,
        )

        diag = get_diag_fn()
        report = diag.evaluate_answers(
            target_subject=profile.target_subject,
            questions=payload.questions,
            student_answers=payload.answers,
        )
        profile.current_level = report.assessed_level
        profile.diagnostic_history = report.answers

        curr_gen = get_curr_gen_fn()
        curriculum = curr_gen.generate(student_profile=profile, diagnostic_report=report)

        if payload.target_days and payload.target_days > 0:
            GamificationEngine.set_goal(
                curriculum,
                target_days=payload.target_days,
                goal_label=payload.goal_label,
            )

        event = GamificationEngine.record_onboarding(profile, curriculum=curriculum)

        store = get_store_fn()
        store.save_student(profile)
        store.save_curriculum(curriculum)
        store.set_current_session(profile.id, curriculum.id)

        return {
            "report": report.model_dump(mode="json"),
            "event": event.model_dump(mode="json"),
            "dashboard": _serialize_dashboard(store),
        }

    @web_app.post("/api/goal")
    async def set_curriculum_goal(payload: GoalUpdateRequest) -> Dict[str, Any]:
        store = get_store_fn()
        _, curriculum = _require_active_session(store)
        goal_status = GamificationEngine.set_goal(
            curriculum,
            target_days=payload.target_days,
            goal_label=payload.goal_label,
        )
        store.save_curriculum(curriculum)
        return {
            "goal_status": goal_status.model_dump(mode="json"),
            "dashboard": _serialize_dashboard(store),
        }

    @web_app.delete("/api/goal")
    async def clear_curriculum_goal() -> Dict[str, Any]:
        store = get_store_fn()
        _, curriculum = _require_active_session(store)
        GamificationEngine.clear_goal(curriculum)
        store.save_curriculum(curriculum)
        return {
            "goal_status": GamificationEngine.get_goal_status(curriculum).model_dump(mode="json"),
            "dashboard": _serialize_dashboard(store),
        }

    @web_app.post("/api/study/explain")
    async def explain_topic(payload: ExplainTopicRequest) -> Dict[str, Any]:
        store = get_store_fn()
        student, curriculum = _require_active_session(store)
        topic = _require_topic(curriculum, payload.topic_id)

        teacher = get_teacher_fn()
        explanation = teacher.explain_topic(
            topic=topic,
            style=payload.style,
            student_context=f"Aluno nível {student.current_level.value}",
        )

        takeaways = topic.key_takeaways
        try:
            takeaways = teacher.summarize_key_takeaways(topic, explanation)
            topic.key_takeaways = takeaways
            if topic.status == TopicStatus.AVAILABLE:
                topic.status = TopicStatus.IN_PROGRESS
            store.save_curriculum(curriculum)
        except LLMClientError:
            pass

        return {
            "topic_id": topic.id,
            "style": payload.style.value,
            "explanation": explanation,
            "key_takeaways": takeaways,
            "dashboard": _serialize_dashboard(store),
        }

    @web_app.post("/api/study/doubt")
    async def answer_topic_doubt(payload: DoubtRequest) -> Dict[str, Any]:
        store = get_store_fn()
        _, curriculum = _require_active_session(store)
        topic = _require_topic(curriculum, payload.topic_id)

        teacher = get_teacher_fn()
        answer = teacher.answer_doubt(
            topic=topic,
            student_question=payload.question,
            previous_explanation=payload.previous_explanation,
        )
        return {"answer": answer}

    @web_app.post("/api/study/lab")
    async def generate_topic_lab(payload: LabRequest) -> Dict[str, Any]:
        store = get_store_fn()
        student, curriculum = _require_active_session(store)
        topic = _require_topic(curriculum, payload.topic_id)

        teacher = get_teacher_fn()
        lab = teacher.generate_guided_lab(topic=topic, student=student)
        topic.total_lab_missions = max(topic.total_lab_missions, len(lab.missions))
        if topic.status == TopicStatus.AVAILABLE:
            topic.status = TopicStatus.IN_PROGRESS
        store.save_curriculum(curriculum)

        return {
            "lab": lab.model_dump(mode="json"),
            "completed_lab_steps": topic.completed_lab_steps,
            "dashboard": _serialize_dashboard(store),
        }

    @web_app.post("/api/study/lab/checkpoint")
    async def complete_lab_checkpoint(payload: LabCheckpointRequest) -> Dict[str, Any]:
        store = get_store_fn()
        student, curriculum = _require_active_session(store)
        topic = _require_topic(curriculum, payload.topic_id)

        topic.completed_lab_steps = max(topic.completed_lab_steps, payload.step_number)
        event = GamificationEngine.award_lab_mission_xp(
            student=student,
            topic=topic,
            curriculum=curriculum,
        )
        store.save_student(student)
        store.save_curriculum(curriculum)

        return {
            "completed_lab_steps": topic.completed_lab_steps,
            "event": event.model_dump(mode="json"),
            "dashboard": _serialize_dashboard(store),
        }

    @web_app.post("/api/study/debug")
    async def debug_terminal_error(payload: DebugErrorRequest) -> Dict[str, Any]:
        store = get_store_fn()
        student, curriculum = _require_active_session(store)
        topic = _require_topic(curriculum, payload.topic_id)

        teacher = get_teacher_fn()
        resolution = teacher.debug_error(
            student=student,
            topic=topic,
            command_attempted=payload.command_attempted,
            error_output=payload.error_output,
        )
        GamificationEngine.record_debug_usage(topic)
        store.save_curriculum(curriculum)

        return {"resolution": resolution.model_dump(mode="json")}

    @web_app.post("/api/study/recall/question")
    async def generate_recall_question(payload: RecallQuestionRequest) -> Dict[str, Any]:
        store = get_store_fn()
        _, curriculum = _require_active_session(store)
        topic = _require_topic(curriculum, payload.topic_id)

        evaluator = get_evaluator_fn()
        question = evaluator.generate_active_recall_question(
            topic=topic,
            key_takeaways=topic.key_takeaways,
        )
        return {"question": question.model_dump(mode="json")}

    @web_app.post("/api/study/recall/evaluate")
    async def evaluate_recall_answer(payload: RecallEvaluateRequest) -> Dict[str, Any]:
        store = get_store_fn()
        student, curriculum = _require_active_session(store)
        topic = _require_topic(curriculum, payload.topic_id)

        evaluator = get_evaluator_fn()
        evaluation = evaluator.evaluate_active_recall(
            question=payload.question,
            student_answer=payload.student_answer,
        )

        was_mastered_before = topic.status == TopicStatus.MASTERED
        previous_best_score = max(
            (r.score for r in topic.recall_history),
            default=topic.mastery_score,
        )

        evaluator.update_topic_mastery(
            topic=topic,
            evaluation=evaluation,
            question=payload.question,
        )
        curriculum.update_topic_statuses()

        event = GamificationEngine.process_topic_evaluation(
            student=student,
            curriculum=curriculum,
            topic=topic,
            evaluation=evaluation,
            was_mastered_before=was_mastered_before,
            previous_score=previous_best_score,
        )

        store.save_student(student)
        store.save_curriculum(curriculum)

        return {
            "evaluation": evaluation.model_dump(mode="json"),
            "event": event.model_dump(mode="json"),
            "topic": topic.model_dump(mode="json"),
            "dashboard": _serialize_dashboard(store),
        }

    @web_app.post("/api/srs/question")
    async def generate_srs_question(payload: RecallQuestionRequest) -> Dict[str, Any]:
        store = get_store_fn()
        _, curriculum = _require_active_session(store)
        topic = _require_topic(curriculum, payload.topic_id)
        if topic.status != TopicStatus.MASTERED:
            raise HTTPException(
                status_code=400,
                detail="Apenas tópicos já dominados podem passar por revisão espaçada (SRS).",
            )

        evaluator = get_evaluator_fn()
        question = evaluator.generate_active_recall_question(
            topic=topic,
            key_takeaways=topic.key_takeaways,
        )
        return {
            "question": question.model_dump(mode="json"),
            "topic": topic.model_dump(mode="json"),
        }

    @web_app.post("/api/srs/evaluate")
    async def evaluate_srs_answer(payload: RecallEvaluateRequest) -> Dict[str, Any]:
        store = get_store_fn()
        student, curriculum = _require_active_session(store)
        topic = _require_topic(curriculum, payload.topic_id)
        if topic.status != TopicStatus.MASTERED:
            raise HTTPException(
                status_code=400,
                detail="Apenas tópicos já dominados podem passar por revisão espaçada (SRS).",
            )

        evaluator = get_evaluator_fn()
        evaluation = evaluator.evaluate_active_recall(
            question=payload.question,
            student_answer=payload.student_answer,
        )

        srs_result, event = SpacedRepetitionEngine.complete_review_session(
            student=student,
            curriculum=curriculum,
            topic=topic,
            evaluation=evaluation,
            question=payload.question,
        )

        store.save_student(student)
        store.save_curriculum(curriculum)

        return {
            "evaluation": evaluation.model_dump(mode="json"),
            "srs_result": srs_result.model_dump(mode="json"),
            "event": event.model_dump(mode="json"),
            "dashboard": _serialize_dashboard(store),
        }

    @web_app.post("/api/export")
    async def export_study_materials(payload: ExportSessionRequest) -> Dict[str, Any]:
        store = get_store_fn()
        student, curriculum = _require_active_session(store)

        exporter = get_exporter_fn()
        fmt = payload.format.strip().lower()
        if fmt not in StudyExporter.VALID_FORMATS:
            raise HTTPException(status_code=400, detail="Formato inválido. Use 'both', 'markdown' ou 'anki'.")

        eligible = exporter.select_exportable_topics(
            curriculum, include_in_progress=payload.include_in_progress
        )
        if not eligible:
            raise HTTPException(
                status_code=400,
                detail="Ainda não há tópicos elegíveis para exportar nesta trilha.",
            )

        result = exporter.export_session(
            student=student,
            curriculum=curriculum,
            fmt=fmt,
            include_in_progress=payload.include_in_progress,
        )

        md_text = (
            Path(result.markdown_path).read_text(encoding="utf-8")
            if result.markdown_path and Path(result.markdown_path).exists()
            else None
        )
        anki_text = (
            Path(result.anki_path).read_text(encoding="utf-8")
            if result.anki_path and Path(result.anki_path).exists()
            else None
        )

        return {
            "topics_exported": result.topics_exported,
            "flashcards_generated": result.flashcards_generated,
            "markdown_filename": Path(result.markdown_path).name if result.markdown_path else None,
            "anki_filename": Path(result.anki_path).name if result.anki_path else None,
            "markdown_content": md_text,
            "anki_content": anki_text,
        }

    return web_app


app = create_app()
