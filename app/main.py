import os
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Import các thành phần hệ thống
from app.core.config import settings
from app.api.v1.router import api_router
from app.db.session import SessionLocal, engine  # Thêm engine để tạo bảng
from app.models.user import User         
from app.core.security import hash_password 
from app.db.base import Base # Cần thiết để nhận diện cấu hình bảng

# 1. Cấu hình Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

# 2. Khởi tạo FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="Hệ thống cấp và xác thực chứng chỉ số — SIU Digital Certificate",
    docs_url="/docs",
    redoc_url="/redoc",
)

# --- TỰ ĐỘNG TẠO BẢNG (DATABASE MIGRATION) ---
# Dòng này giúp giải quyết lỗi "relation users does not exist" 
# bằng cách tự động tạo các bảng vào Neon nếu chúng chưa tồn tại.
Base.metadata.create_all(bind=engine)
# ---------------------------------------------

# 3. Cấu hình CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 4. Định nghĩa Route khởi tạo Admin
@app.get("/api/v1/init-admin", tags=["Setup"])
def init_admin():
    db = SessionLocal()
    try:
        # Kiểm tra theo Email vì Model của bạn không có cột 'username'
        existing_user = db.query(User).filter(User.email == "admin@siu.edu.vn").first()
        if existing_user:
            return {"message": "Admin already exists!"}

        # Tạo tài khoản admin mới khớp 100% với Model User
        new_admin = User(
            email="admin@siu.edu.vn",
            full_name="System Admin",
            password_hash=hash_password("Admin@123"), 
            role="super_admin", 
            is_active=True
        )
        
        db.add(new_admin)
        db.commit()
        return {"message": "Admin created successfully! Email: admin@siu.edu.vn, Pass: Admin@123"}
    except Exception as e:
        db.rollback()
        logging.error(f"Error creating admin: {str(e)}")
        return {"error": str(e)}
    finally:
        db.close()

# 5. Cấu hình Static files (uploads & fonts)
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