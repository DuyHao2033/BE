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

@app.on_event("startup")
def create_default_admin():
    if not settings.ADMIN_AUTO_SEED:
        return

    db = SessionLocal()
    try:
        if not db.query(User).filter(User.email == settings.ADMIN_EMAIL).first():
            # Debug: log password length
            admin_password_raw = str(settings.ADMIN_PASSWORD or "Admin@123")
            logging.info(f"ADMIN_PASSWORD length: {len(admin_password_raw)} chars, {len(admin_password_raw.encode('utf-8'))} bytes")
            
            # Ensure password is truncated to 72 bytes for bcrypt
            admin_password = admin_password_raw
            if len(admin_password.encode('utf-8')) > 72:
                logging.warning(f"ADMIN_PASSWORD too long ({len(admin_password.encode('utf-8'))} bytes), using default password")
                admin_password = "Admin@123"
            admin_password = admin_password[:72]  # Extra safety
            
            admin_user = User(
                email=settings.ADMIN_EMAIL,
                full_name=settings.ADMIN_FULL_NAME,
                role="super_admin",
                password_hash=hash_password(admin_password),
                is_active=True,
            )
            db.add(admin_user)
            db.commit()
            logging.info(f"Created default super_admin: {settings.ADMIN_EMAIL}")
        else:
            logging.info("Default admin already exists, skipping creation.")
    except Exception as e:
        db.rollback()
        logging.error(f"Failed to create default admin: {e}")
        logging.error(traceback.format_exc())
    finally:
        db.close()

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
        # Kiểm tra xem đã có admin chưa
        existing_user = db.query(User).filter(User.email == "admin@siu.edu.vn").first()
        if existing_user:
            return {"message": "Admin already exists!"}

        # CHÚ Ý: Đảm bảo hash_password nhận vào một chuỗi text bình thường
        raw_password = "Admin@123"
        hashed = hash_password(raw_password)

        new_admin = User(
            email="admin@siu.edu.vn",
            full_name="System Admin",
            password_hash=hashed, # Lưu chuỗi đã băm vào đây
            role="super_admin", 
            is_active=True
        )
        
        db.add(new_admin)
        db.commit()
        return {"message": "Admin created successfully!", "email": "admin@siu.edu.vn"}
    except Exception as e:
        db.rollback()
        # In lỗi chi tiết ra console của Render để kiểm tra
        print(f"CRITICAL ERROR: {str(e)}") 
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