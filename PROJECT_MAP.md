# PROJECT_MAP.md — AI Study Agent (Tutor Adaptativo)

## 1. Visão Geral
Agente inteligente de estudos (CLI e, na Fase 3, Interface Web integrada) que atua como um mentor particular adaptativo. Realiza diagnóstico inicial do aluno, monta trilhas e mapas de aprendizado customizados, conduz sessões didáticas (Feynman, Técnico, Prático e Laboratório Guiado com Debugging), faz checagem ativa de conhecimento (Active Recall), exporta resumos/flashcards e evolui na Fase 3 com gamificação orientada à prática, metas com prazo e repetição espaçada (SRS).
- **Stack Atual (Fases 1 e 2):** Python 3.10+, Typer / Click, Rich (Terminal UI), LiteLLM (Gemini, OpenAI, Claude, Ollama), Pydantic v2.
- **Stack Planejada (Fase 3):** FastAPI + Uvicorn + HTML/Tailwind/JS moderno + Mermaid.js (servido diretamente pelo Python, compartilhando `core/` e `storage/`).
- **Como Rodar:** `python -m study_agent.cli`, `.\study-agent` (via `study-agent.bat` no Windows) ou `study-agent` (após `pip install -e .`).

## 2. Árvore Comentada
```text
study-agent/
├── .agent/rules/                # Regras permanentes para o agente/assistente
│   ├── context_management.md    # Economia de contexto, didática e navegação por mapa
│   └── git_workflow.md          # GitFlow automatizado, commits pt-BR e controle de push
├── data/                        # Dados locais de sessões e histórico dos estudantes (JSON)
├── study_agent/
│   ├── __init__.py              # Versão do pacote
│   ├── __main__.py              # Execução direta via python -m study_agent
│   ├── cli.py                   # Ponto de entrada CLI (comandos typer e rich UI)
│   ├── config.py                # Configurações de ambiente, chaves de API e modelos LLM
│   ├── models/                  # Modelos Pydantic (validação estrutural de dados)
│   │   ├── __init__.py
│   │   ├── student.py           # Perfil do aluno, objetivos, nível atual
│   │   └── curriculum.py        # Tópicos, pré-requisitos, árvore/mapa mental e progresso
│   ├── core/                    # Regras de negócio e inteligência pedagógica
│   │   ├── __init__.py
│   │   ├── llm_client.py        # Abstração de chamadas de LLM (LiteLLM)
│   │   ├── diagnostician.py     # Diagnóstico de conhecimentos prévios e nivelamento
│   │   ├── curriculum_gen.py    # Planejador da trilha de estudos e geração de tópicos
│   │   ├── teacher.py           # Explicações didáticas, laboratório guiado e debug de erros
│   │   ├── evaluator.py         # Checagem de absorção (Active Recall) e pontuação de domínio
│   │   ├── exporter.py          # Exportação de resumos Markdown e flashcards Anki TSV
│   │   ├── gamification.py      # Motor de XP prático, níveis, streaks, metas e 17 conquistas
│   │   └── srs.py               # Motor de repetição espaçada Ebbinghaus / SuperMemo SM-2
│   └── storage/                 # Camada de persistência local
│       ├── __init__.py
│       └── session_store.py     # Leitura e escrita de perfis e trilhas em JSON local
├── tests/                       # Testes automatizados (pytest)
│   ├── __init__.py
│   ├── test_gamification.py     # Testes do motor de XP, streaks, metas e conquistas
│   ├── test_llm_client.py       # Testes unitários do cliente unificado LiteLLM
│   ├── test_models.py           # Testes de integridade de schemas Pydantic
│   └── test_srs.py              # Testes do algoritmo SM-2 e fila de repetição espaçada
├── .env.example                 # Exemplo de configuração de variáveis de ambiente
├── .gitignore                   # Ignora dados locais, venv, caches e chaves
├── pyproject.toml               # Metadados PEP 621 e entrypoint console study-agent
├── study-agent.bat              # Wrapper executável direto para Windows (PowerShell/CMD)
├── PROJECT_MAP.md               # [Este arquivo] Arquitetura e mapa cirúrgico
├── PROJECT_TASKS.md             # Registro vivo de tarefas, backlog e decisões
└── README.md                    # Documentação do projeto para a comunidade GitHub
```

## 3. Mapa por Funcionalidade (Se for X, mexa em Y)
| Funcionalidade | Arquivo : Função / Classe |
| :--- | :--- |
| Comandos de Terminal & Telas | `study_agent/cli.py` (`render_llm_error`, `render_debug_resolution`, `render_gamification_event`, `goal`, `review`, `status --badges` e comandos Typer) |
| Configuração de Provedores & Chaves | `study_agent/config.py` (`Settings`: chaves, retries e timeouts) |
| Chamadas unificadas de LLM (Prompt/JSON) | `study_agent/core/llm_client.py` (`LLMClient`, `LLMConnectionError`, `LLMAuthenticationError`) |
| Perguntas de diagnóstico & cálculo de nível | `study_agent/core/diagnostician.py` |
| Montagem da árvore de estudos & tópicos | `study_agent/core/curriculum_gen.py` |
| Explicações didáticas, laboratório & debug | `study_agent/core/teacher.py` (`explain_topic`, `generate_guided_lab`, `debug_error`) |
| Testes de absorção & cálculo de pontuação | `study_agent/core/evaluator.py` (`Evaluator`, histórico `RecallRecord` e agendamento inicial SRS) |
| Exportação de Resumos & Flashcards Anki | `study_agent/core/exporter.py` (`StudyExporter`, `AnkiCard`, `ExportResult`) |
| Gamificação, XP, Streaks, Metas & Badges | `study_agent/core/gamification.py` (`GamificationEngine`, `BADGE_CATALOG`, `GoalStatus`, `LevelProgress`), `study_agent/models/student.py`, `study_agent/models/curriculum.py` |
| Repetição Espaçada SRS / SM-2 | `study_agent/core/srs.py` (`SpacedRepetitionEngine`, `SRSReviewResult`, `SRSQueueSummary`), `study_agent/models/curriculum.py` |
| Servidor & Dashboard Web Integrado *(Planejado `#TASK-14`)* | `study_agent/web/app.py`, `study_agent/web/templates/*`, `study_agent/web/static/*` |
| Schemas do Aluno & Objetivos | `study_agent/models/student.py` |
| Schemas da Trilha, Laboratório & Debug | `study_agent/models/curriculum.py` (`Curriculum`, `Topic`, `GuidedLab`, `LabMission`, `ErrorDebugResolution`) |
| Salvar/Recuperar progresso em disco | `study_agent/storage/session_store.py` |

## 4. Arquivos Sensíveis / Proibidos para Leitura Automática
- `.env` (contém chaves de API reais do usuário)
- `data/*.json` (contém histórico pessoal de estudos sem necessidade de leitura completa)
