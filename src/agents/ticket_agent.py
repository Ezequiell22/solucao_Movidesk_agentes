import os
from typing import Dict, Any, List
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig
from src.tools.knowledge_base import KnowledgeBase
from src.utils.llm import get_llm

class TicketIntelligenceAgent:
    def __init__(self):
        self.kb = KnowledgeBase()
        self.llm = get_llm()

    def run(self, ticket_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze the ticket and search for similar past resolutions.
        READ-ONLY: Does not modify KB or Codebase.
        """
        # Extracting subject and all comments for full context
        subject = ticket_data.get('subject', '')
        comments_list = ticket_data.get('comments', [])
        
        # Combine all comment bodies into a single description for better context
        full_description = "\n".join([c.get('body', '') for c in comments_list if c.get('body')])
        
        query = f"{subject} {full_description}"
        
        # 1. Semantic Search
        results = self.kb.search_similar_tickets(query, k=3)
        
        if not results:
            return {"status": "no_match"}

        # 2. LLM Decision on similarity and Summarization
        past_tickets_str = ""
        for i, doc in enumerate(results):
            content = doc.page_content.replace("{", "{{").replace("}", "}}")
            # Extract rich metadata for the summary
            past_summary = doc.metadata.get("comments_summary", "Sem resumo")
            past_tech = doc.metadata.get("technical_analysis", "Sem análise técnica")
            past_tickets_str += f"\n[Ticket {doc.metadata.get('ticket_id')}]:\n{content}\nResumo Prévio: {past_summary}\nAnálise Técnica Prévia: {past_tech}\n"

        prompt = ChatPromptTemplate.from_messages([
            ("system", """Você é um Agente de Inteligência de Tickets. Seu objetivo é identificar se um novo ticket de suporte pode ser resolvido usando tickets antigos.
            
            Se encontrar uma correspondência, gere um resumo consolidado que combine a análise técnica dos tickets passados com a situação atual.
            
            Retorne uma resposta JSON com:
            - status: "resolved" se uma solução clara for encontrada, caso contrário "no_match"
            - confidence: pontuação de 0 a 1
            - summary: Resumo detalhado consolidando as análises técnicas passadas e como elas resolvem o ticket atual.
            - related_ticket_ids: Lista de IDs de tickets das correspondências passadas
            - comments_summary: Um resumo curto e objetivo apenas dos comentários do ticket ATUAL.
            """),
            ("human", "Novo Ticket:\nAssunto: {subject}\nContexto (Comentários): {context}\n\nTickets Similares Passados:\n{past_tickets}\n\nAnalise todo o contexto e decida se há uma correspondência. Se sim, crie o resumo consolidado. Sempre retorne também o 'comments_summary' do ticket atual.")
        ])

        chain = prompt | self.llm
        
        try:
            # Prepare inputs by escaping braces in content but keeping keys as placeholders
            safe_subject = subject.replace('{', '{{').replace('}', '}}')
            safe_description = full_description.replace('{', '{{').replace('}', '}}')
            safe_past_tickets = past_tickets_str.replace('{', '{{').replace('}', '}}')

            response = chain.invoke({
                "subject": safe_subject,
                "context": safe_description,
                "past_tickets": safe_past_tickets
            })
            content = response.content
            
            # Extract JSON from response
            import json
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            
            try:
                result = json.loads(content, strict=False)
                return {
                    "status": result.get("status", "no_match"),
                    "confidence": result.get("confidence", 0.0),
                    "summary": result.get("summary", ""),
                    "similar_tickets": result.get("related_ticket_ids", [doc.metadata.get("ticket_id") for doc in results]),
                    "comments_summary": result.get("comments_summary", "")
                }
            except json.JSONDecodeError:
                # Basic fallback
                if "resolved" in content.lower():
                    return {"status": "resolved", "summary": content, "confidence": 0.7, "similar_tickets": []}
                return {"status": "no_match"}
                
        except Exception as e:
            print(f"Erro no Agente 1: {e}")
            return {"status": "no_match", "error": str(e)}
