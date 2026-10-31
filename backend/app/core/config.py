"""CircuitLens Application Configuration."""

import os
import shutil
from typing import List


def _load_project_env() -> None:
    """Load simple KEY=VALUE entries from the project .env without extra dependencies."""
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    env_path = os.path.join(root, ".env")
    if not os.path.isfile(env_path):
        return
    with open(env_path, "r", encoding="utf-8") as env_file:
        for line in env_file:
            entry = line.strip()
            if not entry or entry.startswith("#") or "=" not in entry:
                continue
            key, value = entry.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


_load_project_env()


class Settings:
    PROJECT_NAME: str = "CircuitLens"
    VERSION: str = "1.0.0"
    API_PREFIX: str = "/api"

    # Simulation binary
    _repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    _bundled_ngspice = os.path.join(_repo_root, "tools", "ngspice", "bin", "ngspice_con.exe")
    NGSPICE_PATH: str = os.getenv(
        "NGSPICE_PATH", _bundled_ngspice if os.path.isfile(_bundled_ngspice) else "ngspice"
    )

    # AI Configuration (Gemma 4)
    GEMMA_PROVIDER: str = os.getenv("GEMMA_PROVIDER", "ollama")
    GEMMA_MODEL_ID: str = os.getenv("GEMMA_MODEL_ID", "gemma4:e2b")
    GEMMA_API_KEY: str = os.getenv("GEMMA_API_KEY", "")
    GEMMA_BASE_URL: str = os.getenv("GEMMA_BASE_URL", "http://127.0.0.1:11434")

    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
    ]

    @property
    def is_ngspice_available(self) -> bool:
        """Check if ngspice executable is available in PATH or specified location."""
        if shutil.which(self.NGSPICE_PATH) is not None or os.path.isfile(self.NGSPICE_PATH):
            return True
        return os.path.isfile(os.path.join(self._repo_root, "tools", "ngspice", "bin", "ngspice_con.exe"))


settings = Settings()
