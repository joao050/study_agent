# 🧠 AI Study Agent — Tutor Adaptativo & Mentor de Bancada (CLI)

Agente inteligente de estudos via terminal que atua como um mentor particular adaptativo para aprendizado de programação, ferramentas e arquitetura de software.

## ✨ Principais Recursos

- **🩺 Diagnóstico Inicial Adaptativo:** Sondagem rápida de conhecimentos prévios para calibrar seu ponto de partida (`beginner`, `intermediate`, `advanced`).
- **🗺️ Trilhas em Grafo (DAG) & Mapas Mentais:** Decomposição automática do tema em tópicos com pré-requisitos validados, visualização em árvore ASCII e exportação para **Mermaid**.
- **🎓 Múltiplos Estilos Pedagógicos:**
  - **Técnica de Feynman:** Analogias intuitivas e clareza conceitual.
  - **Técnico & Formal:** Definições precisas, contratos e funcionamento interno.
  - **Prático (Hands-on):** Exemplos reais e casos de mercado.
  - **🧪 Laboratório Guiado Passo a Passo:** Missões executáveis incrementais (*scaffolding*) com *checkpoints* de validação.
- **🔧 Assistente de Debugging em Tempo Real (`[E]`):** Cole erros ou *stack traces* de múltiplas linhas diretamente do seu terminal para receber a tradução do erro, a causa raiz e o comando corrigido para o seu sistema operacional.
- **🧠 Checagem Ativa (*Active Recall*):** Perguntas abertas ao final de cada sessão com nota de corte (`>= 70%`) para desbloquear novos tópicos.
- **🛡️ Resiliência Multi-Provedor (LiteLLM):** Suporte intercambiável a **Gemini**, **OpenAI**, **Anthropic (Claude)** e **Ollama**, com *retries* automáticos (*backoff exponencial + jitter*) contra erros `503/429`.

---

## 🚀 Instalação e Configuração

### 1. Clone o repositório e crie o ambiente virtual

```bash
git clone https://github.com/joao050/study_agent.git
cd study_agent
python -m venv .venv
```

### 2. Instale as dependências

**No Windows (sem precisar ativar `.ps1`):**
```powershell
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python -m pip install -e .
```

**No Linux / macOS:**
```bash
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

### 3. Configure sua chave de API

Copie o arquivo `.env.example` para `.env` e preencha a chave do provedor desejado:

```powershell
copy .env.example .env   # Windows
# ou: cp .env.example .env (Linux/macOS)
```

```env
LLM_PROVIDER=gemini
LLM_MODEL=gemini/gemini-flash-lite-latest
GEMINI_API_KEY=sua_chave_aqui
```

---

## 🪟 Guia Rápido para Windows & PowerShell (`ExecutionPolicy`)

Em instalações padrão do Windows, o PowerShell bloqueia scripts `.ps1` (como `.\.venv\Scripts\Activate.ps1`) com o erro `PSSecurityException / Running scripts is disabled on this system`, ou o comando `study-agent` não é reconhecido fora da `.venv`.

Você tem **3 formas simples** de executar o projeto no Windows:

### Opção A — Usar o wrapper `study-agent.bat` (Mais prático, zero configuração)
Na raiz do projeto, execute diretamente (funciona no PowerShell e no CMD sem precisar ativar a `.venv`):
```powershell
.\study-agent init
.\study-agent study
.\study-agent status
```

### Opção B — Comando Python portátil universal
Funciona em qualquer sistema operacional com a `.venv` ativa (ou apontando para `.\.venv\Scripts\python`):
```powershell
python -m study_agent.cli init
python -m study_agent.cli study
```

### Opção C — Liberar ativação da `.venv` no PowerShell + comando global `study-agent`
Caso deseje ativar normalmente seu ambiente virtual no PowerShell e usar `study-agent` diretamente:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
.\.venv\Scripts\Activate.ps1
pip install -e .
study-agent study
```

---

## 💻 Comandos Disponíveis

| Comando | Atalho Windows | Descrição |
| :--- | :--- | :--- |
| `python -m study_agent.cli init` | `.\study-agent init` | Realiza o diagnóstico de nível e gera sua trilha personalizada. |
| `python -m study_agent.cli study` | `.\study-agent study` | Inicia/retoma a aula do próximo tópico (Feynman, Técnico, Prático ou Laboratório Guiado). |
| `python -m study_agent.cli status` | `.\study-agent status` | Exibe o painel de progresso geral e tabela de tópicos. |
| `python -m study_agent.cli map` | `.\study-agent map` | Renderiza a árvore conceitual da trilha (`--mermaid` para código Mermaid). |
| `python -m study_agent.cli export` | `.\study-agent export` | Exporta guia Markdown (`.md`) e flashcards Anki (`.txt`) na pasta `exports/`. |
| `python -m study_agent.cli students` | `.\study-agent students` | Lista perfis salvos e alterna entre trilhas (`--switch <ID>`). |
| `python -m study_agent.cli version` | `.\study-agent version` | Exibe a versão atual instalada. |

---

## 🧪 Executando os Testes Automatizados

```powershell
.\.venv\Scripts\pytest -v
```
