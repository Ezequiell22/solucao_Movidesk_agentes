
import subprocess
import logging
import os
from src.config import settings

logger = logging.getLogger("GitSync")

class GitSyncManager:
    """
    Manages git synchronization for the analyzed codebase.
    """
    def __init__(self, repo_path: str = None):
        self.repo_path = repo_path or settings.CODEBASE_PATH
        # The repo_path might be a 'src' folder inside the repo. 
        # We need the root of the git repo for commands to work best or use -C.
        self.remote = settings.GIT_REMOTE
        self.branch = settings.GIT_BRANCH
        self.enabled = settings.GIT_SYNC_ENABLED

    def _run_git(self, args: list) -> str:
        """Executes a git command and returns the output."""
        cmd = ["git", "-C", self.repo_path] + args
        try:
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                check=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            logger.error(f"Erro ao executar comando git {' '.join(cmd)}: {e.stderr}")
            raise e

    def is_git_repo(self) -> bool:
        """Checks if the path is inside a git repository."""
        if not os.path.exists(self.repo_path):
            return False
        try:
            output = self._run_git(["rev-parse", "--is-inside-work-tree"])
            return output == "true"
        except Exception:
            return False

    def sync(self) -> bool:
        """Performs a git pull to sync with the remote branch."""
        if not self.enabled:
            return False

        if not self.is_git_repo():
            logger.warning(f"Diretório {self.repo_path} não é um repositório Git. Sync ignorado.")
            return False

        try:
            logger.info(f"Sincronizando codebase com {self.remote}/{self.branch}...")
            
            # 1. Fetch
            self._run_git(["fetch", self.remote])
            
            # 2. Check if there are changes
            local_hash = self._run_git(["rev-parse", "HEAD"])
            remote_hash = self._run_git(["rev-parse", f"{self.remote}/{self.branch}"])
            
            if local_hash == remote_hash:
                logger.info("Codebase já está atualizada.")
                return False
            
            # 3. Pull (Reset --hard for security if needed, but pull is safer for standard use)
            # Using 'pull' but could use 'reset --hard' if the local repo should strictly mirror remote
            # Let's use pull for now.
            logger.info("Novas alterações detectadas. Baixando atualizações...")
            self._run_git(["pull", self.remote, self.branch])
            
            logger.info("Codebase atualizada com sucesso via Git.")
            return True
            
        except Exception as e:
            logger.error(f"Falha ao sincronizar via Git: {e}")
            return False

# Singleton instance helper
_manager = None

def get_git_sync() -> GitSyncManager:
    global _manager
    if _manager is None:
        _manager = GitSyncManager()
    return _manager
