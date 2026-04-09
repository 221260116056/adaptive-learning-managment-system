import os
import qrcode
from io import BytesIO
from django.core.files.base import ContentFile
from django.conf import settings
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from .models import Certificate, PlatformSetting

def generate_certificate_pdf(certificate_obj):
    """
    Generates a professional PDF for the given Certificate object.
    Includes student name, course, ID, signer details, and dynamic QR verification code.
    """
    # 1. Setup Canvas (Landscape A4)
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=landscape(A4))
    width, height = landscape(A4)

    # 2. Add Background/Design Element (Borders & Gradient simulation)
    p.setStrokeColor(colors.HexColor("#4F46E5")) # Primary Indigo
    p.setLineWidth(5)
    p.roundRect(1.5*cm, 1.5*cm, width-3*cm, height-3*cm, 10) # Outer Border
    
    p.setStrokeColor(colors.HexColor("#E2E8F0")) # Light slate border
    p.setLineWidth(1)
    p.roundRect(1.8*cm, 1.8*cm, width-3.6*cm, height-3.6*cm, 8) # Inner Border

    # 3. Branding (Adaptive LMS)
    p.setFont("Helvetica-Bold", 42)
    p.setFillColor(colors.HexColor("#1E293B")) # Dark Slate
    p.drawCentredString(width/2, height - 5*cm, "Certificate of Completion")
    
    p.setFont("Helvetica", 14)
    p.drawCentredString(width/2, height - 7*cm, "THIS IS TO CERTIFY THAT")

    # 4. Student Name (Large Bold)
    p.setFont("Helvetica-Bold", 36)
    p.setFillColor(colors.HexColor("#4F46E5"))
    student_name = f"{certificate_obj.user.first_name} {certificate_obj.user.last_name}".strip() or certificate_obj.user.username
    p.drawCentredString(width/2, height - 9.5*cm, student_name)

    # 5. Course and Completion Text
    p.setFont("Helvetica", 14)
    p.setFillColor(colors.HexColor("#334155"))
    p.drawCentredString(width/2, height - 11.5*cm, "HAS SUCCESSFULLY COMPLETED THE COURSE")
    
    p.setFont("Helvetica-Bold", 24)
    p.setFillColor(colors.HexColor("#1E293B"))
    p.drawCentredString(width/2, height - 13*cm, certificate_obj.course.title)

    # 6. Completion Date
    p.setFont("Helvetica", 12)
    p.setFillColor(colors.HexColor("#64748B"))
    issued_date = certificate_obj.issued_at.strftime("%B %d, %Y") if certificate_obj.issued_at else "Not Issued"
    p.drawCentredString(width/2, height - 14.5 * cm, f"Completed on {issued_date}")

    # 7. Signature Section
    
    # Platform / Admin Signature (Left Side)
    p.line(3*cm, 4*cm, 9*cm, 4*cm) # Admin Signature Line
    p.setFont("Helvetica-Bold", 12)
    p.drawCentredString(6*cm, 3.5*cm, "Platform Administrator")
    config = PlatformSetting.objects.first()
    if config and config.admin_signature:
        try:
            admin_sig_path = config.admin_signature.path
            if os.path.exists(admin_sig_path):
                # Draw Admin Signature Image
                p.drawImage(ImageReader(admin_sig_path), 4*cm, 4.1*cm, width=4*cm, height=2*cm, preserveAspectRatio=True, mask='auto')
        except Exception:
            pass

    # Teacher Signature (Right Side)
    p.line(width-9*cm, 4*cm, width-3*cm, 4*cm) # Teacher Signature Line
    p.setFont("Helvetica-Bold", 12)
    teacher_name = f"{certificate_obj.course.teacher.first_name} {certificate_obj.course.teacher.last_name}".strip() or certificate_obj.course.teacher.username
    p.drawCentredString(width-6*cm, 3.5*cm, teacher_name)
    p.setFont("Helvetica", 10)
    p.drawCentredString(width-6*cm, 3*cm, "Course Instructor")
    
    if certificate_obj.course.teacher_signature:
        try:
            teacher_sig_path = certificate_obj.course.teacher_signature.path
            if os.path.exists(teacher_sig_path):
                # Draw Teacher Signature Image
                p.drawImage(ImageReader(teacher_sig_path), width-8*cm, 4.1*cm, width=4*cm, height=2*cm, preserveAspectRatio=True, mask='auto')
        except Exception:
            pass

    # 8. QR Code Generation for Verification (Center)
    base_url = getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000')
    verify_url = f"{base_url}/verify-certificate/{certificate_obj.certificate_id}/"
    
    qr = qrcode.QRCode(box_size=10, border=2)
    qr.add_data(verify_url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")
    
    qr_buffer = BytesIO()
    qr_img.save(qr_buffer, format="PNG")
    qr_buffer.seek(0)
    
    # Draw QR on PDF
    p.drawImage(ImageReader(qr_buffer), width/2 - 1.5*cm, 3.5*cm, width=3*cm, height=3*cm)
    p.setFont("Helvetica", 7)
    p.drawCentredString(width/2, 3.2*cm, "Scan to Verify")
    
    # Draw Certificate ID under QR Code
    p.setFont("Helvetica-Bold", 9)
    p.setFillColor(colors.HexColor("#64748B"))
    p.drawCentredString(width/2, 2.7*cm, f"CERTIFICATE ID: {certificate_obj.certificate_id}")

    # 9. Finalize
    p.showPage()
    p.save()
    
    # 10. Save to Model
    pdf_filename = f"certificate_{certificate_obj.certificate_id}.pdf"
    certificate_obj.certificate_file.save(pdf_filename, ContentFile(buffer.getvalue()))
    certificate_obj.save()
    
    return certificate_obj
