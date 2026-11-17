"""Módulo Gerador de Trilha e Mapa Mental pedagógico (core/curriculum_gen.py)."""

from typing import List, Optional
from pydantic import BaseModel, Field

from study_agent.core.diagnostician import DiagnosticReport
from study_agent.core.llm_client import LLMClient
from study_agent.models.curriculum import Curriculum, Topic, TopicStatus
from study_agent.models.student import KnowledgeLevel, StudentProfile, StudyPace


class CurriculumGenerationPayload(BaseModel):
    """Payload estruturado retornado pelo LLM para construção da trilha."""

    overview: str = Field(
        description="Visão panorâmica e narrativa pedagógica da jornada de estudos planejada"
    )
    topics: List[Topic] = Field(
        description="Lista ordenada e encadeada de tópicos de estudo da trilha"
    )


class CurriculumGenerator:
    """Planejador pedagógico responsável pela árvore de tópicos e mapa mental."""

    SYSTEM_PROMPT = (
        "Você é um arquiteto pedagógico sênior especializado em aprendizado acelerado e adaptativo. "
        "Sua responsabilidade é desenhar uma trilha de estudos personalizada (Curriculum), "
        "composta por uma sequência lógica e atômica de tópicos (Topic). "
        "Cada tópico deve possuir:\n"
        "- id único, conciso e legível (ex: 'topico_01', 'topico_02');\n"
        "- título claro e direto;\n"
        "- descrição concisa dos conceitos e habilidades práticas cobertas;\n"
        "- estimated_minutes condizente com a complexidade do tópico e ritmo do aluno;\n"
        "- prerequisites contendo a lista de IDs de tópicos anteriores obrigatórios "
        "(o 1º tópico deve ter lista de pré-requisitos vazia, e nenhum tópico pode ter ciclo de dependência).\n"
        "A trilha deve respeitar rigorosamente o nível de partida e lacunas do estudante, "
        "construindo uma ponte sólida até o nível pretendido."
    )

    def __init__(self, llm_client: Optional[LLMClient] = None) -> None:
        self.llm_client = llm_client or LLMClient()

    def generate(
        self,
        student_profile: StudentProfile,
        diagnostic_report: Optional[DiagnosticReport] = None,
        target_topic_count: Optional[int] = None,
    ) -> Curriculum:
        """Gera uma trilha customizada com base no perfil do aluno e diagnóstico inicial."""
        if not student_profile.target_subject or not student_profile.target_subject.strip():
            raise ValueError("O perfil do estudante precisa ter um target_subject válido.")

        # Determina a contagem recomendada de tópicos conforme o ritmo de estudo
        count = target_topic_count or self._resolve_topic_count(student_profile.pace)

        # Monta prompt contextualizado com nível atual, metas e diagnóstico
        prompt = self._build_prompt(
            student_profile=student_profile,
            diagnostic_report=diagnostic_report,
            topic_count=count,
        )

        payload = self.llm_client.generate_structured(
            prompt=prompt,
            response_model=CurriculumGenerationPayload,
            system_prompt=self.SYSTEM_PROMPT,
            temperature=0.2,
        )

        # Higieniza e valida as dependências dos tópicos gerados
        sanitized_topics = self._sanitize_and_validate_topics(payload.topics)

        curriculum = Curriculum(
            student_id=student_profile.id,
            subject=student_profile.target_subject,
            overview=payload.overview,
            topics=sanitized_topics,
        )

        # Destrava os tópicos raiz (sem pré-requisitos) para estado AVAILABLE
        curriculum.update_topic_statuses()

        return curriculum

    def _resolve_topic_count(self, pace: StudyPace) -> int:
        """Define o volume inicial de tópicos sugerido conforme o ritmo."""
        if pace == StudyPace.RELAXED:
            return 5
        elif pace == StudyPace.INTENSIVE:
            return 10
        return 7  # REGULAR

    def _build_prompt(
        self,
        student_profile: StudentProfile,
        diagnostic_report: Optional[DiagnosticReport],
        topic_count: int,
    ) -> str:
        """Constrói o prompt enriquecido com dados de perfil e gaps diagnósticos."""
        lines = [
            f"Assunto da Trilha: '{student_profile.target_subject}'",
            f"Nível Atual do Aluno: {student_profile.current_level.value.upper()}",
            f"Nível Pretendido: {student_profile.target_level.value.upper()}",
            f"Ritmo de Estudo: {student_profile.pace.value} ({student_profile.daily_available_minutes} min/dia)",
            f"Quantidade ideal de tópicos atômicos: aproximadamente {topic_count} tópicos.",
        ]

        if diagnostic_report:
            lines.append("\nDados do Diagnóstico Pedagógico:")
            lines.append(f"- Score de partida: {diagnostic_report.overall_score}/100")
            lines.append(f"- Síntese: {diagnostic_report.summary_feedback}")
            if diagnostic_report.strengths:
                lines.append(f"- Pontos Fortes já dominados: {', '.join(diagnostic_report.strengths)}")
            if diagnostic_report.learning_gaps:
                lines.append(
                    f"- Lacunas prioritárias a abordar: {', '.join(diagnostic_report.learning_gaps)}"
                )

        lines.append(
            "\nDiretrizes de montagem da trilha:\n"
            "1. Comece no nível real do estudante (se for avançado, não repita fundamentos básicos; "
            "se for iniciante, construa alicerces firmes).\n"
            "2. Aborde prioritariamente as lacunas apontadas no diagnóstico.\n"
            "3. Garanta encadeamento sequencial através do campo 'prerequisites'. O primeiro tópico NÃO deve ter pré-requisito."
        )

        return "\n".join(lines)

    @staticmethod
    def _sanitize_and_validate_topics(topics: List[Topic]) -> List[Topic]:
        """Garante IDs únicos, remove pré-requisitos fantasmas e impede ciclos simples."""
        if not topics:
            raise ValueError("O LLM não retornou nenhum tópico para a trilha.")

        seen_ids = set()
        sanitized: List[Topic] = []

        for idx, t in enumerate(topics, start=1):
            clean_id = (t.id or f"topico_{idx:02d}").strip()
            # Garante unicidade de ID
            if clean_id in seen_ids:
                clean_id = f"{clean_id}_{idx}"
            t.id = clean_id
            seen_ids.add(clean_id)

            # Filtra pré-requisitos válidos (apenas IDs de tópicos que já apareceram antes)
            # Evita referências circulares e pré-requisitos que apontam para frente
            valid_prereqs = [
                p.strip()
                for p in t.prerequisites
                if p.strip() and p.strip() in seen_ids and p.strip() != clean_id
            ]
            t.prerequisites = valid_prereqs
            t.status = TopicStatus.LOCKED  # Status inicial padrão antes do update
            sanitized.append(t)

        return sanitized

    @staticmethod
    def format_ascii_tree(curriculum: Curriculum) -> str:
        """Gera uma visualização amigável em árvore/mapa mental no terminal."""
        lines = [
            f"🗺️  Trilha de Aprendizado: {curriculum.subject}",
            f"📝 {curriculum.overview}",
            f"📊 Progresso Geral: {curriculum.calculate_overall_progress()}%\n",
            "Tópicos da Trilha:",
        ]

        status_icons = {
            TopicStatus.LOCKED: "🔒 [Bloqueado]  ",
            TopicStatus.AVAILABLE: "🔓 [Disponível] ",
            TopicStatus.IN_PROGRESS: "⏳ [Em Estudo]  ",
            TopicStatus.MASTERED: "✅ [Dominado]   ",
        }

        for idx, t in enumerate(curriculum.topics, start=1):
            icon = status_icons.get(t.status, "• ")
            prereq_str = f" <- pré-req: {', '.join(t.prerequisites)}" if t.prerequisites else ""
            lines.append(
                f"  {idx:02d}. {icon} {t.title} ({t.estimated_minutes} min){prereq_str}"
            )
            lines.append(f"      └─ {t.description}")

        return "\n".join(lines)

    @staticmethod
    def generate_mermaid_graph(curriculum: Curriculum) -> str:
        """Gera código Mermaid para renderização visual em markdown ou web."""
        lines = ["flowchart TD"]

        status_styles = {
            TopicStatus.MASTERED: "fill:#d4edda,stroke:#28a745",
            TopicStatus.IN_PROGRESS: "fill:#fff3cd,stroke:#ffc107",
            TopicStatus.AVAILABLE: "fill:#cce5ff,stroke:#007bff",
            TopicStatus.LOCKED: "fill:#e2e3e5,stroke:#6c757d",
        }

        for t in curriculum.topics:
            lines.append(f'    {t.id}["{t.title}<br/>⏱️ {t.estimated_minutes}m"]')

            for prereq in t.prerequisites:
                lines.append(f"    {prereq} --> {t.id}")

            style = status_styles.get(t.status)
            if style:
                lines.append(f"    style {t.id} {style}")

        return "\n".join(lines)
