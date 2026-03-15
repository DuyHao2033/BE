"""
PDF Service — renders a certificate PDF from a Template + Certificate data.

Template.layout_json format:
{
  "elements": [
    {
      "type": "text",
      "key": "recipient_name",     # maps to cert field or custom_data key
      "value": null,               # null → use cert field value
      "x": 297,                    # mm from left (for A4 landscape: 0-420)
      "y": 100,                    # mm from top (for A4 landscape: 0-297)
      "font": "Helvetica-Bold",
      "font_size": 32,
      "color": [0, 0, 0],          # RGB 0-255
      "align": "center"            # "left" | "center" | "right"
    },
    {
      "type": "qr",
      "x": 370,
      "y": 220,
      "size": 40                   # mm square
    },
    {
      "type": "image",
      "path": "./uploads/logos/siu.png",
      "x": 20,
      "y": 20,
      "width": 40,
      "height": 20
    }
  ]
}

All coordinates in mm. ReportLab uses points internally (1mm = 2.8346 pt).
"""

import io
import os
from typing import Any

from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib.pagesizes import A4, landscape, portrait
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from PIL import Image as PILImage

from app.services.qr_service import generate_qr_bytes
from app.services.storage_service import get_absolute_path


def _resolve_value(key: str, cert_data: dict[str, Any]) -> str | None:
    """Resolve an element key to an actual string value from cert_data."""
    if not key:
        return None
    direct = cert_data.get(key)
    if direct is not None:
        return str(direct)
    # Fallback to nested custom_data
    custom = cert_data.get("custom_data", {})
    val = custom.get(key)
    if val is not None:
        return str(val)
    return None


def _draw_text_robust(
    c: canvas.Canvas, 
    x: float, 
    y_top: float, 
    text: str, 
    font_name: str, 
    font_size: float, 
    align: str, 
    container_width: float,
    container_height: float
):
    """
    Draws text word-by-word to handle fonts with missing space glyphs (avoiding "NO GLYPH" boxes).
    Includes auto-shrink logic to fit text within the container_width.
    """
    if not text:
        return

    # 1. Auto-shrink font size if it exceeds container_width
    if container_width > 0:
        # Measure initial width
        text_width = c.stringWidth(text, font_name, font_size)
        if text_width > container_width:
            # Iteratively shrink font size until it fits or reaches a minimum size
            while font_size > 4 and text_width > container_width:
                font_size -= 0.5
                text_width = c.stringWidth(text, font_name, font_size)
            
            # Apply the new font size to the canvas
            c.setFont(font_name, font_size)

    # 2. Calculate vertical baseline for centering within the container height
    # Adjust y to be the baseline: center of box - small offset for typography
    y = y_top - (container_height / 2) - (font_size * 0.15)

    # For standard/known-good fonts, use built-in methods for efficiency and better kerning
    good_fonts = {"Roboto", "Noto", "Helvetica", "Times", "Courier"}
    is_good = any(gf in font_name for gf in good_fonts)
    
    if is_good:
        if align == "center":
            c.drawCentredString(x + container_width / 2, y, text)
        elif align == "right":
            c.drawRightString(x + container_width, y, text)
        else:
            c.drawString(x, y, text)
        return

    # For potentially broken decorative fonts, split by spaces and draw manually
    words = text.split(" ")
    # Estimate a reasonable space width using a standard font as reference
    space_width = c.stringWidth(" ", "Helvetica", font_size)
    
    word_widths = [c.stringWidth(w, font_name, font_size) for w in words]
    total_text_width = sum(word_widths) + (len(words) - 1) * space_width
    
    start_x = x
    if align == "center":
        start_x = x + (container_width - total_text_width) / 2
    elif align == "right":
        start_x = x + container_width - total_text_width
        
    current_x = start_x
    for i, word in enumerate(words):
        if word: # Skip drawing empty strings but advance x
            c.drawString(current_x, y, word)
        current_x += word_widths[i] + space_width


# --- Font Registration ---
# Register fonts to support Vietnamese characters
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(CURRENT_DIR))
FONTS_DIR = os.path.join(PROJECT_ROOT, "resources", "fonts")

# We use a dictionary to track which fonts we've successfully registered
REGISTERED_FONTS = {}

def register_all_fonts():
    """Scans the resources/fonts directory and registers all .ttf files."""
    if not os.path.exists(FONTS_DIR):
        print(f"Warning: Fonts directory not found at {FONTS_DIR}")
        return

    for filename in os.listdir(FONTS_DIR):
        if filename.lower().endswith(".ttf"):
            font_path = os.path.join(FONTS_DIR, filename)
            # Use the filename without extension as the font name
            font_name = os.path.splitext(filename)[0]
            try:
                pdfmetrics.registerFont(TTFont(font_name, font_path))
                # Map to a more friendly name if possible
                REGISTERED_FONTS[font_name] = font_name
                # Register common variations if named specifically
                if "Regular" in font_name:
                    REGISTERED_FONTS[font_name.replace("-Regular", "")] = font_name
            except Exception as e:
                print(f"Error registering font {font_name}: {e}")

# Initial registration
register_all_fonts()

def _get_font_name(font: str) -> str:
    """
    Resolves a requested font name to a registered font that supports Vietnamese.
    Prioritizes the requested font, then searches for compatible styles.
    """
    # 1. Direct match with registered fonts
    if font in REGISTERED_FONTS:
        return REGISTERED_FONTS[font]
    
    # 2. Case-insensitive search in registered fonts
    for registered_name in REGISTERED_FONTS:
        if font.lower() == registered_name.lower():
            return registered_name

    # 3. Smart fallbacks for standard fonts to ensure Vietnamese support
    # Maps standard Type 1 fonts (which don't support Unicode) to similar TTF fonts
    standard_fallback = {
        "Helvetica": "Roboto-Regular",
        "Helvetica-Bold": "Roboto-Bold",
        "Helvetica-Oblique": "Roboto-Italic",
        "Helvetica-BoldOblique": "Roboto-BoldItalic",
        "Times-Roman": "NotoSerif-Regular",
        "Times-Bold": "NotoSerif-Bold",
        "Times-Italic": "NotoSerif-Italic",
        "Times-BoldItalic": "NotoSerif-BoldItalic",
        "Courier": "NotoSansMono-Regular",
        "Courier-Bold": "NotoSansMono-Bold",
        "Arial": "Roboto-Regular",
        "Arial-Bold": "Roboto-Bold",
    }
    if font in standard_fallback:
        fallback = standard_fallback[font]
        if fallback in REGISTERED_FONTS:
            return REGISTERED_FONTS[fallback]

    # For any fonts not registered and not in standard fallback, 
    # check if we have a "Regular" version of a partially matched name
    for registered_name in REGISTERED_FONTS:
        if font.lower() in registered_name.lower():
            return registered_name

    # 4. Style-based match for unknown fonts
    font_lower = font.lower()
    if "serif" in font_lower:
        if "NotoSerif-Regular" in REGISTERED_FONTS: return "NotoSerif-Regular"
    elif "mono" in font_lower:
        if "NotoSansMono-Regular" in REGISTERED_FONTS: return "NotoSansMono-Regular"
    
    # 5. Check if it's a built-in ReportLab font (use as-is if no Vietnamese needed, 
    # but we already handled standard fallbacks above)
    built_in = {
        "Helvetica", "Helvetica-Bold", "Helvetica-Oblique", "Helvetica-BoldOblique",
        "Times-Roman", "Times-Bold", "Times-Italic", "Times-BoldItalic",
        "Courier", "Courier-Bold", "Courier-Oblique", "Courier-BoldOblique",
    }
    if font in built_in:
        return font
        
    # 6. Absolute fallback
    if font != "Roboto-Regular":
        print(f"Font Conflict: '{font}' not found or unsupported. Falling back to 'Roboto-Regular' for Vietnamese support.")
    
    return "Roboto-Regular" if "Roboto-Regular" in REGISTERED_FONTS else "Helvetica"


def render_certificate_pdf(
    layout_json: dict[str, Any],
    page_size: str,
    orientation: str,
    background_url: str | None,
    cert_data: dict[str, Any],  # flat dict with all cert fields
    qr_bytes: bytes,
) -> bytes:
    """
    Render a certificate PDF and return raw bytes.
    """
    # Determine page size
    base_size = A4  # default
    if page_size.upper() == "A4":
        base_size = A4
    elif page_size.upper() == "LETTER":
        from reportlab.lib.pagesizes import letter
        base_size = letter

    if orientation.lower() == "landscape":
        page = landscape(base_size)
    else:
        page = portrait(base_size)

    page_w, page_h = page

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=page)
    c.setTitle(cert_data.get("title", "Certificate"))

    # --- Background image ---
    if background_url:
        abs_bg_path = get_absolute_path(background_url)
        if os.path.exists(abs_bg_path):
            c.drawImage(abs_bg_path, 0, 0, width=page_w, height=page_h, preserveAspectRatio=False)

    # Scale factor from frontend pixels to millimeters
    # Frontend: 1mm = 3.7795px (96 DPI)
    PX_TO_MM = 3.7795

    elements = layout_json.get("elements", [])

    for el in elements:
        el_type = el.get("type", "text")
        
        # All coordinates/sizes from frontend are in PIXELS
        x_px = el.get("x", 0)
        y_px = el.get("y", 0)
        w_px = el.get("width", 0)
        h_px = el.get("height", 0)
        size_px = el.get("size", 0) # for QR

        # Convert to millimeters
        x_mm = x_px / PX_TO_MM
        y_mm = y_px / PX_TO_MM
        w_mm = w_px / PX_TO_MM
        h_mm = h_px / PX_TO_MM
        size_mm = size_px / PX_TO_MM

        # ReportLab y is from bottom; convert from top-down mm
        # y is the top edge of the element's bounding box
        y = page_h - (y_mm * mm)

        if el_type == "text":
            # Priority logic for resolving text:
            raw_value = None
            key = el.get("key")
            
            if key:
                raw_value = _resolve_value(key, cert_data)
            if raw_value is None:
                raw_value = el.get("value")
            if raw_value is None:
                raw_value = el.get("content")
            
            text = str(raw_value or "")
            font_requested = el.get("font", "Helvetica-Bold")
            font_name = _get_font_name(font_requested)
            font_size = el.get("font_size", 24)
            color = el.get("color", [0, 0, 0])
            align = el.get("align", "center")

            c.setFont(font_name, font_size)
            c.setFillColorRGB(color[0] / 255, color[1] / 255, color[2] / 255)

            # Draw using the robust helper
            _draw_text_robust(
                c=c,
                x=x_mm * mm,
                y_top=y,
                text=text,
                font_name=font_name,
                font_size=font_size,
                align=align,
                container_width=w_mm * mm,
                container_height=h_mm * mm
            )

        elif el_type == "qr":
            size = size_mm * mm
            if size == 0: size = 40 * mm # fallback
            qr_buf = io.BytesIO(qr_bytes)
            qr_reader = ImageReader(qr_buf)
            c.drawImage(qr_reader, x_mm * mm, y - size, width=size, height=size)

        elif el_type == "image":
            path = el.get("path") or el.get("url") or el.get("src") or ""
            abs_path = get_absolute_path(path)
            width = w_mm * mm
            height = h_mm * mm
            if os.path.exists(abs_path):
                # Use ImageReader and mask='auto' to properly handle transparency (alpha channel)
                try:
                    img = ImageReader(abs_path)
                    c.drawImage(img, x_mm * mm, y - height, width=width, height=height, mask='auto')
                except Exception as e:
                    print(f"Error drawing image {abs_path}: {e}")
                    # Fallback to simple path if ImageReader fails
                    c.drawImage(abs_path, x_mm * mm, y - height, width=width, height=height)
            else:
                print(f"Warning: Image not found at {abs_path} (original path: {path})")

    c.save()
    buf.seek(0)
    return buf.read()
