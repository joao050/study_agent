"""Módulo de persistência local em JSON (storage/session_store.py)."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple, Union

from study_agent.config import get_settings
from study_agent.models.curriculum import Curriculum
from study_agent.models.student import StudentProfile


class SessionStoreError(Exception):
    """Exceção base para falhas de persistência e leitura de dados."""

    pass


class SessionNotFoundError(SessionStoreError):
    """Exceção levantada quando uma sessão, perfil ou currículo não é encontrado."""

    pass


class SessionStore:
    """Gerenciador de persistência local em disco usando arquivos JSON."""

    def __init__(self, base_dir: Optional[Union[str, Path]] = None) -> None:
        raw_dir = base_dir or get_settings().data_dir
        self.base_dir = Path(raw_dir)
        self.profiles_dir = self.base_dir / "profiles"
        self.curricula_dir = self.base_dir / "curricula"
        self.current_session_file = self.base_dir / "current_session.json"
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        """Cria a estrutura de pastas necessária caso não exista."""
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.profiles_dir.mkdir(parents=True, exist_ok=True)
        self.curricula_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _atomic_write(target_path: Path, content: str) -> None:
        """Escreve o conteúdo de forma atômica para prevenir corrupção em caso de interrupção."""
        temp_path = target_path.with_suffix(".tmp")
        try:
            temp_path.write_text(content, encoding="utf-8")
            temp_path.replace(target_path)
        except Exception as exc:
            if temp_path.exists():
                temp_path.unlink()
            raise SessionStoreError(f"Falha ao gravar arquivo em '{target_path}': {exc}") from exc

    def save_student(self, student: StudentProfile) -> Path:
        """Salva ou atualiza os dados de um estudante em disco."""
        if not student.id:
            raise ValueError("O perfil do estudante precisa possuir um 'id' válido.")

        student.updated_at = datetime.now(timezone.utc)
        file_path = self.profiles_dir / f"{student.id}.json"
        json_content = student.model_dump_json(indent=2)
        self._atomic_write(file_path, json_content)
        return file_path

    def load_student(self, student_id: str) -> Optional[StudentProfile]:
        """Carrega o perfil de um estudante pelo ID."""
        file_path = self.profiles_dir / f"{student_id}.json"
        if not file_path.exists():
            return None

        try:
            raw_json = file_path.read_text(encoding="utf-8")
            return StudentProfile.model_validate_json(raw_json)
        except Exception as exc:
            raise SessionStoreError(
                f"Erro ao deserializar perfil do estudante '{student_id}': {exc}"
            ) from exc

    def list_students(self) -> List[StudentProfile]:
        """Lista todos os estudantes salvos, ordenados por última atualização (mais recente primeiro)."""
        students: List[StudentProfile] = []
        for file_path in self.profiles_dir.glob("*.json"):
            try:
                raw_json = file_path.read_text(encoding="utf-8")
                students.append(StudentProfile.model_validate_json(raw_json))
            except Exception:
                continue

        students.sort(key=lambda s: s.updated_at, reverse=True)
        return students

    def save_curriculum(self, curriculum: Curriculum) -> Path:
        """Salva ou atualiza uma trilha curricular em disco."""
        if not curriculum.id or not curriculum.student_id:
            raise ValueError("O currículo deve ter 'id' e 'student_id' preenchidos.")

        curriculum.updated_at = datetime.now(timezone.utc)
        file_path = self.curricula_dir / f"{curriculum.student_id}_{curriculum.id}.json"
        json_content = curriculum.model_dump_json(indent=2)
        self._atomic_write(file_path, json_content)
        return file_path

    def load_curriculum(self, curriculum_id: str) -> Optional[Curriculum]:
        """Carrega um currículo pelo seu ID."""
        matching_files = list(self.curricula_dir.glob(f"*_{curriculum_id}.json"))
        if not matching_files:
            return None

        file_path = matching_files[0]
        try:
            raw_json = file_path.read_text(encoding="utf-8")
            return Curriculum.model_validate_json(raw_json)
        except Exception as exc:
            raise SessionStoreError(
                f"Erro ao deserializar currículo '{curriculum_id}': {exc}"
            ) from exc

    def list_curricula_for_student(self, student_id: str) -> List[Curriculum]:
        """Lista todos os currículos de um estudante específico, ordenados por atualização recente."""
        curricula: List[Curriculum] = []
        for file_path in self.curricula_dir.glob(f"{student_id}_*.json"):
            try:
                raw_json = file_path.read_text(encoding="utf-8")
                curricula.append(Curriculum.model_validate_json(raw_json))
            except Exception:
                continue

        curricula.sort(key=lambda c: c.updated_at, reverse=True)
        return curricula

    def load_curriculum_by_student(self, student_id: str) -> Optional[Curriculum]:
        """Recupera o currículo mais recente associado a um estudante."""
        curricula = self.list_curricula_for_student(student_id)
        return curricula[0] if curricula else None

    def set_current_session(self, student_id: str, curriculum_id: str) -> None:
        """Define o ponteiro da sessão ativa atual (último estudante e trilha manipulados)."""
        payload = {
            "student_id": student_id,
            "curriculum_id": curriculum_id,
            "saved_at": datetime.now(timezone.utc).isoformat(),
        }
        self._atomic_write(self.current_session_file, json.dumps(payload, indent=2))

    def get_current_session(self) -> Optional[Tuple[str, str]]:
        """Recupera os identificadores da sessão ativa (student_id, curriculum_id)."""
        if not self.current_session_file.exists():
            return None

        try:
            data = json.loads(self.current_session_file.read_text(encoding="utf-8"))
            student_id = data.get("student_id")
            curriculum_id = data.get("curriculum_id")
            if student_id and curriculum_id:
                return student_id, curriculum_id
            return None
        except Exception:
            return None

    def load_active_session(self) -> Tuple[Optional[StudentProfile], Optional[Curriculum]]:
        """Carrega diretamente os objetos da sessão ativa (estudante e trilha)."""
        session_info = self.get_current_session()
        if not session_info:
            return None, None

        student_id, curriculum_id = session_info
        student = self.load_student(student_id)
        curriculum = self.load_curriculum(curriculum_id)
        return student, curriculum

    def delete_student(self, student_id: str) -> bool:
        """Exclui o perfil do aluno e todas as suas trilhas associadas."""
        student_file = self.profiles_dir / f"{student_id}.json"
        existed = False

        if student_file.exists():
            student_file.unlink()
            existed = True

        for curriculum_file in self.curricula_dir.glob(f"{student_id}_*.json"):
            curriculum_file.unlink()

        # Limpa o ponteiro de sessão se for o aluno ativo
        current = self.get_current_session()
        if current and current[0] == student_id and self.current_session_file.exists():
            self.current_session_file.unlink()

        return existed
