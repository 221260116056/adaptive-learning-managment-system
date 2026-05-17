import qrcode
from io import BytesIO


def generate_qr_code(verification_url):
    from qrcode.image.pil import PilImage
    qr = qrcode.make(verification_url, image_factory=PilImage)
    buffer = BytesIO()
    qr.save(buffer, format='PNG')
    buffer.seek(0)
    return buffer
