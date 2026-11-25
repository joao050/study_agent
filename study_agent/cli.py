"""Ponto de entrada da interface CLI interativa (study_agent/cli.py)."""

from typing import Optional
import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.table import Table

from study_agent import __version__
from study_agent.core.curriculum_gen import CurriculumGenerator
from study_agent.core.diagnostician import Diagnostician
from study_agent.core.evaluator import Evaluator
from study_agent.core.llm_client import (
    LLMAuthenticationError,
    LLMClientError,
    LLMConnectionError,
    LLMResponseValidationError,
)
from study_agent.core.teacher import Teacher
from study_agent.models.curriculum import ExplanationStyle, Topic, TopicStatus
from study_agent.models.student import KnowledgeLevel, StudentProfile, StudyPace
from study_agent.storage.session_store import SessionStore

app = typer.Typer(
    name="study-agent",
    help="🧠 AI Study Agent — Seu mentor e tutor particular adaptativo em linha de comando.",
    add_completion=False,
)
console = Console()


def get_store() -> SessionStore:
    """Retorna uma instância da camada de persistência."""
    return SessionStore()


def render_llm_error(exc: LLMClientError) -> None:
    """Exibe um painel visual amigável no terminal quando ocorre uma falha no provedor de LLM."""
    if isinstance(exc, LLMAuthenticationError):
        console.print(
            Panel(
                "[bold red]Não foi possível autenticar no provedor de IA.[/bold red]\n\n"
                "Verifique se a chave de API está preenchida corretamente no arquivo [bold cyan].env[/bold cyan] "
                "(ex: [cyan]GEMINI_API_KEY[/cyan], [cyan]OPENAI_API_KEY[/cyan] ou [cyan]ANTHROPIC_API_KEY[/cyan]) "
                "e se corresponde ao [cyan]LLM_PROVIDER[/cyan] configurado.",
                title="🔑 Erro de Credenciais / API Key",
                border_style="red",
            )
        )
    elif isinstance(exc, LLMConnectionError):
        reason = (
            "limite de requisições do plano gratuito/atual ([bold]429 Rate Limit[/bold])"
            if exc.is_rate_limit
            else "alta demanda nos servidores ou oscilação de rede ([bold]503 Service Unavailable / Timeout[/bold])"
        )
        console.print(
            Panel(
                f"[bold yellow]O serviço de IA não respondeu mesmo após {exc.attempts} tentativa(s) automática(s).[/bold yellow]\n\n"
                f"• [bold]Causa provável:[/bold] {reason}.\n"
                "• [bold]O que fazer:[/bold] Aguarde alguns segundos e execute o comando novamente, "
                "ou altere [cyan]LLM_MODEL[/cyan] no arquivo [cyan].env[/cyan].",
                title="🌐 Serviço de IA Temporariamente Indisponível",
                border_style="yellow",
            )
        )
    elif isinstance(exc, LLMResponseValidationError):
        console.print(
            Panel(
                "[bold yellow]O modelo de IA retornou uma resposta fora do formato estruturado esperado.[/bold yellow]\n\n"
                "• [bold]O que fazer:[/bold] Execute o comando novamente para gerar uma nova resposta limpa.",
                title="⚠️ Resposta Inesperada do Modelo",
                border_style="yellow",
            )
        )
    else:
        console.print(
            Panel(
                f"[bold red]Ocorreu uma falha ao comunicar com o modelo de IA:[/bold red]\n"
                f"[dim]{exc}[/dim]\n\n"
                "Verifique sua conexão e as configurações de modelo no arquivo [cyan].env[/cyan].",
                title="❌ Falha de Comunicação com o Tutor IA",
                border_style="red",
            )
        )


@app.command()
def version() -> None:
    """Exibe a versão instalada do AI Study Agent."""
    console.print(
        Panel(
            f"[bold cyan]AI Study Agent[/bold cyan] versão [green]{__version__}[/green]\n"
            "[italic dim]Tutor adaptativo com Técnica de Feynman e Active Recall[/italic dim]",
            border_style="cyan",
        )
    )


@app.command()
def init(
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Nome do estudante"),
    subject: Optional[str] = typer.Option(None, "--subject", "-s", help="Assunto de estudo"),
) -> None:
    """Inicia uma nova jornada de estudos com diagnóstico pedagógico e geração de trilha."""
    console.print(
        Panel.fit(
            "[bold green]🎓 Bem-vindo ao AI Study Agent![/bold green]\n"
            "Vamos criar seu perfil adaptativo e construir sua trilha personalizada.",
            border_style="green",
        )
    )

    student_name = name or Prompt.ask("👤 Qual é o seu nome?")
    target_subject = subject or Prompt.ask("🎯 O que você deseja aprender hoje? (ex: FastAPI, Docker, Rust)")

    console.print("\n[bold]Escolha seu objetivo de profundidade:[/bold]")
    console.print("  [1] [cyan]Iniciante[/cyan] (Dominar conceitos e primeiros passos)")
    console.print("  [2] [yellow]Intermediário[/yellow] (Aplicações práticas e resolução de problemas)")
    console.print("  [3] [magenta]Avançado[/magenta] (Arquitetura, boas práticas e performance)")
    target_opt = Prompt.ask("Selecione o nível desejado", choices=["1", "2", "3"], default="3")
    target_level_map = {
        "1": KnowledgeLevel.BEGINNER,
        "2": KnowledgeLevel.INTERMEDIATE,
        "3": KnowledgeLevel.ADVANCED,
    }
    target_level = target_level_map[target_opt]

    console.print("\n[bold]Qual ritmo você prefere seguir?[/bold]")
    console.print("  [1] [green]Relaxado[/green] (15-30 min/dia)")
    console.print("  [2] [blue]Regular[/blue] (45-60 min/dia)")
    console.print("  [3] [red]Intensivo[/red] (90+ min/dia)")
    pace_opt = Prompt.ask("Selecione o ritmo", choices=["1", "2", "3"], default="2")
    pace_map = {
        "1": (StudyPace.RELAXED, 25),
        "2": (StudyPace.REGULAR, 45),
        "3": (StudyPace.INTENSIVE, 90),
    }
    pace, default_mins = pace_map[pace_opt]
    minutes = IntPrompt.ask("Quantos minutos diários você tem disponível?", default=default_mins)

    profile = StudentProfile(
        name=student_name,
        target_subject=target_subject,
        current_level=KnowledgeLevel.BEGINNER,
        target_level=target_level,
        pace=pace,
        daily_available_minutes=minutes,
    )

    # Diagnóstico Pedagógico
    console.print(
        Panel(
            "[bold yellow]🩺 Nivelamento Inicial[/bold yellow]\n"
            "Vou gerar 3 perguntas rápidas para identificar de onde devemos começar.",
            border_style="yellow",
        )
    )

    diagnostician = Diagnostician()
    curriculum_gen = CurriculumGenerator()
    try:
        with console.status("[bold cyan]Elaborando perguntas de diagnóstico pedagógico...[/bold cyan]"):
            questions = diagnostician.generate_questions(target_subject=target_subject, count=3)

        student_answers = []
        for idx, q in enumerate(questions, start=1):
            console.print(
                Panel(
                    f"[bold cyan]Pergunta {idx}/3[/bold cyan] [dim]({q.topic_focus} • Nível: {q.difficulty.value})[/dim]\n\n"
                    f"[bold]{q.question}[/bold]",
                    border_style="cyan",
                )
            )
            answer = Prompt.ask("Sua resposta (pode ser concisa ou 'não sei')")
            student_answers.append(answer)

        with console.status("[bold yellow]Avaliando suas respostas e calibrando seu nível...[/bold yellow]"):
            report = diagnostician.evaluate_answers(
                target_subject=target_subject,
                questions=questions,
                student_answers=student_answers,
            )

        profile.current_level = report.assessed_level
        profile.diagnostic_history = report.answers

        console.print(
            Panel(
                f"[bold green]📊 Resultado do Diagnóstico:[/bold green]\n"
                f"• Nível Identificado: [bold cyan]{report.assessed_level.value.upper()}[/bold cyan]\n"
                f"• Pontuação de Partida: [bold]{report.overall_score}/100[/bold]\n"
                f"• Síntese: [italic]{report.summary_feedback}[/italic]\n"
                f"• Lacunas a Cobrir: [dim]{', '.join(report.learning_gaps) if report.learning_gaps else 'Nenhuma'}[/dim]",
                border_style="green",
            )
        )

        # Geração do Currículo
        with console.status("[bold green]Construindo sua trilha de aprendizado personalizada...[/bold green]"):
            curriculum = curriculum_gen.generate(student_profile=profile, diagnostic_report=report)
    except LLMClientError as exc:
        render_llm_error(exc)
        raise typer.Exit(code=1)

    # Persistência
    store = get_store()
    store.save_student(profile)
    store.save_curriculum(curriculum)
    store.set_current_session(profile.id, curriculum.id)

    console.print(
        Panel.fit(
            f"✅ [bold green]Trilha criada com sucesso para {profile.name}![/bold green]\n"
            f"Assunto: [bold]{curriculum.subject}[/bold] ({len(curriculum.topics)} tópicos mapeados)\n\n"
            "Para iniciar o estudo do primeiro tópico, execute:\n"
            "  [bold cyan]study-agent study[/bold cyan]",
            border_style="green",
        )
    )


@app.command()
def status() -> None:
    """Exibe o progresso atual do estudante na trilha de estudos ativa."""
    store = get_store()
    student, curriculum = store.load_active_session()

    if not student or not curriculum:
        console.print(
            "[yellow]⚠️ Nenhuma sessão ativa encontrada.[/yellow]\n"
            "Execute [bold cyan]study-agent init[/bold cyan] para começar uma nova trilha."
        )
        return

    progress_pct = curriculum.calculate_overall_progress()

    console.print(
        Panel(
            f"[bold cyan]Estudante:[/bold cyan] {student.name} | "
            f"[bold cyan]Trilha:[/bold cyan] {curriculum.subject}\n"
            f"[bold cyan]Nível:[/bold cyan] {student.current_level.value.title()} ➔ {student.target_level.value.title()} | "
            f"[bold cyan]Ritmo:[/bold cyan] {student.pace.value.title()} ({student.daily_available_minutes} min/dia)\n"
            f"[bold cyan]Progresso Geral:[/bold cyan] [bold green]{progress_pct}% dominado[/bold green]",
            title="📊 Painel do Estudante",
            border_style="cyan",
        )
    )

    table = Table(title="🗺️ Tópicos da Trilha", show_header=True, header_style="bold magenta")
    table.add_column("#", style="dim", width=4)
    table.add_column("Status", width=16)
    table.add_column("Tópico", min_width=25)
    table.add_column("Tempo", justify="right", width=10)
    table.add_column("Nota", justify="right", width=8)

    status_badges = {
        TopicStatus.MASTERED: "[green]✅ Dominado[/green]",
        TopicStatus.IN_PROGRESS: "[yellow]⏳ Em Estudo[/yellow]",
        TopicStatus.AVAILABLE: "[cyan]🔓 Disponível[/cyan]",
        TopicStatus.LOCKED: "[dim]🔒 Bloqueado[/dim]",
    }

    for idx, t in enumerate(curriculum.topics, start=1):
        badge = status_badges.get(t.status, str(t.status))
        score_str = f"{t.mastery_score:.0f}%" if t.mastery_score > 0 else "-"
        table.add_row(str(idx), badge, t.title, f"{t.estimated_minutes} min", score_str)

    console.print(table)


@app.command()
def map(
    mermaid: bool = typer.Option(False, "--mermaid", "-m", help="Exibe no formato diagrama Mermaid")
) -> None:
    """Renderiza a árvore de tópicos e mapa mental da trilha ativa."""
    store = get_store()
    student, curriculum = store.load_active_session()

    if not curriculum:
        console.print("[yellow]⚠️ Nenhuma trilha ativa encontrada. Execute 'study-agent init'.[/yellow]")
        return

    if mermaid:
        mermaid_code = CurriculumGenerator.generate_mermaid_graph(curriculum)
        console.print(Panel(mermaid_code, title="Diagrama Mermaid", border_style="magenta"))
    else:
        tree_text = CurriculumGenerator.format_ascii_tree(curriculum)
        console.print(Panel(tree_text, title="Mapa Conceitual da Trilha", border_style="blue"))


@app.command()
def study() -> None:
    """Inicia ou retoma a sessão de estudo no próximo tópico disponível."""
    store = get_store()
    student, curriculum = store.load_active_session()

    if not student or not curriculum:
        console.print("[yellow]⚠️ Nenhuma sessão ativa encontrada. Execute 'study-agent init' primeiro.[/yellow]")
        return

    # Procura o primeiro tópico disponível ou em progresso
    next_topic: Optional[Topic] = None
    for t in curriculum.topics:
        if t.status in (TopicStatus.AVAILABLE, TopicStatus.IN_PROGRESS):
            next_topic = t
            break

    if not next_topic:
        console.print(
            Panel.fit(
                "🎉 [bold green]Parabéns! Todos os tópicos da sua trilha foram dominados![/bold green]\n"
                f"Você concluiu a jornada de [bold cyan]{curriculum.subject}[/bold cyan] com 100% de aproveitamento.",
                border_style="green",
            )
        )
        return

    console.print(
        Panel(
            f"[bold cyan]Tópico Selecionado:[/bold cyan] [bold]{next_topic.title}[/bold]\n"
            f"[dim]{next_topic.description}[/dim]\n"
            f"⏱️ Tempo Estimado: {next_topic.estimated_minutes} minutos",
            title="📖 Sessão de Estudo Ativa",
            border_style="cyan",
        )
    )

    console.print("\n[bold]Escolha o estilo de explicação para esta aula:[/bold]")
    console.print("  [1] [green]Técnica de Feynman[/green] (Analogias intuitivas e linguagem simples)")
    console.print("  [2] [yellow]Técnico e Formal[/yellow] (Definições exatas e arquitetura interna)")
    console.print("  [3] [cyan]Prático (Hands-on)[/cyan] (Código comentado e casos reais)")
    style_opt = Prompt.ask("Estilo", choices=["1", "2", "3"], default="1")
    style_map = {
        "1": ExplanationStyle.FEYNMAN,
        "2": ExplanationStyle.TECHNICAL,
        "3": ExplanationStyle.PRACTICAL,
    }
    chosen_style = style_map[style_opt]

    teacher = Teacher()
    try:
        with console.status("[bold green]O professor está preparando sua explicação didática...[/bold green]"):
            explanation = teacher.explain_topic(
                topic=next_topic,
                style=chosen_style,
                student_context=f"Aluno nível {student.current_level.value}",
            )
    except LLMClientError as exc:
        render_llm_error(exc)
        raise typer.Exit(code=1)

    console.print("\n" + "=" * 60 + "\n")
    console.print(Markdown(explanation))
    console.print("\n" + "=" * 60 + "\n")

    # Extrai takeaways para fixação (degradação graciosa em caso de oscilação)
    takeaways = next_topic.key_takeaways
    try:
        with console.status("[dim]Sintetizando pontos-chave...[/dim]"):
            takeaways = teacher.summarize_key_takeaways(next_topic, explanation)
        next_topic.key_takeaways = takeaways
    except LLMClientError:
        console.print("[dim yellow]⚠️ Síntese de pontos-chave ignorada devido a oscilação momentânea da rede.[/dim yellow]")

    # Ciclo de tirar dúvidas (resiliente: falha pontual não derruba a aula)
    while Confirm.ask("Ficou com alguma dúvida ou gostaria de um exemplo extra?"):
        doubt = Prompt.ask("Digite sua dúvida")
        try:
            with console.status("[bold yellow]O professor está respondendo sua dúvida...[/bold yellow]"):
                answer = teacher.answer_doubt(
                    topic=next_topic,
                    student_question=doubt,
                    previous_explanation=explanation,
                )
            console.print(Panel(Markdown(answer), title="💡 Resposta do Professor", border_style="yellow"))
        except LLMClientError as exc:
            render_llm_error(exc)

    # Checagem ativa (Active Recall)
    console.print(
        Panel(
            "[bold magenta]🧠 Checagem Ativa de Retenção (Active Recall)[/bold magenta]\n"
            "Agora é sua vez! Para consolidar o aprendizado e liberar o próximo tópico,\n"
            "responda à pergunta aberta a seguir com suas próprias palavras.",
            border_style="magenta",
        )
    )

    evaluator = Evaluator()
    try:
        with console.status("[bold magenta]Elaborando pergunta de retenção ativa...[/bold magenta]"):
            recall_question = evaluator.generate_active_recall_question(next_topic, key_takeaways=takeaways)

        console.print(
            Panel(
                f"[bold]{recall_question.question}[/bold]\n\n"
                f"[dim]💡 Dica: {recall_question.hint or 'Explique o porquê com clareza.'}[/dim]",
                border_style="magenta",
            )
        )

        student_answer = Prompt.ask("Sua resposta")
        with console.status("[bold cyan]Avaliando seu domínio conceitual...[/bold cyan]"):
            evaluation = evaluator.evaluate_active_recall(recall_question, student_answer)
    except LLMClientError as exc:
        next_topic.status = TopicStatus.IN_PROGRESS
        store.save_curriculum(curriculum)
        render_llm_error(exc)
        console.print("[dim]💾 Seu progresso parcial neste tópico foi salvo automaticamente.[/dim]")
        raise typer.Exit(code=1)

    # Exibe resultado da avaliação
    status_color = "green" if evaluation.is_passing else "yellow"
    result_title = "✅ Tópico Dominado!" if evaluation.is_passing else "⚠️ Quase lá! Precisa reforçar"

    console.print(
        Panel(
            f"Nota de Domínio: [bold]{evaluation.score:.0f}/100[/bold]\n"
            f"[bold]Feedback:[/bold] {evaluation.feedback}\n\n"
            f"[green]Conceitos dominados:[/green] {', '.join(evaluation.understood_concepts) if evaluation.understood_concepts else '-'}\n"
            f"[red]Pontos a reforçar:[/red] {', '.join(evaluation.missing_or_confused_concepts) if evaluation.missing_or_confused_concepts else 'Nenhum'}",
            title=f"[{status_color}]{result_title}[/{status_color}]",
            border_style=status_color,
        )
    )

    # Atualiza status do tópico e salva trilha
    evaluator.update_topic_mastery(next_topic, evaluation)
    curriculum.update_topic_statuses()
    store.save_curriculum(curriculum)

    if evaluation.is_passing:
        console.print("🚀 [bold green]Excelente! O próximo tópico da trilha foi desbloqueado.[/bold green]")
    else:
        console.print("💡 [bold yellow]O tópico permanece em andamento. Você pode revisá-lo a qualquer momento.[/bold yellow]")


@app.command()
def students(
    switch: Optional[str] = typer.Option(None, "--switch", "-s", help="ID do estudante para ativar sessão")
) -> None:
    """Lista todos os estudantes e permite alternar a sessão ativa."""
    store = get_store()

    if switch:
        student = store.load_student(switch)
        if not student:
            console.print(f"[red]❌ Estudante com ID '{switch}' não foi encontrado.[/red]")
            return
        curriculum = store.load_curriculum_by_student(switch)
        if not curriculum:
            console.print(f"[yellow]⚠️ Estudante '{student.name}' não possui trilha associada.[/yellow]")
            return
        store.set_current_session(student.id, curriculum.id)
        console.print(f"✅ [bold green]Sessão alternada com sucesso para '{student.name}' ({curriculum.subject})![/bold green]")
        return

    all_students = store.list_students()
    if not all_students:
        console.print("[yellow]Nenhum estudante cadastrado no momento.[/yellow]")
        return

    current = store.get_current_session()
    current_student_id = current[0] if current else None

    table = Table(title="👥 Estudantes Cadastrados", show_header=True, header_style="bold cyan")
    table.add_column("Ativo", justify="center", width=6)
    table.add_column("ID", style="dim", width=12)
    table.add_column("Nome", min_width=15)
    table.add_column("Assunto", min_width=20)
    table.add_column("Nível Atual", width=12)

    for s in all_students:
        is_active = "👉 [green]*[/green]" if s.id == current_student_id else ""
        table.add_row(is_active, s.id[:8], s.name, s.target_subject, s.current_level.value.title())

    console.print(table)
    console.print("[dim]Para alternar a sessão ativa: study-agent students --switch <ID>[/dim]")


if __name__ == "__main__":
    app()
