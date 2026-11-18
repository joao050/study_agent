# PROJECT_TASKS.md — Registro Vivo de Tarefas (AI Study Agent)

## 1. Fase Atual
- **Fase:** Fase 1 Concluída! 🎉 (Estrutura Base, Core Pedagógico, Persistência e CLI)
- **Objetivo:** Todas as tarefas da Fase 1 foram entregues com 100% dos testes aprovados.

## 2. Em Andamento
- Nenhuma no momento (Fase 1 finalizada; Fase 2 a ser iniciada após alinhamento do backlog).

## 3. Planejadas (Backlog — Fase 2)

---

### 🔹 `#TASK-09` — Resiliência de Conexão com LLM & Retries Automáticos
- **Status:** `[Planejado]`
- **Áreas:** `study_agent/core/llm_client.py`, `study_agent/cli.py`
- **Origem dos Experimentos:** Durante testes manuais, picos de tráfego do Free Tier da Gemini retornaram `503 Service Unavailable`.
- **Escopo:**
  1. Adicionar política de retry automático com backoff exponencial (`num_retries=3`) no `LLMClient`.
  2. Implementar tratamento gracioso de exceções no CLI, exibindo aviso visual amigável via Rich em vez de traceback bruto.

---

### 🔹 `#TASK-10` — Ergonomia de Execução CLI & Entrypoint no Windows
- **Status:** `[Planejado]`
- **Áreas:** `study_agent/cli.py`, `pyproject.toml` / `setup.py`, `README.md`
- **Origem dos Experimentos:** Usuário se deparou com política de execução restrita de `.ps1` no PowerShell e comando global `study-agent` não encontrado sem ativação explícita de `.venv`.
- **Escopo:**
  1. Padronizar mensagens de instrução no CLI para sugerir o comando portátil `python -m study_agent.cli study`.
  2. Adicionar script wrapper executável (ex: `study-agent.bat`) e registrar entrypoint de console no pacote Python.
  3. Documentar no `README.md` a resolução rápida de `Set-ExecutionPolicy` para novos usuários no Windows.

---

### 🔹 `#TASK-11` — Exportação de Resumos de Sessão (Markdown / PDF)
- **Status:** `[Planejado]`
- **Áreas:** `study_agent/core/`, `study_agent/cli.py`
- **Descrição:** Gerar resumos exportáveis dos tópicos dominados, com perguntas e respostas de Active Recall para revisão espaçada offline.

---

### 🔹 `#TASK-12` — Gamificação & Streaks de Aprendizado
- **Status:** `[Planejado]`
- **Áreas:** `study_agent/models/student.py`, `study_agent/cli.py`
- **Descrição:** Implementar controle de dias seguidos de estudo (streaks), badges de conquista e cálculo de pontuação acumulada.

---

## 4. Concluídas
- [x] `#TASK-08` | 17/11/2026 | Interface CLI interativa com Typer e Rich (init, study, status, map, students, version) orquestrando core e storage com testes | `study_agent/cli.py`, `tests/test_cli.py`
- [x] `#TASK-07` | 17/11/2026 | Camada de persistência SessionStore (gravação atômica, perfis, trilhas, sessão ativa e deleção em cascata) com testes | `study_agent/storage/session_store.py`, `study_agent/storage/__init__.py`, `study_agent/config.py`, `tests/test_session_store.py`
- [x] `#TASK-06` | 16/11/2026 | Módulos Teacher (Feynman, técnico, prático, dúvidas, takeaways) e Evaluator (Active Recall, notas de domínio, atualização de tópicos) com testes | `study_agent/core/teacher.py`, `study_agent/core/evaluator.py`, `study_agent/core/__init__.py`, `tests/test_teacher.py`, `tests/test_evaluator.py`
- [x] `#TASK-05` | 08/11/2026 | Módulo CurriculumGenerator com encadeamento de tópicos, sanitização DAG de pré-requisitos, árvore ASCII, exportação Mermaid e testes | `study_agent/core/curriculum_gen.py`, `study_agent/core/__init__.py`, `tests/test_curriculum_gen.py`
- [x] `#TASK-04` | 08/11/2026 | Módulo Diagnostician com geração progressiva de perguntas, avaliação de respostas e relatório diagnóstico com testes | `study_agent/core/diagnostician.py`, `study_agent/core/__init__.py`, `tests/test_diagnostician.py`
- [x] `#TASK-03` | 04/11/2026 | Cliente unificado LiteLLM com structured outputs, sanitização de JSON e testes | `study_agent/config.py`, `study_agent/core/llm_client.py`, `tests/test_llm_client.py`
- [x] `#TASK-02` | 02/11/2026 | Schemas Pydantic v2 (StudentProfile, Curriculum, Topic, ActiveRecall) com testes unitários | `study_agent/models/*.py`, `tests/test_models.py`
- [x] `#TASK-01` | 02/11/2026 | Estrutura base, regras de contexto, PROJECT_MAP, PROJECT_TASKS, requirements.txt, .gitignore e .env.example | `.agent/rules/*`, `PROJECT_MAP.md`, `PROJECT_TASKS.md`, `requirements.txt`, `.env.example`, `.gitignore`

## 5. Decisões de Arquitetura
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
