import io
import qrcode
from qrcode.image.pil import PilImage

from app.core.config import settings


def generate_qr_bytes(cert_code: str) -> bytes:
    """
    Generate a QR code PNG image (bytes) pointing to the public verify URL.
    """
    verify_url = f"{settings.FRONTEND_URL.rstrip('/')}/verify/{cert_code}/"

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=2,
    )
    qr.add_data(verify_url)
    qr.make(fit=True)

    img: PilImage = qr.make_image(fill_color="black", back_color="white")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.read()
