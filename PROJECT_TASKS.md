# PROJECT_TASKS.md — Registro Vivo de Tarefas (AI Study Agent)

## 1. Fase Atual
- **Fase:** Fase 2 em Andamento 🚀 (Pedagogia Guiada, Resiliência & Ergonomia)
- **Objetivo:** Elevar a robustez de rede, ergonomia no Windows e experiência prática de laboratório com debugging em tempo real.

## 2. Em Andamento
- Nenhuma no momento (`#TASK-11` recém-concluída; próxima da fila: `#TASK-12`).

## 3. Planejadas (Backlog — Fase 2: Pedagogia Guiada, Resiliência & Ergonomia)

---

### 🔹 `#TASK-12` — Exportação de Resumos de Sessão (Markdown & Anki Flashcards)
- **Status:** `[Planejado]`
- **Áreas:** `study_agent/core/`, `study_agent/cli.py`
- **Descrição:** Gerar resumos estruturados dos tópicos dominados em `.md` e cartões de perguntas e respostas prontos para importação no Anki (estudo/revisão offline).

---

## 4. Backlog Futuro (Fase 3: Interface Web & Gamificação Visual)
- **`#TASK-13` — Gamificação, Streaks e Badges Visuais:** Controle de dias seguidos (streaks), conquistas e níveis visuais integrados aos componentes da UI.
- **`#TASK-14` — Interface Gráfica / Web:** Dashboard interativo com gráficos de domínio, visualização da árvore de conhecimento e laboratório de comandos interativo.
- **`#TASK-15` — Sistema de Repetição Espaçada (SRS / Ebbinghaus):** Agendamento automatizado de revisões periódicas de tópicos pré-dominados.

---

## 5. Concluídas
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
