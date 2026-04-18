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
        # Extracting subject and description (usually the first comment in Movidesk)
        subject = ticket_data.get('subject', '')
        comments = ticket_data.get('comments', [])
        description = comments[0].get('body', '') if comments else ""
        
        query = f"{subject} {description}"
        
        # 1. Semantic Search
        results = self.kb.search_similar_tickets(query, k=3)
        
        if not results:
            return {"status": "no_match"}

        # 2. LLM Decision on similarity
        past_tickets_str = ""
        for i, doc in enumerate(results):
            content = doc.page_content.replace("{", "{{").replace("}", "}}")
            past_tickets_str += f"\n[Ticket {i+1}]:\n{content}\n"

        prompt = ChatPromptTemplate.from_messages([
            ("system", """Você é um Agente de Inteligência de Tickets. Seu objetivo é identificar se um novo ticket de suporte pode ser resolvido usando tickets antigos.
            
            Retorne uma resposta JSON com:
            - status: "resolved" se uma solução clara for encontrada, caso contrário "no_match"
            - confidence: pontuação de 0 a 1
            - summary: Breve explicação da solução encontrada ou por que não corresponde
            - related_ticket_ids: Lista de IDs de tickets das correspondências passadas
            """),
            ("human", f"""Novo Ticket:
            Assunto: {subject.replace('{', '{{').replace('}', '}}')}
            Descrição: {description.replace('{', '{{').replace('}', '}}')}

            Tickets Similares Passados:
            {past_tickets_str}

            Analise e decida se há uma correspondência.""")
        ])

        chain = prompt | self.llm
        
        try:
            response = chain.invoke({})
            content = response.content
            
            # Extract JSON from response
            import json
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            
            # Try to parse the JSON output from LLM
            try:
                result = json.loads(content)
                # Ensure all required keys exist, if not, use the LLM's values or fallback
                return {
                    "status": result.get("status", "no_match"),
                    "confidence": result.get("confidence", 0.0),
                    "summary": result.get("summary", ""),
                    "similar_tickets": result.get("related_ticket_ids", [doc.metadata.get("ticket_id") for doc in results])
                }
            except json.JSONDecodeError:
                # Fallback if LLM output is not valid JSON but contains "resolved"
                if "resolved" in content.lower() and "no_match" not in content.lower():
                    return {
                        "status": "resolved",
                        "confidence": 0.8,
                        "summary": content,
                        "similar_tickets": [doc.metadata.get("ticket_id") for doc in results]
                    }
                return {"status": "no_match"}
                
        except Exception as e:
            print(f"Erro no Agente 1: {e}")
            return {"status": "no_match", "error": str(e)}
