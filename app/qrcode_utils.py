import qrcode
import io


def generate_qr_bytes(payload: str) -> bytes:
    """Generate a PNG QR code for the given payload and return bytes."""
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M)
    qr.add_data(payload)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    bio = io.BytesIO()
    img.save(bio, format='PNG')
    return bio.getvalue()
