# PROJECT_TASKS.md — Registro Vivo de Tarefas (AI Study Agent)

## 1. Fase Atual
- **Fase:** Fase 3 — Gamificação, Repetição Espaçada (SRS) & Interface Web Integrada 🚀
- **Objetivo:** Implementar os motores de gamificação/metas (`#TASK-13`) e repetição espaçada (`#TASK-15`) no `core/`, seguidos pelo Web App integrado em FastAPI (`#TASK-14`) compartilhando a mesma base de dados da CLI.

## 2. Em Andamento
- Próxima e última entrega da Fase 3: **`#TASK-14` — Interface Gráfica / Web Integrada (FastAPI + Web App Leve)**.

## 3. Planejadas (Backlog Oficial — Fase 3 | Ordem restante: `#14`)
- **`#TASK-14` — Interface Gráfica / Web Integrada (FastAPI + Web App Leve):**
  - Servidor Python único (`FastAPI` + `Uvicorn` + HTML/Tailwind/JS moderno + `Mermaid.js`) iniciado via `.\study-agent web` / `python -m study_agent.cli web` (zero dependência de Node.js/npm).
  - Compartilhamento direto do `core/` e `SessionStore` (`data/`) entre CLI e Web.
  - Dashboard visual completo: barra de XP/nível, chama de streak, vitrine de badges, termômetro de meta com prazo, árvore de conhecimento interativa, sala de estudo/Laboratório Guiado + Debug e fila de Revisão Rápida (SRS).

---

## 4. Backlog Futuro (Pós-Fase 3)
- A definir após conclusão da Fase 3.

---

## 5. Concluídas
- [x] `#TASK-15` | 27/11/2026 | Motor de Repetição Espaçada SM-2 (`SpacedRepetitionEngine`), campos retrocompatíveis em `Topic`, agendamento automático pós-domínio, comando CLI `review` (mantendo Streak com 0 XP e conquista *Memória Blindada*) e testes | `study_agent/core/srs.py`, `study_agent/core/evaluator.py`, `study_agent/core/__init__.py`, `study_agent/models/curriculum.py`, `study_agent/cli.py`, `README.md`, `tests/test_srs.py`, `tests/test_models.py`, `tests/test_cli.py`
- [x] `#TASK-13` | 27/11/2026 | Motor de gamificação (XP prático anti-farming, níveis Iniciante..Mestre, streaks locais, metas com prazo e 17 conquistas em 6 categorias), comando CLI goal e vitrine em status --badges com testes | `study_agent/core/gamification.py`, `study_agent/core/__init__.py`, `study_agent/models/student.py`, `study_agent/models/curriculum.py`, `study_agent/models/__init__.py`, `study_agent/cli.py`, `README.md`, `tests/test_gamification.py`, `tests/test_models.py`, `tests/test_cli.py`
- [x] `#TASK-12` | 25/11/2026 | Exportador de resumos Markdown (frontmatter + Mermaid + details de Active Recall) e decks TSV Anki 2.1.54+ com histórico RecallRecord e comando CLI export | `study_agent/core/exporter.py`, `study_agent/core/evaluator.py`, `study_agent/core/__init__.py`, `study_agent/models/curriculum.py`, `study_agent/models/__init__.py`, `study_agent/config.py`, `study_agent/cli.py`, `.gitignore`, `README.md`, `tests/test_exporter.py`, `tests/test_cli.py`
- [x] `#TASK-11` | 25/11/2026 | Ergonomia de execução no Windows (wrapper study-agent.bat com UTF-8, pyproject.toml, __main__.py, instruções portáteis na CLI e README.md com guia Set-ExecutionPolicy) | `study-agent.bat`, `pyproject.toml`, `study_agent/__main__.py`, `study_agent/cli.py`, `requirements.txt`, `README.md`, `tests/test_cli.py`
- [x] `#TASK-10` | 25/11/2026 | Modo Laboratório Guiado passo a passo (GuidedLab/LabMission) e Assistente de Debugging em tempo real (debug_error + opção [E] multilinha na CLI) com testes | `study_agent/models/curriculum.py`, `study_agent/models/__init__.py`, `study_agent/core/teacher.py`, `study_agent/cli.py`, `tests/test_models.py`, `tests/test_teacher.py`, `tests/test_cli.py`
- [x] `#TASK-09` | 25/11/2026 | Resiliência de conexão no LLMClient (retries com backoff exponencial + jitter, distinção 503/429 vs 401) e tratamento gracioso com painéis Rich e salvamento parcial na CLI | `study_agent/core/llm_client.py`, `study_agent/core/__init__.py`, `study_agent/config.py`, `study_agent/cli.py`, `.env.example`, `tests/test_llm_client.py`, `tests/test_cli.py`
- [x] `#TASK-08` | 17/11/2026 | Interface CLI interativa com Typer e Rich (init, study, status, map, students, version) orquestrando core e storage com testes | `study_agent/cli.py`, `tests/test_cli.py`
- [x] `#TASK-07` | 17/11/2026 | Camada de persistência SessionStore (gravação atômica, perfis, trilhas, sessão ativa e deleção em cascata) com testes | `study_agent/storage/session_store.py`, `study_agent/storage/__init__.py`, `study_agent/config.py`, `tests/test_session_store.py`
- [x] `#TASK-06` | 16/11/2026 | Módulos Teacher (Feynman, técnico, prático, dúvidas, takeaways) e Evaluator (Active Recall, notas de domínio, atualização de tópicos) com testes | `study_agent/core/teacher.py`, `study_agent/core/evaluator.py`, `study_agent/core/__init__.py`, `tests/test_teacher.py`, `tests/test_evaluator.py`
- [x] `#TASK-05` | 08/11/2026 | Módulo CurriculumGenerator com encadeamento de tópicos, sanitização DAG de pré-requisitos, árvore ASCII, exportação Mermaid e testes | `study_agent/core/curriculum_gen.py`, `study_agent/core/__init__.py`, `tests/test_curriculum_gen.py`
- [x] `#TASK-04` | 08/11/2026 | Módulo Diagnostician com geração progressiva de perguntas, avaliação de respostas e relatório diagnóstico com testes | `study_agent/core/diagnostician.py`, `study_agent/core/__init__.py`, `tests/test_diagnostician.py`
- [x] `#TASK-03` | 04/11/2026 | Cliente unificado LiteLLM com structured outputs, sanitização de JSON e testes | `study_agent/config.py`, `study_agent/core/llm_client.py`, `tests/test_llm_client.py`
- [x] `#TASK-02` | 02/11/2026 | Schemas Pydantic v2 (StudentProfile, Curriculum, Topic, ActiveRecall) com testes unitários | `study_agent/models/*.py`, `tests/test_models.py`
- [x] `#TASK-01` | 02/11/2026 | Estrutura base, regras de contexto, PROJECT_MAP, PROJECT_TASKS, requirements.txt, .gitignore e .env.example | `.agent/rules/*`, `PROJECT_MAP.md`, `PROJECT_TASKS.md`, `requirements.txt`, `.env.example`, `.gitignore`

## 6. Decisões de Arquitetura
- **Decisão 1 (02/11/2026):** Início por CLI em Python utilizando `rich` e `typer` para interface de terminal profissional, desacoplando o "core" para futura extensão web.
- **Decisão 2 (02/11/2026):** Uso de `litellm` para suportar provedores variados (Gemini, OpenAI, Claude, Ollama) de forma intercambiável via variáveis de ambiente.
- **Decisão 3 (02/11/2026):** Adoção de `context_management.md` + `PROJECT_MAP.md` + `PROJECT_TASKS.md` para persistência de memória do agente e economia cirúrgica de tokens.
- **Decisão 4 (02/11/2026):** Uso de Pydantic v2 com `Field(ge=..., le=...)` para validação estrita de scores/limites e métodos de transição de status na própria entidade `Curriculum`.
- **Decisão 5 (04/11/2026):** GitFlow adotado com branches `main` (produção estável), `develop` (integração) e branches dinâmicas `feature/*` ou `fix/*`. Commits padronizados em pt-BR e `git push` condicionado à aprovação prévia do usuário (documentado em `.agent/rules/git_workflow.md`).
- **Decisão 6 (04/11/2026):** Extração e sanitização robusta de JSON regex em `LLMClient` para garantir compatibilidade de Structured Outputs mesmo em provedores/modelos que envolvem retornos em blocos markdown.
- **Decisão 7 (08/11/2026):** Diagnostician concebido com injeção de dependência de `LLMClient`, containers de structured outputs e consolidação determinística de `KnowledgeLevel` através de faixas de pontuação (<50: beginner, 50-80: intermediate, >=80: advanced).
- **Decisão 8 (08/11/2026):** CurriculumGenerator com sanitização de dependências DAG (eliminação de auto-referências e ciclos simples), desbloqueio dinâmico dos tópicos iniciais e visualização dupla (árvore formatada e Mermaid flowchart).
- **Decisão 9 (16/11/2026):** Módulo Teacher com 3 abordagens pedagógicas (Feynman com analogias, Técnico formal e Prático com código) e Evaluator com checagem de retenção ativa (Active Recall), nota de corte >= 70% para promoção a MASTERED e atualização ponderada de domínio.
- **Decisão 10 (17/11/2026):** SessionStore implementado com gravação atômica via arquivos temporários (.tmp -> replace), separação em subpastas profiles e curricula, e ponteiro current_session.json para retomada imediata do último estudo sem argumentos de CLI.
- **Decisão 11 (17/11/2026):** Interface CLI construída com Typer e Rich, suportando fluxo conversacional com spin indicators, renderização rica de tabelas de status, visualização de mapas ASCII e Mermaid, ciclo de estudo com dúvidas ilimitadas e checagem de Active Recall.
- **Decisão 12 (18/11/2026):** Gamificação (badges, streaks, níveis) postergada para a Fase 3 (Interface Web), onde o apelo visual e a recompensa gráfica são muito maiores. O foco da Fase 2 foi direcionado 100% para a eficácia pedagógica prática (Modo Laboratório Guiado e Debugging em tempo real), resiliência de rede e ergonomia no Windows.
- **Decisão 13 (25/11/2026):** Implementação de resiliência em duas camadas: no `LLMClient`, loop explícito de retry com *backoff exponencial + jitter* apenas para falhas transitórias (`503`, `429`, timeouts) e *fail-fast* imediato para credenciais inválidas (`401/403`); na `CLI`, renderização amigável via `render_llm_error` sem stack traces brutos e persistência automática de progresso parcial caso a rede caia no Active Recall.
- **Decisão 14 (25/11/2026):** Modo Laboratório Guiado estruturado via *Scaffolding* com `GuidedLab` e `LabMission` (checkpoints explícitos `[P/E/D/A]`), somado ao método `Teacher.debug_error` sensível ao sistema operacional do aluno e captura multilinha de stack traces na opção `[E]` da CLI.
- **Decisão 15 (25/11/2026):** Ergonomia multiplataforma e Windows garantida em 3 camadas: wrapper `study-agent.bat` (força UTF-8 e localiza `.venv` sem depender de `ExecutionPolicy` do PowerShell), empacotamento PEP 621 via `pyproject.toml` (`study-agent` entrypoint) + `__main__.py`, e padronização das mensagens da CLI para `python -m study_agent.cli`.
- **Decisão 16 (25/11/2026):** Exportação offline determinística via `StudyExporter` (zero custo de API na hora de exportar): persistência de `RecallRecord` em cada tópico avaliado, geração de guia `.md` com blocos retráteis `<details>` para revisão ativa no Obsidian/GitHub, e geração de deck `.txt` com cabeçalhos nativos do Anki 2.1.54+ (`#separator:tab`, `#html:true`, `#deck`, `#tags column:3`).
- **Decisão 17 (25/11/2026):** Stack da Interface Web (`#TASK-14`) definida como `FastAPI` + Web App leve integrado (`Uvicorn` + HTML/Tailwind/JS moderno + `Mermaid.js`), servida diretamente pelo Python via comando `web` sem necessidade de Node.js/npm e compartilhando o mesmo `SessionStore` JSON com a CLI.
- **Decisão 18 (25/11/2026):** Design de Gamificação (`#TASK-13`) com separação estrita entre *Hábito* (Streak) e *Prática Real* (XP): revisões rápidas (SRS) mantêm a ofensiva diária acesa nos dias corridos mas concedem `0 XP`, restringindo o ganho de XP ao avanço prático inédito (missões de laboratório e domínio de tópicos). Inclusão de metas temporais opcionais/editáveis (`target_days` / `deadline_at`) e catálogo unificado de conquistas em 6 categorias.
- **Decisão 19 (25/11/2026):** Sequência de engenharia da Fase 3 definida como "Motores Primeiro, Vitrine Depois" (`#TASK-13` Gamificação ➔ `#TASK-15` SRS ➔ `#TASK-14` Interface Web), garantindo que regras de XP, metas, conquistas e fila de repetição espaçada estejam consolidadas e testadas no `core/` antes da construção do Dashboard Web.
