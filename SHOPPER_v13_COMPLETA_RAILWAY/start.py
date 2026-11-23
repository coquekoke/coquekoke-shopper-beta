"""SHOPPER launcher: prefers the Python environment with production dependencies."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys

def ensure_python_dependencies():
    # Usually Railpack configures Python correctly. An unusual PATH can select
    # the system Python instead of the virtual environment used during build.
    if importlib.util.find_spec("uvicorn") and importlib.util.find_spec("fastapi"):
        return
    for candidate in ("/app/venv/bin/python", "/app/.venv/bin/python", "/opt/venv/bin/python"):
        if not Path(candidate).is_file():
            continue
        probe = subprocess.run(
            [candidate, "-c", "import uvicorn, fastapi"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            check=False, timeout=12,
        )
        if probe.returncode == 0 and Path(candidate).resolve() != Path(sys.executable).resolve():
            os.execv(candidate, [candidate, str(Path(__file__).resolve())])
    raise RuntimeError(
        "SHOPPER: faltan dependencias del servidor (uvicorn/fastapi). "
        "Comprueba que requirements.txt existe en la RAIZ de GitHub, "
        "que Railway usa esa raiz y que Build Logs muestra la instalacion."
    )

def main():
    ensure_python_dependencies()
    import uvicorn
    port = int(os.environ.get("PORT", "8000"))
    if not 1 <= port <= 65535:
        raise ValueError("Invalid PORT")
    uvicorn.run("main:app", host="0.0.0.0", port=port, workers=1)

if __name__ == "__main__":
    main()
