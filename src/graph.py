from langgraph.graph import StateGraph, END
from src.state import AgentState
from src.nodes.ticket_nodes import (
    ticket_intelligence_node,
    store_knowledge_node,
    code_analysis_node,
    send_to_movidesk_node
)

def create_graph():
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("ticket_intelligence", ticket_intelligence_node)
    workflow.add_node("store_knowledge", store_knowledge_node)
    workflow.add_node("code_analysis", code_analysis_node)
    workflow.add_node("send_to_movidesk", send_to_movidesk_node)

    # Entry point: Analysis starts directly from intelligence agent
    workflow.set_entry_point("ticket_intelligence")

    # Conditional Routing from Agent 1 (for the ticket)
    def route_after_intelligence(state: AgentState):
        if state.get("error"):
            return END
            
        output = state.get("ticket_agent_output")
        if output and output.get("status") == "resolved":
            return "send_to_movidesk"
        
        # If no match in local knowledge base, proceed to store and then code analysis
        return "store_knowledge"

    workflow.add_conditional_edges(
        "ticket_intelligence",
        route_after_intelligence,
        {
            "send_to_movidesk": "send_to_movidesk",
            "store_knowledge": "store_knowledge",
            END: END
        }
    )

    # Store knowledge, then analyze code
    workflow.add_edge("store_knowledge", "code_analysis")
    
    # After analysis, send result to Movidesk
    workflow.add_edge("code_analysis", "send_to_movidesk")
    
    # End of flow for this ticket
    workflow.add_edge("send_to_movidesk", END)

    return workflow.compile()
