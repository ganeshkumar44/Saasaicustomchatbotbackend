"""Invoice generation, PDF storage, download, and email delivery."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

import fitz
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.core import messages
from app.core.config import PROJECT_ROOT, get_settings
from app.modules.auth.model import User
from app.modules.auth.utils import send_email_with_attachment
from app.modules.billing.checkout import (
    BillingValidationError,
    build_checkout_amounts,
    money_to_float,
)
from app.modules.billing.model import (
    INVOICE_STATUS_PAID,
    Invoice,
    PaymentTransaction,
)
from app.modules.plan_master.model import PlanMaster
from app.modules.user_plan.utils import get_plan_display_name

logger = logging.getLogger(__name__)

_SAFE_FILENAME = re.compile(r"[^A-Za-z0-9._-]+")


def calculate_gst(
    taxable_amount: Decimal | float | int,
    gst_percentage: float | None = None,
) -> tuple[Decimal, Decimal, Decimal]:
    """
    Return (taxable, gst_amount, grand_total).

    GST rate comes from settings when not provided (admin-configurable).
    """
    settings = get_settings()
    rate = Decimal(str(gst_percentage if gst_percentage is not None else settings.GST_PERCENTAGE))
    taxable = Decimal(str(taxable_amount)).quantize(Decimal("0.01"))
    gst_amount = (taxable * rate / Decimal("100")).quantize(Decimal("0.01"))
    total = (taxable + gst_amount).quantize(Decimal("0.01"))
    return taxable, gst_amount, total


def generate_invoice_number(db: Session) -> str:
    """Generate the next unique invoice number: NGC-YYYY-000001."""
    settings = get_settings()
    year = datetime.now(timezone.utc).year
    prefix = f"{settings.INVOICE_NUMBER_PREFIX}-{year}-"

    last = db.scalar(
        select(Invoice.invoice_number)
        .where(Invoice.invoice_number.like(f"{prefix}%"))
        .order_by(Invoice.invoice_number.desc())
        .limit(1)
    )
    next_seq = 1
    if last:
        try:
            next_seq = int(str(last).rsplit("-", 1)[-1]) + 1
        except ValueError:
            next_seq = 1
    return f"{prefix}{next_seq:06d}"


def _invoice_upload_dir() -> Path:
    settings = get_settings()
    path = Path(settings.INVOICE_UPLOAD_DIR)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    path.mkdir(parents=True, exist_ok=True)
    return path


def _resolve_pdf_path(stored: str | None) -> Path | None:
    if not stored:
        return None
    path = Path(stored)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path if path.is_file() else None


def _billing_name(user: User) -> str:
    parts = [user.first_name or "", user.last_name or ""]
    name = " ".join(p.strip() for p in parts if p and p.strip()).strip()
    return name or (user.email.split("@")[0] if user.email else "Customer")


def _user_company(db: Session, user_id: int) -> str | None:
    try:
        from app.modules.user_details.model import UserDetails

        details = db.execute(
            select(UserDetails).where(UserDetails.user_id == user_id)
        ).scalar_one_or_none()
        if details and details.company:
            return str(details.company).strip() or None
    except Exception:
        logger.debug("user_details unavailable for invoice user_id=%s", user_id)
    return None


def _money(currency: str, value: Decimal) -> str:
    return f"{currency} {money_to_float(value):,.2f}"


def _generate_invoice_pdf_reportlab(
    absolute_path: Path,
    invoice: Invoice,
    plan: PlanMaster | None,
) -> None:
    """Preferred PDF engine when reportlab is installed."""
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        Image,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    settings = get_settings()
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "InvoiceTitle",
        parent=styles["Heading1"],
        fontSize=18,
        textColor=colors.HexColor("#003A96"),
        spaceAfter=6,
    )
    heading_style = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        fontSize=11,
        textColor=colors.HexColor("#111827"),
        spaceBefore=10,
        spaceAfter=4,
    )
    body_style = ParagraphStyle("Body", parent=styles["Normal"], fontSize=9, leading=12)
    right_style = ParagraphStyle("Right", parent=body_style, alignment=TA_RIGHT)
    center_style = ParagraphStyle(
        "Center",
        parent=body_style,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#6B7280"),
    )
    muted_style = ParagraphStyle(
        "Muted", parent=body_style, textColor=colors.HexColor("#6B7280")
    )

    doc = SimpleDocTemplate(
        str(absolute_path),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
    )
    story: list[Any] = []

    logo_path = settings.COMPANY_LOGO_PATH.strip()
    if logo_path:
        logo_file = Path(logo_path)
        if not logo_file.is_absolute():
            logo_file = PROJECT_ROOT / logo_file
        if logo_file.is_file():
            try:
                story.append(Image(str(logo_file), width=36 * mm, height=12 * mm))
                story.append(Spacer(1, 4 * mm))
            except Exception:
                logger.warning("Unable to embed company logo at %s", logo_file)

    story.append(Paragraph(settings.COMPANY_NAME, title_style))
    company_lines = [
        settings.COMPANY_ADDRESS,
        f"GSTIN: {settings.COMPANY_GST_NUMBER}" if settings.COMPANY_GST_NUMBER else "",
        f"Support: {settings.COMPANY_SUPPORT_EMAIL}",
        settings.COMPANY_SUPPORT_PHONE,
        settings.COMPANY_WEBSITE,
    ]
    story.append(
        Paragraph("<br/>".join(line for line in company_lines if line), muted_style)
    )
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph("TAX INVOICE", heading_style))

    invoice_date = invoice.invoice_date or invoice.created_at
    if invoice_date and invoice_date.tzinfo is None:
        invoice_date = invoice_date.replace(tzinfo=timezone.utc)
    date_label = invoice_date.strftime("%d %b %Y") if invoice_date else "—"

    meta = [
        [Paragraph("<b>Invoice Number</b>", body_style), Paragraph(invoice.invoice_number, body_style)],
        [Paragraph("<b>Invoice Date</b>", body_style), Paragraph(date_label, body_style)],
        [
            Paragraph("<b>Payment Status</b>", body_style),
            Paragraph((invoice.payment_status or invoice.invoice_status or "—").title(), body_style),
        ],
        [
            Paragraph("<b>Payment Method</b>", body_style),
            Paragraph((invoice.payment_method or "Razorpay").title(), body_style),
        ],
    ]
    meta_table = Table(meta, colWidths=[55 * mm, 115 * mm])
    meta_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    story.append(meta_table)
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("Bill To", heading_style))
    bill_to = [
        invoice.billing_name or "—",
        invoice.company_name or "",
        invoice.billing_email or "",
        invoice.billing_phone or "",
        invoice.billing_address or "",
        " ".join(
            part
            for part in [invoice.billing_city, invoice.billing_state, invoice.billing_pincode]
            if part
        ),
        invoice.billing_country or "",
        f"GSTIN: {invoice.gst_number}" if invoice.gst_number else "",
    ]
    story.append(Paragraph("<br/>".join(line for line in bill_to if line), body_style))
    story.append(Spacer(1, 4 * mm))

    plan_label = get_plan_display_name(
        plan.plan_name if plan is not None else f"Plan #{invoice.plan_id}"
    )
    cycle = (invoice.billing_cycle or "—").replace("_", " ").title()
    currency = invoice.currency or settings.BILLING_CURRENCY

    line_data = [
        [
            Paragraph("<b>Description</b>", body_style),
            Paragraph("<b>Billing Cycle</b>", body_style),
            Paragraph("<b>Amount</b>", right_style),
        ],
        [
            Paragraph(f"{plan_label} subscription", body_style),
            Paragraph(cycle, body_style),
            Paragraph(_money(currency, invoice.subtotal + invoice.discount), right_style),
        ],
    ]
    line_table = Table(line_data, colWidths=[90 * mm, 40 * mm, 40 * mm])
    line_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F3F4F6")),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#E5E7EB")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(line_table)
    story.append(Spacer(1, 4 * mm))

    totals = [
        ["Subtotal", _money(currency, invoice.subtotal + invoice.discount)],
        [
            "Discount",
            f"- {_money(currency, invoice.discount)}"
            if invoice.discount > 0
            else _money(currency, Decimal("0")),
        ],
        [
            f"GST ({money_to_float(invoice.gst_percentage):.0f}%)",
            _money(currency, invoice.gst_amount),
        ],
        ["Grand Total", _money(currency, invoice.total_amount)],
    ]
    totals_table = Table(totals, colWidths=[130 * mm, 40 * mm], hAlign="RIGHT")
    totals_table.setStyle(
        TableStyle(
            [
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("TEXTCOLOR", (0, -1), (-1, -1), colors.HexColor("#003A96")),
                ("LINEABOVE", (0, -1), (-1, -1), 0.8, colors.HexColor("#003A96")),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(totals_table)
    story.append(Spacer(1, 8 * mm))
    story.append(
        Paragraph(
            f"Thank you for purchasing {settings.COMPANY_NAME}. We appreciate your business.",
            body_style,
        )
    )
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph(settings.INVOICE_FOOTER, center_style))
    doc.build(story)


def _generate_invoice_pdf_fitz(
    absolute_path: Path,
    invoice: Invoice,
    plan: PlanMaster | None,
) -> None:
    """Fallback PDF engine using PyMuPDF (already in project dependencies)."""
    settings = get_settings()
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    y = 50
    brand = (0 / 255, 58 / 255, 150 / 255)

    def write(text: str, *, size: float = 10, color=(0, 0, 0), bold: bool = False) -> None:
        nonlocal y
        font = "helv"
        page.insert_text((50, y), text, fontsize=size, fontname=font, color=color)
        y += size + 6

    write(settings.COMPANY_NAME, size=18, color=brand, bold=True)
    if settings.COMPANY_ADDRESS:
        write(settings.COMPANY_ADDRESS, size=9, color=(0.4, 0.4, 0.4))
    if settings.COMPANY_GST_NUMBER:
        write(f"GSTIN: {settings.COMPANY_GST_NUMBER}", size=9, color=(0.4, 0.4, 0.4))
    write(f"Support: {settings.COMPANY_SUPPORT_EMAIL}", size=9, color=(0.4, 0.4, 0.4))
    if settings.COMPANY_SUPPORT_PHONE:
        write(settings.COMPANY_SUPPORT_PHONE, size=9, color=(0.4, 0.4, 0.4))
    if settings.COMPANY_WEBSITE:
        write(settings.COMPANY_WEBSITE, size=9, color=(0.4, 0.4, 0.4))
    y += 8
    write("TAX INVOICE", size=14, color=brand)

    invoice_date = invoice.invoice_date or invoice.created_at
    if invoice_date and invoice_date.tzinfo is None:
        invoice_date = invoice_date.replace(tzinfo=timezone.utc)
    date_label = invoice_date.strftime("%d %b %Y") if invoice_date else "—"
    write(f"Invoice Number: {invoice.invoice_number}")
    write(f"Invoice Date: {date_label}")
    write(f"Payment Status: {(invoice.payment_status or invoice.invoice_status or '—').title()}")
    write(f"Payment Method: {(invoice.payment_method or 'Razorpay').title()}")
    y += 8
    write("Bill To", size=12, color=brand)
    for line in [
        invoice.billing_name,
        invoice.company_name,
        invoice.billing_email,
        invoice.billing_phone,
        invoice.billing_address,
        " ".join(
            part
            for part in [invoice.billing_city, invoice.billing_state, invoice.billing_pincode]
            if part
        ),
        invoice.billing_country,
        f"GSTIN: {invoice.gst_number}" if invoice.gst_number else None,
    ]:
        if line:
            write(str(line))

    y += 10
    plan_label = get_plan_display_name(
        plan.plan_name if plan is not None else f"Plan #{invoice.plan_id}"
    )
    cycle = (invoice.billing_cycle or "—").replace("_", " ").title()
    currency = invoice.currency or settings.BILLING_CURRENCY
    write("Plan Details", size=12, color=brand)
    write(f"Plan: {plan_label}")
    write(f"Billing Cycle: {cycle}")
    write(f"Subtotal: {_money(currency, invoice.subtotal + invoice.discount)}")
    write(f"Discount: {_money(currency, invoice.discount)}")
    write(
        f"GST ({money_to_float(invoice.gst_percentage):.0f}%): "
        f"{_money(currency, invoice.gst_amount)}"
    )
    write(f"Grand Total: {_money(currency, invoice.total_amount)}", size=12, color=brand)
    y += 14
    write(
        f"Thank you for purchasing {settings.COMPANY_NAME}. Your invoice is attached in email copies.",
        size=9,
    )
    y += 10
    write(settings.INVOICE_FOOTER, size=8, color=(0.45, 0.45, 0.45))
    doc.save(str(absolute_path))
    doc.close()


def generate_invoice_pdf(invoice: Invoice, plan: PlanMaster | None = None) -> str:
    """
    Generate a professional invoice PDF.

    Prefers reportlab when installed; otherwise uses PyMuPDF (project dependency).
    Returns a project-relative path stored in invoice.pdf_path.
    """
    upload_dir = _invoice_upload_dir()
    safe_number = _SAFE_FILENAME.sub("_", invoice.invoice_number)
    filename = f"invoice_{safe_number}.pdf"
    absolute_path = upload_dir / filename

    try:
        import reportlab  # noqa: F401

        _generate_invoice_pdf_reportlab(absolute_path, invoice, plan)
    except ImportError:
        logger.info("reportlab not installed; generating invoice PDF with PyMuPDF")
        _generate_invoice_pdf_fitz(absolute_path, invoice, plan)

    try:
        relative = absolute_path.relative_to(PROJECT_ROOT)
        return str(relative).replace("\\", "/")
    except ValueError:
        return str(absolute_path)


def create_invoice_for_payment(
    db: Session,
    *,
    user: User,
    payment: PaymentTransaction,
    plan: PlanMaster,
) -> Invoice:
    """
    Create one invoice for a successful payment (idempotent).

    Does not send email. Caller should commit, then call send_invoice_email.
    """
    existing = db.execute(
        select(Invoice).where(Invoice.payment_transaction_id == payment.id)
    ).scalar_one_or_none()
    if existing is not None:
        if not existing.pdf_path or not _resolve_pdf_path(existing.pdf_path):
            existing.pdf_path = generate_invoice_pdf(existing, plan)
            db.flush()
        return existing

    amounts = build_checkout_amounts(plan, payment.billing_cycle)
    now = datetime.now(timezone.utc)
    company = _user_company(db, user.id)

    invoice: Invoice | None = None
    for _attempt in range(5):
        invoice_number = generate_invoice_number(db)
        candidate = Invoice(
            invoice_number=invoice_number,
            payment_transaction_id=payment.id,
            user_id=user.id,
            plan_id=plan.id,
            invoice_date=payment.transaction_date or now,
            billing_cycle=payment.billing_cycle,
            subtotal=amounts.subtotal,
            discount=amounts.discount,
            gst_percentage=amounts.gst_percentage,
            gst_amount=amounts.gst_amount,
            total_amount=amounts.total_amount,
            currency=(payment.currency or amounts.currency or "INR").upper(),
            invoice_status=INVOICE_STATUS_PAID,
            billing_name=_billing_name(user),
            billing_email=user.email,
            billing_phone=getattr(user, "mobile", None),
            company_name=company,
            payment_method=payment.payment_method or "razorpay",
            payment_status=payment.status,
        )
        nested = db.begin_nested()
        try:
            db.add(candidate)
            db.flush()
            nested.commit()
            invoice = candidate
            break
        except IntegrityError:
            nested.rollback()
            continue

    if invoice is None:
        raise BillingValidationError("Unable to allocate a unique invoice number.")

    invoice.pdf_path = generate_invoice_pdf(invoice, plan)
    db.flush()
    logger.info(
        "Invoice created number=%s payment_id=%s user_id=%s",
        invoice.invoice_number,
        payment.id,
        user.id,
    )
    return invoice


def send_invoice_email(invoice: Invoice) -> None:
    """Email the invoice PDF. Failures are raised so resend API can report them."""
    settings = get_settings()
    to_email = (invoice.billing_email or "").strip()
    if not to_email:
        raise BillingValidationError(messages.BILLING_INVOICE_EMAIL_FAILED)

    pdf_path = _resolve_pdf_path(invoice.pdf_path)
    if pdf_path is None:
        plan = None
        # regenerate if possible later; for now fail
        raise BillingValidationError(messages.BILLING_INVOICE_PDF_MISSING)

    content = pdf_path.read_bytes()
    subject = "Payment Successful - Invoice"
    plain_body = (
        f"Hi {invoice.billing_name or 'there'},\n\n"
        f"Thank you for purchasing {settings.COMPANY_NAME}.\n"
        f"Your invoice {invoice.invoice_number} is attached.\n\n"
        f"Support: {settings.COMPANY_SUPPORT_EMAIL}\n"
        f"{settings.COMPANY_WEBSITE}\n"
    )
    html_body = (
        f"<p>Hi {invoice.billing_name or 'there'},</p>"
        f"<p>Thank you for purchasing <strong>{settings.COMPANY_NAME}</strong>.</p>"
        f"<p>Your invoice <strong>{invoice.invoice_number}</strong> is attached.</p>"
        f"<p>Support: {settings.COMPANY_SUPPORT_EMAIL}<br/>"
        f"{settings.COMPANY_WEBSITE}</p>"
    )
    send_email_with_attachment(
        to_email,
        subject,
        plain_body,
        html_body,
        filename=pdf_path.name,
        content=content,
        mime_subtype="pdf",
    )


def issue_invoice_after_payment(
    db: Session,
    *,
    user: User,
    payment: PaymentTransaction,
    plan: PlanMaster,
) -> Invoice | None:
    """
    Create invoice + PDF for a successful payment and email it.

    Email failures never undo invoice creation.
    """
    if payment.status != "success":
        return None

    try:
        invoice = create_invoice_for_payment(
            db,
            user=user,
            payment=payment,
            plan=plan,
        )
        db.commit()
    except Exception:
        db.rollback()
        logger.exception(
            "Invoice generation failed payment_id=%s user_id=%s",
            payment.id,
            user.id,
        )
        return None

    try:
        send_invoice_email(invoice)
    except Exception:
        logger.exception(
            "Invoice email failed invoice_id=%s user_id=%s",
            invoice.id,
            user.id,
        )
    return invoice


def get_invoice_for_actor(
    db: Session,
    actor: User,
    invoice_id: int,
    *,
    user_id: int | None = None,
) -> Invoice:
    """Load invoice with ownership checks via billing target resolution."""
    from app.modules.billing.utils import (
        BillingUserNotFoundError,
        resolve_billing_target_user,
    )

    target = resolve_billing_target_user(db, actor, user_id)
    invoice = (
        db.execute(
            select(Invoice)
            .options(
                joinedload(Invoice.plan),
                joinedload(Invoice.payment_transaction),
            )
            .where(Invoice.id == invoice_id)
        )
        .unique()
        .scalar_one_or_none()
    )
    if invoice is None or invoice.user_id != target.id:
        raise BillingUserNotFoundError(messages.BILLING_INVOICE_NOT_FOUND)
    return invoice


def get_invoice_details(invoice: Invoice) -> dict[str, Any]:
    """Serialize invoice into a detail dict (service layer helper)."""
    from app.modules.billing.utils import serialize_invoice

    item = serialize_invoice(invoice)
    return item.model_dump()


def download_invoice(invoice: Invoice) -> Path:
    """Return absolute PDF path or raise when missing."""
    path = _resolve_pdf_path(invoice.pdf_path)
    if path is None:
        # Attempt regeneration once.
        plan = None
        if invoice.plan_id:
            # plan may already be loaded
            plan = invoice.plan
        if plan is None and invoice.plan_id:
            # can't get db here easily; raise
            raise BillingValidationError(messages.BILLING_INVOICE_PDF_MISSING)
        invoice.pdf_path = generate_invoice_pdf(invoice, plan)
        path = _resolve_pdf_path(invoice.pdf_path)
        if path is None:
            raise BillingValidationError(messages.BILLING_INVOICE_PDF_MISSING)
    return path


def get_latest_invoice_for_user(db: Session, user_id: int) -> Invoice | None:
    """Newest invoice for a user (for Current Plan widgets)."""
    return db.scalars(
        select(Invoice)
        .options(joinedload(Invoice.plan))
        .where(Invoice.user_id == user_id)
        .order_by(Invoice.created_at.desc(), Invoice.id.desc())
        .limit(1)
    ).first()
