"""Módulo Teacher: responsável pelas explicações didáticas e resolução de dúvidas pedagógicas."""

from typing import List, Optional
from pydantic import BaseModel, Field

from study_agent.core.llm_client import LLMClient
from study_agent.models.curriculum import ExplanationStyle, Topic


class KeyTakeawaysPayload(BaseModel):
    """Container para extração estruturada de pontos-chave de um tópico."""

    takeaways: List[str] = Field(
        description="Lista de 3 a 5 pontos centrais e memoráveis que resumem o tópico"
    )


class Teacher:
    """Tutor didático especialista em técnicas pedagógicas (Feynman, técnica e prática)."""

    STYLE_PROMPTS = {
        ExplanationStyle.FEYNMAN: (
            "Adote a Técnica de Feynman:\n"
            "- Use analogias intuitivas do dia a dia para ilustrar o conceito central.\n"
            "- Elimine jargões desnecessários; quando usar um termo técnico, explique-o imediatamente de forma simples.\n"
            "- Foque no 'porquê' as coisas funcionam assim antes de entrar em detalhes mecânicos."
        ),
        ExplanationStyle.TECHNICAL: (
            "Adote uma abordagem Técnica e Formal:\n"
            "- Forneça definições exatas, contratos de interface e terminologia precisa.\n"
            "- Explique o funcionamento interno (sob o capô), ciclo de vida e garantias da ferramenta/linguagem.\n"
            "- Destaque arquitetura, trade-offs de desempenho e boas práticas de engenharia."
        ),
        ExplanationStyle.PRACTICAL: (
            "Adote uma abordagem Prática (Hands-on):\n"
            "- Foque em exemplos de código concisos, limpos e funcionais comentados passo a passo.\n"
            "- Demonstre casos de uso reais do mercado e resolução de problemas comuns.\n"
            "- Aponte armadilhas frequentes (gotchas) que desenvolvedores enfrentam na prática."
        ),
    }

    def __init__(self, llm_client: Optional[LLMClient] = None) -> None:
        self.llm_client = llm_client or LLMClient()

    def explain_topic(
        self,
        topic: Topic,
        style: ExplanationStyle = ExplanationStyle.FEYNMAN,
        student_context: Optional[str] = None,
    ) -> str:
        """Gera uma aula/explicação completa e formatada em Markdown sobre o tópico."""
        if not topic.title or not topic.title.strip():
            raise ValueError("O tópico precisa ter um título válido para ser explicado.")

        style_instruction = self.STYLE_PROMPTS.get(
            style, self.STYLE_PROMPTS[ExplanationStyle.FEYNMAN]
        )

        prompt_lines = [
            f"Tópico a ser ensinado: '{topic.title}'",
            f"Descrição e objetivos: {topic.description}",
            f"Tempo estimado da sessão: {topic.estimated_minutes} minutos.",
        ]

        if topic.prerequisites:
            prompt_lines.append(
                f"Pré-requisitos que o aluno já dominou: {', '.join(topic.prerequisites)}"
            )

        if student_context:
            prompt_lines.append(f"Contexto do estudante: {student_context}")

        prompt_lines.extend(
            [
                f"\nDiretriz de estilo pedagógico ({style.value.upper()}):\n{style_instruction}",
                "\nEstrutura esperada da explicação (use Markdown elegante):\n"
                "1. **Gancho/Introdução:** O que é e por que isso importa.\n"
                "2. **Desenvolvimento Principal:** Explicação clara do conceito com base no estilo escolhido.\n"
                "3. **Exemplo Ilustrativo:** Analogia ou snippet prático de código.\n"
                "4. **Resumo Rápido:** 2 ou 3 frases fechando a ideia.",
            ]
        )

        system_prompt = (
            "Você é um tutor de excelência pedagógica, paciente, didático e inspirador. "
            "Sua missão é explicar conceitos complexos de programação e tecnologia com maestria, "
            "gerando clareza mental imediata no estudante."
        )

        return self.llm_client.generate(
            prompt="\n".join(prompt_lines),
            system_prompt=system_prompt,
            temperature=0.3,
        )

    def answer_doubt(
        self,
        topic: Topic,
        student_question: str,
        previous_explanation: Optional[str] = None,
    ) -> str:
        """Responde a uma dúvida pontual do aluno contextualizada pelo tópico."""
        if not student_question or not student_question.strip():
            raise ValueError("A pergunta do estudante não pode ser vazia.")

        prompt_lines = [
            f"Tópico em estudo: '{topic.title}' ({topic.description})",
            f"Dúvida do estudante: '{student_question.strip()}'",
        ]

        if previous_explanation:
            prompt_lines.append(
                f"\nExplicação recente fornecida anteriormente:\n{previous_explanation[:1500]}..."
            )

        prompt_lines.append(
            "\nResponda diretamente à dúvida com clareza, empatia e brevidade, "
            "esclarecendo o ponto de confusão com um exemplo simples ou analogia."
        )

        system_prompt = (
            "Você é um mentor técnico auxiliando um estudante com dúvidas. "
            "Seja encorajador, responda com precisão didática e evite respostas prolixas."
        )

        return self.llm_client.generate(
            prompt="\n".join(prompt_lines),
            system_prompt=system_prompt,
            temperature=0.3,
        )

    def summarize_key_takeaways(
        self,
        topic: Topic,
        explanation: str,
    ) -> List[str]:
        """Extrai de 3 a 5 pontos-chave essenciais da aula para retenção duradoura."""
        if not explanation or not explanation.strip():
            return [topic.title]

        prompt = (
            f"Tópico: '{topic.title}'\n"
            f"Aula explicativa:\n{explanation}\n\n"
            "Com base na explicação acima, sintetize exatamente de 3 a 5 pontos-chave essenciais "
            "(bullet points concisos) que representam o núcleo do aprendizado deste tópico."
        )

        system_prompt = (
            "Você é um sintetizador pedagógico. Extraia apenas as conclusões e conceitos mais "
            "relevantes para fixação do estudante."
        )

        result = self.llm_client.generate_structured(
            prompt=prompt,
            response_model=KeyTakeawaysPayload,
            system_prompt=system_prompt,
            temperature=0.1,
        )

        return result.takeaways
