import logging
from typing import Dict, Any
from src.state import AgentState
from src.tools.movidesk import MovideskClient
from src.tools.knowledge_base import KnowledgeBase
from src.agents.ticket_agent import TicketIntelligenceAgent
from src.agents.code_agent import CodeAnalysisAgent
from src.config import settings

logger = logging.getLogger(__name__)

# Lazy global components
_ticket_agent = None
_code_agent = None
_movidesk = None
_kb = None
_analyzer = None

def get_analyzer():
    global _analyzer
    if _analyzer is None:
        from src.tools.code_analyzer import CodeAnalyzer
        _analyzer = CodeAnalyzer(codebase_path=settings.CODEBASE_PATH)
    return _analyzer

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
        _ticket_agent = TicketIntelligenceAgent(kb=get_kb())
    return _ticket_agent

def get_code_agent():
    global _code_agent
    if _code_agent is None:
        _code_agent = CodeAnalysisAgent(analyzer=get_analyzer())
    return _code_agent

def ticket_intelligence_node(state: AgentState) -> Dict[str, Any]:
    """Agent 1: Intelligence analysis (read-only) for the ticket."""
    ticket_data = state["ticket_data"]
    logger.info(f"--- [AGENTE 1: ANALISANDO TICKET {ticket_data.get('id')}] ---")
    agent = get_ticket_agent()
    output = agent.run(ticket_data)
    
    return {
        "ticket_agent_output": output,
        "comments_summary": output.get("comments_summary", "")
    }

def store_knowledge_node(state: AgentState) -> Dict[str, Any]:
    """Stores the ticket in Knowledge Base with summary and technical analysis."""
    logger.info("--- [ARMAZENANDO TICKET NA KB] ---")
    kb = get_kb()
    
    code_output = state.get("code_agent_output")
    tech_analysis = ""
    if code_output:
        # Salva ambas as análises na KB para referência futura
        analise_t = code_output.get("Analise_tecnica", "")
        analise_g = code_output.get("Analise_geral", "")
        tech_analysis = f"[ANÁLISE TÉCNICA]\n{analise_t}\n\n[ANÁLISE GERAL]\n{analise_g}"
    
    kb.add_ticket(
        ticket=state["ticket_data"],
        comments_summary=state.get("comments_summary", ""),
        technical_analysis=tech_analysis
    )
    return {}

def code_analysis_node(state: AgentState) -> Dict[str, Any]:
    """Agent 2: Deep code analysis (Cursor-style) for the ticket."""
    ticket_output = state.get("ticket_agent_output", {})
    if ticket_output.get("status") == "matched" and ticket_output.get("confidence", 0) > 0.8:
        logger.info("--- [SKIP: ANALISE DE CÓDIGO (JÁ RESOLVIDO NA KB)] ---")
        return {}

    logger.info("--- [AGENTE 2: ANÁLISE DE CÓDIGO] ---")
    ticket_data = state["ticket_data"]
    initial_queries = ticket_output.get("technical_queries", [])
    agent = get_code_agent()
    output = agent.run(ticket_data, initial_queries=initial_queries)
    return {"code_agent_output": output}

def send_to_movidesk_node(state: AgentState) -> Dict[str, Any]:
    """Sends the consolidated analysis response back to Movidesk."""
    logger.info("--- [ENVIANDO PARA O MOVIDESK] ---")
    
    ticket_data = state["ticket_data"]
    ticket_id = ticket_data["id"]
    ticket_output = state.get("ticket_agent_output")
    code_output = state.get("code_agent_output")
    
    message = ""
    if ticket_output and ticket_output.get("status") == "matched" and ticket_output.get("confidence", 0) > 0.8:
        similar_ids = [str(tid) for tid in ticket_output.get('similar_tickets', [])]
        message = (
            f"🤖 **Agente analista encontrou tickets anteriores semelhantes**\n\n"
            f"**Tickets:** {', '.join([f'[Ticket {tid}]' for tid in similar_ids])}\n\n"
            f"**Resumo das análises do ticket atual e dos anteriores:**\n"
            f"{ticket_output.get('past_match_summary')}\n\n"
            f"**Confiança:** {ticket_output.get('confidence')}"
        )
    elif code_output:
        # Envia apenas a Analise_geral para o Movidesk conforme solicitado
        analise_geral = code_output.get("Analise_geral")
        if analise_geral:
            message = f"🤖 **Análise do Especialista IA**\n\n{analise_geral}"
        else:
            # Fallback caso a chave nova não exista (retrocompatibilidade temporária)
            message = f"💻 **Análise Técnica de Código IA**\n\n{code_output.get('full_analysis', 'Análise indisponível.')}"
    else:
        message = "A IA não conseguiu encontrar uma resolução clara ou a causa raiz."

    movidesk = get_movidesk()
    movidesk.update_ticket(ticket_id, {"comments": [{"body": message, "type": 1}]})
    
    return {"is_processed": True}
