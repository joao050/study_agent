"""Módulo Exporter: exportação de resumos em Markdown e decks de flashcards para Anki."""

from datetime import datetime, timezone
import html
from pathlib import Path
import re
import unicodedata
from typing import List, Optional, Union
from pydantic import BaseModel, Field

from study_agent.config import get_settings
from study_agent.core.curriculum_gen import CurriculumGenerator
from study_agent.models.curriculum import Curriculum, Topic, TopicStatus
from study_agent.models.student import StudentProfile


class AnkiCard(BaseModel):
    """Representa um cartão frente/verso formatado para importação direta no Anki."""

    front: str = Field(description="Frente do cartão (pergunta ou gatilho de revisão)")
    back: str = Field(description="Verso do cartão (resposta, conceitos esperados e síntese)")
    tags: List[str] = Field(default_factory=list, description="Tags sem espaço para organização no Anki")


class ExportResult(BaseModel):
    """Resultado consolidado de uma operação de exportação de sessão/trilha."""

    markdown_path: Optional[Path] = None
    anki_path: Optional[Path] = None
    topics_exported: int = 0
    flashcards_generated: int = 0


class StudyExporter:
    """Exporta tópicos estudados para Markdown (Obsidian/GitHub) e Anki TSV (2.1.54+)."""

    VALID_FORMATS = {"both", "markdown", "md", "anki"}

    def __init__(self, base_dir: Optional[Union[str, Path]] = None) -> None:
        raw_dir = base_dir or get_settings().exports_dir
        self.base_dir = Path(raw_dir)

    @staticmethod
    def slugify(value: str) -> str:
        """Converte texto livre em slug ASCII seguro para nomes de arquivo e tags Anki."""
        normalized = unicodedata.normalize("NFKD", value or "estudo")
        ascii_only = normalized.encode("ascii", "ignore").decode("ascii").lower()
        slug = re.sub(r"[^a-z0-9]+", "_", ascii_only).strip("_")
        return slug or "estudo"

    @staticmethod
    def select_exportable_topics(
        curriculum: Curriculum,
        include_in_progress: bool = False,
    ) -> List[Topic]:
        """Filtra os tópicos elegíveis para exportação mantendo a ordem pedagógica da trilha."""
        allowed = {TopicStatus.MASTERED}
        if include_in_progress:
            allowed.add(TopicStatus.IN_PROGRESS)
        return [t for t in curriculum.topics if t.status in allowed]

    def render_markdown_summary(
        self,
        student: StudentProfile,
        curriculum: Curriculum,
        include_in_progress: bool = False,
    ) -> str:
        """Gera documento Markdown completo com frontmatter, mapa Mermaid, resumos e Active Recall."""
        topics = self.select_exportable_topics(curriculum, include_in_progress=include_in_progress)
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        progress_pct = curriculum.calculate_overall_progress()
        subject_tag = self.slugify(curriculum.subject)

        lines: List[str] = [
            "---",
            f'title: "Resumo de Estudos — {curriculum.subject}"',
            f'student: "{student.name}"',
            f'level: "{student.current_level.value} -> {student.target_level.value}"',
            f'progress: "{progress_pct}%"',
            f'exported_at: "{now_str}"',
            f"tags: [study-agent, {subject_tag}, active-recall]",
            "---",
            "",
            f"# 📚 Guia de Revisão: {curriculum.subject}",
            "",
            f"- **Estudante:** {student.name}",
            f"- **Nível:** `{student.current_level.value}` ➔ `{student.target_level.value}`",
            f"- **Progresso Geral na Trilha:** **{progress_pct}%** "
            f"({sum(1 for t in curriculum.topics if t.status == TopicStatus.MASTERED)}/{len(curriculum.topics)} tópicos dominados)",
            f"- **Gerado em:** {now_str}",
            "",
            "## 🗺️ Visão Geral & Mapa da Trilha",
            "",
            curriculum.overview,
            "",
            "```mermaid",
            CurriculumGenerator.generate_mermaid_graph(curriculum),
            "```",
            "",
            "---",
            "",
            "## 🧠 Tópicos Consolidados",
            "",
        ]

        if not topics:
            lines.append("_Nenhum tópico elegível encontrado para exportação._")
            return "\n".join(lines) + "\n"

        for idx, topic in enumerate(topics, start=1):
            status_label = "✅ Dominado" if topic.status == TopicStatus.MASTERED else "⏳ Em Estudo"
            lines.extend(
                [
                    f"### {idx}. {topic.title}",
                    "",
                    f"- **Status:** {status_label} | **Nota de Domínio:** `{topic.mastery_score:.0f}/100` "
                    f"| **Revisões:** `{topic.review_count}`"
                    + (
                        f" | **Missões de Lab:** `{topic.completed_lab_steps}`"
                        if topic.completed_lab_steps > 0
                        else ""
                    ),
                    f"- **Objetivo:** {topic.description}",
                    "",
                ]
            )

            if topic.key_takeaways:
                lines.append("#### 📌 Pontos-Chave (Key Takeaways)")
                lines.append("")
                for item in topic.key_takeaways:
                    lines.append(f"- {item}")
                lines.append("")

            if topic.recall_history:
                lines.append("#### 🎯 Revisão Ativa (Active Recall — tente responder antes de abrir!)")
                lines.append("")
                for r_idx, rec in enumerate(topic.recall_history, start=1):
                    lines.extend(
                        [
                            "<details>",
                            f"<summary><strong>Pergunta {r_idx}:</strong> {rec.question}</summary>",
                            "",
                        ]
                    )
                    if rec.expected_concepts:
                        lines.append(
                            f"- **Conceitos esperados:** {', '.join(rec.expected_concepts)}"
                        )
                    if rec.student_answer:
                        lines.append(f"- **Sua resposta registrada:** {rec.student_answer}")
                    if rec.feedback:
                        lines.append(
                            f"- **Feedback do Avaliador ({rec.score:.0f}/100):** {rec.feedback}"
                        )
                    lines.extend(["", "</details>", ""])

            lines.append("---")
            lines.append("")

        return "\n".join(lines).rstrip() + "\n"

    @staticmethod
    def _sanitize_anki_html(text: str) -> str:
        """Escapa HTML sensível e remove quebras de linha/tabs que quebrariam o TSV do Anki."""
        escaped = html.escape(text or "")
        escaped = escaped.replace("\t", " ")
        escaped = escaped.replace("\r\n", "<br>").replace("\n", "<br>")
        return escaped.strip()

    def build_anki_cards(
        self,
        curriculum: Curriculum,
        include_in_progress: bool = False,
    ) -> List[AnkiCard]:
        """Constrói cartões Anki a partir do histórico de Active Recall e dos pontos-chave."""
        topics = self.select_exportable_topics(curriculum, include_in_progress=include_in_progress)
        subject_tag = self.slugify(curriculum.subject)
        cards: List[AnkiCard] = []

        for topic in topics:
            topic_tag = self.slugify(topic.title)
            base_tags = ["study-agent", subject_tag, topic_tag]

            # 1. Cartões oriundos das perguntas reais de Active Recall respondidas na sessão
            for rec in topic.recall_history:
                front_html = (
                    f"<b>[{self._sanitize_anki_html(topic.title)}]</b><br><br>"
                    f"{self._sanitize_anki_html(rec.question)}"
                )
                back_parts: List[str] = []
                if rec.expected_concepts:
                    items = "".join(
                        f"<li>{self._sanitize_anki_html(c)}</li>" for c in rec.expected_concepts
                    )
                    back_parts.append(f"<b>Conceitos-chave:</b><ul>{items}</ul>")
                if rec.feedback:
                    back_parts.append(
                        f"<b>Síntese Pedagógica:</b> {self._sanitize_anki_html(rec.feedback)}"
                    )
                if rec.student_answer:
                    back_parts.append(
                        f"<br><i>Sua resposta ({rec.score:.0f}/100):</i> "
                        f"{self._sanitize_anki_html(rec.student_answer)}"
                    )

                back_html = "<br>".join(back_parts) or self._sanitize_anki_html(topic.description)
                cards.append(
                    AnkiCard(
                        front=front_html,
                        back=back_html,
                        tags=base_tags + ["active-recall"],
                    )
                )

            # 2. Cartão-síntese dos Key Takeaways do tópico (garante revisão mesmo sem recall_history prévio)
            if topic.key_takeaways:
                front_summary = (
                    f"<b>[{self._sanitize_anki_html(topic.title)}]</b><br><br>"
                    f"Quais são os <b>{len(topic.key_takeaways)} pontos-chave</b> essenciais sobre "
                    f"<i>{self._sanitize_anki_html(topic.title)}</i>?"
                )
                bullets = "".join(
                    f"<li>{self._sanitize_anki_html(item)}</li>" for item in topic.key_takeaways
                )
                back_summary = (
                    f"<b>Objetivo:</b> {self._sanitize_anki_html(topic.description)}<br><br>"
                    f"<b>Pontos-chave:</b><ul>{bullets}</ul>"
                )
                cards.append(
                    AnkiCard(
                        front=front_summary,
                        back=back_summary,
                        tags=base_tags + ["key-takeaways"],
                    )
                )
            elif not topic.recall_history:
                # Fallback caso o tópico não tenha nem recall_history nem key_takeaways
                cards.append(
                    AnkiCard(
                        front=(
                            f"<b>[{self._sanitize_anki_html(topic.title)}]</b><br><br>"
                            f"Explique o conceito central e objetivo de: "
                            f"<i>{self._sanitize_anki_html(topic.title)}</i>."
                        ),
                        back=self._sanitize_anki_html(topic.description),
                        tags=base_tags + ["conceito"],
                    )
                )

        return cards

    def render_anki_deck(
        self,
        curriculum: Curriculum,
        include_in_progress: bool = False,
    ) -> str:
        """Renderiza arquivo TSV com cabeçalhos oficiais do Anki 2.1.54+ pronto para importação."""
        cards = self.build_anki_cards(curriculum, include_in_progress=include_in_progress)
        clean_deck_subject = curriculum.subject.replace("\t", " ").replace("\n", " ").strip()

        lines = [
            "#separator:tab",
            "#html:true",
            f"#deck:AI Study Agent::{clean_deck_subject}",
            "#tags column:3",
        ]

        for card in cards:
            tags_str = " ".join(card.tags)
            lines.append(f"{card.front}\t{card.back}\t{tags_str}")

        return "\n".join(lines) + "\n"

    def export_session(
        self,
        student: StudentProfile,
        curriculum: Curriculum,
        output_dir: Optional[Union[str, Path]] = None,
        fmt: str = "both",
        include_in_progress: bool = False,
    ) -> ExportResult:
        """Grava em disco os arquivos de resumo Markdown e/ou deck Anki solicitados."""
        normalized_fmt = fmt.strip().lower()
        if normalized_fmt not in self.VALID_FORMATS:
            raise ValueError(
                f"Formato inválido '{fmt}'. Use 'both', 'markdown' ou 'anki'."
            )

        topics = self.select_exportable_topics(curriculum, include_in_progress=include_in_progress)
        if not topics:
            raise ValueError("Não há tópicos elegíveis para exportação nesta trilha.")

        target_dir = Path(output_dir) if output_dir else self.base_dir
        target_dir.mkdir(parents=True, exist_ok=True)

        subject_slug = self.slugify(curriculum.subject)
        student_slug = self.slugify(student.name)
        file_prefix = f"{student_slug}_{subject_slug}"

        md_path: Optional[Path] = None
        anki_path: Optional[Path] = None
        cards_count = 0

        if normalized_fmt in ("both", "markdown", "md"):
            md_content = self.render_markdown_summary(
                student=student,
                curriculum=curriculum,
                include_in_progress=include_in_progress,
            )
            md_path = target_dir / f"resumo_{file_prefix}.md"
            md_path.write_text(md_content, encoding="utf-8")

        if normalized_fmt in ("both", "anki"):
            cards = self.build_anki_cards(
                curriculum=curriculum,
                include_in_progress=include_in_progress,
            )
            cards_count = len(cards)
            anki_content = self.render_anki_deck(
                curriculum=curriculum,
                include_in_progress=include_in_progress,
            )
            anki_path = target_dir / f"anki_{file_prefix}.txt"
            anki_path.write_text(anki_content, encoding="utf-8")

        return ExportResult(
            markdown_path=md_path,
            anki_path=anki_path,
            topics_exported=len(topics),
            flashcards_generated=cards_count,
        )
