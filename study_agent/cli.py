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
from study_agent.core.exporter import StudyExporter
from study_agent.core.gamification import (
    BADGE_BY_ID,
    BADGE_CATALOG,
    GamificationEngine,
    GamificationEvent,
)
from study_agent.core.llm_client import (
    LLMAuthenticationError,
    LLMClientError,
    LLMConnectionError,
    LLMResponseValidationError,
)
from study_agent.core.teacher import Teacher
from study_agent.models.curriculum import (
    Curriculum,
    ErrorDebugResolution,
    ExplanationStyle,
    Topic,
    TopicStatus,
)
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


def _collect_multiline_error_output() -> str:
    """Abre painel dedicado e captura saídas de erro ou stack traces de múltiplas linhas."""
    console.print(
        Panel(
            "Cole abaixo a saída de erro ou [bold]stack trace[/bold] exibido no seu terminal.\n"
            "Para enviar, pressione [bold cyan]ENTER em uma linha vazia[/bold cyan] "
            "(ou digite [bold cyan]FIM[/bold cyan]).",
            title="🚨 Reportar Erro / Colar Terminal",
            border_style="red",
        )
    )
    lines: list[str] = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line.strip().upper() in ("FIM", "EOF"):
            break
        if line == "" and lines:
            break
        if line != "" or lines:
            lines.append(line)
    return "\n".join(lines).strip()


def render_debug_resolution(resolution: ErrorDebugResolution) -> None:
    """Renderiza o diagnóstico pedagógico e os passos de correção de um erro."""
    steps_md = "\n".join(
        f"{idx}. {step}" for idx, step in enumerate(resolution.fix_instructions, start=1)
    )
    tip_section = (
        f"\n\n💡 **Dica de Prevenção:** {resolution.prevention_tip}"
        if resolution.prevention_tip
        else ""
    )
    body_md = (
        f"### 🩺 O que esse erro significa\n{resolution.error_summary}\n\n"
        f"### 🔍 Causa Raiz\n{resolution.root_cause}\n\n"
        f"### 🛠️ Passo a Passo para Corrigir\n{steps_md}\n\n"
        f"### 💻 Comando / Código Corrigido\n```\n{resolution.corrected_command_or_code}\n```"
        f"{tip_section}"
    )
    console.print(
        Panel(
            Markdown(body_md),
            title="🔧 Assistente de Debugging em Tempo Real",
            border_style="green",
        )
    )


def render_gamification_event(event: GamificationEvent, student: StudentProfile) -> None:
    """Exibe painel visual de recompensas (XP ganho, subida de nível, streak e novas conquistas)."""
    if not event.has_rewards and not event.streak_updated:
        return

    lines: list[str] = []
    lvl_info = GamificationEngine.calculate_level_progress(student.xp)

    if event.xp_gained > 0:
        for item in event.xp_breakdown:
            lines.append(f"⚡ [bold green]{item}[/bold green]")
        lines.append(
            f"[dim]Progresso de Nível: Nv. {lvl_info.level} ({lvl_info.title}) • "
            f"{lvl_info.current_xp}/{lvl_info.next_level_xp} XP ({lvl_info.progress_pct:.0f}%)[/dim]"
        )

    if event.leveled_up:
        lines.append(
            f"🎉 [bold yellow]LEVEL UP![/bold yellow] Você avançou do Nível {event.previous_level} "
            f"para [bold cyan]Nível {event.new_level} — {event.new_title}[/bold cyan]!"
        )

    if event.streak_updated:
        lines.append(
            f"🔥 [bold orange1]Ofensiva Diária Ativa:[/bold orange1] "
            f"[bold]{event.current_streak} dia(s) consecutivo(s)[/bold]!"
        )

    if event.newly_unlocked_badges:
        if lines:
            lines.append("")
        lines.append("🏅 [bold magenta]Nova(s) Conquista(s) Desbloqueada(s):[/bold magenta]")
        for badge in event.newly_unlocked_badges:
            lines.append(f"  • {badge.icon} [bold]{badge.title}[/bold] — [dim]{badge.description}[/dim]")

    console.print(
        Panel(
            "\n".join(lines),
            title="🌟 Evolução & Conquistas",
            border_style="gold1",
        )
    )


def _handle_error_debugging_flow(
    teacher: Teacher,
    student: StudentProfile,
    topic: Topic,
    default_command: str = "",
) -> None:
    """Coleta comando e erro do terminal do aluno e aciona o assistente de debugging."""
    command_attempted = Prompt.ask(
        "💻 Qual comando ou código você tentou executar? (Enter para usar o padrão/pular)",
        default=default_command,
    )
    error_output = _collect_multiline_error_output()
    if not error_output:
        console.print("[yellow]⚠️ Nenhuma saída de erro informada. Retornando ao estudo.[/yellow]")
        return

    try:
        with console.status("[bold cyan]Analisando o erro e preparando a correção passo a passo...[/bold cyan]"):
            resolution = teacher.debug_error(
                student=student,
                topic=topic,
                command_attempted=command_attempted,
                error_output=error_output,
            )
        GamificationEngine.record_debug_usage(topic)
        render_debug_resolution(resolution)
    except LLMClientError as exc:
        render_llm_error(exc)


def _run_guided_lab_flow(
    teacher: Teacher,
    student: StudentProfile,
    topic: Topic,
    curriculum: Optional[Curriculum] = None,
) -> str:
    """Conduz uma sessão prática passo a passo com checkpoints e suporte a debugging."""
    with console.status("[bold magenta]Montando seu laboratório prático passo a passo...[/bold magenta]"):
        lab = teacher.generate_guided_lab(topic=topic, student=student)

    total = len(lab.missions)
    topic.total_lab_missions = max(topic.total_lab_missions, total)

    prereq_line = (
        f"\n\n[bold yellow]🔎 Checagem prévia:[/bold yellow] {lab.prerequisites_check}"
        if lab.prerequisites_check
        else ""
    )
    console.print(
        Panel(
            f"{lab.intro_brief}{prereq_line}",
            title=f"🧪 Laboratório Guiado: {topic.title}",
            border_style="magenta",
        )
    )

    summary_parts = [f"# {topic.title}\n\n{lab.intro_brief}"]

    for mission in lab.missions:
        hint_md = (
            f"\n\n> 💡 **Atenção:** {mission.verification_hint}"
            if mission.verification_hint
            else ""
        )
        mission_md = (
            f"{mission.instruction}\n\n"
            f"**Execute / Teste:**\n```\n{mission.command_or_code}\n```\n\n"
            f"✅ **Checkpoint esperado:** {mission.expected_outcome}{hint_md}"
        )
        console.print(
            Panel(
                Markdown(mission_md),
                title=f"🛠️ Missão {mission.step_number}/{total}: {mission.title}",
                border_style="cyan",
            )
        )
        summary_parts.append(f"## Missão {mission.step_number}: {mission.title}\n{mission.instruction}")

        abort_lab = False
        while True:
            console.print(
                "  [bold green][P][/bold green] Funcionou! Próximo passo  |  "
                "[bold red][E][/bold red] Reportar Erro / Colar Terminal  |  "
                "[bold yellow][D][/bold yellow] Tirar dúvida  |  "
                "[bold magenta][A][/bold magenta] Ir para Avaliação"
            )
            choice = Prompt.ask("Checkpoint", default="P").strip().lower()

            if choice in ("p", "proximo", "próximo", "ok", ""):
                topic.completed_lab_steps = max(topic.completed_lab_steps, mission.step_number)
                lab_event = GamificationEngine.award_lab_mission_xp(
                    student=student,
                    topic=topic,
                    curriculum=curriculum,
                )
                xp_tag = f" (+{lab_event.xp_gained} XP ⚡)" if lab_event.xp_gained > 0 else ""
                console.print(f"[green]✔️ Missão {mission.step_number}/{total} validada!{xp_tag}[/green]")
                if lab_event.leveled_up or lab_event.newly_unlocked_badges:
                    render_gamification_event(lab_event, student)
                break
            if choice in ("e", "erro"):
                _handle_error_debugging_flow(
                    teacher=teacher,
                    student=student,
                    topic=topic,
                    default_command=mission.command_or_code,
                )
            elif choice in ("d", "duvida", "dúvida", "y"):
                doubt = Prompt.ask("Digite sua dúvida sobre este passo")
                try:
                    with console.status("[bold yellow]O professor está respondendo sua dúvida...[/bold yellow]"):
                        answer = teacher.answer_doubt(
                            topic=topic,
                            student_question=doubt,
                            previous_explanation="\n\n".join(summary_parts),
                        )
                    console.print(Panel(Markdown(answer), title="💡 Resposta do Professor", border_style="yellow"))
                except LLMClientError as exc:
                    render_llm_error(exc)
            elif choice in ("a", "avaliar", "sair"):
                abort_lab = True
                break
            else:
                console.print("[yellow]Opção inválida. Escolha P, E, D ou A.[/yellow]")

        if abort_lab:
            break

    return "\n\n".join(summary_parts)


def _run_interactive_study_menu(
    teacher: Teacher,
    student: StudentProfile,
    topic: Topic,
    explanation: str,
    curriculum: Optional[Curriculum] = None,
) -> None:
    """Menu interativo pós-aula com suporte a dúvidas, reporte de erro e laboratório prático."""
    while True:
        console.print(
            Panel(
                "  [bold green][C][/bold green] Concluir estudo e ir para o Active Recall [dim](padrão)[/dim]\n"
                "  [bold yellow][D][/bold yellow] Tirar dúvida conceitual ou pedir exemplo extra\n"
                "  [bold red][E][/bold red] Reportar Erro / Colar saída do terminal 🚨\n"
                "  [bold magenta][L][/bold magenta] Praticar em Laboratório Guiado passo a passo 🛠️",
                title="🧭 Acompanhamento Prático & Dúvidas",
                border_style="blue",
            )
        )
        action = Prompt.ask("Escolha uma ação [C/D/E/L]", default="C").strip().lower()

        if action in ("c", "n", "continuar", ""):
            break
        if action in ("d", "y", "duvida", "dúvida"):
            doubt = Prompt.ask("Digite sua dúvida")
            try:
                with console.status("[bold yellow]O professor está respondendo sua dúvida...[/bold yellow]"):
                    answer = teacher.answer_doubt(
                        topic=topic,
                        student_question=doubt,
                        previous_explanation=explanation,
                    )
                console.print(Panel(Markdown(answer), title="💡 Resposta do Professor", border_style="yellow"))
            except LLMClientError as exc:
                render_llm_error(exc)
        elif action in ("e", "erro"):
            _handle_error_debugging_flow(
                teacher=teacher,
                student=student,
                topic=topic,
            )
        elif action in ("l", "lab", "laboratorio", "laboratório"):
            try:
                _run_guided_lab_flow(
                    teacher=teacher,
                    student=student,
                    topic=topic,
                    curriculum=curriculum,
                )
            except LLMClientError as exc:
                render_llm_error(exc)
        else:
            console.print("[yellow]Opção não reconhecida. Use C, D, E ou L.[/yellow]")


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
    days: Optional[int] = typer.Option(None, "--days", "-d", help="Prazo opcional em dias para concluir a meta"),
    goal: Optional[str] = typer.Option(None, "--goal", "-g", help="Descrição opcional da meta com prazo"),
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

    # Meta opcional com prazo
    total_estimated_mins = sum(t.estimated_minutes for t in curriculum.topics)
    suggested_days = max(1, round(total_estimated_mins / max(15, minutes)))

    chosen_days = days
    if chosen_days is None:
        try:
            chosen_days = IntPrompt.ask(
                f"⏳ Deseja definir um prazo em dias para concluir esta meta? "
                f"(sugestão p/ seu ritmo: ~{suggested_days}d | 0 para sem prazo)",
                default=0,
            )
        except EOFError:
            chosen_days = 0

    if chosen_days and chosen_days > 0:
        default_label = goal or f"Concluir {curriculum.subject} em {chosen_days} dias"
        if goal is not None:
            chosen_label = goal
        else:
            try:
                chosen_label = Prompt.ask("🏁 Como deseja chamar esta meta?", default=default_label)
            except EOFError:
                chosen_label = default_label
        GamificationEngine.set_goal(curriculum, target_days=chosen_days, goal_label=chosen_label)

    onboarding_event = GamificationEngine.record_onboarding(profile, curriculum=curriculum)

    # Persistência
    store = get_store()
    store.save_student(profile)
    store.save_curriculum(curriculum)
    store.set_current_session(profile.id, curriculum.id)

    render_gamification_event(onboarding_event, profile)

    goal_line = ""
    if curriculum.target_days and curriculum.deadline_at:
        deadline_fmt = curriculum.deadline_at.strftime("%d/%m/%Y")
        goal_line = f"\n🏁 Meta ativa: [bold yellow]{curriculum.goal_label}[/bold yellow] (até {deadline_fmt})"

    console.print(
        Panel.fit(
            f"✅ [bold green]Trilha criada com sucesso para {profile.name}![/bold green]\n"
            f"Assunto: [bold]{curriculum.subject}[/bold] ({len(curriculum.topics)} tópicos mapeados){goal_line}\n\n"
            "Para iniciar o estudo do primeiro tópico, execute:\n"
            "  [bold cyan]python -m study_agent.cli study[/bold cyan]\n"
            "  [dim](No Windows, você também pode usar: .\\study-agent study)[/dim]",
            border_style="green",
        )
    )


@app.command()
def goal(
    days: Optional[int] = typer.Option(None, "--days", "-d", help="Prazo em dias corridos para concluir a trilha"),
    label: Optional[str] = typer.Option(None, "--label", "-l", help="Descrição personalizada da meta"),
    clear: bool = typer.Option(False, "--clear", "-c", help="Remove o prazo da trilha ativa"),
) -> None:
    """Define, edita ou consulta a meta com prazo (Goal Deadline) da trilha ativa."""
    store = get_store()
    student, curriculum = store.load_active_session()

    if not student or not curriculum:
        console.print(
            "[yellow]⚠️ Nenhuma sessão ativa encontrada.[/yellow]\n"
            "Execute [bold cyan]python -m study_agent.cli init[/bold cyan] "
            "[dim](ou .\\study-agent init)[/dim] para começar uma nova trilha."
        )
        return

    if clear:
        GamificationEngine.clear_goal(curriculum)
        store.save_curriculum(curriculum)
        console.print(
            Panel(
                f"Prazo removido da trilha [bold cyan]{curriculum.subject}[/bold cyan].\n"
                "Você continua estudando no seu próprio ritmo!",
                title="🕊️ Meta sem Prazo",
                border_style="cyan",
            )
        )
        return

    if days is not None:
        if days < 1:
            console.print("[red]❌ O prazo deve ser de pelo menos 1 dia (ou use --clear para remover).[/red]")
            raise typer.Exit(code=1)
        goal_status = GamificationEngine.set_goal(curriculum, target_days=days, goal_label=label)
        store.save_curriculum(curriculum)
    elif label is not None and curriculum.target_days:
        curriculum.goal_label = label.strip() or curriculum.goal_label
        store.save_curriculum(curriculum)
        goal_status = GamificationEngine.get_goal_status(curriculum)
    else:
        current_status = GamificationEngine.get_goal_status(curriculum)
        if current_status.has_goal and current_status.deadline_at:
            console.print(
                Panel(
                    f"• [bold]Meta Atual:[/bold] {current_status.goal_label}\n"
                    f"• [bold]Prazo:[/bold] {current_status.target_days} dia(s) "
                    f"(até {current_status.deadline_at.strftime('%d/%m/%Y')})\n"
                    f"• [bold]Status:[/bold] {current_status.status_label}",
                    title="🏁 Meta Atual da Trilha",
                    border_style="yellow",
                )
            )
        new_days = IntPrompt.ask(
            "⏳ Informe o novo prazo em dias (ou digite 0 para remover o prazo)",
            default=curriculum.target_days or 7,
        )
        if new_days <= 0:
            GamificationEngine.clear_goal(curriculum)
            store.save_curriculum(curriculum)
            console.print("[cyan]🕊️ Prazo removido com sucesso.[/cyan]")
            return
        default_lbl = label or curriculum.goal_label or f"Concluir {curriculum.subject} em {new_days} dias"
        new_label = Prompt.ask("🏁 Descrição da meta", default=default_lbl)
        goal_status = GamificationEngine.set_goal(curriculum, target_days=new_days, goal_label=new_label)
        store.save_curriculum(curriculum)

    deadline_str = goal_status.deadline_at.strftime("%d/%m/%Y") if goal_status.deadline_at else "-"
    pace_line = (
        f"\n• [bold]Ritmo sugerido:[/bold] ~{goal_status.recommended_topics_per_day} tópico(s)/dia"
        if goal_status.recommended_topics_per_day
        else ""
    )
    console.print(
        Panel(
            f"• [bold]Meta:[/bold] [yellow]{goal_status.goal_label}[/yellow]\n"
            f"• [bold]Prazo:[/bold] {goal_status.target_days} dia(s) (data limite: [bold]{deadline_str}[/bold])\n"
            f"• [bold]Termômetro:[/bold] {goal_status.status_label} • {goal_status.progress_pct}% concluído"
            f"{pace_line}",
            title="✅ Meta Atualizada com Sucesso",
            border_style="green",
        )
    )


@app.command()
def status(
    badges: bool = typer.Option(False, "--badges", "-b", help="Exibe a vitrine completa de conquistas (badges)")
) -> None:
    """Exibe o progresso atual, nível de XP, ofensiva diária, meta e conquistas do estudante."""
    store = get_store()
    student, curriculum = store.load_active_session()

    if not student or not curriculum:
        console.print(
            "[yellow]⚠️ Nenhuma sessão ativa encontrada.[/yellow]\n"
            "Execute [bold cyan]python -m study_agent.cli init[/bold cyan] "
            "[dim](ou .\\study-agent init)[/dim] para começar uma nova trilha."
        )
        return

    progress_pct = curriculum.calculate_overall_progress()
    lvl_info = GamificationEngine.calculate_level_progress(student.xp)
    effective_streak = GamificationEngine.get_effective_streak(student)
    goal_info = GamificationEngine.get_goal_status(curriculum)

    goal_line = (
        f"[bold cyan]Meta:[/bold cyan] {goal_info.goal_label} ([yellow]{goal_info.status_label}[/yellow])"
        if goal_info.has_goal
        else "[bold cyan]Meta:[/bold cyan] [dim]Sem prazo definido (use 'goal --days N' para criar)[/dim]"
    )

    unlocked_icons = " ".join(
        BADGE_BY_ID[b.badge_id].icon
        for b in student.unlocked_badges
        if b.badge_id in BADGE_BY_ID
    )
    badges_summary = (
        f"{len(student.unlocked_badges)}/{len(BADGE_CATALOG)} {unlocked_icons}".strip()
        if student.unlocked_badges
        else f"0/{len(BADGE_CATALOG)} [dim](use 'status --badges' para ver o catálogo)[/dim]"
    )

    console.print(
        Panel(
            f"[bold cyan]Estudante:[/bold cyan] {student.name} | "
            f"[bold cyan]Trilha:[/bold cyan] {curriculum.subject}\n"
            f"[bold cyan]Nível:[/bold cyan] {student.current_level.value.title()} ➔ {student.target_level.value.title()} | "
            f"[bold cyan]Ritmo:[/bold cyan] {student.pace.value.title()} ({student.daily_available_minutes} min/dia)\n"
            f"[bold cyan]Patente & XP:[/bold cyan] [bold yellow]Nv. {lvl_info.level} • {lvl_info.title}[/bold yellow] "
            f"({lvl_info.current_xp}/{lvl_info.next_level_xp} XP) | "
            f"[bold cyan]Ofensiva:[/bold cyan] 🔥 [bold orange1]{effective_streak}d[/bold orange1] "
            f"[dim](recorde: {student.longest_streak}d)[/dim]\n"
            f"{goal_line}\n"
            f"[bold cyan]Conquistas:[/bold cyan] 🏅 {badges_summary} | "
            f"[bold cyan]Progresso Geral:[/bold cyan] [bold green]{progress_pct}% dominado[/bold green]",
            title="📊 Painel do Estudante",
            border_style="cyan",
        )
    )

    if badges:
        badge_table = Table(title="🏅 Catálogo de Conquistas", show_header=True, header_style="bold gold1")
        badge_table.add_column("Status", width=14)
        badge_table.add_column("Conquista", min_width=24)
        badge_table.add_column("Critério", min_width=32)

        for b_def in BADGE_CATALOG:
            unlocked = student.has_badge(b_def.id)
            st_text = "[green]✅ Conquistada[/green]" if unlocked else "[dim]🔒 Bloqueada[/dim]"
            title_fmt = f"{b_def.icon} [bold]{b_def.title}[/bold]" if unlocked else f"[dim]{b_def.icon} {b_def.title}[/dim]"
            badge_table.add_row(st_text, title_fmt, b_def.description)

        console.print(badge_table)

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
        console.print(
            "[yellow]⚠️ Nenhuma trilha ativa encontrada. "
            "Execute 'python -m study_agent.cli init' (ou '.\\study-agent init').[/yellow]"
        )
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
        console.print(
            "[yellow]⚠️ Nenhuma sessão ativa encontrada. "
            "Execute 'python -m study_agent.cli init' (ou '.\\study-agent init') primeiro.[/yellow]"
        )
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
    console.print("  [4] [magenta]Laboratório Guiado Passo a Passo[/magenta] (Missões práticas + Suporte a Erros)")
    style_opt = Prompt.ask("Estilo", choices=["1", "2", "3", "4"], default="1")
    style_map = {
        "1": ExplanationStyle.FEYNMAN,
        "2": ExplanationStyle.TECHNICAL,
        "3": ExplanationStyle.PRACTICAL,
        "4": ExplanationStyle.GUIDED_LAB,
    }
    chosen_style = style_map[style_opt]

    teacher = Teacher()
    if chosen_style == ExplanationStyle.GUIDED_LAB:
        try:
            explanation = _run_guided_lab_flow(
                teacher=teacher,
                student=student,
                topic=next_topic,
                curriculum=curriculum,
            )
        except LLMClientError as exc:
            render_llm_error(exc)
            raise typer.Exit(code=1)
    else:
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

    # Menu interativo de estudo (dúvidas, debugging de erros de terminal e laboratório prático)
    if chosen_style != ExplanationStyle.GUIDED_LAB:
        _run_interactive_study_menu(
            teacher=teacher,
            student=student,
            topic=next_topic,
            explanation=explanation,
            curriculum=curriculum,
        )

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
        store.save_student(student)
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

    # Atualiza status do tópico, gamificação (XP, streak, metas e conquistas) e salva sessão
    was_mastered_before = next_topic.status == TopicStatus.MASTERED
    previous_best_score = max(
        (r.score for r in next_topic.recall_history),
        default=next_topic.mastery_score,
    )
    evaluator.update_topic_mastery(next_topic, evaluation, question=recall_question)
    curriculum.update_topic_statuses()
    gamification_event = GamificationEngine.process_topic_evaluation(
        student=student,
        curriculum=curriculum,
        topic=next_topic,
        evaluation=evaluation,
        was_mastered_before=was_mastered_before,
        previous_score=previous_best_score,
    )
    store.save_student(student)
    store.save_curriculum(curriculum)

    render_gamification_event(gamification_event, student)

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
    console.print(
        "[dim]Para alternar a sessão ativa: python -m study_agent.cli students --switch <ID> "
        "(ou .\\study-agent students --switch <ID>)[/dim]"
    )


@app.command()
def export(
    format: str = typer.Option(
        "both",
        "--format",
        "-f",
        help="Formato de exportação: 'both' (padrão), 'markdown' ou 'anki'",
    ),
    include_in_progress: bool = typer.Option(
        False,
        "--in-progress",
        "-i",
        help="Inclui também tópicos em andamento (além dos dominados)",
    ),
    output_dir: Optional[str] = typer.Option(
        None,
        "--output-dir",
        "-o",
        help="Diretório de saída dos arquivos (padrão: exports/)",
    ),
) -> None:
    """Exporta resumos em Markdown e flashcards Anki dos tópicos estudados."""
    store = get_store()
    student, curriculum = store.load_active_session()

    if not student or not curriculum:
        console.print(
            "[yellow]⚠️ Nenhuma sessão ativa encontrada. "
            "Execute 'python -m study_agent.cli init' (ou '.\\study-agent init') primeiro.[/yellow]"
        )
        return

    normalized_fmt = format.strip().lower()
    if normalized_fmt not in StudyExporter.VALID_FORMATS:
        console.print(
            f"[red]❌ Formato inválido '{format}'. Escolha entre: both, markdown ou anki.[/red]"
        )
        raise typer.Exit(code=1)

    exporter = StudyExporter(base_dir=output_dir) if output_dir else StudyExporter()
    eligible = exporter.select_exportable_topics(
        curriculum, include_in_progress=include_in_progress
    )

    if not eligible:
        has_in_progress = any(t.status == TopicStatus.IN_PROGRESS for t in curriculum.topics)
        extra_tip = (
            "\n💡 Dica: Use a flag [bold cyan]--in-progress[/bold cyan] para exportar tópicos já iniciados."
            if has_in_progress and not include_in_progress
            else ""
        )
        console.print(
            Panel(
                "[yellow]Ainda não há tópicos dominados nesta trilha para exportar.[/yellow]\n"
                "Conclua ao menos um tópico com [bold cyan]python -m study_agent.cli study[/bold cyan]."
                f"{extra_tip}",
                title="📦 Exportação de Resumos",
                border_style="yellow",
            )
        )
        return

    result = exporter.export_session(
        student=student,
        curriculum=curriculum,
        output_dir=output_dir,
        fmt=normalized_fmt,
        include_in_progress=include_in_progress,
    )

    details = [
        f"• [bold]Estudante / Trilha:[/bold] {student.name} — {curriculum.subject}",
        f"• [bold]Tópicos exportados:[/bold] [green]{result.topics_exported}[/green]",
    ]
    if result.markdown_path:
        details.append(f"• [bold]Resumo Markdown:[/bold] [cyan]{result.markdown_path}[/cyan]")
    if result.anki_path:
        details.append(
            f"• [bold]Deck Anki ({result.flashcards_generated} cartões):[/bold] [cyan]{result.anki_path}[/cyan]\n"
            "  [dim]No Anki: Arquivo ➔ Importar ➔ selecione o arquivo .txt gerado (separador e deck automáticos).[/dim]"
        )

    console.print(
        Panel(
            "\n".join(details),
            title="✅ Material de Revisão Exportado com Sucesso",
            border_style="green",
        )
    )


if __name__ == "__main__":
    app()
