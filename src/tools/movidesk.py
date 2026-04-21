import os
import requests
import json
import logging
from typing import Dict, Any, Optional, List
from src.tools.models import Ticket
from src.config import settings

logger = logging.getLogger(__name__)

class MovideskClient:
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        self.api_key = api_key
        self.base_url = base_url or settings.MOVIDESK_BASE_URL
        self.mock_file_path = settings.MOVIDESK_MOCK_PATH

    def get_tickets(self) -> List[Ticket]:
        """Fetch all tickets from Movidesk with pagination support."""
        # Verificação se deve usar MOCK ou API Real
        is_mock = not self.api_key or "your_" in self.api_key
        
        if is_mock:
            logger.info(f"Usando MOCK para tickets (Arquivo: {self.mock_file_path})")
            if os.path.exists(self.mock_file_path):
                try:
                    with open(self.mock_file_path, 'r') as f:
                        data = json.load(f)
                        tickets = []
                        for i, item in enumerate(data):
                            if not item.get("id"):
                                item["id"] = item.get("protocol") or str(1000 + i)
                            tickets.append(Ticket(**item))
                        logger.info(f"Retornando {len(tickets)} tickets do mock.")
                        return tickets
                except Exception as e:
                    logger.error(f"Error loading mock file: {e}")
            else:
                logger.warning(f"Arquivo de mock não encontrado em: {self.mock_file_path}")
            return []
        
        all_tickets = []
        skip = 0
        top = 50 # Reduzi para 50 para ser mais seguro com timeouts
        
        logger.info(f"Iniciando busca na API Real da Movidesk (Base URL: {self.base_url})")
        
        try:
            while True:
                params = {
                    "token": self.api_key,
                    "$skip": skip,
                    "$top": top,
                    "$orderby": "lastActionDate desc",
                    "$select": "id,subject,protocol,lastActionDate,status,tags",
                    "$expand": "comments"
                }
                
                logger.debug(f"Requesting Movidesk: skip={skip}, top={top}")
                response = requests.get(f"{self.base_url}/tickets", params=params, timeout=30)
                
                if response.status_code == 401:
                    logger.error("ERRO 401: Token da Movidesk inválido. Verifique o seu .env")
                    break
                    
                response.raise_for_status()
                
                data = response.json()
                if not data or not isinstance(data, list):
                    logger.info(f"Fim dos dados da API (recebido: {type(data)})")
                    break
                    
                logger.info(f"Página recebida com {len(data)} tickets.")
                
                page_tickets = []
                for item in data:
                    try:
                        page_tickets.append(Ticket(**item))
                    except Exception as parse_err:
                        logger.error(f"Erro ao parsear ticket {item.get('id')}: {parse_err}")
                
                all_tickets.extend(page_tickets)
                
                if len(data) < top:
                    break # Última página alcançada
                    
                skip += top
                
            logger.info(f"Total de tickets carregados da API: {len(all_tickets)}")
            return all_tickets
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro de rede ao consultar Movidesk: {e}")
            return []

    def update_ticket(self, ticket_id: str, data: Dict[str, Any]) -> bool:
        """Update a ticket in Movidesk using PATCH."""
        if not self.api_key or "your_" in self.api_key:
            logger.info(f"MOCK: Updating ticket {ticket_id} with {data}")
            return True

        params = {"token": self.api_key, "id": ticket_id}
        response = requests.patch(f"{self.base_url}/tickets", params=params, json=data)
        response.raise_for_status()
        return True
