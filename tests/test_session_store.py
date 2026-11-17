"""Testes unitários para a camada de armazenamento (storage/session_store.py)."""

from pathlib import Path
import pytest

from study_agent.models.curriculum import Curriculum, Topic, TopicStatus
from study_agent.models.student import KnowledgeLevel, StudentProfile, StudyPace
from study_agent.storage.session_store import SessionStore, SessionStoreError


@pytest.fixture
def store(tmp_path: Path) -> SessionStore:
    """Fixture que provê um SessionStore isolado em diretório temporário."""
    return SessionStore(base_dir=tmp_path)


@pytest.fixture
def sample_student() -> StudentProfile:
    """Fixture de perfil de estudante padrão."""
    return StudentProfile(
        id="student_123",
        name="Mariana",
        target_subject="FastAPI com Pydantic",
        current_level=KnowledgeLevel.BEGINNER,
        target_level=KnowledgeLevel.ADVANCED,
        pace=StudyPace.REGULAR,
    )


@pytest.fixture
def sample_curriculum(sample_student: StudentProfile) -> Curriculum:
    """Fixture de currículo padrão vinculado ao estudante."""
    return Curriculum(
        id="curr_456",
        student_id=sample_student.id,
        subject="FastAPI com Pydantic",
        overview="Trilha completa de APIs rápidas.",
        topics=[
            Topic(
                id="t1",
                title="Fundamentos",
                description="Conceitos base",
                estimated_minutes=30,
                status=TopicStatus.AVAILABLE,
            ),
            Topic(
                id="t2",
                title="Validação",
                description="Pydantic Schemas",
                estimated_minutes=45,
                status=TopicStatus.LOCKED,
                prerequisites=["t1"],
            ),
        ],
    )


def test_ensure_directories(tmp_path: Path):
    """Verifica se as pastas de persistência são criadas na inicialização."""
    store = SessionStore(base_dir=tmp_path / "custom_data")
    assert store.base_dir.exists()
    assert store.profiles_dir.exists()
    assert store.curricula_dir.exists()


def test_save_and_load_student(store: SessionStore, sample_student: StudentProfile):
    """Testa salvar e recuperar um estudante com integridade dos dados."""
    file_path = store.save_student(sample_student)
    assert file_path.exists()
    assert file_path.name == f"{sample_student.id}.json"

    loaded = store.load_student(sample_student.id)
    assert loaded is not None
    assert loaded.id == sample_student.id
    assert loaded.name == "Mariana"
    assert loaded.target_subject == "FastAPI com Pydantic"
    assert loaded.current_level == KnowledgeLevel.BEGINNER


def test_load_non_existent_student(store: SessionStore):
    """Garante que carregar estudante inexistente retorna None."""
    assert store.load_student("fantasma_999") is None


def test_save_student_without_id(store: SessionStore):
    """Garante validação para perfil sem id."""
    invalid = StudentProfile(id="", name="Sem ID", target_subject="Python")
    with pytest.raises(ValueError, match="id"):
        store.save_student(invalid)


def test_list_students_ordered(store: SessionStore):
    """Testa listagem de estudantes ordenados por data de atualização recente."""
    s1 = StudentProfile(id="s1", name="Aluno 1", target_subject="Python")
    s2 = StudentProfile(id="s2", name="Aluno 2", target_subject="Docker")

    store.save_student(s1)
    store.save_student(s2)

    students = store.list_students()
    assert len(students) == 2
    # O último salvo (s2) tem updated_at mais recente
    assert students[0].id == "s2"
    assert students[1].id == "s1"


def test_save_and_load_curriculum(store: SessionStore, sample_curriculum: Curriculum):
    """Testa persistência e recuperação de trilha curricular com tópicos."""
    file_path = store.save_curriculum(sample_curriculum)
    assert file_path.exists()

    loaded = store.load_curriculum(sample_curriculum.id)
    assert loaded is not None
    assert loaded.id == sample_curriculum.id
    assert loaded.student_id == sample_curriculum.student_id
    assert len(loaded.topics) == 2
    assert loaded.topics[0].id == "t1"
    assert loaded.topics[0].status == TopicStatus.AVAILABLE
    assert loaded.topics[1].prerequisites == ["t1"]


def test_load_curriculum_by_student(
    store: SessionStore, sample_student: StudentProfile, sample_curriculum: Curriculum
):
    """Testa busca do currículo mais recente associado a um estudante."""
    store.save_student(sample_student)
    store.save_curriculum(sample_curriculum)

    curr = store.load_curriculum_by_student(sample_student.id)
    assert curr is not None
    assert curr.id == sample_curriculum.id
    assert curr.student_id == sample_student.id


def test_list_curricula_for_student(store: SessionStore, sample_student: StudentProfile):
    """Testa listagem de múltiplos currículos de um mesmo estudante."""
    c1 = Curriculum(id="c1", student_id=sample_student.id, subject="Sub 1", overview="O1")
    c2 = Curriculum(id="c2", student_id=sample_student.id, subject="Sub 2", overview="O2")

    store.save_curriculum(c1)
    store.save_curriculum(c2)

    curricula = store.list_curricula_for_student(sample_student.id)
    assert len(curricula) == 2
    assert curricula[0].id == "c2"


def test_load_non_existent_curriculum(store: SessionStore):
    """Retorna None ao buscar currículo inexistente."""
    assert store.load_curriculum("curr_inexistente") is None


def test_current_session_flow(
    store: SessionStore, sample_student: StudentProfile, sample_curriculum: Curriculum
):
    """Testa fluxo completo de marcação e leitura da sessão ativa."""
    # Antes de configurar
    assert store.get_current_session() is None
    s, c = store.load_active_session()
    assert s is None and c is None

    # Salva dados
    store.save_student(sample_student)
    store.save_curriculum(sample_curriculum)
    store.set_current_session(sample_student.id, sample_curriculum.id)

    # Verifica ponteiro
    current = store.get_current_session()
    assert current == (sample_student.id, sample_curriculum.id)

    # Carrega diretamente
    active_student, active_curr = store.load_active_session()
    assert active_student is not None and active_student.id == sample_student.id
    assert active_curr is not None and active_curr.id == sample_curriculum.id


def test_delete_student_cascade(
    store: SessionStore, sample_student: StudentProfile, sample_curriculum: Curriculum
):
    """Testa exclusão em cascata do aluno, currículos e sessão ativa."""
    store.save_student(sample_student)
    store.save_curriculum(sample_curriculum)
    store.set_current_session(sample_student.id, sample_curriculum.id)

    assert store.delete_student(sample_student.id) is True

    # Verifica se foi tudo removido
    assert store.load_student(sample_student.id) is None
    assert store.load_curriculum(sample_curriculum.id) is None
    assert store.get_current_session() is None


def test_corrupted_json_handling(store: SessionStore):
    """Garante que arquivo JSON inválido levanta SessionStoreError ao carregar."""
    corrupted_file = store.profiles_dir / "corrupted_id.json"
    corrupted_file.write_text("{json_invalido: 123", encoding="utf-8")

    with pytest.raises(SessionStoreError, match="Erro ao deserializar"):
        store.load_student("corrupted_id")
