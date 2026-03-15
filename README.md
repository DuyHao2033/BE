# SIU Digital Certificate

Hệ thống cấp và xác thực chứng chỉ số cho trường đại học — tương tự mô hình Coursera.

---

## Mục tiêu

Cho phép trường phát hành, quản lý và xác thực chứng chỉ điện tử cho nhiều hoạt động:

- ✅ Hoàn thành khóa học
- ✅ Tham gia workshop / sự kiện
- ✅ Kết quả kỳ thi / kiểm tra
- ✅ Đào tạo nội bộ

Mỗi chứng chỉ có mã ID duy nhất và trang xác thực công khai. Chứng chỉ PDF nhúng QR code dẫn đến trang verify.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11 + FastAPI |
| ORM | SQLAlchemy 2 |
| Database | PostgreSQL |
| Migrations | Alembic |
| Auth | JWT (python-jose) + bcrypt (passlib) |
| PDF | ReportLab |
| QR Code | qrcode[pil] |
| Batch | CSV / Excel (openpyxl) |

---

## Cấu trúc thư mục

```
siu-digital-certificate/
├── app/
│   ├── api/v1/
│   │   ├── endpoints/
│   │   │   ├── auth.py          # Login, refresh, me
│   │   │   ├── organizations.py # Quản lý tổ chức
│   │   │   ├── users.py         # Quản lý người dùng
│   │   │   ├── templates.py     # Mẫu chứng chỉ
│   │   │   ├── certificates.py  # Cấp / Thu hồi / Thay thế chứng chỉ
│   │   │   ├── batches.py       # Cấp hàng loạt
│   │   │   └── verify.py        # Xác thực công khai (no auth)
│   │   └── router.py
│   ├── core/
│   │   ├── config.py            # Settings (Pydantic)
│   │   ├── deps.py              # FastAPI dependencies
│   │   └── security.py          # JWT + bcrypt
│   ├── db/
│   │   ├── base.py              # SQLAlchemy Base
│   │   ├── mixins.py            # UUID + Timestamp mixins
│   │   └── session.py           # DB engine + SessionLocal
│   ├── models/                  # SQLAlchemy models
│   ├── schemas/                 # Pydantic request/response schemas
│   ├── services/
│   │   ├── cert_code.py         # Sinh mã chứng chỉ XXXX-XXXX-XXXX
│   │   ├── qr_service.py        # Tạo QR code PNG
│   │   ├── pdf_service.py       # Render PDF từ template layout JSON
│   │   ├── certificate_service.py # Logic cấp chứng chỉ
│   │   ├── batch_service.py     # Xử lý batch CSV/Excel
│   │   ├── storage_service.py   # Lưu file lên disk
│   │   └── log_service.py       # Ghi audit log
│   └── main.py
├── alembic/                     # DB migrations
├── uploads/                     # (auto-created) PDF, QR, backgrounds
├── seed.py                      # Tạo dữ liệu mẫu ban đầu
├── docs/
│   └── batch_sample.csv         # CSV mẫu cho batch upload
├── requirements.txt
└── .env.example
```

---

## Hướng dẫn cài đặt

### Yêu cầu

- Python 3.11+
- PostgreSQL 14+

### 1. Clone & tạo môi trường

```bash
git clone <repo-url>
cd siu-digital-certificate
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Cấu hình môi trường

```bash
cp .env.example .env
# Chỉnh sửa .env với thông tin database và secret key của bạn
```

Các biến quan trọng trong `.env`:

| Biến | Mô tả |
|------|--------|
| `DATABASE_URL` | PostgreSQL connection string |
| `SECRET_KEY` | Secret key cho JWT (generate random dài) |
| `PUBLIC_BASE_URL` | URL công khai của server (dùng trong QR code) |
| `UPLOAD_DIR` | Thư mục lưu file (PDF, QR, backgrounds) |

### 3. Chạy migration

```bash
alembic upgrade head
```

### 4. Seed dữ liệu ban đầu

```bash
python seed.py
# Tạo: Organization "SIU" + user admin@siu.edu.vn / Admin@123
```

### 5. Khởi động server

```bash
uvicorn app.main:app --reload --port 8000
```

Truy cập: http://localhost:8000/docs (Swagger UI)

---

## API Overview

Tất cả API đều có prefix `/api/v1`.

### Authentication

| Method | Path | Mô tả |
|--------|------|--------|
| POST | `/auth/login` | Đăng nhập → nhận access+refresh token |
| POST | `/auth/refresh` | Làm mới access token |
| GET | `/auth/me` | Thông tin user hiện tại |

### Organizations (super_admin only)

| Method | Path | Mô tả |
|--------|------|--------|
| GET | `/organizations` | Danh sách tổ chức |
| POST | `/organizations` | Tạo tổ chức mới |
| GET | `/organizations/{id}` | Chi tiết tổ chức |
| PATCH | `/organizations/{id}` | Cập nhật tổ chức |

### Users

| Method | Path | Mô tả |
|--------|------|--------|
| GET | `/users` | Danh sách users |
| POST | `/users` | Tạo user mới |
| GET | `/users/{id}` | Chi tiết user |
| PATCH | `/users/{id}` | Cập nhật user |
| DELETE | `/users/{id}` | Vô hiệu hóa user |

### Templates (Mẫu chứng chỉ)

| Method | Path | Mô tả |
|--------|------|--------|
| GET | `/templates` | Danh sách templates |
| POST | `/templates` | Tạo template |
| GET | `/templates/{id}` | Chi tiết template |
| PATCH | `/templates/{id}` | Cập nhật template |
| POST | `/templates/{id}/background` | Upload ảnh nền |

**Cấu trúc `layout_json`** — mảng các elements:

```json
{
  "elements": [
    {
      "type": "text",
      "key": "recipient_name",
      "x": 297, "y": 100,
      "font": "Helvetica-Bold",
      "font_size": 32,
      "color": [30, 30, 30],
      "align": "center"
    },
    {
      "type": "text",
      "key": "title",
      "x": 297, "y": 140,
      "font": "Helvetica",
      "font_size": 20,
      "color": [80, 80, 80],
      "align": "center"
    },
    {
      "type": "qr",
      "x": 370, "y": 220, "size": 40
    }
  ]
}
```

> Tọa độ tính bằng mm từ góc trên-trái. A4 landscape: 420mm × 297mm.

### Certificates (Chứng chỉ)

| Method | Path | Mô tả |
|--------|------|--------|
| POST | `/certificates` | Cấp 1 chứng chỉ |
| GET | `/certificates` | Danh sách chứng chỉ |
| GET | `/certificates/{id}` | Chi tiết chứng chỉ |
| POST | `/certificates/{id}/revoke` | Thu hồi |
| POST | `/certificates/{id}/replace` | Thay thế (tạo cert mới) |
| GET | `/certificates/{id}/pdf` | Download PDF |

### Batches (Cấp hàng loạt)

| Method | Path | Mô tả |
|--------|------|--------|
| POST | `/batches` | Upload CSV/Excel → cấp batch |
| GET | `/batches` | Danh sách batches |
| GET | `/batches/{id}` | Trạng thái batch |

CSV mẫu: `docs/batch_sample.csv`

### Verify (Xác thực — Public)

| Method | Path | Auth |
|--------|------|------|
| GET | `/verify/{cert_code}` | **Không cần đăng nhập** |

Đây là endpoint được nhúng trong QR code trên PDF. Trả về toàn bộ thông tin xác thực.

---

## Roles & Phân quyền

| Role | Quyền |
|------|-------|
| `super_admin` | Toàn quyền — quản lý mọi org, user, template, cert |
| `org_admin` | Quản lý trong org của mình: users, templates, certs |
| `issuer` | Chỉ cấp chứng chỉ và đọc trong org của mình |

---

## Luồng hoạt động

### Cấp chứng chỉ đơn lẻ

```
Issuer → POST /certificates
    → sinh cert_code (XXXX-XXXX-XXXX)
    → save Certificate record
    → generate QR code PNG (verify URL)
    → render PDF (template layout + cert data + QR)
    → save PDF file
    → write audit log (event: issued)
    → return CertRead
```

### Xác thực QR

```
Người xem quét QR → GET /verify/{cert_code}
    → lookup Certificate
    → log VerifySession + CertificateLog
    → return VerifyResult (tên, chứng chỉ, đơn vị, ngày, trạng thái)
```

---

## Phát triển

### Tạo Alembic migration mới

```bash
alembic revision --autogenerate -m "mô tả thay đổi"
alembic upgrade head
```

### Chạy với reload

```bash
uvicorn app.main:app --reload --port 8000
```
