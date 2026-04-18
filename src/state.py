from typing import TypedDict, List, Dict, Any, Optional

class AgentState(TypedDict):
    # Input ticket data (passed from external loop)
    ticket_data: Dict[str, Any]
    
    # Agent 1 (Ticket Intelligence) Output
    ticket_agent_output: Optional[Dict[str, Any]]
    
    # Agent 2 (Code Analysis) Output
    code_agent_output: Optional[Dict[str, Any]]
    
    # LLM Summary of comments
    comments_summary: Optional[str]
    
    # Errors
    error: Optional[str]
    
    # Flag to indicate if processing is complete for this ticket
    is_processed: bool
