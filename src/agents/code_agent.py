import re
import logging
from typing import List, Dict, Any

from src.tools.code_analyzer import CodeAnalyzer
from src.utils.llm import get_llm
from src.utils.json_utils import parse_llm_json

logger = logging.getLogger(__name__)


class CodeAnalysisAgent:

    def __init__(self, analyzer: CodeAnalyzer = None, max_iterations: int = 3):
        self.analyzer = analyzer or CodeAnalyzer()
        self.llm = get_llm()
        self.max_iterations = max_iterations or 3

    # =========================
    # 🔥 FOLLOWUP INTELIGENTE (MELHORADO)
    # =========================
    def next_query(self, query, docs):

        context = "\n".join([d.page_content[:300] for d in docs[:10]])

        prompt = f"""
        Você está investigando um bug em Delphi.

        Query atual:
        {query}

        Código analisado:
        {context}

        Sugira a PRÓXIMA busca técnica mais útil para encontrar a causa raiz.

        Regras:
        - Seja específico (nome de método, classe, tabela, etc)
        - Evite frases genéricas
        - Foque em onde o bug pode estar

        Se já encontrou a resposta, responda apenas:
        STOP
        """

        resp = self.llm.invoke(prompt)
        text = resp.content.strip()

        if "STOP" in text.upper():
            return None

        return text

    # =========================
    # 🔥 LOOP CURSOR STYLE (CORRIGIDO)
    # =========================
    def run(self, ticket_data: Dict[str, Any], initial_queries: List[str] = None):

        try:
            subject = ticket_data.get('subject', '')
            comments_list = ticket_data.get('comments', [])
            full_description = "\n".join([
                c.get('body', '') for c in comments_list if c.get('body')
            ])

            if initial_queries and len(initial_queries) > 0:
                current = " ".join(initial_queries)
                logger.info(f"Usando queries do Agente 1: {current}")
            else:
                current = re.sub(r"\[Comentario \d+\]", "", f"{subject} {full_description}")

            history = []
            seen = set()

            for i in range(self.max_iterations):
                logger.info(f"Iteração {i+1} | Query: {current}")

                # 🔥 retrieve já faz: vector + bm25 + graph + rerank LLM
                docs = self.analyzer.retrieve(current)

                # 🔥 evita duplicação
                for d in docs:
                    key = f"{d.metadata.get('unit')}.{d.metadata.get('method')}"
                    if key not in seen:
                        history.append(d)
                        seen.add(key)

                # 🔥 próxima query (estilo cursor)
                new_query = self.next_query(current, docs)

                if not new_query:
                    break

                current = new_query

            return self.generate_answer(current, history)
        except Exception as e:
            logger.error(f"Erro fatal no CodeAnalysisAgent: {e}")
            return {
                "Analise_tecnica": f"Erro interno durante a análise: {str(e)}",
                "Analise_geral": "Não foi possível concluir a análise técnica devido a um erro interno.",
                "docs_used": 0
            }

    # =========================
    # 🔥 RESPOSTA FINAL (OTIMIZADA)
    # =========================
    def generate_answer(self, query, docs):

        # 🔥 limita contexto (evita estouro de token)
        docs = docs[:15]

        context = "\n\n".join([
            f"{d.metadata.get('unit')}.{d.metadata.get('method')}\n{d.page_content[:800]}"
            for d in docs
        ])

        prompt = f"""
        Você é um engenheiro Delphi analisando um bug REAL.

        PERGUNTA:
        {query}

        CÓDIGO DISPONÍVEL:
        {context}

        REGRAS CRÍTICAS:
        - ❌ NÃO invente nada que não esteja no código.
        - ❌ NÃO use conhecimento genérico.
        - ✅ Use SOMENTE o código acima.
        - ✅ Se não encontrar evidência, diga: "não encontrado no código".

        TAREFA:
        Gere duas análises distintas em formato JSON:
        1. "Analise_tecnica": Identifique a causa raiz, aponte exatamente ONDE no código (Unit/Método), forneça uma explicação técnica profunda e uma sugestão de correção contendo um trecho breve de código fonte Pascal/Delphi.
        2. "Analise_geral": Uma explicação clara e executiva da análise para o cliente, sem trechos de código complexos, focando no que foi identificado e como será resolvido.

        RETORNE APENAS O JSON NO FORMATO:
        {{
          "Analise_tecnica": "...",
          "Analise_geral": "..."
        }}

        Responda em português.
        """

        # Forçar formato JSON
        try:
            llm_json = self.llm.bind(response_format={"type": "json_object"})
            resp = llm_json.invoke(prompt)
            data = parse_llm_json(resp.content)
            
            return {
                "Analise_tecnica": data.get("Analise_tecnica", "Erro ao gerar análise técnica."),
                "Analise_geral": data.get("Analise_geral", "Erro ao gerar análise geral."),
                "docs_used": len(docs)
            }
        except Exception as e:
            logger.error(f"Erro ao gerar resposta estruturada: {e}")
            # Fallback básico se o JSON falhar
            resp = self.llm.invoke(prompt)
            return {
                "Analise_tecnica": resp.content,
                "Analise_geral": "Consulte a análise técnica para detalhes.",
                "docs_used": len(docs)
            }