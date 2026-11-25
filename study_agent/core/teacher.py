"""Módulo Teacher: explicações didáticas, laboratório guiado e assistente de debugging."""

import platform
from typing import List, Optional
from pydantic import BaseModel, Field

from study_agent.core.llm_client import LLMClient
from study_agent.models.curriculum import (
    ErrorDebugResolution,
    ExplanationStyle,
    GuidedLab,
    LabMission,
    Topic,
)
from study_agent.models.student import StudentProfile


class KeyTakeawaysPayload(BaseModel):
    """Container para extração estruturada de pontos-chave de um tópico."""

    takeaways: List[str] = Field(
        description="Lista de 3 a 5 pontos centrais e memoráveis que resumem o tópico"
    )


class GuidedLabPayload(BaseModel):
    """Container de saída estruturada para geração de roteiro de laboratório guiado."""

    intro_brief: str = Field(
        description="Resumo conceitual curto (1 a 2 parágrafos) preparando o terreno antes da prática"
    )
    prerequisites_check: Optional[str] = Field(
        default=None,
        description="Comando ou verificação rápida de pré-condição de ambiente",
    )
    missions: List[LabMission] = Field(
        min_length=1,
        description="Lista sequencial de missões práticas com checkpoints claros",
    )


class Teacher:
    """Tutor didático especialista em técnicas pedagógicas (Feynman, técnica, prática e laboratório)."""

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
        ExplanationStyle.GUIDED_LAB: (
            "Adote o Modo Laboratório Guiado (Scaffolding Passo a Passo):\n"
            "- Introduza o conceito de forma enxuta e divida o aprendizado em pequenas missões executáveis.\n"
            "- Para cada passo, mostre o comando/código exato e o resultado esperado para validação.\n"
            "- Antecipe possíveis erros de ambiente e explique como conferi-los."
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

    def generate_guided_lab(
        self,
        topic: Topic,
        student: Optional[StudentProfile] = None,
        mission_count: int = 3,
        os_context: Optional[str] = None,
    ) -> GuidedLab:
        """Gera um roteiro de laboratório prático passo a passo (scaffolding com checkpoints)."""
        if not topic.title or not topic.title.strip():
            raise ValueError("O tópico precisa ter um título válido para gerar o laboratório.")

        clamped_count = max(2, min(mission_count, 5))
        detected_os = os_context or platform.system() or "Multiplataforma"

        prompt_lines = [
            f"Tópico do laboratório prático: '{topic.title}'",
            f"Objetivo de aprendizado: {topic.description}",
            f"Sistema operacional / ambiente do aluno: {detected_os}",
            f"Quantidade desejada de missões graduais: {clamped_count}",
        ]

        if student:
            prompt_lines.append(
                f"Perfil do estudante: nível atual '{student.current_level.value}', "
                f"estudando '{student.target_subject}' ({student.daily_available_minutes} min/dia)."
            )

        if topic.prerequisites:
            prompt_lines.append(f"Pré-requisitos já vistos: {', '.join(topic.prerequisites)}")

        prompt_lines.append(
            "\nConstrua um roteiro guiado usando Scaffolding (Andaimes Cognitivos):\n"
            "1. 'intro_brief': breve explicação intuitiva (máx. 2 parágrafos) do conceito antes da prática.\n"
            "2. 'prerequisites_check': checagem rápida opcional (ex: verificar versão instalada).\n"
            "3. 'missions': sequência progressiva onde cada missão tem um único objetivo claro, "
            "o comando ou código exato compatível com o sistema operacional informado, e o resultado "
            "observável ('expected_outcome') para o aluno validar se funcionou antes de avançar."
        )

        system_prompt = (
            "Você é um instrutor sênior de laboratório prático de engenharia de software. "
            "Crie exercícios executáveis, seguros, autocontidos e progressivos que o estudante "
            "consiga testar imediatamente em sua máquina local."
        )

        payload = self.llm_client.generate_structured(
            prompt="\n".join(prompt_lines),
            response_model=GuidedLabPayload,
            system_prompt=system_prompt,
            temperature=0.3,
        )

        normalized_missions = [
            mission.model_copy(update={"step_number": idx})
            for idx, mission in enumerate(payload.missions, start=1)
        ]

        return GuidedLab(
            topic_id=topic.id,
            intro_brief=payload.intro_brief,
            prerequisites_check=payload.prerequisites_check,
            missions=normalized_missions,
        )

    def debug_error(
        self,
        student: Optional[StudentProfile],
        topic: Topic,
        command_attempted: str,
        error_output: str,
        os_context: Optional[str] = None,
    ) -> ErrorDebugResolution:
        """Decodifica erros de execução/stack traces e orienta a correção passo a passo."""
        if not error_output or not error_output.strip():
            raise ValueError("A saída de erro do terminal não pode ser vazia.")

        detected_os = os_context or platform.system() or "Desconhecido"
        clean_cmd = (
            command_attempted.strip()
            if command_attempted and command_attempted.strip()
            else "(comando/código não informado separadamente)"
        )

        prompt_lines = [
            f"Tópico em estudo: '{topic.title}' ({topic.description})",
            f"Sistema operacional do aluno: {detected_os}",
        ]

        if student:
            prompt_lines.append(
                f"Estudante: {student.name} | Nível: {student.current_level.value} | Trilha: {student.target_subject}"
            )

        prompt_lines.extend(
            [
                f"\nComando ou trecho que o estudante tentou executar:\n```\n{clean_cmd}\n```",
                f"\nSaída de erro / Stack Trace obtido no terminal:\n```\n{error_output.strip()[:3000]}\n```",
                "\nAnalise o erro pedagogicamente:\n"
                "1. Traduza o que a mensagem de erro significa sem jargões intimidadores.\n"
                "2. Aponte a causa raiz exata (ex: sintaxe, pacote ausente, PATH, permissão de execução no Windows/PowerShell, versão ou indentação).\n"
                "3. Liste passos diretos e ordenados para corrigir o problema agora.\n"
                "4. Forneça o comando ou código corrigido pronto para testar e uma dica rápida de prevenção.",
            ]
        )

        system_prompt = (
            "Você é um mentor sênior de bancada especialista em debugging didático. "
            "Transforme cada erro de terminal em aprendizado real: acolha o estudante, explique o "
            "porquê técnico com clareza cristalina e entregue a solução exata para destravar a prática."
        )

        return self.llm_client.generate_structured(
            prompt="\n".join(prompt_lines),
            response_model=ErrorDebugResolution,
            system_prompt=system_prompt,
            temperature=0.2,
        )
