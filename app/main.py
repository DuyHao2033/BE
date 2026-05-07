import os
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.api.v1.router import api_router

from app.db.session import SessionLocal # Hoặc đường dẫn session của bạn
from app.models.user import User        # Nhớ kiểm tra đường dẫn Model User
from app.core.security import get_password_hash # Hàm hash mật khẩu của bạn

@app.get("/api/v1/init-admin", tags=["Setup"])
def init_admin():
    db = SessionLocal()
    try:
        # 1. Kiểm tra xem user admin đã tồn tại chưa
        existing_user = db.query(User).filter(User.username == "admin").first()
        if existing_user:
            return {"message": "Admin already exists!"}

        # 2. Tạo tài khoản admin mới
        # Lưu ý: Kiểm tra các trường (fields) trong Model User của bạn
        new_admin = User(
            username="admin",
            email="admin@siu.edu.vn",
            hashed_password=get_password_hash("Admin@123"), # Dùng đúng hàm hash của dự án
            full_name="System Admin",
            is_active=True,
            is_superuser=True # Nếu dự án của bạn có dùng quyền này
        )
        
        db.add(new_admin)
        db.commit()
        return {"message": "Admin created successfully! User: admin, Pass: Admin@123"}
    except Exception as e:
        db.rollback()
        return {"error": str(e)}
    finally:
        db.close()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

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
