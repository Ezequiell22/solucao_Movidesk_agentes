import os
import json
import logging
from typing import List, Dict, Any
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document

from src.config import settings

logger = logging.getLogger(__name__)

class KnowledgeBase:
    def __init__(self, persist_directory: str = None):
        self.persist_directory = persist_directory or settings.KB_TICKETS_DIR
        self.embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        self.db = Chroma(
            collection_name="past_tickets",
            embedding_function=self.embeddings,
            persist_directory=self.persist_directory
        )

    def search_similar_tickets(self, query: str, k: int = 3) -> List[Document]:
        """Search for similar past tickets."""
        return self.db.similarity_search(query, k=k)

    def add_ticket(self, ticket: Dict[str, Any], comments_summary: str = "", technical_analysis: str = ""):
        """
        Add or update a ticket entry in the knowledge base.
        Prevents duplicates by checking the ticket_id.
        """
        ticket_id = str(ticket.get("id"))
        subject = ticket.get('subject', '')
        comments_list = ticket.get('comments', [])
        full_description = "\n".join([c.get('body', '') for c in comments_list if c.get('body')])
        
        # Store comprehensive content for retrieval
        content = f"Subject: {subject}\nResumo: {comments_summary}\nAnálise Técnica: {technical_analysis}\nContexto: {full_description}"
        
        metadata = {
            "ticket_id": ticket_id,
            "tags": ",".join(ticket.get("tags", [])) if isinstance(ticket.get("tags"), list) else str(ticket.get("tags", "")),
            "type": "ticket",
            "raw_ticket": json.dumps(ticket),
            "comments_summary": comments_summary,
            "technical_analysis": technical_analysis
        }
        
        # Check if ticket already exists to avoid duplicates
        existing = self.db.get(where={"ticket_id": ticket_id})
        if existing and existing['ids']:
            logger.info(f"Updating existing ticket {ticket_id} in Knowledge Base.")
            self.db.delete(ids=existing['ids'])
            
        doc = Document(page_content=content, metadata=metadata)
        self.db.add_documents([doc])
        logger.info(f"Ticket {ticket_id} stored in Knowledge Base.")
