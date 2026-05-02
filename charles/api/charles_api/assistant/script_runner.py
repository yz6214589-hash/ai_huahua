from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any


def get_project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def run_python_script(args: list[str], *, cwd: Path | None = None, timeout: int = 300) -> dict[str, Any]:
    root = get_project_root()
    workdir = cwd or root
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    cmd = [sys.executable, *args]
    p = subprocess.run(
        cmd,
        cwd=str(workdir),
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        env=env,
    )
    out = (p.stdout or "").strip()
    err = (p.stderr or "").strip()
    return {"code": p.returncode, "stdout": out, "stderr": err}
