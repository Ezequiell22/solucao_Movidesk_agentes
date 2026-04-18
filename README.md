# Movidesk AI Agent - Analista de Suporte Inteligente 🚀

Este projeto é um sistema de IA de nível de produção projetado para automatizar a análise e resolução de tickets do Movidesk, especializado em sistemas legados (Delphi). Utiliza uma arquitetura de agentes duplos orquestrada por **LangGraph** para oferecer suporte técnico preciso e rápido.

---

## 📖 O que é esta solução?

### **Explicação Leiga (Para Gestores e Usuários)**
Imagine que você tem um super-analista de suporte que nunca dorme. Toda vez que um novo ticket chega no Movidesk, este sistema:
1.  **Lê o problema** e vasculha instantaneamente todos os tickets resolvidos no passado para ver se alguém já consertou algo parecido.
2.  **Se encontrar a solução**, ele já responde o ticket com o passo a passo.
3.  **Se for um problema novo**, ele "abre o código-fonte" do seu software (como um desenvolvedor faria), analisa as funções e procedimentos e tenta encontrar onde está o erro, sugerindo uma correção técnica para o seu time de desenvolvimento.

Isso reduz drasticamente o tempo de resposta e ajuda a equipe técnica a focar em problemas complexos, enquanto a IA resolve o "repetitivo".

### **Explicação Técnica (Para Desenvolvedores)**
A solução é um pipeline de **RAG (Retrieval-Augmented Generation)** multi-agente:
-   **Orquestração**: Baseada em **LangGraph**, permitindo um fluxo de estados cíclico e condicional.
-   **Agente 1 (Ticket Intelligence)**: Realiza busca semântica em um banco vetorial (**ChromaDB**) de tickets históricos. Decide via LLM (**Llama 3.3 70B via Groq**) se a similaridade é suficiente para uma resolução automática.
-   **Agente 2 (Code Analysis)**: Ativado apenas em caso de novos problemas. Ele realiza busca semântica no código-fonte Delphi (indexado por procedimentos/funções) e gera um relatório de causa raiz e sugestão de correção.
-   **Infraestrutura**: Loop eterno assíncrono que consome a API do Movidesk a cada 60 segundos.

---

## 🛠️ Tecnologias Utilizadas

-   **Python 3.10+**
-   **LangChain / LangGraph**: Frameworks de agentes e orquestração.
-   **Groq (Llama 3.3 70B)**: Inferência de LLM ultra-rápida.
-   **ChromaDB**: Banco de dados vetorial para tickets e código.
-   **HuggingFace**: Embeddings locais (`all-MiniLM-L6-v2`).
-   **FastAPI**: Interface de monitoramento e ciclo de vida.

---

## 🚀 Como Instalar e Usar

### **1. Pré-requisitos**
-   Python 3.10 ou superior instalado.
-   Chave de API do **Groq** (obtenha em [console.groq.com](https://console.groq.com/)).
-   Token de API do **Movidesk**.

### **2. Instalação**

Clone o repositório e instale as dependências:

```bash
# Instalar dependências
python3 -m pip install -r requirements.txt
```

### **3. Configuração**

Crie um arquivo `.env` na raiz do projeto com as seguintes variáveis:

```env
# API Keys
GROQ_API_KEY=sua_chave_groq_aqui
MOVIDESK_API_KEY=seu_token_movidesk_aqui

# Caminhos
CODEBASE_PATH=/caminho/para/seu/codigo/delphi/src
MOVIDESK_BASE_URL=https://api.movidesk.com/public/v1

# Opcional: Token do HuggingFace para evitar avisos de limite
HF_TOKEN=seu_token_hf_aqui
```

### **4. Execução**

Para iniciar o sistema em modo de produção (loop eterno):

```bash
python3 main.py
```

O sistema irá:
1.  Indexar o seu código-fonte local (apenas na primeira execução ou mudanças).
2.  Iniciar um servidor FastAPI na porta 8000.
3.  Entrar no ciclo de busca e análise de tickets a cada 1 minuto.

---

## 🔄 Fluxo de Trabalho

1.  **Busca**: O sistema consulta a API do Movidesk por tickets atualizados nos últimos 90 dias.
2.  **Triagem**: Para cada ticket, o **Agente 1** verifica a Base de Conhecimento.
3.  **Decisão**:
    *   *Match encontrado?* IA responde no Movidesk e encerra.
    *   *Não encontrado?* O ticket é salvo na base para futuras consultas e o **Agente 2** é acionado.
4.  **Análise de Código**: O Agente 2 vasculha o código-fonte, encontra a causa raiz e sugere a correção.
5.  **Finalização**: A análise técnica é enviada como comentário interno para os analistas humanos.

---

## 📂 Estrutura do Projeto

-   `src/agents/`: Lógica e prompts dos agentes inteligentes.
-   `src/nodes/`: Nós de execução do grafo (LangGraph).
-   `src/tools/`: Ferramentas de busca vetorial e integração com API.
-   `src/utils/`: Utilitários de inicialização (LLM, etc).
-   `main.py`: Ponto de entrada com o loop eterno e servidor API.
