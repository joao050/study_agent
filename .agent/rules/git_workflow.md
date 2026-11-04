---
trigger: always_on
description: Diretrizes obrigatórias para gerenciamento de branches GitFlow, commits em pt-BR e controle de push para o repositório GitHub.
---

# Regra Permanente: Fluxo Git & GitFlow Automatizado (AI Study Agent)

Esta regra é de cumprimento mandatório pelo assistente para qualquer tarefa de nova funcionalidade, alteração ou correção de código no repositório `https://github.com/joao050/study_agent.git`.

---

## 1. Estratégia de Branches (GitFlow)

O repositório opera com três níveis de branches:
1. **`main`**: Versão final e estável de produção. Nunca commitar diretamente nela.
2. **`develop`**: Branch de integração onde confluem todos os Pull Requests validados.
3. **Branches de Trabalho (Features / Fixes)**:
   - Toda nova funcionalidade, módulo ou tarefa deve ser desenvolvida em uma branch específica criada a partir de `develop`:
     - Formato para novas funcionalidades: `feature/<TASK-ID>-<descricao-curta>` (ex.: `feature/TASK-03-llm-client`)
     - Formato para correções/bugs: `fix/<TASK-ID>-<descricao-curta>` (ex.: `fix/TASK-02-schema-validator`)
     - Formato para documentação ou refatoração pontual: `chore/<descricao-curta>` ou `docs/<descricao-curta>`

### Protocolo de início de tarefa:
Antes de escrever ou alterar qualquer arquivo de uma nova tarefa:
```bash
git checkout develop
git pull origin develop
git checkout -b <tipo>/<identificador>
```

---

## 2. Padrão de Commits em Português Brasileiro (pt-BR)

Todos os commits devem seguir a convenção de Commits Semânticos (Conventional Commits), com **mensagens descritivas obrigatoriamente escritas em Português do Brasil**:

- `feat: <descrição em português>` — Nova funcionalidade ou módulo.
  - *Exemplo:* `feat: adiciona cliente unificado de LLM com suporte a structured outputs`
- `fix: <descrição em português>` — Correção de bug ou falha em código existente.
  - *Exemplo:* `fix: corrige cálculo de pontuação nos modelos Pydantic`
- `test: <descrição em português>` — Criação ou ajuste de testes automatizados.
  - *Exemplo:* `test: adiciona testes unitários para o gerador de currículo`
- `docs: <descrição em português>` — Alterações em documentação ou regras de agente.
  - *Exemplo:* `docs: atualiza mapa do projeto com novo módulo de diagnóstico`
- `refactor: <descrição em português>` — Refatoração de código sem alteração de comportamento.
  - *Exemplo:* `refactor: desacopla chamadas de prompt do módulo do professor`
- `chore: <descrição em português>` — Tarefas de configuração, dependências ou ambiente.
  - *Exemplo:* `chore: adiciona dependência litellm ao requirements.txt`

---

## 3. Controle Rigoroso de `git push` (Autorização Prévia Mandatória)

O assistente está autorizado a:
- Criar branches locais;
- Fazer edições de código e testes;
- Executar `git add` e `git commit` localmente na branch de trabalho correspondente.

O assistente **NUNCA DEVE EXECUTAR `git push` AUTOMATICAMENTE**:
1. Ao concluir os commits de uma tarefa ou etapa, o assistente deve:
   - Exibir um resumo claro das mudanças realizadas;
   - Informar o hash e mensagem do commit gerado;
   - **Solicitar expressamente a revisão e aprovação do usuário para fazer o push para o GitHub**.
2. Somente após a resposta afirmativa explícita do usuário (ex.: *"pode subir"*, *"autorizado"*, *"faça o push"*), o assistente executará:
   ```bash
   git push -u origin <nome-da-branch>
   ```
3. Após o envio bem-sucedido, o assistente fornecerá as orientações/link para abertura do Pull Request em direção à branch `develop` no GitHub.
