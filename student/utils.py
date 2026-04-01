import qrcode
from io import BytesIO


def generate_qr_code(verification_url):
    qr = qrcode.make(verification_url)
    buffer = BytesIO()
    qr.save(buffer, format='PNG')
    buffer.seek(0)
    return buffer
