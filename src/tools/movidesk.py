import os
import requests
import json
from typing import Dict, Any, Optional, List
from src.tools.models import Ticket

class MovideskClient:
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        self.api_key = api_key or os.getenv("MOVIDESK_API_KEY")
        self.base_url = base_url or os.getenv("MOVIDESK_BASE_URL", "https://api.movidesk.com/public/v1")
        self.mock_file_path = "/Users/ezequielmenegas/git/agentes/mocs/movideskTickets.txt"

    def get_tickets(self) -> List[Ticket]:
        """Fetch all tickets from Movidesk updated in the last 90 days."""
        if not self.api_key or "your_" in self.api_key:
            # Load mock data from the specified file
            if os.path.exists(self.mock_file_path):
                try:
                    with open(self.mock_file_path, 'r') as f:
                        data = json.load(f)
                        tickets = []
                        for i, item in enumerate(data):
                            # Fallback for ID if missing in mock
                            if not item.get("id"):
                                item["id"] = item.get("protocol") or str(1000 + i)
                            tickets.append(Ticket(**item))
                        return tickets
                except Exception as e:
                    print(f"Error loading mock file: {e}")
            
            # Fallback if file loading fails
            return []
        
        # According to documentation, GET /tickets returns a list of tickets updated in the last 90 days
        params = {"token": self.api_key}
        response = requests.get(f"{self.base_url}/tickets", params=params)
        response.raise_for_status()
        
        data = response.json()
        if isinstance(data, list):
            return [Ticket(**item) for item in data]
        return [Ticket(**data)]

    def update_ticket(self, ticket_id: str, data: Dict[str, Any]) -> bool:
        """Update a ticket in Movidesk using PATCH."""
        if not self.api_key or "your_" in self.api_key:
            print(f"MOCK: Updating ticket {ticket_id} with {data}")
            return True

        params = {"token": self.api_key, "id": ticket_id}
        response = requests.patch(f"{self.base_url}/tickets", params=params, json=data)
        response.raise_for_status()
        return True
