"""Motor de Gamificação: economia de XP prático, níveis, streaks, metas com prazo e conquistas."""

from datetime import date, datetime, timedelta, timezone
from math import ceil
from typing import Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

from study_agent.models.curriculum import (
    ActiveRecallEvaluation,
    Curriculum,
    Topic,
    TopicStatus,
)
from study_agent.models.student import (
    BadgeCategory,
    KnowledgeLevel,
    StudentProfile,
    UnlockedBadge,
)


class BadgeDefinition(BaseModel):
    """Metadados imutáveis de uma conquista (badge) disponível no catálogo."""

    id: str = Field(description="Identificador único da conquista")
    title: str = Field(description="Título exibido ao estudante")
    description: str = Field(description="Critério claro para desbloqueio")
    icon: str = Field(description="Emoji ou ícone representativo")
    category: BadgeCategory = Field(description="Categoria temática da conquista")


class LevelProgress(BaseModel):
    """Fotografia detalhada do nível atual e progresso rumo ao próximo patamar."""

    level: int
    title: str
    current_xp: int
    current_tier_floor_xp: int
    next_level_xp: int
    xp_in_current_level: int
    xp_needed_for_next_level: int
    progress_pct: float = Field(ge=0.0, le=100.0)


class GoalStatus(BaseModel):
    """Estado calculado da meta com prazo (termômetro temporal da trilha)."""

    has_goal: bool = False
    goal_label: Optional[str] = None
    target_days: Optional[int] = None
    deadline_at: Optional[datetime] = None
    days_remaining: Optional[int] = None
    is_overdue: bool = False
    is_completed: bool = False
    completed_on_time: Optional[bool] = None
    progress_pct: float = 0.0
    recommended_topics_per_day: Optional[float] = None
    status_label: str = "Sem prazo definido"


class GamificationEvent(BaseModel):
    """Resumo das recompensas e evoluções disparadas por uma ação do estudante."""

    xp_gained: int = 0
    xp_breakdown: List[str] = Field(default_factory=list)
    leveled_up: bool = False
    previous_level: int = 1
    new_level: int = 1
    new_title: str = "Iniciante"
    streak_updated: bool = False
    current_streak: int = 0
    newly_unlocked_badges: List[BadgeDefinition] = Field(default_factory=list)

    @property
    def has_rewards(self) -> bool:
        """Indica se houve ganho de XP, subida de nível ou nova conquista."""
        return bool(self.xp_gained > 0 or self.leveled_up or self.newly_unlocked_badges)


# Catálogo unificado de conquistas organizado em 6 categorias
BADGE_CATALOG: Tuple[BadgeDefinition, ...] = (
    # 1. Início da Jornada (Onboarding)
    BadgeDefinition(
        id="adquirindo_conhecimento",
        title="Adquirindo Conhecimento",
        description="Iniciou sua primeira trilha personalizada de estudos.",
        icon="🌱",
        category=BadgeCategory.ONBOARDING,
    ),
    # 2. Escala de Tópicos
    BadgeDefinition(
        id="primeiro_dominio",
        title="Primeiro Domínio",
        description="Dominou seu 1º tópico com aprovação no Active Recall (>= 70%).",
        icon="🎯",
        category=BadgeCategory.SCALE,
    ),
    BadgeDefinition(
        id="base_solida",
        title="Base Sólida",
        description="Dominou 5 tópicos construindo alicerces consistentes.",
        icon="🧱",
        category=BadgeCategory.SCALE,
    ),
    BadgeDefinition(
        id="mente_afiada",
        title="Mente Afiada",
        description="Dominou 10 tópicos ao longo da sua jornada.",
        icon="🧠",
        category=BadgeCategory.SCALE,
    ),
    BadgeDefinition(
        id="erudito_pratico",
        title="Erudito Prático",
        description="Alcançou a marca expressiva de 25 tópicos dominados.",
        icon="🏛️",
        category=BadgeCategory.SCALE,
    ),
    # 3. Evolução & Prática
    BadgeDefinition(
        id="salto_de_dominio",
        title="Salto de Domínio",
        description="Evoluiu de nível de conhecimento ou saltou +20 pontos entre tentativas até dominar.",
        icon="🚀",
        category=BadgeCategory.PRACTICE,
    ),
    BadgeDefinition(
        id="maestria_impecavel",
        title="Maestria Impecável",
        description="Dominou um tópico com nota igual ou superior a 95%.",
        icon="💎",
        category=BadgeCategory.PRACTICE,
    ),
    BadgeDefinition(
        id="mao_na_massa",
        title="Mão na Massa",
        description="Concluiu 100% das missões práticas de um Laboratório Guiado.",
        icon="🛠️",
        category=BadgeCategory.PRACTICE,
    ),
    BadgeDefinition(
        id="cacador_de_bugs",
        title="Caçador de Bugs",
        description="Investigou um erro real no Assistente de Debugging e dominou o tópico.",
        icon="🐛",
        category=BadgeCategory.PRACTICE,
    ),
    # 4. Sequência (Streaks)
    BadgeDefinition(
        id="faisca_inicial",
        title="Faísca Inicial",
        description="Manteve 3 dias seguidos de ofensiva diária.",
        icon="🔥",
        category=BadgeCategory.STREAK,
    ),
    BadgeDefinition(
        id="foco_10_dias",
        title="Foco de 10 Dias",
        description="Alcançou 10 dias consecutivos de estudo ou revisão.",
        icon="⚡",
        category=BadgeCategory.STREAK,
    ),
    BadgeDefinition(
        id="disciplina_50_dias",
        title="Disciplina de 50 Dias",
        description="Sustentou 50 dias ininterruptos de consistência.",
        icon="🛡️",
        category=BadgeCategory.STREAK,
    ),
    BadgeDefinition(
        id="lenda_100_dias",
        title="Lenda dos 100 Dias",
        description="Atingiu 100 dias seguidos de hábito de aprendizado.",
        icon="👑",
        category=BadgeCategory.STREAK,
    ),
    # 5. Metas & Trilhas
    BadgeDefinition(
        id="sprint_vencida",
        title="Sprint Vencida",
        description="Concluiu 100% de uma trilha com meta curta (até 10 dias) dentro do prazo.",
        icon="⏱️",
        category=BadgeCategory.GOALS,
    ),
    BadgeDefinition(
        id="missao_cumprida",
        title="Missão Cumprida",
        description="Concluiu 100% de uma trilha antes do prazo final da meta.",
        icon="🏁",
        category=BadgeCategory.GOALS,
    ),
    BadgeDefinition(
        id="trilha_completa",
        title="Trilha Completa",
        description="Dominou 100% de todos os tópicos de uma trilha de estudos.",
        icon="🏆",
        category=BadgeCategory.GOALS,
    ),
    # 6. Retenção (SRS)
    BadgeDefinition(
        id="memoria_blindada",
        title="Memória Blindada",
        description="Completou 10 revisões espaçadas (SRS) fortalecendo a memória de longo prazo.",
        icon="🔒",
        category=BadgeCategory.RETENTION,
    ),
)

BADGE_BY_ID: Dict[str, BadgeDefinition] = {b.id: b for b in BADGE_CATALOG}

_KNOWLEDGE_RANK: Dict[KnowledgeLevel, int] = {
    KnowledgeLevel.BEGINNER: 1,
    KnowledgeLevel.INTERMEDIATE: 2,
    KnowledgeLevel.ADVANCED: 3,
}


class GamificationEngine:
    """Orquestrador determinístico de XP, níveis, ofensivas, metas e conquistas."""

    # Economia de XP ("Mão na Massa")
    XP_PER_LAB_MISSION: int = 15
    XP_TOPIC_FIRST_MASTERY: int = 100
    XP_EXCELLENCE_BONUS: int = 25

    MASTERY_THRESHOLD: float = 70.0
    EXCELLENCE_THRESHOLD: float = 90.0
    IMPECCABLE_THRESHOLD: float = 95.0
    MASTERY_LEAP_MIN_DELTA: float = 20.0
    SPRINT_MAX_DAYS: int = 10
    SRS_BADGE_TARGET: int = 10

    # Escada de níveis: (level, piso_xp, título)
    LEVEL_TIERS: Tuple[Tuple[int, int, str], ...] = (
        (1, 0, "Iniciante"),
        (2, 150, "Explorador"),
        (3, 400, "Praticante"),
        (4, 800, "Construtor"),
        (5, 1400, "Especialista"),
        (6, 2200, "Mestre"),
    )
    MASTER_EXTRA_LEVEL_STEP: int = 1000

    @staticmethod
    def _local_today() -> date:
        """Retorna a data civil no fuso local do estudante."""
        return datetime.now().astimezone().date()

    @staticmethod
    def _utc_now() -> datetime:
        """Retorna o instante atual em UTC."""
        return datetime.now(timezone.utc)

    @staticmethod
    def _ensure_utc(dt: datetime) -> datetime:
        """Normaliza datetimes ingênuos ou com fuso para UTC."""
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    @classmethod
    def calculate_level_progress(cls, xp: int) -> LevelProgress:
        """Calcula nível, título e percentual da barra de progresso para um total de XP."""
        safe_xp = max(0, xp)

        # Acima do piso de Mestre (Nível 6 = 2200 XP), cada +1000 XP sobe um nível mantendo título Mestre
        _, master_floor, master_title = cls.LEVEL_TIERS[-1]
        if safe_xp >= master_floor:
            extra_xp = safe_xp - master_floor
            extra_levels = extra_xp // cls.MASTER_EXTRA_LEVEL_STEP
            level = 6 + extra_levels
            tier_floor = master_floor + (extra_levels * cls.MASTER_EXTRA_LEVEL_STEP)
            next_xp = tier_floor + cls.MASTER_EXTRA_LEVEL_STEP
            in_level = safe_xp - tier_floor
            span = cls.MASTER_EXTRA_LEVEL_STEP
            pct = round((in_level / span) * 100.0, 1)
            return LevelProgress(
                level=level,
                title=master_title,
                current_xp=safe_xp,
                current_tier_floor_xp=tier_floor,
                next_level_xp=next_xp,
                xp_in_current_level=in_level,
                xp_needed_for_next_level=next_xp - safe_xp,
                progress_pct=pct,
            )

        current_idx = 0
        for idx, (_, floor_xp, _) in enumerate(cls.LEVEL_TIERS):
            if safe_xp >= floor_xp:
                current_idx = idx
            else:
                break

        level, tier_floor, title = cls.LEVEL_TIERS[current_idx]
        _, next_xp, _ = cls.LEVEL_TIERS[current_idx + 1]
        span = max(1, next_xp - tier_floor)
        in_level = safe_xp - tier_floor
        pct = round(min(100.0, (in_level / span) * 100.0), 1)

        return LevelProgress(
            level=level,
            title=title,
            current_xp=safe_xp,
            current_tier_floor_xp=tier_floor,
            next_level_xp=next_xp,
            xp_in_current_level=in_level,
            xp_needed_for_next_level=max(0, next_xp - safe_xp),
            progress_pct=pct,
        )

    @classmethod
    def sync_level(cls, student: StudentProfile) -> Tuple[bool, int, int, str]:
        """Sincroniza `level` e `level_title` do estudante com seu `xp` atual."""
        prev_level = student.level
        progress = cls.calculate_level_progress(student.xp)
        student.level = progress.level
        student.level_title = progress.title
        return progress.level > prev_level, prev_level, progress.level, progress.title

    @classmethod
    def get_effective_streak(
        cls,
        student: StudentProfile,
        reference_date: Optional[date] = None,
    ) -> int:
        """
        Retorna a ofensiva ativa para exibição (zera visualmente se passou mais de 1 dia sem estudo).
        Não muta o perfil até que ocorra nova atividade.
        """
        if not student.last_study_date or student.current_streak <= 0:
            return 0
        today = reference_date or cls._local_today()
        if (today - student.last_study_date).days > 1:
            return 0
        return student.current_streak

    @classmethod
    def update_streak(
        cls,
        student: StudentProfile,
        reference_date: Optional[date] = None,
    ) -> bool:
        """
        Registra atividade diária (estudo inédito ou revisão SRS) e atualiza a ofensiva.
        Retorna True se o contador diário avançou ou iniciou hoje.
        """
        today = reference_date or cls._local_today()

        if student.last_study_date is None:
            student.current_streak = 1
            student.longest_streak = max(student.longest_streak, 1)
            student.last_study_date = today
            return True

        delta_days = (today - student.last_study_date).days
        if delta_days == 0:
            # Já estudou hoje: mantém streak sem duplicar
            student.longest_streak = max(student.longest_streak, student.current_streak)
            return False

        if delta_days == 1:
            student.current_streak += 1
        elif delta_days > 1:
            # Quebrou a sequência: recomeça em 1 hoje
            student.current_streak = 1
        else:
            # Data anterior ao último registro (ajuste de relógio): ignora mutação regressiva
            return False

        student.last_study_date = today
        student.longest_streak = max(student.longest_streak, student.current_streak)
        return True

    @classmethod
    def set_goal(
        cls,
        curriculum: Curriculum,
        target_days: int,
        goal_label: Optional[str] = None,
        now: Optional[datetime] = None,
    ) -> GoalStatus:
        """Define ou edita a meta com prazo de uma trilha de estudos."""
        if target_days < 1:
            raise ValueError("O prazo da meta deve ser de pelo menos 1 dia.")

        ref_now = cls._ensure_utc(now) if now else cls._utc_now()
        clean_label = (goal_label or "").strip() or f"Concluir {curriculum.subject} em {target_days} dias"

        # Concede até o fim do último dia (23:59:59 UTC) para não penalizar horários quebrados
        deadline = (ref_now + timedelta(days=target_days)).replace(
            hour=23, minute=59, second=59, microsecond=0
        )

        curriculum.goal_label = clean_label
        curriculum.target_days = target_days
        curriculum.goal_created_at = ref_now
        curriculum.deadline_at = deadline

        # Se a trilha já estava 100% dominada, registra conclusão
        if curriculum.topics and all(t.status == TopicStatus.MASTERED for t in curriculum.topics):
            curriculum.goal_completed_at = curriculum.goal_completed_at or ref_now

        return cls.get_goal_status(curriculum, now=ref_now)

    @staticmethod
    def clear_goal(curriculum: Curriculum) -> None:
        """Remove a meta de prazo associada à trilha."""
        curriculum.goal_label = None
        curriculum.target_days = None
        curriculum.goal_created_at = None
        curriculum.deadline_at = None

    @classmethod
    def get_goal_status(
        cls,
        curriculum: Curriculum,
        now: Optional[datetime] = None,
    ) -> GoalStatus:
        """Calcula o status atual do prazo, dias restantes e ritmo sugerido."""
        progress_pct = curriculum.calculate_overall_progress()
        is_completed = bool(curriculum.topics) and all(
            t.status == TopicStatus.MASTERED for t in curriculum.topics
        )

        if not curriculum.deadline_at or not curriculum.target_days:
            return GoalStatus(
                has_goal=False,
                is_completed=is_completed,
                progress_pct=progress_pct,
                status_label="Concluída! 🏆" if is_completed else "Sem prazo definido",
            )

        ref_now = cls._ensure_utc(now) if now else cls._utc_now()
        deadline = cls._ensure_utc(curriculum.deadline_at)

        if is_completed:
            completed_at = cls._ensure_utc(curriculum.goal_completed_at) if curriculum.goal_completed_at else ref_now
            on_time = completed_at <= deadline
            label = "Concluída no prazo! 🏁" if on_time else "Concluída após o prazo ✅"
            return GoalStatus(
                has_goal=True,
                goal_label=curriculum.goal_label,
                target_days=curriculum.target_days,
                deadline_at=deadline,
                days_remaining=0,
                is_overdue=not on_time,
                is_completed=True,
                completed_on_time=on_time,
                progress_pct=progress_pct,
                recommended_topics_per_day=0.0,
                status_label=label,
            )

        remaining_seconds = (deadline - ref_now).total_seconds()
        is_overdue = remaining_seconds < 0
        days_remaining = (
            ceil(remaining_seconds / 86400.0)
            if remaining_seconds > 0
            else -ceil(abs(remaining_seconds) / 86400.0)
        )

        pending_topics = sum(1 for t in curriculum.topics if t.status != TopicStatus.MASTERED)
        effective_days = max(1, days_remaining) if not is_overdue else 1
        rec_per_day = round(pending_topics / effective_days, 1) if pending_topics > 0 else 0.0

        if is_overdue:
            overdue_days = abs(days_remaining) or 1
            status_label = f"Prazo expirado há {overdue_days}d ⚠️"
        elif days_remaining <= 1:
            status_label = "Reta final: último dia! ⚡"
        else:
            status_label = f"No prazo ({days_remaining}d restantes)"

        return GoalStatus(
            has_goal=True,
            goal_label=curriculum.goal_label,
            target_days=curriculum.target_days,
            deadline_at=deadline,
            days_remaining=days_remaining,
            is_overdue=is_overdue,
            is_completed=False,
            completed_on_time=None,
            progress_pct=progress_pct,
            recommended_topics_per_day=rec_per_day,
            status_label=status_label,
        )

    @classmethod
    def _unlock_badge(
        cls,
        student: StudentProfile,
        badge_id: str,
        curriculum_id: Optional[str] = None,
        now: Optional[datetime] = None,
    ) -> Optional[BadgeDefinition]:
        """Desbloqueia uma conquista caso ainda não pertença ao estudante."""
        if student.has_badge(badge_id):
            return None
        definition = BADGE_BY_ID.get(badge_id)
        if not definition:
            return None
        student.unlocked_badges.append(
            UnlockedBadge(
                badge_id=badge_id,
                unlocked_at=cls._ensure_utc(now) if now else cls._utc_now(),
                curriculum_id=curriculum_id,
            )
        )
        return definition

    @classmethod
    def evaluate_badges(
        cls,
        student: StudentProfile,
        curriculum: Optional[Curriculum] = None,
        topic: Optional[Topic] = None,
        latest_score: Optional[float] = None,
        is_topic_mastered: bool = False,
        made_mastery_leap: bool = False,
        now: Optional[datetime] = None,
    ) -> List[BadgeDefinition]:
        """Avalia todas as regras de conquistas e retorna apenas as recém-desbloqueadas."""
        unlocked: List[BadgeDefinition] = []
        curr_id = curriculum.id if curriculum else None

        def try_unlock(b_id: str) -> None:
            badge = cls._unlock_badge(student, b_id, curriculum_id=curr_id, now=now)
            if badge:
                unlocked.append(badge)

        # 1. Onboarding
        try_unlock("adquirindo_conhecimento")

        # 2. Escala de Tópicos
        mastered_in_curr = (
            sum(
                1
                for t in curriculum.topics
                if t.status == TopicStatus.MASTERED
                or (topic is not None and t.id == topic.id and is_topic_mastered)
            )
            if curriculum
            else 0
        )
        total_mastered = max(student.total_topics_mastered, mastered_in_curr)
        student.total_topics_mastered = total_mastered

        if total_mastered >= 1:
            try_unlock("primeiro_dominio")
        if total_mastered >= 5:
            try_unlock("base_solida")
        if total_mastered >= 10:
            try_unlock("mente_afiada")
        if total_mastered >= 25:
            try_unlock("erudito_pratico")

        # 3. Evolução & Prática
        if made_mastery_leap:
            try_unlock("salto_de_dominio")

        if topic is not None:
            score_check = latest_score if latest_score is not None else topic.mastery_score
            if is_topic_mastered and score_check >= cls.IMPECCABLE_THRESHOLD:
                try_unlock("maestria_impecavel")

            if (
                topic.total_lab_missions > 0
                and topic.completed_lab_steps >= topic.total_lab_missions
            ):
                try_unlock("mao_na_massa")

            if is_topic_mastered and topic.used_debug_assistant:
                try_unlock("cacador_de_bugs")

        # 4. Sequência (Streaks)
        best_streak = max(student.current_streak, student.longest_streak)
        if best_streak >= 3:
            try_unlock("faisca_inicial")
        if best_streak >= 10:
            try_unlock("foco_10_dias")
        if best_streak >= 50:
            try_unlock("disciplina_50_dias")
        if best_streak >= 100:
            try_unlock("lenda_100_dias")

        # 5. Metas & Trilhas
        if curriculum and curriculum.topics:
            all_topics_mastered = all(
                t.status == TopicStatus.MASTERED
                or (topic is not None and t.id == topic.id and is_topic_mastered)
                for t in curriculum.topics
            )
            if all_topics_mastered:
                try_unlock("trilha_completa")

                if curriculum.deadline_at and curriculum.target_days:
                    ref_now = cls._ensure_utc(now) if now else cls._utc_now()
                    completed_at = (
                        cls._ensure_utc(curriculum.goal_completed_at)
                        if curriculum.goal_completed_at
                        else ref_now
                    )
                    deadline = cls._ensure_utc(curriculum.deadline_at)
                    if completed_at <= deadline:
                        try_unlock("missao_cumprida")
                        if curriculum.target_days <= cls.SPRINT_MAX_DAYS:
                            try_unlock("sprint_vencida")

        # 6. Retenção (SRS)
        if student.total_srs_reviews >= cls.SRS_BADGE_TARGET:
            try_unlock("memoria_blindada")

        return unlocked

    @classmethod
    def record_onboarding(
        cls,
        student: StudentProfile,
        curriculum: Optional[Curriculum] = None,
        now: Optional[datetime] = None,
    ) -> GamificationEvent:
        """Registra a criação da primeira trilha desbloqueando a conquista inicial."""
        cls.sync_level(student)
        badges = cls.evaluate_badges(student=student, curriculum=curriculum, now=now)
        return GamificationEvent(
            xp_gained=0,
            leveled_up=False,
            previous_level=student.level,
            new_level=student.level,
            new_title=student.level_title,
            streak_updated=False,
            current_streak=student.current_streak,
            newly_unlocked_badges=badges,
        )

    @staticmethod
    def record_debug_usage(topic: Topic) -> None:
        """Marca que o estudante investigou um erro real neste tópico (0 XP; habilita Caçador de Bugs)."""
        topic.used_debug_assistant = True

    @classmethod
    def award_lab_mission_xp(
        cls,
        student: StudentProfile,
        topic: Topic,
        curriculum: Optional[Curriculum] = None,
        reference_date: Optional[date] = None,
        now: Optional[datetime] = None,
    ) -> GamificationEvent:
        """
        Concede +15 XP por missão inédita concluída no Laboratório Guiado.
        Missões repetidas não geram XP adicional.
        """
        unrewarded_steps = max(0, topic.completed_lab_steps - topic.rewarded_lab_steps)
        xp_gained = unrewarded_steps * cls.XP_PER_LAB_MISSION
        breakdown: List[str] = []

        if unrewarded_steps > 0:
            topic.rewarded_lab_steps = topic.completed_lab_steps
            student.xp += xp_gained
            plural = "missões práticas inéditas" if unrewarded_steps > 1 else "missão prática inédita"
            breakdown.append(f"+{xp_gained} XP ({unrewarded_steps} {plural} no Laboratório)")

        streak_changed = cls.update_streak(student, reference_date=reference_date) if unrewarded_steps > 0 else False
        leveled_up, prev_lvl, new_lvl, new_title = cls.sync_level(student)
        badges = cls.evaluate_badges(
            student=student,
            curriculum=curriculum,
            topic=topic,
            is_topic_mastered=(topic.status == TopicStatus.MASTERED),
            now=now,
        )

        return GamificationEvent(
            xp_gained=xp_gained,
            xp_breakdown=breakdown,
            leveled_up=leveled_up,
            previous_level=prev_lvl,
            new_level=new_lvl,
            new_title=new_title,
            streak_updated=streak_changed,
            current_streak=student.current_streak,
            newly_unlocked_badges=badges,
        )

    @classmethod
    def process_topic_evaluation(
        cls,
        student: StudentProfile,
        curriculum: Curriculum,
        topic: Topic,
        evaluation: ActiveRecallEvaluation,
        was_mastered_before: bool = False,
        previous_score: float = 0.0,
        reference_date: Optional[date] = None,
        now: Optional[datetime] = None,
    ) -> GamificationEvent:
        """
        Processa recompensas de uma sessão de Active Recall:
        - +15 XP por eventual missão de laboratório pendente de recompensa;
        - +100 XP na 1ª vez que o tópico atinge domínio (>= 70%);
        - +25 XP de bônus único de excelência para nota >= 90%;
        - Atualização da ofensiva diária (Streak), nível, meta temporal e conquistas.
        """
        ref_now = cls._ensure_utc(now) if now else cls._utc_now()
        xp_gained = 0
        breakdown: List[str] = []

        # Garante recompensa de missões práticas caso ainda não tenham sido contabilizadas
        unrewarded_lab = max(0, topic.completed_lab_steps - topic.rewarded_lab_steps)
        if unrewarded_lab > 0:
            lab_xp = unrewarded_lab * cls.XP_PER_LAB_MISSION
            topic.rewarded_lab_steps = topic.completed_lab_steps
            xp_gained += lab_xp
            breakdown.append(f"+{lab_xp} XP ({unrewarded_lab} missão(ões) de Laboratório)")

        is_mastered_now = (
            was_mastered_before
            or topic.status == TopicStatus.MASTERED
            or evaluation.is_passing
            or evaluation.score >= cls.MASTERY_THRESHOLD
        )

        if is_mastered_now:
            if not was_mastered_before and not topic.mastery_xp_awarded:
                topic.mastery_xp_awarded = True
                xp_gained += cls.XP_TOPIC_FIRST_MASTERY
                student.total_topics_mastered += 1
                breakdown.append(f"+{cls.XP_TOPIC_FIRST_MASTERY} XP (1º domínio do tópico)")

            if evaluation.score >= cls.EXCELLENCE_THRESHOLD and not topic.excellence_xp_awarded:
                topic.excellence_xp_awarded = True
                xp_gained += cls.XP_EXCELLENCE_BONUS
                breakdown.append(f"+{cls.XP_EXCELLENCE_BONUS} XP (Bônus de Excelência >= 90%)")

        student.xp += xp_gained
        streak_changed = cls.update_streak(student, reference_date=reference_date)
        leveled_up, prev_lvl, new_lvl, new_title = cls.sync_level(student)

        # Verifica conclusão de 100% da trilha e evolução de nível pedagógico
        made_leap = False
        if is_mastered_now and previous_score > 0.0:
            if (evaluation.score - previous_score) >= cls.MASTERY_LEAP_MIN_DELTA:
                made_leap = True

        # Também checa histórico do tópico caso existam múltiplas tentativas anteriores
        if is_mastered_now and len(topic.recall_history) >= 2:
            earliest_min = min(r.score for r in topic.recall_history[:-1])
            if (evaluation.score - earliest_min) >= cls.MASTERY_LEAP_MIN_DELTA:
                made_leap = True

        all_mastered = bool(curriculum.topics) and all(
            t.status == TopicStatus.MASTERED or (t.id == topic.id and is_mastered_now)
            for t in curriculum.topics
        )
        if all_mastered:
            if curriculum.goal_completed_at is None:
                curriculum.goal_completed_at = ref_now
            if _KNOWLEDGE_RANK[student.target_level] > _KNOWLEDGE_RANK[student.current_level]:
                student.current_level = student.target_level
                made_leap = True

        badges = cls.evaluate_badges(
            student=student,
            curriculum=curriculum,
            topic=topic,
            latest_score=evaluation.score,
            is_topic_mastered=is_mastered_now,
            made_mastery_leap=made_leap,
            now=ref_now,
        )

        return GamificationEvent(
            xp_gained=xp_gained,
            xp_breakdown=breakdown,
            leveled_up=leveled_up,
            previous_level=prev_lvl,
            new_level=new_lvl,
            new_title=new_title,
            streak_updated=streak_changed,
            current_streak=student.current_streak,
            newly_unlocked_badges=badges,
        )

    @classmethod
    def record_srs_review(
        cls,
        student: StudentProfile,
        curriculum: Optional[Curriculum] = None,
        reference_date: Optional[date] = None,
        now: Optional[datetime] = None,
    ) -> GamificationEvent:
        """
        Registra conclusão de uma revisão espaçada (SRS):
        - Concede estritamente 0 XP (separação entre Hábito e Prática inédita);
        - Mantém/incrementa a ofensiva diária (Streak);
        - Contabiliza revisão para a conquista 'Memória Blindada'.
        """
        student.total_srs_reviews += 1
        streak_changed = cls.update_streak(student, reference_date=reference_date)
        cls.sync_level(student)
        badges = cls.evaluate_badges(student=student, curriculum=curriculum, now=now)

        return GamificationEvent(
            xp_gained=0,
            xp_breakdown=[],
            leveled_up=False,
            previous_level=student.level,
            new_level=student.level,
            new_title=student.level_title,
            streak_updated=streak_changed,
            current_streak=student.current_streak,
            newly_unlocked_badges=badges,
        )
