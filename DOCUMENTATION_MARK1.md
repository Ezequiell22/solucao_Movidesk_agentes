# Documentação Técnica Oficial: Projeto MARK1 (Autonomous Delphi Support)

## 1. Visão Geral
O **MARK1** é um sistema de suporte técnico autônomo de nível industrial, projetado para triagem, análise profunda e resolução de tickets do Movidesk. Especializado em ecossistemas **Delphi**, o MARK1 não apenas busca soluções em bases históricas, mas atua como um **Arquiteto Sênior** que navega no código-fonte real para identificar bugs lógicos, erros de SQL e falhas de arquitetura.

---

## 2. Arquitetura de Agentes e Orquestração

### 2.1. O Ciclo de Vida do Ticket
O sistema opera em um **Eternal Loop** (monitoramento contínuo) integrado ao ciclo de vida da aplicação FastAPI:
1.  **Git Sync**: Sincronização automática com a branch `main` do repositório de código a cada 5 minutos.
2.  **Real-time Watcher**: Monitoramento via `watchdog` que detecta alterações físicas nos arquivos `.pas` e atualiza o índice incrementalmente.
3.  **Polling Movidesk**: Consulta de novos tickets via API.
4.  **Graph Execution**: Disparo do fluxo de agentes via **LangGraph**.

### 2.2. Fluxo de Decisão (LangGraph)
-   **Agente 1 (Ticket Intelligence)**: Analisa o ticket e gera "Queries Técnicas" (nomes de classes, métodos prováveis, termos SQL).
-   **Agente 2 (Code Analysis)**: O "Cérebro" do sistema. Executa o loop iterativo estilo Cursor para encontrar a causa raiz.
-   **Nós de Suporte**: Gerenciam persistência no ChromaDB e integração de retorno com o Movidesk.

---

## 3. CodeAnalysisAgent: O Cérebro Técnico (Agente 2)

O **CodeAnalysisAgent** representa o estado da arte em análise de código assistida por IA, utilizando uma arquitetura de recuperação híbrida e raciocínio cíclico.

### 3.1. Recuperação Híbrida (Hybrid Retrieval)
Diferente de sistemas RAG convencionais, o MARK1 utiliza três fontes de verdade simultâneas:
-   **Busca Vetorial (ChromaDB)**: Utiliza `jinaai/jina-embeddings-v2-small-code` (especializado em código) para capturar intenção semântica.
-   **Busca Textual (BM25)**: Utiliza o algoritmo `rank_bm25` para encontrar termos exatos, como nomes de variáveis e identificadores Delphi específicos, onde o embedding pode ser impreciso.
-   **Expansão de Grafo (Graph Expansion)**: Após a busca inicial, o sistema analisa o código recuperado, identifica chamadas de outros métodos (`calls`) e injeta automaticamente o corpo dessas funções no contexto.

### 3.2. Reranking com LLM (Pro Filtro)
Para garantir que o agente não se perca em ruídos, implementamos uma camada de **Reranking**:
1.  O sistema recupera até 25 trechos de código (Vetorial + BM25).
2.  Um LLM de alta performance analisa apenas os metadados e resumos desses trechos.
3.  O LLM pontua e seleciona os **5 trechos mais críticos** para a análise atual, descartando o que não é relevante.

### 3.3. Loop Iterativo "Cursor Style"
O agente opera em um ciclo de até **3 iterações** (configurável):
-   **Busca Refinada**: A cada iteração, o agente decide qual a próxima busca técnica necessária baseada no que ele acabou de ler.
-   **Follow-up Inteligente**: Se o agente lê um método que chama uma procedure `CalcularImposto`, ele gera uma nova query focada nessa procedure na iteração seguinte.
-   **Critério de Parada (STOP)**: O loop encerra assim que a evidência técnica é conclusiva ou o limite de iterações é atingido.

---

## 4. Parser Estruturado (DelphiParser)
O parser do MARK1 foi desenvolvido para entender a gramática do Delphi:
-   **Consciência de Seção**: Ignora declarações na `interface` e foca exclusivamente na `implementation`.
-   **Stack-based Parsing**: Utiliza um contador de profundidade (`begin/try/case` vs `end`) para capturar métodos completos, mesmo com múltiplos níveis de aninhamento e blocos de exceção.
-   **Identificação Qualificada**: Associa métodos às suas respectivas classes (ex: `TController.ProcessarData`), permitindo mapeamento perfeito no grafo.

---

## 5. Estratégia de Embeddings e Resiliência
O sistema possui uma hierarquia de fallback para garantir disponibilidade 24/7:
1.  **Prioridade 1**: `jinaai/jina-embeddings-v2-small-code` (Melhor performance para lógica Pascal).
2.  **Prioridade 2**: `text-embedding-3-large` (OpenAI - Alta precisão semântica).
3.  **Fallback Local**: Modelos locais leves para garantir que o sistema não trave em caso de falha nas APIs externas.

---

## 6. Configurações e Variáveis de Ambiente
O arquivo [config.py](file:///Users/ezequielmenegas/git/agentes/src/config.py) centraliza toda a inteligência:
-   `CODEBASE_PATH`: Caminho do projeto Delphi a ser analisado.
-   `LLM_MODEL_NAME`: Padrão `gpt-4o` para raciocínio sênior.
-   `GIT_SYNC_ENABLED`: Controle de sincronização automática.
-   `EMBEDDING_MODEL_JINA_NAME`: Identificador do modelo especializado.

---

**Última Atualização**: 2026-04-21
**Versão**: 2.0 (Arquitetura Híbrida)
**Autor**: IA Pair Programmer (MARK1 Core Team)
