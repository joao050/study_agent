# PROJECT_TASKS.md — Registro Vivo de Tarefas (AI Study Agent)

## 1. Fase Atual
- **Fase:** Fase 1 — Inicialização do Projeto & Estrutura Base
- **Objetivo:** Configurar ambiente, dependências, schemas Pydantic e regras operacionais.

## 2. Em Andamento
- Nenhuma no momento (próxima: `#TASK-06`).

## 3. Planejadas (Backlog)

---

### 🔹 `#TASK-06` — Módulos Professor & Avaliador (`core/teacher.py` e `core/evaluator.py`)
- **Status:** `[Planejado]`
- **Áreas:** `study_agent/core/teacher.py`, `study_agent/core/evaluator.py`
- **Descrição:** Implementar explicação didática (Feynman/analogias) e questionador de absorção (Active Recall) para calcular a nota de domínio do tópico.

---

### 🔹 `#TASK-07` — Persistência Local em JSON (`storage/session_store.py`)
- **Status:** `[Planejado]`
- **Áreas:** `study_agent/storage/session_store.py`
- **Descrição:** Salvar e carregar o progresso do aluno no diretório local de dados para permitir retomada de estudos a qualquer momento.

---

### 🔹 `#TASK-08` — Interface CLI Interativa (`study_agent/cli.py`)
- **Status:** `[Planejado]`
- **Áreas:** `study_agent/cli.py`
- **Descrição:** Implementar a experiência do terminal usando Rich (painéis, tabelas, barra de progresso, prompts interativos e formatação Markdown).

---

## 4. Concluídas
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
