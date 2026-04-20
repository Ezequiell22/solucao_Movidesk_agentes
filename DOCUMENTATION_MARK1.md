# Documentação Técnica Oficial: Projeto MARK1

## 1. Visão Geral
O **MARK1** é um sistema autônomo de suporte técnico de nível sênior, projetado para automatizar a triagem, análise e resolução de tickets do Movidesk, com foco especializado em sistemas legados e modernos desenvolvidos em **Delphi**. Ele combina orquestração de agentes via LangGraph, busca vetorial (RAG) e análise de grafo de dependências para fornecer diagnósticos técnicos precisos e sugestões de correção de código diretamente nos tickets.

---

## 2. Arquitetura do Sistema

### 2.1. Fluxo de Execução (Eternal Loop)
O sistema opera em um loop contínuo definido no `main.py`:
1. **Startup**: Realiza a indexação estrutural e semântica do codebase Delphi configurado.
2. **Polling**: A cada 60 segundos, consulta a API do Movidesk em busca de novos tickets ou atualizações.
3. **Orquestração**: Para cada ticket encontrado, instancia um grafo de estados (LangGraph) que gerencia o ciclo de vida da análise.

### 2.2. O Grafo de Estados (LangGraph)
O fluxo de decisão é cíclico e orientado por estados:
- **ticket_intelligence**: Agente 1 analisa se o problema já foi resolvido anteriormente (KB Search).
- **store_knowledge**: Armazena o ticket atual e metadados iniciais.
- **code_analysis**: Agente 2 realiza a análise profunda do código-fonte (RAG + Grafo).
- **update_kb_after_analysis**: Atualiza a Base de Conhecimento com a nova análise técnica gerada.
- **send_to_movidesk**: Envia a resposta final consolidada para o ticket.

---

## 3. Inteligência de Análise de Código (Agente 2)

O diferencial do MARK1 é o seu **CodeAnalysisAgent**, que utiliza uma abordagem de "Raciocínio Iterativo em Camadas":

### 3.1. Indexação por Grafo (CodeGraph)
Diferente de RAGs comuns que tratam arquivos como texto plano, o MARK1 constrói um grafo de dependências:
- **Extração de Unidades**: Identifica cláusulas `uses`, classes e assinaturas de métodos.
- **Mapeamento de Chamadas**: Detecta quem chama quem, permitindo que o agente "navegue" pelas Units.

### 3.2. Retrieval em Múltiplas Camadas
Ao receber um problema:
- **Camada Semântica**: Busca trechos de código relevantes usando embeddings e busca MMR (Maximal Marginal Relevance) para evitar redundância.
- **Expansão por Grafo**: Identifica as Units de dependência (do `uses`) e injeta o contexto estrutural dessas Units no prompt do LLM.

### 3.3. Loop Iterativo de Raciocínio (Max 5 iterações)
O agente não responde imediatamente. Ele segue um processo de **Chain-of-Thought**:
1. **Hipóteses**: Levanta pelo menos 3 causas possíveis.
2. **Evidências**: Busca no código provas para confirmar ou refutar cada hipótese.
3. **Auditoria Pedante**: Realiza a transcrição literal de strings SQL para detectar typos sutis (ex: `nullo` em vez de `null`).
4. **Decisão**: Se o contexto for insuficiente, ele gera uma nova query de busca e itera novamente.

---

## 4. Tecnologias Utilizadas
- **LangChain & LangGraph**: Orquestração e RAG.
- **ChromaDB**: Banco vetorial para tickets e código.
- **HuggingFace Embeddings**: `all-MiniLM-L6-v2` para representação vetorial eficiente.
- **LLM**: Suporte a GPT-4, GPT-5 e Llama 3 (via Groq/OpenAI) com `json_object` nativo.
- **FastAPI**: Interface de monitoramento e status.

---

## 5. Análise Crítica (MARK1)

### 5.1. Pontos Fortes
- **Resiliência Estrutural**: O uso de `response_format={"type": "json_object"}` e esquemas de reparo automático garante que o sistema não trave por erros de parsing.
- **Contexto Delphi Real**: O `DelphiCodeSplitter` personalizado respeita a sintaxe da linguagem, evitando quebra de funções no meio da análise.
- **Memória de Longo Prazo**: A integração contínua com a Base de Conhecimento permite que o sistema "aprenda" com cada novo bug resolvido.

### 5.2. Defeitos e Limitações Atuais
- **Parser de Código Baseado em Regex**: A extração de métodos e chamadas usa expressões regulares, que podem falhar em sintaxes Delphi extremamente complexas ou macros de pré-processamento.
- **Custo de Tokens**: O loop iterativo com acúmulo de contexto pode consumir muitos tokens em análises que exigem 4 ou 5 iterações.
- **Dependência de Embeddings Genéricos**: O uso de um modelo de embedding geral pode não capturar nuances semânticas específicas de termos de negócio do domínio Delphi/ERP.

### 5.3. Oportunidades de Melhoria
- **AST Parsing**: Substituir regex por um parser AST (Abstract Syntax Tree) real para Delphi para mapeamento perfeito de dependências.
- **Fine-tuning de Embedding**: Treinar ou ajustar um modelo de embedding focado em código-fonte Pascal/Delphi.
- **Interface Visual**: Implementar um dashboard para visualizar o grafo de dependências e o rastro de pensamento (thought trace) do agente em tempo real.

---

**Status do Projeto**: MARK1 - Versão de Produção Estável.
**Data**: 2026-04-19
**Autor**: IA Pair Programmer (Trae IDE)
