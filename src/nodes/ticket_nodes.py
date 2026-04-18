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
    return {"ticket_agent_output": output}

def store_knowledge_node(state: AgentState) -> Dict[str, Any]:
    """Armazena o ticket na Base de Conhecimento antes da análise de código."""
    print("--- [ARMAZENANDO TICKET NA KB] ---")
    kb = get_kb()
    kb.add_ticket(state["current_ticket_data"] if "current_ticket_data" in state else state["ticket_data"])
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
        message = f"✅ IA encontrou um problema similar no passado:\n{ticket_output['summary']}\nConfiança: {ticket_output['confidence']}\nTickets Relacionados: {', '.join(similar_ids)}"
    elif code_output and code_output.get("status") == "analyzed":
        affected_files = [str(f) for f in code_output.get('affected_files', [])]
        message = f"💻 Análise de Código IA:\nCausa Raiz: {code_output['root_cause']}\nSugestão de Correção: {code_output['suggested_fix']}\nArquivos Afetados: {', '.join(affected_files)}\nConfiança: {code_output['confidence']}"
    else:
        message = "A IA não conseguiu encontrar uma resolução clara ou a causa raiz."

    movidesk = get_movidesk()
    movidesk.update_ticket(ticket_id, {"comments": [{"body": message, "type": 1}]})
    
    return {"is_processed": True}
