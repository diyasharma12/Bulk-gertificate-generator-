import io
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import date

import qrcode
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

from app.config import settings


def generate_qr_image(url: str) -> io.BytesIO:
    """Generate an in-memory QR code image for certificate verification."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=4,
        border=1,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#1E293B", back_color="#FFFFFF")
    
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format="PNG")
    img_byte_arr.seek(0)
    return img_byte_arr


def draw_official_seal(c: canvas.Canvas, cx: float, cy: float, radius: float = 36) -> None:
    """Draw a decorative gold official verified seal on the canvas."""
    # Outer gold circle
    c.saveState()
    c.setFillColor(colors.HexColor("#D97706"))
    c.setStrokeColor(colors.HexColor("#B45309"))
    c.setLineWidth(2)
    c.circle(cx, cy, radius, stroke=1, fill=1)

    # Inner dotted/dashed circle
    c.setStrokeColor(colors.HexColor("#FEF3C7"))
    c.setLineWidth(1.5)
    c.setDash(2, 2)
    c.circle(cx, cy, radius - 4, stroke=1, fill=0)

    # Core inner circle
    c.setFillColor(colors.HexColor("#B45309"))
    c.circle(cx, cy, radius - 7, stroke=0, fill=1)

    # Star / Seal text
    c.setFillColor(colors.HexColor("#FFFFFF"))
    c.setFont("Helvetica-Bold", 8)
    c.drawCentredString(cx, cy + 6, "OFFICIAL")
    c.setFont("Helvetica-Bold", 7)
    c.drawCentredString(cx, cy - 4, "VERIFIED")
    c.setFont("Helvetica", 6)
    c.drawCentredString(cx, cy - 14, "★ ★ ★")
    c.restoreState()


def generate_certificate_pdf(
    output_path: Path,
    certificate_id: str,
    recipient_name: str,
    recipient_email: str,
    title: str,
    issuer_name: str,
    issue_date: date,
    description: Optional[str] = None,
    custom_attributes: Optional[Dict[str, Any]] = None,
) -> Path:
    """
    Renders a high-resolution, vector PDF certificate for a recipient.
    
    Uses standard landscape Letter dimensions with double-bordered framing,
    custom typography, official seal, verification ID, and verification QR code.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Landscape Letter: 11 x 8.5 inches (792 x 612 points)
    page_width, page_height = landscape(letter)
    c = canvas.Canvas(str(output_path), pagesize=(page_width, page_height))
    
    # 1. Background Fill
    c.setFillColor(colors.HexColor("#FAFAF9"))
    c.rect(0, 0, page_width, page_height, stroke=0, fill=1)

    # 2. Outer Deep Navy Border
    navy = colors.HexColor("#0F172A")
    c.setStrokeColor(navy)
    c.setLineWidth(5)
    c.rect(24, 24, page_width - 48, page_height - 48, stroke=1, fill=0)

    # 3. Inner Gold Accent Border
    gold = colors.HexColor("#D97706")
    c.setStrokeColor(gold)
    c.setLineWidth(1.5)
    c.rect(32, 32, page_width - 64, page_height - 64, stroke=1, fill=0)

    # Corner decorative brackets
    bracket_len = 20
    for x_corner, y_corner in [
        (38, 38),
        (page_width - 38, 38),
        (38, page_height - 38),
        (page_width - 38, page_height - 38),
    ]:
        c.setStrokeColor(gold)
        c.setLineWidth(2)
        c.circle(x_corner, y_corner, 3, stroke=1, fill=1)

    # 4. Header: Certificate Title
    center_x = page_width / 2.0

    c.setFillColor(gold)
    c.setFont("Helvetica-Bold", 13)
    c.drawCentredString(center_x, page_height - 85, issuer_name.upper())

    c.setFillColor(navy)
    c.setFont("Times-Bold", 32)
    c.drawCentredString(center_x, page_height - 125, "CERTIFICATE OF ACHIEVEMENT")

    # Divider bar
    c.setStrokeColor(gold)
    c.setLineWidth(1.5)
    c.line(center_x - 140, page_height - 138, center_x + 140, page_height - 138)

    # 5. Presentation Text
    c.setFillColor(colors.HexColor("#475569"))
    c.setFont("Helvetica", 12)
    c.drawCentredString(center_x, page_height - 170, "THIS CERTIFICATE IS PROUDLY PRESENTED TO")

    # 6. Recipient Name
    c.setFillColor(colors.HexColor("#0F172A"))
    c.setFont("Times-BoldItalic", 34)
    c.drawCentredString(center_x, page_height - 215, recipient_name)

    # Underline under recipient name
    name_width = min(400, max(260, len(recipient_name) * 16))
    c.setStrokeColor(colors.HexColor("#CBD5E1"))
    c.setLineWidth(1)
    c.line(center_x - (name_width / 2), page_height - 225, center_x + (name_width / 2), page_height - 225)

    # 7. Reason / Statement
    c.setFillColor(colors.HexColor("#475569"))
    c.setFont("Helvetica", 12)
    c.drawCentredString(center_x, page_height - 255, "for successfully completing")

    # Course / Event Title
    c.setFillColor(colors.HexColor("#1E3A8A"))
    c.setFont("Helvetica-Bold", 20)
    c.drawCentredString(center_x, page_height - 285, title)

    # Optional description statement
    y_cursor = page_height - 315
    if description:
        c.setFillColor(colors.HexColor("#64748B"))
        c.setFont("Helvetica-Oblique", 11)
        c.drawCentredString(center_x, y_cursor, description)
        y_cursor -= 25

    # Optional custom attributes (e.g. Grade, Track, Honors)
    if custom_attributes:
        attr_strs = [f"{k.capitalize()}: {v}" for k, v in custom_attributes.items()]
        attr_line = "  •  ".join(attr_strs)
        c.setFillColor(colors.HexColor("#334155"))
        c.setFont("Helvetica-Bold", 10)
        c.drawCentredString(center_x, y_cursor, attr_line)

    # 8. Footer Section
    # Left: Issue Date
    date_str = issue_date.strftime("%B %d, %Y") if hasattr(issue_date, "strftime") else str(issue_date)
    c.setStrokeColor(colors.HexColor("#94A3B8"))
    c.setLineWidth(1)
    c.line(90, 115, 250, 115)
    c.setFillColor(colors.HexColor("#1E293B"))
    c.setFont("Helvetica-Bold", 11)
    c.drawCentredString(170, 125, date_str)
    c.setFillColor(colors.HexColor("#64748B"))
    c.setFont("Helvetica", 9)
    c.drawCentredString(170, 100, "DATE OF ISSUANCE")

    # Center: Official Seal Emblem
    draw_official_seal(c, center_x, 118, radius=34)

    # Right: Signature line & Issuer
    c.line(page_width - 250, 115, page_width - 90, 115)
    c.setFillColor(colors.HexColor("#1E293B"))
    c.setFont("Helvetica-Bold", 11)
    c.drawCentredString(page_width - 170, 125, issuer_name)
    c.setFillColor(colors.HexColor("#64748B"))
    c.setFont("Helvetica", 9)
    c.drawCentredString(page_width - 170, 100, "AUTHORIZED SIGNATURE")

    # 9. Verification Bar & QR Code
    verify_url = f"{settings.VERIFY_BASE_URL}/{certificate_id}"
    try:
        qr_io = generate_qr_image(verify_url)
        qr_reader = ImageReader(qr_io)
        # Draw QR code in bottom-left
        c.drawImage(qr_reader, 45, 42, width=48, height=48)
    except Exception:
        # Fallback if QR generation encounters unexpected issue
        pass

    # Certificate ID text
    c.setFillColor(colors.HexColor("#94A3B8"))
    c.setFont("Helvetica", 8)
    c.drawString(100, 52, f"Certificate ID: {certificate_id}")
    c.drawString(100, 42, f"Verify authenticity at: {verify_url}")

    c.showPage()
    c.save()

    return output_path
