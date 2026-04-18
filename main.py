import os
import asyncio
import time
from dotenv import load_dotenv

# Load environment variables BEFORE importing nodes or graph
load_dotenv()

from contextlib import asynccontextmanager
from fastapi import FastAPI, BackgroundTasks
from src.graph import create_graph
from src.nodes.ticket_nodes import get_movidesk, get_code_agent

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start the eternal loop as a background task on startup."""
    loop_task = asyncio.create_task(process_tickets_loop())
    yield
    loop_task.cancel()
    try:
        await loop_task
    except asyncio.CancelledError:
        print("--- [ETERNAL LOOP STOPPED] ---")

app = FastAPI(title="Dual-Agent Eternal Loop System", lifespan=lifespan)

# Shared state to track processed tickets in the current session (to avoid re-processing same IDs in the same loop if desired)
processed_ticket_ids = set()

async def process_tickets_loop():
    """
    Loop eterno: Busca tickets -> Processa cada um -> Dorme 1 minuto.
    """
    print("--- [LOOP ETERNO INICIADO] ---")
    graph = create_graph()
    
    # Pré-indexa o código uma vez no início
    codebase_path = os.getenv("CODEBASE_PATH", "/Users/ezequielmenegas/git/testeDelphi/src")
    if os.path.exists(codebase_path):
        print(f"Indexando código em {codebase_path}...")
        agent = get_code_agent()
        agent.analyzer.index_codebase()
    
    while True:
        try:
            print(f"\n--- [BUSCANDO TICKETS: {time.strftime('%Y-%m-%d %H:%M:%S')}] ---")
            movidesk = get_movidesk()
            tickets = movidesk.get_tickets()
            
            if not tickets:
                print("Nenhum ticket encontrado para processar.")
            else:
                print(f"Encontrados {len(tickets)} tickets. Iniciando processamento individual...")
                for ticket in tickets:
                    print(f"\n>> Iniciando análise para o Ticket ID: {ticket.id}")
                    
                    # Converte para dict para o LangGraph
                    initial_state = {"ticket_data": ticket.model_dump()}
                    
                    # Executa o grafo para este ticket único
                    await graph.ainvoke(initial_state, config={"recursion_limit": 50})
                    print(f">> Finalizado Ticket ID: {ticket.id}")
            
            print("\n--- [CICLO COMPLETO. AGUARDANDO 1 MINUTO] ---")
            await asyncio.sleep(60)
            
        except Exception as e:
            print(f"Erro no loop eterno: {e}")
            await asyncio.sleep(10) # Aguarda um pouco antes de tentar novamente após erro

@app.get("/status")
async def get_status():
    return {"status": "running", "loop": "eternal_1min_active"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
