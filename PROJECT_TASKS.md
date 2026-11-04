# PROJECT_TASKS.md — Registro Vivo de Tarefas (AI Study Agent)

## 1. Fase Atual
- **Fase:** Fase 1 — Inicialização do Projeto & Estrutura Base
- **Objetivo:** Configurar ambiente, dependências, schemas Pydantic e regras operacionais.

## 2. Em Andamento
- Nenhuma no momento (próxima: `#TASK-03`).

## 3. Planejadas (Backlog)

---

### 🔹 `#TASK-03` — Cliente Unificado de LLM (`core/llm_client.py`)
- **Status:** `[Planejado]`
- **Áreas:** `study_agent/core/llm_client.py`, `study_agent/config.py`
- **Descrição:** Implementar cliente com LiteLLM para chamar Gemini, OpenAI, Claude ou Ollama, com suporte a Structured Outputs (retorno em JSON validado por Pydantic).

---

### 🔹 `#TASK-04` — Módulo Diagnosticador (`core/diagnostician.py`)
- **Status:** `[Planejado]`
- **Áreas:** `study_agent/core/diagnostician.py`
- **Descrição:** Lógica para gerar perguntas de nivelamento baseadas no objetivo do aluno e avaliar suas respostas para estimar o ponto de partida.

---

### 🔹 `#TASK-05` — Gerador de Trilha e Mapa Mental (`core/curriculum_gen.py`)
- **Status:** `[Planejado]`
- **Áreas:** `study_agent/core/curriculum_gen.py`
- **Descrição:** Gerar a árvore de tópicos hierárquica, do nível atual do aluno até o objetivo desejado, com pré-requisitos e estimativa de tempo.

---

### 🔹 `#TASK-06` — Módulos Professor & Avaliador (`core/teacher.py` e `core/evaluator.py`)
- **Status:** `[Planejado]`
- **Áreas:** `study_agent/core/`
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
- [x] `#TASK-02` | 02/11/2026 | Schemas Pydantic v2 (StudentProfile, Curriculum, Topic, ActiveRecall) com testes unitários | `study_agent/models/*.py`, `tests/test_models.py`
- [x] `#TASK-01` | 02/11/2026 | Estrutura base, regras de contexto, PROJECT_MAP, PROJECT_TASKS, requirements.txt, .gitignore e .env.example | `.agent/rules/*`, `PROJECT_MAP.md`, `PROJECT_TASKS.md`, `requirements.txt`, `.env.example`, `.gitignore`

## 5. Decisões de Arquitetura
- **Decisão 1 (02/11/2026):** Início por CLI em Python utilizando `rich` e `typer` para interface de terminal profissional, desacoplando o "core" para futura extensão web.
- **Decisão 2 (02/11/2026):** Uso de `litellm` para suportar provedores variados (Gemini, OpenAI, Claude, Ollama) de forma intercambiável via variáveis de ambiente.
- **Decisão 3 (02/11/2026):** Adoção de `context_management.md` + `PROJECT_MAP.md` + `PROJECT_TASKS.md` para persistência de memória do agente e economia cirúrgica de tokens.
- **Decisão 4 (02/11/2026):** Uso de Pydantic v2 com `Field(ge=..., le=...)` para validação estrita de scores/limites e métodos de transição de status na própria entidade `Curriculum`.
- **Decisão 5 (04/11/2026):** GitFlow adotado com branches `main` (produção estável), `develop` (integração) e branches dinâmicas `feature/*` ou `fix/*`. Commits padronizados em pt-BR e `git push` condicionado à aprovação prévia do usuário (documentado em `.agent/rules/git_workflow.md`).
