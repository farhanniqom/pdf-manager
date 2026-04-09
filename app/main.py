from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.routes.pdf_routes import router as pdf_router
from app.services.autodelete_service import start_cleanup_scheduler

app = FastAPI(title="PDF Manager", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(pdf_router, prefix="/api")


@app.get("/api/health")
async def health_check():
    return {"status": "ok"}

_frontend = Path(__file__).resolve().parent.parent / "frontend"
if _frontend.is_dir():
    app.mount(
        "/",
        StaticFiles(
            directory=str(_frontend),
            html=True),
        name="static")

# Start auto-delete schedulers for storage folders
_storage = Path(__file__).resolve().parent.parent / "storage"
if _storage.is_dir():
    uploads_dir = _storage / "uploads"
    outputs_dir = _storage / "outputs"
    if uploads_dir.is_dir():
        start_cleanup_scheduler(str(uploads_dir))
    if outputs_dir.is_dir():
        start_cleanup_scheduler(str(outputs_dir))
