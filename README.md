# 🧠 AI Study Agent — Tutor Adaptativo & Mentor de Bancada (`v0.3.0`)

![Versão](https://img.shields.io/badge/version-0.3.0-06b6d4)
![Python](https://img.shields.io/badge/python-3.10%2B-3b82f6)
![Interface](https://img.shields.io/badge/interface-CLI%20%2B%20Web%20Studio-10b981)
![LLM](https://img.shields.io/badge/LLM-Gemini%20%7C%20OpenAI%20%7C%20Claude%20%7C%20Ollama-8b5cf6)

O **AI Study Agent** é um mentor particular adaptativo para estudar programação, ferramentas e arquitetura de software — combinando **Terminal Interativo (CLI)** e **Dashboard Web Integrado (`FastAPI`)** sobre a mesma base de dados local.

Em vez de gerar respostas genéricas de chat, ele diagnostica seu nível real, constrói uma **trilha em grafo (DAG)** sob medida, conduz aulas práticas com **Laboratório Guiado** e **Debugging em Tempo Real**, avalia sua retenção via **Active Recall**, agenda revisões periódicas com **Repetição Espaçada (SuperMemo SM-2)** e recompensa sua evolução prática com **XP, Ofensivas (Streaks), Metas com Prazo e Conquistas**.

---

## 🌟 O que traz a Versão Atual (`v0.3.0`)

1. **🖥️ Dupla Experiência Sincronizada (CLI + Web Studio):**
   - Estude pelo terminal (`.\study-agent study`) ou abra o painel visual completo no navegador (`.\study-agent web`) sem precisar de Node.js ou `npm`. Todo o progresso em `data/` é compartilhado instantaneamente entre ambos.
2. **🎓 Pedagogia Ativa e Mão na Massa:**
   - **Diagnóstico Adaptativo:** 3 perguntas graduais calibram sua trilha (`beginner`, `intermediate` ou `advanced`).
   - **4 Modos de Estudo:** *Técnica de Feynman* (analogias), *Técnico & Formal*, *Prático (Hands-on)* e *Laboratório Guiado Passo a Passo* com checkpoints executáveis.
   - **Assistente de Debugging em Tempo Real:** Cole qualquer erro ou *stack trace* do terminal para receber a tradução didática, a causa raiz e o comando corrigido para o seu sistema operacional.
   - **Active Recall:** Perguntas abertas ao final de cada tópico (nota de corte `>= 70%` para desbloquear os próximos nós do grafo).
3. **🏆 Gamificação "Mão na Massa", Metas & Streaks:**
   - **XP focado em prática real (anti-farming):** `+15 XP` por missão inédita de laboratório, `+100 XP` ao dominar um tópico pela 1ª vez, `+25 XP` de bônus de excelência (`>= 90%`) e `0 XP` em dúvidas ou revisões.
   - **6 Patentes de Evolução:** `Iniciante` ➔ `Explorador` ➔ `Praticante` ➔ `Construtor` ➔ `Especialista` ➔ `Mestre`.
   - **Metas com Prazo & 17 Conquistas:** Defina sprints ou prazos personalizados com recomendação diária de ritmo e desbloqueie medalhas em 6 categorias.
4. **🔄 Repetição Espaçada (SRS / Algoritmo SM-2) & Exportação Offline:**
   - Tópicos dominados entram automaticamente na fila SM-2 (`1d ➔ 6d ➔ round(I × EF)`), mantendo sua **Ofensiva Diária 🔥** acesa e blindando a memória de longo prazo.
   - Exporte a qualquer momento seus resumos estruturados em **Markdown** (Obsidian/GitHub) e decks de flashcards prontos para o **Anki 2.1.54+**.

---

## 🚀 Instalação e Configuração

### 1. Clone o repositório e crie o ambiente virtual

```bash
git clone https://github.com/joao050/study_agent.git
cd study_agent
python -m venv .venv
```

### 2. Instale as dependências

**No Windows (PowerShell ou CMD, sem precisar ativar `.ps1`):**
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

### 3. Configure seu Provedor de IA (`.env`)

Copie o arquivo de exemplo e preencha a chave do provedor de sua preferência:

```powershell
copy .env.example .env   # Windows
# ou: cp .env.example .env (Linux/macOS)
```

Exemplos de configuração no `.env`:

```env
# Opção 1: Google Gemini (Padrão recomendado)
LLM_PROVIDER=gemini
LLM_MODEL=gemini/gemini-flash-lite-latest
GEMINI_API_KEY=sua_chave_aqui

# Opção 2: OpenAI
# LLM_PROVIDER=openai
# LLM_MODEL=gpt-4o-mini
# OPENAI_API_KEY=sk-...

# Opção 3: Anthropic Claude
# LLM_PROVIDER=anthropic
# LLM_MODEL=claude-3-5-haiku-latest
# ANTHROPIC_API_KEY=sk-ant-...

# Opção 4: 100% Local com Ollama (sem chave de API)
# LLM_PROVIDER=ollama
# LLM_MODEL=ollama/llama3.1
# OLLAMA_API_BASE=http://localhost:11434
```

---

## 🧭 Como Utilizar (Guia Prático)

Você pode usar o **AI Study Agent** pelo navegador, pelo terminal, ou alternando entre os dois a qualquer momento.

### 🖥️ Modo 1 — Interface Gráfica (Web Studio Integrado)

Inicie o servidor local (ele abrirá seu navegador automaticamente em `http://127.0.0.1:8000`):

```powershell
.\study-agent web
# ou de forma multiplataforma: python -m study_agent.cli web
```

Opções úteis do comando `web`:
- `.\study-agent web --port 8080` — Escolhe outra porta HTTP local.
- `.\study-agent web --no-open` — Sobe o servidor sem abrir aba automática no navegador.

**O que você encontra no Web Studio:**
1. **✨ Nova Trilha & Alternador de Perfis (Topo):** Crie uma nova jornada respondendo às 3 perguntas diagnósticas direto na tela ou alterne entre trilhas existentes.
2. **📊 Faixa de Status Viva:** Acompanhe sua patente/barra de XP, chama da Ofensiva Diária, Termômetro de Meta (com botão *Editar* para definir/remover prazos) e contador da fila SRS.
3. **🗺️ Aba Mapa & Trilha:** Visualize o grafo interativo `Mermaid.js` de pré-requisitos e abra qualquer tópico desbloqueado na Sala de Estudo.
4. **📖 Aba Sala de Estudo & Lab:** Gere aulas (*Feynman*, *Técnico* ou *Prático*), execute missões do **Laboratório Guiado** ganhando `+15 XP` por checkpoint, tire dúvidas, cole erros no **Assistente de Debugging** lateral e faça a avaliação de **Active Recall**.
5. **🔄 Aba Revisão Rápida (SRS):** Revise os tópicos vencidos do dia com recálculo automático da curva SM-2 (`EF` e próximo intervalo).
6. **🏅 Aba Conquistas & Botão Exportar:** Consulte as 17 medalhas disponíveis e baixe em 1 clique seu resumo `.md` e seu deck `.txt` do Anki.

---

### 💻 Modo 2 — Linha de Comando (Fluxo Completo via CLI)

#### Passo 1: Criar sua trilha personalizada (`init`)
```powershell
.\study-agent init
# Opcionalmente já passando nome, assunto e meta com prazo:
.\study-agent init --name "João" --subject "FastAPI Assíncrono" --days 10 --goal "Dominar antes do novo projeto"
```

#### Passo 2: Estudar, praticar no Lab e debugar erros (`study`)
```powershell
.\study-agent study
```
- Escolha entre **[1] Feynman**, **[2] Técnico**, **[3] Prático** ou **[4] Laboratório Guiado Passo a Passo**.
- Durante o estudo ou laboratório, use **`[D]`** para tirar dúvidas, **`[E]`** para colar saídas de erro/stack traces multilinha do seu terminal, e conclua respondendo à checagem de **Active Recall**.

#### Passo 3: Acompanhar evolução, conquistas e metas (`status`, `goal`, `map`)
```powershell
.\study-agent status            # Painel geral: XP, patente, ofensiva, fila SRS e tópicos
.\study-agent status --badges   # Exibe a vitrine completa das 17 conquistas
.\study-agent goal --days 7     # Cria ou atualiza o prazo da meta (use --clear para remover)
.\study-agent map               # Árvore conceitual ASCII (use --mermaid para diagrama Mermaid)
```

#### Passo 4: Revisão Espaçada SM-2 e Exportação (`review` e `export`)
```powershell
.\study-agent review            # Revisão rápida dos tópicos dominados vencidos (mantém Streak 🔥)
.\study-agent export            # Gera resumo Markdown e flashcards Anki na pasta exports/
```

---

## 📋 Referência Rápida de Comandos

| Comando Portátil | Atalho Windows | Descrição |
| :--- | :--- | :--- |
| `python -m study_agent.cli web` | `.\study-agent web` | Inicia o **Dashboard Web Integrado** (`--host`, `--port`, `--no-open`). |
| `python -m study_agent.cli init` | `.\study-agent init` | Executa o diagnóstico pedagógico e gera uma nova trilha (`--days`, `--goal`). |
| `python -m study_agent.cli study` | `.\study-agent study` | Inicia/retoma a aula ou Laboratório Guiado do próximo tópico disponível. |
| `python -m study_agent.cli review` | `.\study-agent review` | Conduz sessão de Repetição Espaçada SM-2 nos tópicos vencidos (`--limit N`). |
| `python -m study_agent.cli status` | `.\study-agent status` | Exibe progresso, XP/patente, streak, meta e fila SRS (`--badges`). |
| `python -m study_agent.cli goal` | `.\study-agent goal` | Define, edita ou limpa a meta com prazo da trilha (`--days`, `--label`, `--clear`). |
| `python -m study_agent.cli map` | `.\study-agent map` | Renderiza a árvore da trilha no terminal ou código `--mermaid`. |
| `python -m study_agent.cli export` | `.\study-agent export` | Exporta resumo `.md` e deck Anki `.txt` (`--format`, `--in-progress`, `-o`). |
| `python -m study_agent.cli students` | `.\study-agent students` | Lista estudantes cadastrados e alterna a sessão ativa (`--switch <ID>`). |
| `python -m study_agent.cli version` | `.\study-agent version` | Exibe a versão instalada (`v0.3.0`). |

---

## 🪟 Dica para Windows & PowerShell (`ExecutionPolicy`)

Em instalações padrão do Windows, o PowerShell pode bloquear a ativação de scripts `.ps1` (`Activate.ps1`) com `PSSecurityException`. Você tem **3 maneiras simples** de rodar:

1. **Wrapper `study-agent.bat` (Zero configuração):** Na raiz do projeto, use direto `.\study-agent web` ou `.\study-agent study` (localiza automaticamente a `.venv` e força UTF-8).
2. **Módulo Python portátil:** `.\.venv\Scripts\python -m study_agent.cli web` (ou `python -m study_agent.cli` com ambiente ativo).
3. **Liberar ativação da `.venv` no usuário atual (opcional):**
   ```powershell
   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
   .\.venv\Scripts\Activate.ps1
   study-agent web
   ```

---

## 🧪 Executando os Testes Automatizados

A suíte conta com **111 testes automatizados** cobrindo modelos Pydantic, resiliência LiteLLM, gerador DAG, professor/debug, avaliador, gamificação, algoritmo SM-2, exportadores, CLI e rotas FastAPI:

```powershell
.\.venv\Scripts\pytest -v
```
