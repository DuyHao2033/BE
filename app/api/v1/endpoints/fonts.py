import os
from typing import List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_roles
from app.schemas.font import FontRead, FontListResponse
from app.services.pdf_service import REGISTERED_FONTS, FONTS_DIR, register_all_fonts

router = APIRouter(prefix="/fonts", tags=["Fonts"])

@router.get("", response_model=FontListResponse)
def list_available_fonts(
    current_user = Depends(require_roles("super_admin", "org_admin", "issuer"))
):
    """
    Returns a list of fonts registered in the system that support Vietnamese.
    """
    items = []
    # Use the REGISTERED_FONTS dict which maps friendly names to filename-based names
    # or just collect from the directory directly to get filenames too
    if not os.path.exists(FONTS_DIR):
        return {"items": [], "total": 0}
    
    files = [f for f in os.listdir(FONTS_DIR) if f.lower().endswith(".ttf")]
    
    for filename in files:
        name = os.path.splitext(filename)[0]
        items.append(FontRead(name=name, filename=filename))
    
    # Sort by name
    items.sort(key=lambda x: x.name)
    
    return {
        "items": items,
        "total": len(items)
    }

@router.post("", response_model=FontRead, status_code=status.HTTP_201_CREATED)
async def upload_font(
    file: UploadFile = File(...),
    current_user = Depends(require_roles("super_admin"))
):
    """
    Upload a new .ttf font file to the system.
    Only super_admin can manage system-wide fonts.
    """
    if not file.filename.lower().endswith(".ttf"):
        raise HTTPException(status_code=400, detail="Only .ttf files are supported")
    
    # Check if directory exists
    if not os.path.exists(FONTS_DIR):
        os.makedirs(FONTS_DIR, exist_ok=True)
    
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:  # 10MB limit
        raise HTTPException(status_code=400, detail="Font file too large (max 10MB)")
    
    save_path = os.path.join(FONTS_DIR, file.filename)
    with open(save_path, "wb") as f:
        f.write(content)
    
    # Refresh registration in pdf_service
    register_all_fonts()
    
    name = os.path.splitext(file.filename)[0]
    return FontRead(name=name, filename=file.filename)

@router.delete("/{font_filename}", status_code=status.HTTP_204_NO_CONTENT)
def delete_font(
    font_filename: str,
    current_user = Depends(require_roles("super_admin"))
):
    """
    Delete a font file from the system.
    """
    if not font_filename.lower().endswith(".ttf"):
        font_filename += ".ttf"
        
    file_path = os.path.join(FONTS_DIR, font_filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Font file not found")
    
    # Prevent deleting core fonts if needed, but for now we trust the super_admin
    try:
        os.remove(file_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not delete font: {str(e)}")
    
    # Clear and Refresh registration
    # Since REGISTERED_FONTS is a global dict in pdf_service, we should clear it or 
    # it might still have references. 
    # Let's adjust pdf_service to allow a clean refresh.
    from app.services import pdf_service
    pdf_service.REGISTERED_FONTS.clear()
    pdf_service.register_all_fonts()
    
    return None
