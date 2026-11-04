# PROJECT_MAP.md — AI Study Agent (Tutor Adaptativo)

## 1. Visão Geral
Agente inteligente de estudos via terminal (CLI) que atua como um mentor particular adaptativo. Realiza diagnóstico inicial do aluno, monta trilhas e mapas de aprendizado customizados, conduz sessões didáticas com a técnica de Feynman, faz checagem ativa de conhecimento (Active Recall) e mantém acompanhamento de domínio com gamificação leve (barras de progresso e níveis).
- **Stack:** Python 3.10+, Typer / Click, Rich (Terminal UI), LiteLLM (suporte flexível a Gemini, OpenAI, Claude, Ollama), Pydantic v2 (validação de schemas e structured outputs).
- **Como Rodar:** `python -m study_agent.cli` ou via comando `study-agent start`.

## 2. Árvore Comentada
```text
study-agent/
├── .agent/rules/                # Regras permanentes para o agente/assistente
│   ├── context_management.md    # Economia de contexto, didática e navegação por mapa
│   └── git_workflow.md          # GitFlow automatizado, commits pt-BR e controle de push
├── data/                        # Dados locais de sessões e histórico dos estudantes (JSON)
├── study_agent/
│   ├── __init__.py              # Versão do pacote
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
│   │   ├── teacher.py           # Explicações didáticas, analogias e resolução de dúvidas
│   │   └── evaluator.py         # Checagem de absorção (Active Recall) e pontuação de domínio
│   └── storage/                 # Camada de persistência local
│       ├── __init__.py
│       └── session_store.py     # Leitura e escrita de perfis e trilhas em JSON local
├── tests/                       # Testes automatizados (pytest)
│   ├── __init__.py
│   └── test_models.py           # Testes de integridade de schemas Pydantic
├── .env.example                 # Exemplo de configuração de variáveis de ambiente
├── .gitignore                   # Ignora dados locais, venv, caches e chaves
├── PROJECT_MAP.md               # [Este arquivo] Arquitetura e mapa cirúrgico
├── PROJECT_TASKS.md             # Registro vivo de tarefas, backlog e decisões
└── README.md                    # Documentação do projeto para a comunidade GitHub
```

## 3. Mapa por Funcionalidade (Se for X, mexa em Y)
| Funcionalidade | Arquivo : Função / Classe |
| :--- | :--- |
| Comandos de Terminal & Telas | `study_agent/cli.py` |
| Configuração de Provedores & Chaves | `study_agent/config.py` |
| Chamadas unificadas de LLM (Prompt/JSON) | `study_agent/core/llm_client.py` |
| Perguntas de diagnóstico & cálculo de nível | `study_agent/core/diagnostician.py` |
| Montagem da árvore de estudos & tópicos | `study_agent/core/curriculum_gen.py` |
| Explicações didáticas, analogias Feynman | `study_agent/core/teacher.py` |
| Testes de absorção & cálculo de pontuação | `study_agent/core/evaluator.py` |
| Schemas do Aluno & Objetivos | `study_agent/models/student.py` |
| Schemas da Trilha & Tópicos | `study_agent/models/curriculum.py` |
| Salvar/Recuperar progresso em disco | `study_agent/storage/session_store.py` |

## 4. Arquivos Sensíveis / Proibidos para Leitura Automática
- `.env` (contém chaves de API reais do usuário)
- `data/*.json` (contém histórico pessoal de estudos sem necessidade de leitura completa)
