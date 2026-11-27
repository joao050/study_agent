"""Módulo Evaluator: responsável por testes de retenção ativa (Active Recall) e pontuação de domínio."""

from datetime import datetime, timedelta, timezone
from typing import List, Optional
from pydantic import BaseModel, Field

from study_agent.core.llm_client import LLMClient
from study_agent.models.curriculum import (
    ActiveRecallEvaluation,
    ActiveRecallQuestion,
    RecallRecord,
    Topic,
    TopicStatus,
)


class ActiveRecallEvaluationPayload(BaseModel):
    """Payload estruturado retornado pelo LLM para avaliação da resposta do aluno."""

    score: float = Field(
        ge=0.0,
        le=100.0,
        description="Nota pedagógica de 0 a 100 com base no domínio e precisão demonstrados",
    )
    understood_concepts: List[str] = Field(
        default_factory=list,
        description="Conceitos ou ideias que o estudante explicou corretamente",
    )
    missing_or_confused_concepts: List[str] = Field(
        default_factory=list,
        description="Conceitos centrais que faltaram ou foram explicados com imprecisão/equívoco",
    )
    feedback: str = Field(
        description="Comentário didático, acolhedor e encorajador com orientações de melhoria"
    )


class Evaluator:
    """Avaliador pedagógico focado em checagem ativa de absorção (Active Recall)."""

    PASSING_SCORE_DEFAULT = 70.0

    SYSTEM_QUESTION_PROMPT = (
        "Você é um avaliador pedagógico especialista na técnica de Active Recall (Recuperação Ativa). "
        "Sua função é formular perguntas abertas e instigantes que exijam do estudante conectar ideias, "
        "justificar decisões ou explicar mecanismos com suas próprias palavras. "
        "Evite perguntas puramente decorativas ou de 'sim/não'. "
        "Preencha a pergunta, a lista de conceitos essenciais esperados (expected_concepts) "
        "e uma dica sutil (hint) para guiar o aluno caso necessário."
    )

    SYSTEM_EVALUATION_PROMPT = (
        "Você é um avaliador criterioso, acolhedor e pedagógico. "
        "Sua missão é avaliar a resposta de um aluno em um teste de Active Recall. "
        "Compare a resposta com os conceitos esperados. "
        "Diferencie claramente o que o aluno dominou (understood_concepts) das lacunas ou confusões "
        "(missing_or_confused_concepts). "
        "Atribua uma nota justa de 0 a 100 e forneça um feedback construtivo."
    )

    def __init__(self, llm_client: Optional[LLMClient] = None) -> None:
        self.llm_client = llm_client or LLMClient()

    def generate_active_recall_question(
        self,
        topic: Topic,
        key_takeaways: Optional[List[str]] = None,
    ) -> ActiveRecallQuestion:
        """Gera uma questão aberta de reflexão e retenção baseada no tópico."""
        if not topic.title or not topic.title.strip():
            raise ValueError("O tópico precisa ter um título válido para gerar questão de avaliação.")

        prompt_lines = [
            f"Tópico em avaliação: '{topic.title}'",
            f"Descrição do tópico: {topic.description}",
        ]

        takeaways = key_takeaways or topic.key_takeaways
        if takeaways:
            prompt_lines.append(f"Pontos-chave ensinados: {'; '.join(takeaways)}")

        prompt_lines.extend(
            [
                "\nFormule uma única questão aberta de Active Recall de alto impacto.",
                "Exemplos de bom formato de questão:",
                "- 'Imagine que um desenvolvedor júnior te perguntou por que usar X em vez de Y... como você explicaria?'",
                "- 'Explique o fluxo interno do que acontece quando executamos Z, apontando onde entra X.'",
                "Preencha: question, expected_concepts (2 a 4 itens) e hint (dica curta).",
            ]
        )

        return self.llm_client.generate_structured(
            prompt="\n".join(prompt_lines),
            response_model=ActiveRecallQuestion,
            system_prompt=self.SYSTEM_QUESTION_PROMPT,
            temperature=0.2,
        )

    def evaluate_active_recall(
        self,
        question: ActiveRecallQuestion,
        student_answer: str,
        passing_score: float = PASSING_SCORE_DEFAULT,
    ) -> ActiveRecallEvaluation:
        """Avalia a resposta do aluno contra os conceitos esperados e emite a nota de domínio."""
        if not student_answer or not student_answer.strip():
            # Resposta em branco ou desistência
            return ActiveRecallEvaluation(
                question_id=question.id,
                student_answer="",
                score=0.0,
                understood_concepts=[],
                missing_or_confused_concepts=question.expected_concepts,
                feedback="Nenhuma resposta fornecida. Recomendamos revisar o material do tópico.",
                is_passing=False,
            )

        prompt_lines = [
            f"Pergunta formulada: '{question.question}'",
            f"Conceitos esperados na resposta: {'; '.join(question.expected_concepts)}",
            f"Resposta do aluno:\n'{student_answer.strip()}'\n",
            "Avalie a resposta detalhadamente:",
            "- score: Nota de 0.0 a 100.0.",
            "- understood_concepts: conceitos que o aluno demonstrou dominar.",
            "- missing_or_confused_concepts: conceitos ausentes ou que foram confundidos.",
            "- feedback: orientação didática destacando acertos e onde aprofundar.",
        ]

        payload = self.llm_client.generate_structured(
            prompt="\n".join(prompt_lines),
            response_model=ActiveRecallEvaluationPayload,
            system_prompt=self.SYSTEM_EVALUATION_PROMPT,
            temperature=0.1,
        )

        is_passing = payload.score >= passing_score

        return ActiveRecallEvaluation(
            question_id=question.id,
            student_answer=student_answer.strip(),
            score=payload.score,
            understood_concepts=payload.understood_concepts,
            missing_or_confused_concepts=payload.missing_or_confused_concepts,
            feedback=payload.feedback,
            is_passing=is_passing,
        )

    def update_topic_mastery(
        self,
        topic: Topic,
        evaluation: ActiveRecallEvaluation,
        passing_score: float = PASSING_SCORE_DEFAULT,
        question: Optional[ActiveRecallQuestion] = None,
    ) -> Topic:
        """Atualiza o estado de domínio, nota e histórico de revisões do tópico."""
        now = datetime.now(timezone.utc)
        topic.review_count += 1
        topic.last_reviewed_at = now

        if question is not None:
            topic.recall_history.append(
                RecallRecord(
                    question=question.question,
                    student_answer=evaluation.student_answer,
                    expected_concepts=list(question.expected_concepts),
                    feedback=evaluation.feedback,
                    score=evaluation.score,
                    recorded_at=now,
                )
            )

        if evaluation.is_passing or evaluation.score >= passing_score:
            topic.status = TopicStatus.MASTERED
            # Agenda a 1ª revisão espaçada (+1 dia) caso ainda não possua agendamento SRS
            if topic.next_review_at is None:
                topic.interval_days = 1
                topic.next_review_at = now + timedelta(days=1)
            # Se já tinha nota anterior, calcula média ponderada favorecendo o resultado recente
            if topic.mastery_score > 0:
                topic.mastery_score = round((topic.mastery_score * 0.3) + (evaluation.score * 0.7), 2)
            else:
                topic.mastery_score = evaluation.score
        else:
            # Se não atingiu nota de corte e ainda não era MASTERED, marca como IN_PROGRESS
            if topic.status != TopicStatus.MASTERED:
                topic.status = TopicStatus.IN_PROGRESS
                topic.mastery_score = max(topic.mastery_score, evaluation.score)

        return topic
