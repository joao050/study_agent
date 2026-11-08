"""Módulo Diagnosticador: responsável pelo nivelamento pedagógico inicial do estudante."""

from typing import List, Optional
from pydantic import BaseModel, Field

from study_agent.core.llm_client import LLMClient
from study_agent.models.student import (
    DiagnosticAnswer,
    DiagnosticQuestion,
    KnowledgeLevel,
)


class DiagnosticQuestionsContainer(BaseModel):
    """Container para geração estruturada da lista de perguntas de diagnóstico."""

    questions: List[DiagnosticQuestion] = Field(
        description="Lista ordenada de perguntas de sondagem diagnóstica"
    )


class SingleEvaluationItem(BaseModel):
    """Avaliação de uma única questão retornada pelo LLM."""

    question_id: str
    assessed_level: KnowledgeLevel
    feedback: str = Field(description="Comentário didático pontuando acertos e lacunas")
    score: float = Field(ge=0.0, le=100.0, description="Nota atribuída de 0 a 100")


class DiagnosticEvaluationPayload(BaseModel):
    """Payload estruturado retornado pelo LLM ao avaliar todas as respostas do aluno."""

    evaluations: List[SingleEvaluationItem] = Field(
        description="Avaliações individuais de cada resposta"
    )
    summary_feedback: str = Field(
        description="Síntese pedagógica geral sobre o estágio atual do aluno"
    )
    strengths: List[str] = Field(
        default_factory=list, description="Lista de conceitos bem dominados pelo estudante"
    )
    learning_gaps: List[str] = Field(
        default_factory=list, description="Conceitos ou lacunas prioritárias a serem trabalhadas"
    )


class DiagnosticReport(BaseModel):
    """Relatório consolidado e pronto para consumo pelo perfil do aluno e gerador de currículo."""

    target_subject: str
    assessed_level: KnowledgeLevel
    overall_score: float = Field(ge=0.0, le=100.0)
    answers: List[DiagnosticAnswer]
    summary_feedback: str
    strengths: List[str] = Field(default_factory=list)
    learning_gaps: List[str] = Field(default_factory=list)


class Diagnostician:
    """Coordenador pedagógico para diagnóstico e nivelamento de conhecimento."""

    SYSTEM_QUESTION_PROMPT = (
        "Você é um tutor pedagógico e especialista em ensino adaptativo. "
        "Sua missão é criar perguntas de nivelamento para descobrir o ponto de partida ideal de um estudante. "
        "Crie perguntas progressivas de sondagem: desde conceitos fundamentais (beginner) "
        "até aplicação prática (intermediate) e cenários mais profundos/arquitetura (advanced). "
        "As perguntas devem ser abertas, instigantes e específicas sobre o assunto alvo."
    )

    SYSTEM_EVALUATION_PROMPT = (
        "Você é um avaliador pedagógico paciente, acolhedor e didático. "
        "Seu papel é analisar as respostas fornecidas pelo aluno em um teste de diagnóstico. "
        "Avalie a maturidade conceitual, raciocínio e domínio técnico demonstrados em cada resposta. "
        "Se o aluno responder 'não sei', 'nunca vi' ou deixar incompleta, trate isso com naturalidade e acolhimento, "
        "atribuindo score condizente (ex: 0 a 20, nível beginner) e indicando que isso é o ponto ideal para aprender. "
        "Para cada resposta, forneça uma nota de 0 a 100, nível (beginner, intermediate ou advanced) e feedback didático."
    )

    def __init__(self, llm_client: Optional[LLMClient] = None) -> None:
        self.llm_client = llm_client or LLMClient()

    def generate_questions(
        self, target_subject: str, count: int = 3
    ) -> List[DiagnosticQuestion]:
        """Gera uma lista balanceada e progressiva de perguntas de nivelamento."""
        if not target_subject or not target_subject.strip():
            raise ValueError("O assunto alvo (target_subject) não pode ser vazio.")

        if count < 1:
            raise ValueError("A quantidade de perguntas deve ser de no mínimo 1.")

        prompt = (
            f"Assunto a ser diagnosticado: '{target_subject}'.\n"
            f"Gere exatamente {count} perguntas de nivelamento progressivas:\n"
            f"- A 1ª pergunta deve focar em conceitos fundamentais (beginner).\n"
            f"- As intermediárias devem testar aplicação prática e resolução de problemas (intermediate).\n"
            f"- A última deve sondar tópicos avançados, boas práticas ou arquitetura (advanced).\n"
            f"Para cada questão, preencha id, question, topic_focus e difficulty."
        )

        result = self.llm_client.generate_structured(
            prompt=prompt,
            response_model=DiagnosticQuestionsContainer,
            system_prompt=self.SYSTEM_QUESTION_PROMPT,
            temperature=0.2,
        )

        return result.questions[:count]

    def evaluate_answers(
        self,
        target_subject: str,
        questions: List[DiagnosticQuestion],
        student_answers: List[str],
    ) -> DiagnosticReport:
        """Avalia as respostas do aluno contra as perguntas diagnósticas e emite o relatório."""
        if not questions:
            raise ValueError("A lista de perguntas não pode estar vazia.")

        if len(questions) != len(student_answers):
            raise ValueError(
                f"O número de respostas ({len(student_answers)}) difere do número de perguntas ({len(questions)})."
            )

        # Monta o contexto da avaliação
        qa_pairs_text = []
        for idx, (q, ans) in enumerate(zip(questions, student_answers), start=1):
            qa_pairs_text.append(
                f"Questão {idx} [ID: {q.id}] (Foco: {q.topic_focus}, Nível Esperado: {q.difficulty.value}):\n"
                f"Enunciado: {q.question}\n"
                f"Resposta do Estudante: {ans.strip() or '[Sem resposta fornecida]'}\n"
            )

        prompt = (
            f"Assunto avaliado: '{target_subject}'.\n\n"
            f"Avalie as respostas a seguir:\n\n"
            + "\n".join(qa_pairs_text)
            + "\nPara cada uma das questões acima, gere uma avaliação correspondente contendo "
            f"question_id, assessed_level, feedback e score (0 a 100). "
            f"Identifique também os pontos fortes (strengths), lacunas de aprendizagem (learning_gaps) "
            f"e uma síntese geral pedagógica (summary_feedback)."
        )

        payload = self.llm_client.generate_structured(
            prompt=prompt,
            response_model=DiagnosticEvaluationPayload,
            system_prompt=self.SYSTEM_EVALUATION_PROMPT,
            temperature=0.1,
        )

        # Mapeia avaliações individuais garantindo integridade
        eval_dict = {item.question_id: item for item in payload.evaluations}
        final_answers: List[DiagnosticAnswer] = []

        for q, ans in zip(questions, student_answers):
            if q.id in eval_dict:
                item = eval_dict[q.id]
                final_answers.append(
                    DiagnosticAnswer(
                        question_id=q.id,
                        student_answer=ans,
                        assessed_level=item.assessed_level,
                        feedback=item.feedback,
                        score=item.score,
                    )
                )
            else:
                # Fallback de segurança se o LLM omitir algum ID
                final_answers.append(
                    DiagnosticAnswer(
                        question_id=q.id,
                        student_answer=ans,
                        assessed_level=KnowledgeLevel.BEGINNER,
                        feedback="Resposta avaliada com nível introdutório.",
                        score=50.0 if ans.strip() else 0.0,
                    )
                )

        overall_score = (
            sum(a.score for a in final_answers) / len(final_answers) if final_answers else 0.0
        )
        assessed_level = self.calculate_level(final_answers)

        return DiagnosticReport(
            target_subject=target_subject,
            assessed_level=assessed_level,
            overall_score=round(overall_score, 2),
            answers=final_answers,
            summary_feedback=payload.summary_feedback,
            strengths=payload.strengths,
            learning_gaps=payload.learning_gaps,
        )

    @staticmethod
    def calculate_level(answers: List[DiagnosticAnswer]) -> KnowledgeLevel:
        """Determina o nível consolidado do aluno baseado na média e consistência das notas.

        Regra pedagógica de pontuação:
        - Média < 50.0: BEGINNER (Necessita construir base e fundamentos essenciais)
        - 50.0 <= Média < 80.0: INTERMEDIATE (Já compreende o básico, pronto para aplicar e consolidar)
        - Média >= 80.0: ADVANCED (Domínio maduro, pronto para tópicos avançados e arquitetura)
        """
        if not answers:
            return KnowledgeLevel.BEGINNER

        avg_score = sum(a.score for a in answers) / len(answers)

        if avg_score >= 80.0:
            return KnowledgeLevel.ADVANCED
        elif avg_score >= 50.0:
            return KnowledgeLevel.INTERMEDIATE
        else:
            return KnowledgeLevel.BEGINNER
