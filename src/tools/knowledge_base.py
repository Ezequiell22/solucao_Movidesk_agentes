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

    def add_ticket(self, ticket: Dict[str, Any]):
        """Add a new ticket to the knowledge base."""
        subject = ticket.get('subject', '')
        comments = ticket.get('comments', [])
        description = comments[0].get('body', '') if comments else ""
        
        content = f"Subject: {subject}\nDescription: {description}"
        metadata = {
            "ticket_id": ticket.get("id"),
            "tags": ",".join(ticket.get("tags", [])) if isinstance(ticket.get("tags"), list) else str(ticket.get("tags", "")),
            "type": "ticket"
        }
        doc = Document(page_content=content, metadata=metadata)
        self.db.add_documents([doc])
