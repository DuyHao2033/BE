import os
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.api.v1.router import api_router
from app.db.session import SessionLocal 
from app.models.user import User         
# ĐÃ SỬA: Import đúng tên hàm hash_password từ security.py
from app.core.security import hash_password 

# 1. Cấu hình Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

# 2. Khởi tạo FastAPI app (Phải nằm TRƯỚC khi định nghĩa các route)
app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="Hệ thống cấp và xác thực chứng chỉ số — SIU Digital Certificate",
    docs_url="/docs",
    redoc_url="/redoc",
)

# 3. Cấu hình CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 4. Định nghĩa Route init-admin (Đã đưa xuống dưới lệnh khởi tạo app)
@app.get("/api/v1/init-admin", tags=["Setup"])
def init_admin():
    db = SessionLocal()
    try:
        # Kiểm tra xem user admin đã tồn tại chưa
        existing_user = db.query(User).filter(User.username == "admin").first()
        if existing_user:
            return {"message": "Admin already exists!"}

        # Tạo tài khoản admin mới
        new_admin = User(
            username="admin",
            email="admin@siu.edu.vn",
            hashed_password=hash_password("Admin@123"), # Sử dụng đúng tên hàm hash_password
            full_name="System Admin",
            is_active=True,
            is_superuser=True 
        )
        
        db.add(new_admin)
        db.commit()
        return {"message": "Admin created successfully! User: admin, Pass: Admin@123"}
    except Exception as e:
        db.rollback()
        return {"error": str(e)}
    finally:
        db.close()

# 5. Static file serving (uploads & fonts)
uploads_dir = settings.UPLOAD_DIR.lstrip("./")
os.makedirs(uploads_dir, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=uploads_dir), name="uploads")

fonts_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "resources", "fonts")
if not os.path.exists(fonts_dir):
    os.makedirs(fonts_dir, exist_ok=True)
app.mount("/fonts-static", StaticFiles(directory=fonts_dir), name="fonts-static")

# 6. API Routes
app.include_router(api_router, prefix="/api/v1")

@app.get("/", tags=["Health"])
def root():
    return {"service": settings.APP_NAME, "version": "1.0.0", "status": "ok"}

@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok"}