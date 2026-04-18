import os
from typing import Dict, Any
from src.state import AgentState
from src.tools.movidesk import MovideskClient
from src.tools.knowledge_base import KnowledgeBase
from src.agents.ticket_agent import TicketIntelligenceAgent
from src.agents.code_agent import CodeAnalysisAgent

# Lazy initialization of components to avoid error at import time if environment variables are missing
_ticket_agent = None
_code_agent = None
_movidesk = None
_kb = None

def get_movidesk():
    global _movidesk
    if _movidesk is None:
        _movidesk = MovideskClient()
    return _movidesk

def get_kb():
    global _kb
    if _kb is None:
        _kb = KnowledgeBase()
    return _kb

def get_ticket_agent():
    global _ticket_agent
    if _ticket_agent is None:
        _ticket_agent = TicketIntelligenceAgent()
    return _ticket_agent

def get_code_agent():
    global _code_agent
    if _code_agent is None:
        _code_agent = CodeAnalysisAgent()
    return _code_agent

def ticket_intelligence_node(state: AgentState) -> Dict[str, Any]:
    """Agent 1: Análise de inteligência apenas leitura para o ticket."""
    ticket_data = state["ticket_data"]
    print(f"--- [AGENTE 1: ANALISANDO TICKET {ticket_data.get('id')}] ---")
    agent = get_ticket_agent()
    output = agent.run(ticket_data)
    
    return {
        "ticket_agent_output": output,
        "comments_summary": output.get("comments_summary", "")
    }

def store_knowledge_node(state: AgentState) -> Dict[str, Any]:
    """Armazena o ticket na Base de Conhecimento com resumo e análise técnica."""
    print("--- [ARMAZENANDO TICKET NA KB] ---")
    kb = get_kb()
    
    # Get technical analysis if it was just performed (Agent 2)
    # or if we are just storing it after Agent 1 found no match
    tech_analysis = ""
    code_output = state.get("code_agent_output")
    if code_output:
        tech_analysis = code_output.get("full_analysis", "")
    
    kb.add_ticket(
        ticket=state["ticket_data"],
        comments_summary=state.get("comments_summary", ""),
        technical_analysis=tech_analysis
    )
    return {}

def code_analysis_node(state: AgentState) -> Dict[str, Any]:
    """Agent 2: Análise de código estilo Cursor para o ticket."""
    print("--- [AGENTE 2: ANÁLISE DE CÓDIGO] ---")
    ticket_data = state["ticket_data"]
    agent = get_code_agent()
    output = agent.run(ticket_data)
    return {"code_agent_output": output}

def send_to_movidesk_node(state: AgentState) -> Dict[str, Any]:
    """Envia a resposta para o Movidesk para o ticket processado."""
    print("--- [ENVIANDO PARA O MOVIDESK] ---")
    
    ticket_data = state["ticket_data"]
    ticket_id = ticket_data["id"]
    ticket_output = state.get("ticket_agent_output")
    code_output = state.get("code_agent_output")
    
    if ticket_output and ticket_output.get("status") == "resolved":
        similar_ids = [str(tid) for tid in ticket_output.get('similar_tickets', [])]
        message = (
            f"🤖 **Agente analista encontrou tickets anteriores semelhantes**\n\n"
            f"**Tickets:** [{', '.join(similar_ids)}]\n\n"
            f"**Resumo das análises do ticket atual e dos anteriores:**\n"
            f"{ticket_output['summary']}\n\n"
            f"**Confiança:** {ticket_output['confidence']}"
        )
    elif code_output and (code_output.get("status") == "analyzed" or code_output.get("full_analysis")):
        # Esta parte é acionada quando é um problema novo (Agent 2 rodou)
        message = f"💻 **Análise Técnica de Código IA**\n\n{code_output.get('full_analysis')}"
    else:
        message = "A IA não conseguiu encontrar uma resolução clara ou a causa raiz."

    movidesk = get_movidesk()
    movidesk.update_ticket(ticket_id, {"comments": [{"body": message, "type": 1}]})
    
    return {"is_processed": True}
