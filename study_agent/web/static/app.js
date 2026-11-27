/* Frontend SPA do AI Study Agent — integrado ao FastAPI local */

const state = {
  dashboard: null,
  selectedTopicId: null,
  currentExplanation: "",
  currentRecallQuestion: null,
  currentSrsTopicId: null,
  currentSrsQuestion: null,
  onboardingQuestions: [],
};

const CATEGORY_LABELS = {
  onboarding: "🌱 Início da Jornada",
  scale: "📈 Escala de Tópicos",
  practice: "🛠️ Evolução & Prática",
  streak: "🔥 Consistência & Ofensiva",
  goals: "🏁 Metas & Trilhas",
  retention: "🔒 Retenção & Memória",
};

function escapeHtml(raw) {
  const div = document.createElement("div");
  div.textContent = raw ?? "";
  return div.innerHTML;
}

function renderMarkdown(mdText) {
  if (!mdText) return "";
  if (window.marked && typeof window.marked.parse === "function") {
    return window.marked.parse(mdText);
  }
  return `<pre class="whitespace-pre-wrap">${escapeHtml(mdText)}</pre>`;
}

function setLoading(isLoading, message = "Consultando o Mentor IA...") {
  const loader = document.getElementById("global-loader");
  const textEl = document.getElementById("global-loader-text");
  if (textEl) textEl.textContent = message;
  loader.classList.toggle("hidden", !isLoading);
}

function showToast(title, bodyHtml, variant = "info") {
  const container = document.getElementById("toast-container");
  const palette = {
    info: "border-cyan-500/50 bg-slate-900/95 text-cyan-200",
    success: "border-emerald-500/60 bg-slate-900/95 text-emerald-200",
    reward: "border-amber-400/70 bg-slate-900/95 text-amber-200",
    error: "border-rose-500/60 bg-slate-900/95 text-rose-200",
  };
  const card = document.createElement("div");
  card.className = `toast-enter pointer-events-auto rounded-2xl border p-4 shadow-2xl backdrop-blur-md ${palette[variant] || palette.info}`;
  card.innerHTML = `
    <div class="flex items-start justify-between gap-2">
      <div class="font-bold text-sm">${escapeHtml(title)}</div>
      <button class="text-slate-400 hover:text-white text-sm leading-none">&times;</button>
    </div>
    <div class="text-xs text-slate-300 mt-1.5 space-y-1">${bodyHtml}</div>
  `;
  card.querySelector("button").onclick = () => card.remove();
  container.appendChild(card);
  setTimeout(() => {
    if (card.parentElement) card.remove();
  }, 6500);
}

function celebrateGamificationEvent(event) {
  if (!event) return;
  const parts = [];
  if (event.xp_gained > 0 && Array.isArray(event.xp_breakdown)) {
    event.xp_breakdown.forEach((line) => {
      parts.push(`<div class="text-emerald-300 font-semibold">⚡ ${escapeHtml(line)}</div>`);
    });
  }
  if (event.leveled_up) {
    parts.push(
      `<div class="text-amber-300 font-bold">🎉 LEVEL UP! Nível ${event.previous_level} ➔ Nível ${event.new_level} (${escapeHtml(event.new_title)})</div>`
    );
  }
  if (event.streak_updated) {
    parts.push(`<div class="text-orange-300">🔥 Ofensiva Diária: <strong>${event.current_streak}d</strong>!</div>`);
  }
  if (Array.isArray(event.newly_unlocked_badges) && event.newly_unlocked_badges.length > 0) {
    event.newly_unlocked_badges.forEach((b) => {
      parts.push(
        `<div class="text-fuchsia-300 font-semibold">🏅 Nova Conquista: ${escapeHtml(b.icon)} ${escapeHtml(b.title)}</div>`
      );
    });
  }
  if (parts.length > 0) {
    showToast("🌟 Evolução Registrada!", parts.join(""), "reward");
  }
}

async function apiRequest(url, options = {}, loadingMessage = null) {
  if (loadingMessage) setLoading(true, loadingMessage);
  try {
    const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
    const response = await fetch(url, { ...options, headers });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(data.detail || "Ocorreu um erro ao processar a requisição.");
    }
    return data;
  } finally {
    if (loadingMessage) setLoading(false);
  }
}

function switchTab(tabName) {
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    const isActive = btn.dataset.tab === tabName;
    btn.classList.toggle("active", isActive);
    btn.classList.toggle("border-cyan-400", isActive);
    btn.classList.toggle("text-cyan-300", isActive);
    btn.classList.toggle("border-transparent", !isActive);
    btn.classList.toggle("text-slate-400", !isActive);
  });
  document.querySelectorAll(".tab-panel").forEach((panel) => {
    panel.classList.toggle("hidden", panel.id !== `tab-${tabName}`);
  });
  if (tabName === "overview" && state.dashboard?.mermaid_code) {
    renderMermaidDiagram(state.dashboard.mermaid_code);
  }
}

async function renderMermaidDiagram(code) {
  const container = document.getElementById("mermaid-container");
  if (!container || !code) return;

  if (!window.mermaid) {
    container.innerHTML = `<pre class="text-xs text-slate-300 whitespace-pre-wrap">${escapeHtml(code)}</pre>`;
    return;
  }

  try {
    const graphId = `mermaid-svg-${Date.now()}`;
    const { svg } = await window.mermaid.render(graphId, code);
    container.innerHTML = svg;
  } catch (_err) {
    container.innerHTML = `<pre class="text-xs text-slate-300 whitespace-pre-wrap">${escapeHtml(code)}</pre>`;
  }
}

function applyDashboard(dash) {
  state.dashboard = dash;

  const emptyState = document.getElementById("empty-state");
  const root = document.getElementById("dashboard-root");
  const mainTabs = document.getElementById("main-tabs");
  const switcher = document.getElementById("student-switcher");
  const exportBtn = document.getElementById("btn-export");

  // Renderiza seletor de estudantes
  if (Array.isArray(dash.students) && dash.students.length > 0) {
    switcher.classList.remove("hidden");
    switcher.innerHTML = dash.students
      .map(
        (s) =>
          `<option value="${escapeHtml(s.id)}" ${s.is_active ? "selected" : ""}>👤 ${escapeHtml(s.name)} — ${escapeHtml(s.target_subject)} (Nv.${s.level})</option>`
      )
      .join("");
  } else {
    switcher.classList.add("hidden");
  }

  if (!dash.has_active_session) {
    emptyState.classList.remove("hidden");
    root.classList.add("hidden");
    mainTabs.classList.add("hidden");
    exportBtn.classList.add("hidden");
    return;
  }

  emptyState.classList.add("hidden");
  root.classList.remove("hidden");
  mainTabs.classList.remove("hidden");
  exportBtn.classList.remove("hidden");

  const { student, curriculum, level_progress: lvl, goal_status: goal, srs_summary: srs } = dash;

  // Hero 1: XP & Level
  document.getElementById("hero-level-title").textContent = `Nv. ${lvl.level} • ${lvl.title}`;
  document.getElementById("hero-xp-numbers").textContent = `${lvl.current_xp} / ${lvl.next_level_xp} XP`;
  document.getElementById("hero-xp-pct").textContent = `${lvl.progress_pct}%`;
  document.getElementById("hero-xp-bar").style.width = `${Math.min(100, lvl.progress_pct)}%`;
  document.getElementById("hero-student-summary").textContent = `${student.name} • ${student.current_level} ➔ ${student.target_level}`;

  // Hero 2: Streak
  const streakDays = dash.effective_streak || 0;
  document.getElementById("hero-streak-days").textContent = `${streakDays} ${streakDays === 1 ? "dia" : "dias"}`;
  document.getElementById("hero-streak-best").textContent = `recorde: ${student.longest_streak}d`;
  document.getElementById("hero-streak-flame").textContent = streakDays > 0 ? "🔥" : "🕯️";
  document.getElementById("hero-streak-hint").textContent =
    streakDays > 0
      ? "Ofensiva ativa! Continue amanhã com estudo inédito ou revisão rápida."
      : "Sua chama aguarda o estudo ou revisão de hoje!";

  // Hero 3: Goal & Track Progress
  document.getElementById("hero-goal-title").textContent = goal.has_goal ? goal.goal_label : "Sem prazo definido";
  document.getElementById("hero-goal-status").textContent = goal.status_label;
  document.getElementById("hero-track-pct").textContent = `${dash.overall_progress_pct}%`;
  document.getElementById("hero-track-bar").style.width = `${Math.min(100, dash.overall_progress_pct)}%`;
  document.getElementById("hero-goal-pace").textContent =
    goal.has_goal && goal.recommended_topics_per_day
      ? `Ritmo sugerido: ~${goal.recommended_topics_per_day} tópico(s)/dia`
      : `Trilha com ${curriculum.topics.length} tópicos mapeados`;

  // Hero 4 & Nav Badge: SRS
  const dueCount = srs.due_now_count || 0;
  const navSrsBadge = document.getElementById("nav-srs-badge");
  navSrsBadge.textContent = String(dueCount);
  navSrsBadge.classList.toggle("hidden", dueCount === 0);

  document.getElementById("hero-srs-headline").textContent =
    dueCount > 0 ? `${dueCount} pendente(s) agora` : srs.total_mastered > 0 ? "Memória em dia! ✅" : "Aguardando 1º domínio";
  document.getElementById("hero-srs-sub").textContent = `🔒 Memória Blindada: ${Math.min(10, student.total_srs_reviews)}/10 revisões`;

  // Overview Tab
  document.getElementById("overview-subject-pill").textContent = curriculum.subject;
  document.getElementById("overview-description").textContent = curriculum.overview;
  renderTopicsList(curriculum.topics);
  renderMermaidDiagram(dash.mermaid_code);

  // Study Tab Topic Selector
  populateStudyTopicSelector(curriculum.topics);

  // SRS Tab
  renderSrsQueue(dash.due_topics, srs);

  // Badges Tab
  renderBadgesShowcase(dash.badges);
}

function renderTopicsList(topics) {
  const container = document.getElementById("topics-list");
  const badgeMeta = {
    mastered: { label: "✅ Dominado", cls: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30" },
    in_progress: { label: "⏳ Em Estudo", cls: "bg-amber-500/15 text-amber-300 border-amber-500/30" },
    available: { label: "🔓 Disponível", cls: "bg-cyan-500/15 text-cyan-300 border-cyan-500/30" },
    locked: { label: "🔒 Bloqueado", cls: "bg-slate-800 text-slate-400 border-slate-700" },
  };

  container.innerHTML = topics
    .map((t, idx) => {
      const meta = badgeMeta[t.status] || badgeMeta.locked;
      const isLocked = t.status === "locked";
      const scoreTag = t.mastery_score > 0 ? `<span class="text-xs text-emerald-300 font-semibold">Nota: ${Math.round(t.mastery_score)}%</span>` : "";
      const labTag =
        t.completed_lab_steps > 0
          ? `<span class="text-xs text-fuchsia-300">🧪 Lab: ${t.completed_lab_steps}${t.total_lab_missions ? `/${t.total_lab_missions}` : ""}</span>`
          : "";

      return `
        <div class="rounded-xl border ${isLocked ? "border-slate-800/70 bg-slate-950/40 opacity-65" : "border-slate-800 bg-slate-950/85 hover:border-slate-700"} p-4 transition flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div class="space-y-1">
            <div class="flex flex-wrap items-center gap-2">
              <span class="text-xs font-mono text-slate-500">#${idx + 1}</span>
              <span class="text-[11px] font-semibold px-2.5 py-0.5 rounded-full border ${meta.cls}">${meta.label}</span>
              <h4 class="text-sm font-bold text-white">${escapeHtml(t.title)}</h4>
            </div>
            <p class="text-xs text-slate-400">${escapeHtml(t.description)}</p>
            <div class="flex flex-wrap items-center gap-3 pt-1">
              <span class="text-[11px] text-slate-500">⏱️ ${t.estimated_minutes} min</span>
              ${scoreTag}
              ${labTag}
            </div>
          </div>
          <div class="shrink-0">
            ${
              isLocked
                ? `<span class="text-xs text-slate-500">Requer: ${escapeHtml(t.prerequisites.join(", "))}</span>`
                : `<button data-open-topic="${escapeHtml(t.id)}" class="btn-open-topic px-3.5 py-2 rounded-xl text-xs font-semibold bg-cyan-500/15 hover:bg-cyan-500/25 text-cyan-300 border border-cyan-500/30 transition">
                    Abrir na Sala ➔
                  </button>`
            }
          </div>
        </div>
      `;
    })
    .join("");

  container.querySelectorAll(".btn-open-topic").forEach((btn) => {
    btn.onclick = () => {
      state.selectedTopicId = btn.dataset.openTopic;
      populateStudyTopicSelector(topics);
      switchTab("study");
    };
  });
}

function populateStudyTopicSelector(topics) {
  const select = document.getElementById("study-topic-select");
  const unlocked = topics.filter((t) => t.status !== "locked");

  if (!unlocked.length) {
    select.innerHTML = `<option value="">Nenhum tópico desbloqueado</option>`;
    return;
  }

  const preferred =
    unlocked.find((t) => t.id === state.selectedTopicId) ||
    unlocked.find((t) => t.status === "in_progress" || t.status === "available") ||
    unlocked[0];

  state.selectedTopicId = preferred.id;

  select.innerHTML = unlocked
    .map((t) => {
      const icon = t.status === "mastered" ? "✅" : t.status === "in_progress" ? "⏳" : "🔓";
      return `<option value="${escapeHtml(t.id)}" ${t.id === state.selectedTopicId ? "selected" : ""}>${icon} ${escapeHtml(t.title)} (${t.estimated_minutes} min)</option>`;
    })
    .join("");

  document.getElementById("study-topic-desc").textContent = preferred.description;
}

function renderSrsQueue(dueTopics, srsSummary) {
  const container = document.getElementById("srs-due-list");

  if (!srsSummary || srsSummary.total_mastered === 0) {
    container.innerHTML = `
      <div class="rounded-xl border border-slate-800 bg-slate-950/60 p-6 text-center text-sm text-slate-400">
        Você ainda não possui tópicos dominados para agendar revisões espaçadas. Domine seu primeiro tópico na aba <strong>Sala de Estudo</strong>!
      </div>
    `;
    return;
  }

  if (!dueTopics || dueTopics.length === 0) {
    const nextDate = srsSummary.next_upcoming_at
      ? new Date(srsSummary.next_upcoming_at).toLocaleString("pt-BR")
      : "em breve";
    container.innerHTML = `
      <div class="rounded-xl border border-emerald-500/30 bg-emerald-950/20 p-6 text-center space-y-1">
        <div class="text-2xl">🎉</div>
        <div class="text-base font-bold text-emerald-300">Sua memória está 100% em dia!</div>
        <p class="text-xs text-slate-400">Próxima revisão agendada para: <strong>${escapeHtml(nextDate)}</strong></p>
      </div>
    `;
    return;
  }

  container.innerHTML = dueTopics
    .map(
      (t) => `
      <div class="rounded-xl border border-amber-500/30 bg-slate-950/85 p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h4 class="text-sm font-bold text-white">${escapeHtml(t.title)}</h4>
          <p class="text-xs text-slate-400">EF atual: <strong>${Number(t.easiness_factor).toFixed(2)}</strong> • Intervalo anterior: ${t.interval_days}d • Repetições: ${t.srs_repetitions}</p>
        </div>
        <button data-srs-topic="${escapeHtml(t.id)}" class="btn-start-srs-item px-4 py-2 rounded-xl text-xs font-bold bg-amber-500/20 hover:bg-amber-500/30 text-amber-200 border border-amber-500/40 transition">
          🔄 Revisar Agora
        </button>
      </div>
    `
    )
    .join("");

  container.querySelectorAll(".btn-start-srs-item").forEach((btn) => {
    btn.onclick = () => startSrsReviewItem(btn.dataset.srsTopic);
  });
}

function renderBadgesShowcase(badges) {
  const unlockedCount = badges.filter((b) => b.unlocked).length;
  document.getElementById("nav-badges-count").textContent = `${unlockedCount}/${badges.length}`;
  document.getElementById("badges-header-counter").textContent = `${unlockedCount} / ${badges.length} Conquistadas`;

  const grid = document.getElementById("badges-grid");
  grid.innerHTML = badges
    .map((b) => {
      const catLabel = CATEGORY_LABELS[b.category] || b.category;
      const unlockedDate = b.unlocked_at ? new Date(b.unlocked_at).toLocaleDateString("pt-BR") : "";
      return `
        <div class="rounded-2xl border p-4 transition ${
          b.unlocked
            ? "border-amber-400/50 bg-gradient-to-br from-amber-500/10 to-slate-900 shadow-lg shadow-amber-500/5"
            : "border-slate-800 bg-slate-950/50 opacity-55"
        }">
          <div class="flex items-start justify-between gap-2">
            <div class="text-3xl">${escapeHtml(b.icon)}</div>
            <span class="text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-full ${
              b.unlocked ? "bg-emerald-500/20 text-emerald-300" : "bg-slate-800 text-slate-400"
            }">
              ${b.unlocked ? `✅ ${unlockedDate}` : "🔒 Bloqueada"}
            </span>
          </div>
          <h4 class="text-sm font-bold text-white mt-2">${escapeHtml(b.title)}</h4>
          <p class="text-xs text-slate-400 mt-1 leading-relaxed">${escapeHtml(b.description)}</p>
          <div class="text-[11px] text-cyan-400/80 mt-2.5 font-medium">${escapeHtml(catLabel)}</div>
        </div>
      `;
    })
    .join("");
}

async function startSrsReviewItem(topicId) {
  try {
    const data = await apiRequest(
      "/api/srs/question",
      { method: "POST", body: JSON.stringify({ topic_id: topicId }) },
      "Formulando pergunta rápida de Repetição Espaçada..."
    );
    state.currentSrsTopicId = topicId;
    state.currentSrsQuestion = data.question;

    document.getElementById("srs-active-title").textContent = `Revisando: ${data.topic.title}`;
    document.getElementById("srs-active-meta").textContent = `EF ${Number(data.topic.easiness_factor).toFixed(2)} • Intervalo ${data.topic.interval_days}d`;
    document.getElementById("srs-question-text").textContent = data.question.question;
    document.getElementById("srs-question-hint").textContent = data.question.hint ? `💡 Dica: ${data.question.hint}` : "";
    document.getElementById("srs-answer-input").value = "";
    document.getElementById("srs-result-box").classList.add("hidden");
    document.getElementById("srs-active-card").classList.remove("hidden");
  } catch (err) {
    showToast("Erro ao iniciar revisão", escapeHtml(err.message), "error");
  }
}

function bindEvents() {
  // Tabs
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => switchTab(btn.dataset.tab));
  });

  document.getElementById("btn-hero-srs").onclick = () => switchTab("srs");

  // Student Switcher
  document.getElementById("student-switcher").onchange = async (ev) => {
    try {
      const dash = await apiRequest(
        "/api/students/switch",
        { method: "POST", body: JSON.stringify({ student_id: ev.target.value }) },
        "Alternando sessão ativa..."
      );
      applyDashboard(dash);
      showToast("Sessão Alternada", "Trilha carregada com sucesso!", "success");
    } catch (err) {
      showToast("Erro ao alternar aluno", escapeHtml(err.message), "error");
    }
  };

  // Study Topic Change
  document.getElementById("study-topic-select").onchange = (ev) => {
    state.selectedTopicId = ev.target.value;
    const topic = state.dashboard?.curriculum?.topics?.find((t) => t.id === state.selectedTopicId);
    if (topic) {
      document.getElementById("study-topic-desc").textContent = topic.description;
    }
    document.getElementById("recall-box").classList.add("hidden");
    document.getElementById("recall-result").classList.add("hidden");
  };

  // Explain Styles
  document.querySelectorAll(".btn-explain").forEach((btn) => {
    btn.onclick = async () => {
      if (!state.selectedTopicId) return;
      try {
        const res = await apiRequest(
          "/api/study/explain",
          {
            method: "POST",
            body: JSON.stringify({ topic_id: state.selectedTopicId, style: btn.dataset.style }),
          },
          "O Professor está preparando sua aula personalizada..."
        );
        state.currentExplanation = res.explanation;
        document.getElementById("lesson-placeholder").classList.add("hidden");
        const contentEl = document.getElementById("lesson-content");
        contentEl.innerHTML = renderMarkdown(res.explanation);
        contentEl.classList.remove("hidden");

        const tkWrap = document.getElementById("lesson-takeaways");
        const tkList = document.getElementById("lesson-takeaways-list");
        if (Array.isArray(res.key_takeaways) && res.key_takeaways.length > 0) {
          tkList.innerHTML = res.key_takeaways.map((item) => `<li>${escapeHtml(item)}</li>`).join("");
          tkWrap.classList.remove("hidden");
        } else {
          tkWrap.classList.add("hidden");
        }
        applyDashboard(res.dashboard);
      } catch (err) {
        showToast("Falha ao gerar explicação", escapeHtml(err.message), "error");
      }
    };
  });

  // Guided Lab
  document.getElementById("btn-generate-lab").onclick = async () => {
    if (!state.selectedTopicId) return;
    try {
      const res = await apiRequest(
        "/api/study/lab",
        { method: "POST", body: JSON.stringify({ topic_id: state.selectedTopicId }) },
        "Montando missões práticas do Laboratório Guiado..."
      );
      renderGuidedLab(res.lab, res.completed_lab_steps);
      applyDashboard(res.dashboard);
    } catch (err) {
      showToast("Falha ao montar laboratório", escapeHtml(err.message), "error");
    }
  };

  // Active Recall: Generate Question
  document.getElementById("btn-start-recall").onclick = async () => {
    if (!state.selectedTopicId) return;
    try {
      const res = await apiRequest(
        "/api/study/recall/question",
        { method: "POST", body: JSON.stringify({ topic_id: state.selectedTopicId }) },
        "Elaborando questão aberta de Active Recall..."
      );
      state.currentRecallQuestion = res.question;
      document.getElementById("recall-question-text").textContent = res.question.question;
      document.getElementById("recall-hint-text").textContent = res.question.hint
        ? `💡 Dica: ${res.question.hint}`
        : "";
      document.getElementById("recall-answer-input").value = "";
      document.getElementById("recall-result").classList.add("hidden");
      document.getElementById("recall-box").classList.remove("hidden");
    } catch (err) {
      showToast("Erro ao gerar questão", escapeHtml(err.message), "error");
    }
  };

  // Active Recall: Evaluate Answer
  document.getElementById("btn-submit-recall").onclick = async () => {
    const ans = document.getElementById("recall-answer-input").value.trim();
    if (!ans || !state.currentRecallQuestion) {
      showToast("Resposta vazia", "Escreva sua explicação antes de enviar.", "error");
      return;
    }
    try {
      const res = await apiRequest(
        "/api/study/recall/evaluate",
        {
          method: "POST",
          body: JSON.stringify({
            topic_id: state.selectedTopicId,
            question: state.currentRecallQuestion,
            student_answer: ans,
          }),
        },
        "Avaliando seu domínio conceitual..."
      );
      const ev = res.evaluation;
      const box = document.getElementById("recall-result");
      box.className = `rounded-xl p-4 border text-xs space-y-2 ${
        ev.is_passing
          ? "border-emerald-500/40 bg-emerald-950/25 text-emerald-100"
          : "border-amber-500/40 bg-amber-950/25 text-amber-100"
      }`;
      box.innerHTML = `
        <div class="font-bold text-sm">${ev.is_passing ? "✅ Tópico Dominado!" : "⚠️ Quase lá — continue praticando!"} (Nota: ${Math.round(ev.score)}/100)</div>
        <p class="text-slate-200">${escapeHtml(ev.feedback)}</p>
        ${ev.understood_concepts?.length ? `<div class="text-emerald-300"><strong>Dominados:</strong> ${escapeHtml(ev.understood_concepts.join(", "))}</div>` : ""}
        ${ev.missing_or_confused_concepts?.length ? `<div class="text-rose-300"><strong>Reforçar:</strong> ${escapeHtml(ev.missing_or_confused_concepts.join(", "))}</div>` : ""}
      `;
      box.classList.remove("hidden");
      applyDashboard(res.dashboard);
      celebrateGamificationEvent(res.event);
    } catch (err) {
      showToast("Erro na avaliação", escapeHtml(err.message), "error");
    }
  };

  // Real-time Error Debugger
  document.getElementById("btn-run-debug").onclick = async () => {
    const cmd = document.getElementById("debug-command-input").value.trim();
    const errOut = document.getElementById("debug-error-input").value.trim();
    if (!errOut) {
      showToast("Saída vazia", "Cole a mensagem de erro ou stack trace do terminal.", "error");
      return;
    }
    try {
      const res = await apiRequest(
        "/api/study/debug",
        {
          method: "POST",
          body: JSON.stringify({
            topic_id: state.selectedTopicId,
            command_attempted: cmd,
            error_output: errOut,
          }),
        },
        "Analisando stack trace e montando correção passo a passo..."
      );
      const r = res.resolution;
      const out = document.getElementById("debug-output");
      out.innerHTML = `
        <div class="font-bold text-emerald-300">🩺 Tradução do Erro</div>
        <p class="text-slate-300">${escapeHtml(r.error_summary)}</p>
        <div class="font-bold text-amber-300 pt-1">🔍 Causa Raiz</div>
        <p class="text-slate-300">${escapeHtml(r.root_cause)}</p>
        <div class="font-bold text-cyan-300 pt-1">🛠️ Como Corrigir</div>
        <ol class="list-decimal pl-4 text-slate-300 space-y-1">
          ${r.fix_instructions.map((s) => `<li>${escapeHtml(s)}</li>`).join("")}
        </ol>
        <pre class="bg-slate-900 border border-slate-700 rounded-lg p-2.5 text-emerald-300 overflow-x-auto mt-2"><code>${escapeHtml(r.corrected_command_or_code)}</code></pre>
        ${r.prevention_tip ? `<div class="text-slate-400 italic pt-1">💡 ${escapeHtml(r.prevention_tip)}</div>` : ""}
      `;
      out.classList.remove("hidden");
    } catch (err) {
      showToast("Erro no Assistente de Debug", escapeHtml(err.message), "error");
    }
  };

  // Teacher Doubt
  document.getElementById("btn-ask-doubt").onclick = async () => {
    const q = document.getElementById("doubt-input").value.trim();
    if (!q) return;
    try {
      const res = await apiRequest(
        "/api/study/doubt",
        {
          method: "POST",
          body: JSON.stringify({
            topic_id: state.selectedTopicId,
            question: q,
            previous_explanation: state.currentExplanation,
          }),
        },
        "O Mentor está respondendo sua dúvida..."
      );
      const out = document.getElementById("doubt-output");
      out.innerHTML = renderMarkdown(res.answer);
      out.classList.remove("hidden");
    } catch (err) {
      showToast("Erro ao responder dúvida", escapeHtml(err.message), "error");
    }
  };

  // SRS Submit & Cancel
  document.getElementById("btn-cancel-srs").onclick = () => {
    document.getElementById("srs-active-card").classList.add("hidden");
  };

  document.getElementById("btn-submit-srs").onclick = async () => {
    const ans = document.getElementById("srs-answer-input").value.trim();
    if (!ans || !state.currentSrsTopicId || !state.currentSrsQuestion) return;
    try {
      const res = await apiRequest(
        "/api/srs/evaluate",
        {
          method: "POST",
          body: JSON.stringify({
            topic_id: state.currentSrsTopicId,
            question: state.currentSrsQuestion,
            student_answer: ans,
          }),
        },
        "Verificando retenção e recalculando curva SM-2..."
      );
      const srs = res.srs_result;
      const nextDt = new Date(srs.next_review_at).toLocaleDateString("pt-BR");
      const box = document.getElementById("srs-result-box");
      box.className = `rounded-xl p-4 border text-xs space-y-1.5 ${
        srs.is_retained
          ? "border-emerald-500/40 bg-emerald-950/25 text-emerald-100"
          : "border-amber-500/40 bg-amber-950/25 text-amber-100"
      }`;
      box.innerHTML = `
        <div class="font-bold text-sm">${srs.is_retained ? "✅ Memória Consolidada!" : "🔄 Reforço Agendado para Amanhã"} (Nota: ${Math.round(res.evaluation.score)}/100 • Qualidade SM-2: ${srs.quality}/5)</div>
        <p class="text-slate-200">${escapeHtml(res.evaluation.feedback)}</p>
        <div class="text-cyan-300 font-semibold">📅 Próxima revisão em +${srs.new_interval_days} dia(s) (${escapeHtml(nextDt)}) • EF: ${Number(srs.previous_ef).toFixed(2)} ➔ ${Number(srs.new_ef).toFixed(2)}</div>
      `;
      box.classList.remove("hidden");
      applyDashboard(res.dashboard);
      celebrateGamificationEvent(res.event);
    } catch (err) {
      showToast("Erro na revisão SRS", escapeHtml(err.message), "error");
    }
  };

  // Goal Modal
  const goalModal = document.getElementById("modal-goal");
  document.getElementById("btn-edit-goal").onclick = () => {
    const g = state.dashboard?.goal_status;
    document.getElementById("goal-days-input").value = g?.target_days || 7;
    document.getElementById("goal-label-input").value = g?.goal_label || "";
    goalModal.classList.remove("hidden");
  };
  document.getElementById("btn-close-goal-modal").onclick = () => goalModal.classList.add("hidden");
  document.getElementById("btn-cancel-goal").onclick = () => goalModal.classList.add("hidden");

  document.getElementById("btn-save-goal").onclick = async () => {
    const days = Number(document.getElementById("goal-days-input").value);
    const label = document.getElementById("goal-label-input").value.trim();
    if (!days || days < 1) {
      showToast("Prazo inválido", "Informe pelo menos 1 dia.", "error");
      return;
    }
    try {
      const res = await apiRequest(
        "/api/goal",
        { method: "POST", body: JSON.stringify({ target_days: days, goal_label: label || null }) },
        "Salvando meta com prazo..."
      );
      goalModal.classList.add("hidden");
      applyDashboard(res.dashboard);
      showToast("Meta Atualizada! 🏁", escapeHtml(res.goal_status.status_label), "success");
    } catch (err) {
      showToast("Erro ao salvar meta", escapeHtml(err.message), "error");
    }
  };

  document.getElementById("btn-clear-goal").onclick = async () => {
    try {
      const res = await apiRequest("/api/goal", { method: "DELETE" }, "Removendo prazo...");
      goalModal.classList.add("hidden");
      applyDashboard(res.dashboard);
      showToast("Prazo Removido", "Trilha configurada para ritmo livre.", "info");
    } catch (err) {
      showToast("Erro ao limpar meta", escapeHtml(err.message), "error");
    }
  };

  // Export Button
  document.getElementById("btn-export").onclick = async () => {
    try {
      const res = await apiRequest(
        "/api/export",
        { method: "POST", body: JSON.stringify({ format: "both", include_in_progress: true }) },
        "Exportando Resumo Markdown e Deck Anki..."
      );
      if (res.markdown_content && res.markdown_filename) {
        triggerDownload(res.markdown_filename, res.markdown_content, "text/markdown");
      }
      if (res.anki_content && res.anki_filename) {
        triggerDownload(res.anki_filename, res.anki_content, "text/plain");
      }
      showToast(
        "Material Exportado! 📦",
        `${res.topics_exported} tópico(s) e ${res.flashcards_generated} cartões Anki gerados (também salvos em exports/).`,
        "success"
      );
    } catch (err) {
      showToast("Aviso na Exportação", escapeHtml(err.message), "error");
    }
  };

  // Onboarding Modal
  const onbModal = document.getElementById("modal-onboarding");
  const openOnb = () => {
    document.getElementById("onb-step-1").classList.remove("hidden");
    document.getElementById("onb-step-2").classList.add("hidden");
    onbModal.classList.remove("hidden");
  };
  document.getElementById("btn-new-track").onclick = openOnb;
  document.getElementById("btn-empty-start").onclick = openOnb;
  document.getElementById("btn-close-onboarding").onclick = () => onbModal.classList.add("hidden");
  document.getElementById("btn-onb-back").onclick = () => {
    document.getElementById("onb-step-2").classList.add("hidden");
    document.getElementById("onb-step-1").classList.remove("hidden");
  };

  document.getElementById("btn-onb-generate-questions").onclick = async () => {
    const name = document.getElementById("onb-name").value.trim();
    const subject = document.getElementById("onb-subject").value.trim();
    if (!name || !subject) {
      showToast("Campos obrigatórios", "Preencha seu nome e o assunto desejado.", "error");
      return;
    }
    try {
      const res = await apiRequest(
        "/api/onboarding/questions",
        { method: "POST", body: JSON.stringify({ target_subject: subject }) },
        "Elaborando 3 perguntas de diagnóstico pedagógico..."
      );
      state.onboardingQuestions = res.questions;
      const list = document.getElementById("onb-questions-list");
      list.innerHTML = res.questions
        .map(
          (q, idx) => `
          <div class="rounded-xl border border-slate-800 bg-slate-950 p-4 space-y-2">
            <div class="text-xs text-cyan-300 font-semibold">Pergunta ${idx + 1}/3 • ${escapeHtml(q.topic_focus)} (${escapeHtml(q.difficulty)})</div>
            <p class="text-sm text-white font-medium">${escapeHtml(q.question)}</p>
            <textarea data-onb-ans="${idx}" rows="2" class="w-full bg-slate-900 border border-slate-700 rounded-lg p-2.5 text-xs text-white" placeholder="Sua resposta (ou 'não sei')"></textarea>
          </div>
        `
        )
        .join("");
      document.getElementById("onb-step-1").classList.add("hidden");
      document.getElementById("onb-step-2").classList.remove("hidden");
    } catch (err) {
      showToast("Falha no Diagnóstico", escapeHtml(err.message), "error");
    }
  };

  document.getElementById("btn-onb-finish").onclick = async () => {
    const name = document.getElementById("onb-name").value.trim();
    const subject = document.getElementById("onb-subject").value.trim();
    const targetLevel = document.getElementById("onb-target-level").value;
    const pace = document.getElementById("onb-pace").value;
    const days = Number(document.getElementById("onb-days").value) || 0;
    const paceMins = { relaxed: 25, regular: 45, intensive: 90 }[pace] || 45;

    const answers = state.onboardingQuestions.map((_, idx) => {
      const el = document.querySelector(`[data-onb-ans="${idx}"]`);
      return (el?.value || "não sei").trim() || "não sei";
    });

    try {
      const res = await apiRequest(
        "/api/onboarding/complete",
        {
          method: "POST",
          body: JSON.stringify({
            name,
            target_subject: subject,
            target_level: targetLevel,
            pace,
            daily_available_minutes: paceMins,
            questions: state.onboardingQuestions,
            answers,
            target_days: days > 0 ? days : null,
          }),
        },
        "Avaliando respostas e construindo sua trilha personalizada..."
      );
      onbModal.classList.add("hidden");
      applyDashboard(res.dashboard);
      celebrateGamificationEvent(res.event);
      showToast(
        `Nível Identificado: ${res.report.assessed_level.toUpperCase()}`,
        escapeHtml(res.report.summary_feedback),
        "success"
      );
    } catch (err) {
      showToast("Falha ao criar trilha", escapeHtml(err.message), "error");
    }
  };
}

function renderGuidedLab(lab, completedSteps) {
  const wrap = document.getElementById("lab-container");
  wrap.classList.remove("hidden");
  document.getElementById("lab-intro").textContent = lab.intro_brief;

  const prereqEl = document.getElementById("lab-prereq");
  if (lab.prerequisites_check) {
    prereqEl.textContent = `🔎 Pré-requisito de ambiente: ${lab.prerequisites_check}`;
    prereqEl.classList.remove("hidden");
  } else {
    prereqEl.classList.add("hidden");
  }

  const total = lab.missions.length;
  document.getElementById("lab-progress-badge").textContent = `${Math.min(completedSteps, total)}/${total} missões concluídas`;

  const list = document.getElementById("lab-missions-list");
  list.innerHTML = lab.missions
    .map((m) => {
      const done = completedSteps >= m.step_number;
      return `
        <div class="rounded-xl border ${done ? "border-emerald-500/40 bg-emerald-950/15" : "border-slate-800 bg-slate-950"} p-4 space-y-2.5">
          <div class="flex items-center justify-between gap-2">
            <h4 class="text-sm font-bold text-white">🛠️ Missão ${m.step_number}/${total}: ${escapeHtml(m.title)}</h4>
            <span class="text-xs font-semibold ${done ? "text-emerald-300" : "text-slate-400"}">${done ? "✔️ Concluída" : "+15 XP"}</span>
          </div>
          <p class="text-xs text-slate-300 leading-relaxed">${escapeHtml(m.instruction)}</p>
          <pre class="bg-slate-900 border border-slate-800 rounded-lg p-3 text-xs text-cyan-300 overflow-x-auto"><code>${escapeHtml(m.command_or_code)}</code></pre>
          <div class="text-xs text-emerald-300/90"><strong>✅ Resultado esperado:</strong> ${escapeHtml(m.expected_outcome)}</div>
          ${m.verification_hint ? `<div class="text-xs text-amber-300/90">💡 ${escapeHtml(m.verification_hint)}</div>` : ""}
          <div class="pt-1 flex justify-end">
            <button data-step="${m.step_number}" class="btn-lab-check px-3.5 py-1.5 rounded-lg text-xs font-bold ${
              done
                ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
                : "bg-fuchsia-600 hover:bg-fuchsia-500 text-white"
            } transition">
              ${done ? "✔️ Missão Validada" : "✔️ Funcionou! Validar Missão (+15 XP)"}
            </button>
          </div>
        </div>
      `;
    })
    .join("");

  list.querySelectorAll(".btn-lab-check").forEach((btn) => {
    btn.onclick = async () => {
      const stepNumber = Number(btn.dataset.step);
      try {
        const res = await apiRequest(
          "/api/study/lab/checkpoint",
          {
            method: "POST",
            body: JSON.stringify({ topic_id: state.selectedTopicId, step_number: stepNumber }),
          },
          "Validando checkpoint prático..."
        );
        renderGuidedLab(lab, res.completed_lab_steps);
        applyDashboard(res.dashboard);
        celebrateGamificationEvent(res.event);
      } catch (err) {
        showToast("Erro ao validar missão", escapeHtml(err.message), "error");
      }
    };
  });
}

function triggerDownload(filename, content, mimeType) {
  const blob = new Blob([content], { type: `${mimeType};charset=utf-8` });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

async function initApp() {
  if (window.mermaid) {
    window.mermaid.initialize({ startOnLoad: false, theme: "dark", securityLevel: "loose" });
  }
  bindEvents();
  try {
    const dash = await apiRequest("/api/dashboard", {}, "Carregando seu ambiente de estudos...");
    applyDashboard(dash);
  } catch (err) {
    showToast("Falha ao carregar Dashboard", escapeHtml(err.message), "error");
  }
}

document.addEventListener("DOMContentLoaded", initApp);
