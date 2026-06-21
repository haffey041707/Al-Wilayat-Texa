"""Wilayat API — FastAPI application entrypoint.

Run any of:
    python app/main.py            (from the backend/ folder — starts + opens the app)
    python -m app.main
    uvicorn app.main:app --reload

It serves both the JSON API (/api/...) and the web app (/) at http://localhost:8000
Docs: http://localhost:8000/docs
"""
import os
import pathlib
import sys

# Make `import app...` work no matter how this file is launched
# (e.g. `python app/main.py` puts backend/app on the path, not backend/).
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))


def _load_dotenv() -> None:
    """Load backend/.env into the environment (no extra dependency).
    Keeps secrets like OPENAI_API_KEY out of source code."""
    env = pathlib.Path(__file__).resolve().parent.parent / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


_load_dotenv()


def _ensure_deps() -> None:
    """Make `python app/main.py` work with ANY interpreter:
    if FastAPI isn't available, re-launch using the project's own venv
    (backend/.venv) — and if that's missing, install requirements first."""
    try:
        import fastapi  # noqa: F401
        return
    except ModuleNotFoundError:
        pass

    backend = pathlib.Path(__file__).resolve().parent.parent
    venv_py = backend / ".venv" / ("Scripts" if os.name == "nt" else "bin") / \
        ("python.exe" if os.name == "nt" else "python")
    stage = os.environ.get("WILAYAT_BOOTSTRAP", "")

    # 1) A project venv exists and we're not using it → relaunch with it.
    if venv_py.exists() and pathlib.Path(sys.prefix).resolve() != (backend / ".venv").resolve() and stage != "reexec":
        os.environ["WILAYAT_BOOTSTRAP"] = "reexec"
        os.execv(str(venv_py), [str(venv_py), *sys.argv])

    # 2) No usable venv / deps still missing → install them, then restart.
    if stage != "installed":
        import subprocess
        print("Installing Al-Wilayat dependencies (first run)…")
        subprocess.run([sys.executable, "-m", "pip", "install", "-r",
                        str(backend / "requirements.txt")], check=True)
        os.environ["WILAYAT_BOOTSTRAP"] = "installed"
        os.execv(sys.executable, [sys.executable, *sys.argv])

    raise SystemExit("Dependencies unavailable. Run:  pip install -r requirements.txt")


_ensure_deps()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app import auth
from app.routers import ai, content

# Path to the web frontend (Al-Wilayat-App/web).
WEB_DIR = pathlib.Path(__file__).resolve().parent.parent.parent / "web"

app = FastAPI(
    title="Wilayat API",
    description="Backend for the Wilayat Shia Islamic super app.",
    version="0.1.0",
)

# CORS — allow the static web client (any localhost origin during dev)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(content.router)
app.include_router(ai.router)


@app.get("/api")
def root():
    return {"name": "Wilayat API", "status": "ok", "docs": "/docs"}


@app.get("/api/health")
def health():
    return {"status": "healthy"}


# Serve the web app at "/" (so http://localhost:8000 opens the app). Mounted
# LAST so the /api/* routes above take precedence over the static files.
if WEB_DIR.exists():
    app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")


if __name__ == "__main__":
    # Running `python app/main.py` directly: start the server and open the app.
    import threading
    import webbrowser

    import uvicorn

    url = "http://localhost:8000"
    print(f"\n  Al-Wilayat is starting…\n  App:  {url}\n  Docs: {url}/docs\n")
    # Open the browser shortly after the server comes up (skip with WILAYAT_NOBROWSER=1).
    if os.environ.get("WILAYAT_NOBROWSER") != "1":
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    uvicorn.run(app, host="0.0.0.0", port=8000)
