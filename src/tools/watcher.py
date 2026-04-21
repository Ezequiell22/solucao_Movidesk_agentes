
import logging
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from src.tools.code_analyzer import CodeAnalyzer

logger = logging.getLogger("CodebaseWatcher")

class CodebaseHandler(FileSystemEventHandler):
    """
    Handles file system events to update the CodeAnalyzer index.
    """
    def __init__(self, analyzer: CodeAnalyzer):
        self.analyzer = analyzer
        # Debounce logic to avoid multiple updates for rapid saves
        self.last_updated = {}
        self.debounce_seconds = 2

    def on_modified(self, event):
        if not event.is_directory and event.src_path.lower().endswith(('.pas', '.dpr')):
            current_time = time.time()
            if current_time - self.last_updated.get(event.src_path, 0) > self.debounce_seconds:
                logger.info(f"Detectada modificação: {event.src_path}")
                self.analyzer.update_file(event.src_path)
                self.last_updated[event.src_path] = current_time

    def on_created(self, event):
        if not event.is_directory and event.src_path.lower().endswith(('.pas', '.dpr')):
            logger.info(f"Detectada criação: {event.src_path}")
            self.analyzer.update_file(event.src_path)

    def on_deleted(self, event):
        if not event.is_directory and event.src_path.lower().endswith(('.pas', '.dpr')):
            logger.info(f"Detectada exclusão: {event.src_path}")
            self.analyzer.remove_file(event.src_path)

    def on_moved(self, event):
        if not event.is_directory:
            if event.src_path.lower().endswith(('.pas', '.dpr')):
                logger.info(f"Detectada movimentação (origem): {event.src_path}")
                self.analyzer.remove_file(event.src_path)
            if event.dest_path.lower().endswith(('.pas', '.dpr')):
                logger.info(f"Detectada movimentação (destino): {event.dest_path}")
                self.analyzer.update_file(event.dest_path)

class CodebaseWatcher:
    """
    Monitor that watches for codebase changes and updates the index in real-time.
    """
    def __init__(self, codebase_path: str, analyzer: CodeAnalyzer):
        self.codebase_path = codebase_path
        self.analyzer = analyzer
        self.observer = Observer()
        self.handler = CodebaseHandler(analyzer)

    def start(self):
        logger.info(f"Iniciando monitoramento da codebase em: {self.codebase_path}")
        self.observer.schedule(self.handler, self.codebase_path, recursive=True)
        self.observer.start()

    def stop(self):
        logger.info("Parando monitoramento da codebase...")
        self.observer.stop()
        self.observer.join()
