"""
File Storage Service — handles saving uploaded/generated files to disk.
"""
import os
import uuid
from pathlib import Path

from app.core.config import settings


def _ensure_dir(path: str) -> None:
    Path(path).mkdir(parents=True, exist_ok=True)


def save_bytes(data: bytes, subdir: str, filename: str) -> str:
    """
    Save raw bytes to UPLOAD_DIR/subdir/filename.
    Returns the relative file path (to be stored as URL).
    """
    dir_path = os.path.join(settings.UPLOAD_DIR, subdir)
    _ensure_dir(dir_path)
    file_path = os.path.join(dir_path, filename)
    with open(file_path, "wb") as f:
        f.write(data)
    # Return as a relative URL path (served as static files)
    return f"/uploads/{subdir}/{filename}"


def save_upload(data: bytes, subdir: str, original_filename: str) -> str:
    """
    Save an uploaded file with a unique name.
    Returns the relative URL path.
    """
    ext = os.path.splitext(original_filename)[-1].lower()
    unique_name = f"{uuid.uuid4().hex}{ext}"
    return save_bytes(data, subdir, unique_name)


def get_absolute_path(relative_url: str) -> str:
    """Convert a /uploads/... URL to absolute filesystem path."""
    if relative_url.startswith("/uploads/"):
        # Replace /uploads/ with the actual UPLOAD_DIR
        rel_path = relative_url.replace("/uploads/", "", 1)
        return os.path.abspath(os.path.join(settings.UPLOAD_DIR, rel_path))
    return relative_url
