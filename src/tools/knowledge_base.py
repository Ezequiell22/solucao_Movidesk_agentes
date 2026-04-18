import os
from typing import List, Dict, Any
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document

class KnowledgeBase:
    def __init__(self, persist_directory: str = "./data/tickets_db"):
        self.embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        self.db = Chroma(
            collection_name="past_tickets",
            embedding_function=self.embeddings,
            persist_directory=persist_directory
        )

    def search_similar_tickets(self, query: str, k: int = 3) -> List[Document]:
        """Search for similar past tickets."""
        return self.db.similarity_search(query, k=k)

    def add_ticket(self, ticket: Dict[str, Any], comments_summary: str = "", technical_analysis: str = ""):
        """Add a rich ticket entry to the knowledge base."""
        subject = ticket.get('subject', '')
        comments_list = ticket.get('comments', [])
        full_description = "\n".join([c.get('body', '') for c in comments_list if c.get('body')])
        
        # Store comprehensive content for retrieval
        content = f"Subject: {subject}\nResumo: {comments_summary}\nAnálise Técnica: {technical_analysis}\nContexto: {full_description}"
        
        # Metadata stores the raw objects as JSON strings for later reconstruction
        import json
        metadata = {
            "ticket_id": str(ticket.get("id")),
            "tags": ",".join(ticket.get("tags", [])) if isinstance(ticket.get("tags"), list) else str(ticket.get("tags", "")),
            "type": "ticket",
            "raw_ticket": json.dumps(ticket),
            "comments_summary": comments_summary,
            "technical_analysis": technical_analysis
        }
        doc = Document(page_content=content, metadata=metadata)
        self.db.add_documents([doc])
