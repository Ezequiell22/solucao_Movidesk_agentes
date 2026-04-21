import logging
from typing import Dict, Any, List
from langchain_core.prompts import ChatPromptTemplate
from src.tools.knowledge_base import KnowledgeBase
from src.utils.llm import get_llm
from src.utils.json_utils import parse_llm_json

logger = logging.getLogger(__name__)

class TicketIntelligenceAgent:
    def __init__(self, kb: KnowledgeBase = None):
        self.kb = kb or KnowledgeBase()
        self.llm = get_llm()

    def run(self, ticket_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyzes a technical ticket and determines if it's a known problem or needs deep code analysis.
        """
        subject = ticket_data.get('subject', '')
        comments_list = ticket_data.get('comments', [])
        full_description = "\n".join([c.get('body', '') for c in comments_list if c.get('body')])
        
        # 1. Search for similar tickets in KB
        query = f"{subject} {full_description}"
        similar_tickets = self.kb.search_similar_tickets(query, k=3)
        
        # 2. Extract past solutions from matches
        past_solutions = []
        for doc in similar_tickets:
            # We only care about tickets with a confidence score implicitly handled by vector search
            # But let's assume we want to show the technical analysis if available
            past_solutions.append({
                "ticket_id": doc.metadata.get("ticket_id"),
                "summary": doc.metadata.get("comments_summary"),
                "analysis": doc.metadata.get("technical_analysis")
            })

        # 3. LLM Analysis
        prompt = ChatPromptTemplate.from_messages([
            ("system", """Você é um Analista de Suporte Técnico Sênior. 
            Seu objetivo é analisar o ticket atual e compará-lo com resoluções passadas.
            
            DIRETRIZES:
            1. Se houver uma correspondência clara (Similaridade > 0.8), consolide as análises passadas.
            2. Se não houver correspondência ou a solução for inconclusiva, encaminhe para ANÁLISE DE CÓDIGO.
            3. SEMPRE forneça um resumo claro dos comentários do ticket atual.
            
            Retorne um JSON com:
            - status: "matched" ou "need_analysis"
            - comments_summary: Resumo executivo dos comentários do ticket atual.
            - past_match_summary: Se matched, consolidação das análises técnicas anteriores.
            - confidence: pontuação de 0 a 1
            - technical_queries: Se need_analysis, uma lista de 3 buscas técnicas (ex: nome de funções, classes T*, termos SQL) para o próximo agente.
            
            IMPORTANTE: Se você já encontrou o ticket na base de conhecimento, mas a solução passada não parece resolver 100% ou se você acha que o código mudou, responda com "need_analysis" para forçar uma nova verificação técnica.
            """),
            ("human", "Ticket Atual:\nAssunto: {subject}\nComentários: {context}\n\nPossíveis Correspondências na KB:\n{past_solutions}")
        ])

        chain = prompt | (self.llm.bind(response_format={"type": "json_object"}) 
                         if hasattr(self.llm, "bind") else self.llm)
        
        try:
            response = chain.invoke({
                "subject": subject,
                "context": full_description,
                "past_solutions": str(past_solutions)
            })
            
            return parse_llm_json(response.content)
        except Exception as e:
            logger.error(f"Error in TicketIntelligenceAgent: {e}")
            return {
                "status": "need_analysis",
                "comments_summary": "Erro ao processar resumo automático.",
                "confidence": 0
            }
