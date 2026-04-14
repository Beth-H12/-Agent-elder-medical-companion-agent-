import subprocess
import threading
import time
from pathlib import Path
from typing import Dict, Optional

import httpx

from app.core.config import settings


class OllamaService:
    _start_lock = threading.Lock()
    _last_start_attempt = 0.0

    def is_available(self, timeout_seconds: float = 2.0) -> bool:
        try:
            response = httpx.get(
                f"{settings.ollama_base_url}/api/tags",
                timeout=timeout_seconds,
                trust_env=False,
            )
            response.raise_for_status()
            data = response.json()
            return isinstance(data.get("models"), list)
        except Exception:
            return False

    def ensure_available(self, start_if_needed: bool = True) -> bool:
        if self.is_available():
            return True
        if not start_if_needed or not settings.auto_start_ollama:
            return False

        executable = self.find_executable()
        if not executable:
            return False

        with self._start_lock:
            if self.is_available():
                return True

            now = time.monotonic()
            if now - self._last_start_attempt >= 3:
                self._start_server(executable)
                self._last_start_attempt = now

        return self._wait_until_available(settings.ollama_startup_timeout_seconds)

    def health(self) -> Dict[str, Optional[str]]:
        executable = self.find_executable()
        ready = self.is_available()
        return {
            "ready": ready,
            "executable": executable,
            "base_url": settings.ollama_base_url,
        }

    def warm_model(self) -> bool:
        if not self.ensure_available(start_if_needed=True):
            return False

        try:
            response = httpx.post(
                f"{settings.ollama_base_url}/api/generate",
                json={
                    "model": settings.ollama_model,
                    "prompt": "请回复：ok",
                    "stream": False,
                    "think": False,
                    "keep_alive": settings.ollama_keep_alive,
                    "options": {"num_predict": 8, "temperature": 0},
                },
                timeout=max(30.0, float(settings.ollama_timeout_seconds)),
                trust_env=False,
            )
            response.raise_for_status()
            return True
        except Exception:
            return False

    @staticmethod
    def find_executable() -> Optional[str]:
        configured = settings.ollama_executable.strip()
        if configured and Path(configured).exists():
            return configured

        common_paths = [
            Path.home() / "AppData" / "Local" / "Programs" / "Ollama" / "ollama.exe",
            Path("C:/Program Files/Ollama/ollama.exe"),
        ]
        for path in common_paths:
            if path.exists():
                return str(path)
        return None

    @staticmethod
    def _start_server(executable: str) -> None:
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        subprocess.Popen(
            [executable, "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            creationflags=creation_flags,
        )

    def _wait_until_available(self, timeout_seconds: int) -> bool:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            if self.is_available(timeout_seconds=1.5):
                return True
            time.sleep(1)
        return False
