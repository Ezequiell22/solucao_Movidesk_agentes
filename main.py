import os
import time
import logging
import signal
import sys
import warnings
from contextlib import asynccontextmanager
from dotenv import load_dotenv

# Silenciar avisos de compatibilidade do Pydantic v1 com Python 3.14+
warnings.filterwarnings("ignore", category=UserWarning, message=".*Pydantic V1 functionality.*")

# Configuração de logging profissional
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("mark1.log")
    ]
)
logger = logging.getLogger("MARK1")

# Silenciar logs ruidosos de bibliotecas externas
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("huggingface_hub").setLevel(logging.ERROR)
logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("chromadb").setLevel(logging.WARNING)

# Carregar variáveis de ambiente
load_dotenv()

from fastapi import FastAPI
import uvicorn
import threading

from src.graph import graph
from src.config import settings
from src.nodes.ticket_nodes import get_movidesk, get_analyzer
from src.tools.watcher import CodebaseWatcher
from src.tools.git_sync import get_git_sync

# Evento para controle de encerramento gracioso
stop_event = threading.Event()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ciclo de vida da aplicação FastAPI."""
    logger.info("--- [STARTUP MARK1] ---")
    
    # Startup: Sincronização Git Inicial
    if settings.GIT_SYNC_ENABLED:
        try:
            git_sync = get_git_sync()
            git_sync.sync()
        except Exception as e:
            logger.error(f"Erro na sincronização git inicial: {e}")

    # Startup: Pré-indexação (Pode ser demorado, melhor deixar pronto)
    watcher = None
    if os.path.exists(settings.CODEBASE_PATH):
        logger.info(f"Indexando codebase em: {settings.CODEBASE_PATH}")
        try:
            analyzer = get_analyzer()
            analyzer.index_codebase()
            
            # Inicia o Watcher para monitorar mudanças em tempo real
            watcher = CodebaseWatcher(settings.CODEBASE_PATH, analyzer)
            watcher.start()
        except Exception as e:
            logger.error(f"Falha crítica na indexação inicial: {e}")
    
    # Inicia o loop eterno em uma thread separada
    worker_thread = threading.Thread(target=eternal_loop, daemon=True)
    worker_thread.start()
    
    yield
    # Shutdown
    logger.info("--- [SHUTTING DOWN MARK1] ---")
    if watcher:
        watcher.stop()
    stop_event.set()
    worker_thread.join(timeout=5)
    logger.info("--- [ETERNAL LOOP STOPPED] ---")

app = FastAPI(
    title="MARK1 - Delphi Autonomous Support",
    description="Sistema de agentes inteligentes para análise de tickets e código Delphi.",
    version="1.0.0",
    lifespan=lifespan
)

def process_tickets():
    """Busca e processa tickets pendentes de forma segura."""
    movidesk = get_movidesk()
    
    try:
        logger.info(f"--- [BUSCANDO TICKETS: {time.strftime('%Y-%m-%d %H:%M:%S')}] ---")
        tickets = movidesk.get_tickets()
        
        if not tickets:
            logger.info("Nenhum ticket pendente.")
            return

        logger.info(f"Processando {len(tickets)} tickets...")
        
        for ticket in tickets:
            if stop_event.is_set():
                break
                
            ticket_id = ticket.id
            logger.info(f"Analisando Ticket ID: {ticket_id}")
            
            try:
                # Executa o Grafo de Agentes (Sincronamente na thread do worker)
                inputs = {"ticket_data": ticket.model_dump()}
                graph.invoke(inputs)
                logger.info(f"Ticket ID: {ticket_id} processado com sucesso.")
            except Exception as ticket_err:
                logger.error(f"Erro ao processar ticket {ticket_id}: {ticket_err}")

    except Exception as e:
        logger.error(f"Erro na rotina de busca de tickets: {e}")

def eternal_loop():
    """Thread de processamento contínuo com espera inteligente."""
    logger.info("--- [LOOP ETERNO INICIADO] ---")
    
    last_git_sync = time.time()
    git_sync_manager = get_git_sync()

    while not stop_event.is_set():
        # 1. Verificar Sincronização Git
        current_time = time.time()
        if settings.GIT_SYNC_ENABLED and (current_time - last_git_sync >= settings.GIT_SYNC_INTERVAL):
            try:
                git_sync_manager.sync()
                last_git_sync = current_time
            except Exception as e:
                logger.error(f"Erro no loop de sincronização git: {e}")

        # 2. Processar Tickets
        process_tickets()
        
        # Espera 60 segundos ou até o sinal de parada
        if stop_event.wait(timeout=60):
            break
            
    logger.info("Worker thread finalizada.")

@app.get("/")
async def health_check():
    """Endpoint de saúde para monitoramento."""
    return {
        "status": "online",
        "project": "MARK1",
        "timestamp": time.time(),
        "worker_active": not stop_event.is_set()
    }

if __name__ == "__main__":
    # Configuração de host e porta via env ou default
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    # O Uvicorn já gerencia sinais de interrupção e aciona o lifespan shutdown
    uvicorn.run(app, host=host, port=port, log_level="info")
