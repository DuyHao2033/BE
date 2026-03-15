import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.api.v1.router import api_router

app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="Hệ thống cấp và xác thực chứng chỉ số — SIU Digital Certificate",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ─── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Static file serving (uploads) ────────────────────────────────────────────
uploads_dir = settings.UPLOAD_DIR.lstrip("./")
os.makedirs(uploads_dir, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=uploads_dir), name="uploads")

# Serve fonts for frontend preview
fonts_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "resources", "fonts")
if not os.path.exists(fonts_dir):
    os.makedirs(fonts_dir, exist_ok=True)
app.mount("/fonts-static", StaticFiles(directory=fonts_dir), name="fonts-static")

# ─── API Routes ───────────────────────────────────────────────────────────────
app.include_router(api_router, prefix="/api/v1")


@app.get("/", tags=["Health"])
def root():
    return {"service": settings.APP_NAME, "version": "1.0.0", "status": "ok"}


@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok"}
