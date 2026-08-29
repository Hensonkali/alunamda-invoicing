import os
import re
from fastapi import APIRouter, Request
from fastapi.responses import Response, RedirectResponse, HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from database import async_session
from models import Document, CompanySettings, Client
from config import get_settings
from app_templates import templates

router = APIRouter()
app_settings = get_settings()

_logo_base64_cache = None


def get_logo_base64():
    global _logo_base64_cache
    if _logo_base64_cache is not None:
        return _logo_base64_cache

    logo_py = os.path.join("data", "logo_base64.py")
    if os.path.exists(logo_py):
        try:
            _logo_base64_cache = ""
            with open(logo_py, "r", encoding="utf-8") as f:
                content = f.read()
            match = re.search(r"LOGO_BASE64\s*=\s*['\"](.+?)['\"]", content, re.DOTALL)
            if match:
                _logo_base64_cache = match.group(1)
        except Exception:
            _logo_base64_cache = ""
    else:
        _logo_base64_cache = ""

    return _logo_base64_cache


def format_zar(value):
    try:
        return f"R {value:,.2f}"
    except (ValueError, TypeError):
        return "R 0.00"


def render_pdf_html_original(doc, client, settings):
    from jinja2 import Environment, FileSystemLoader
    env = Environment(loader=FileSystemLoader("templates"))
    env.filters['zar'] = format_zar
    template = env.get_template("pdf.html")
    logo_b64 = get_logo_base64()
    return template.render(doc=doc, client=client, settings=settings, logo_base64=logo_b64)


def render_pdf_html(doc, client, settings):
    user_template_path = "templates/quote_template.html"
    if os.path.exists(user_template_path):
        try:
            return render_user_template(doc, client, settings)
        except Exception:
            pass
    return render_pdf_html_original(doc, client, settings)


def generate_pdf_bytes(html: str) -> bytes:
    try:
        from xhtml2pdf import pisa
        import io
        output = io.BytesIO()
        pisa_status = pisa.CreatePDF(io.BytesIO(html.encode('utf-8')), dest=output, encoding='utf-8')
        if pisa_status.err:
            raise Exception(f"xhtml2pdf errors: {pisa_status.err}")
        return output.getvalue()
    except Exception:
        pass

    try:
        import weasyprint
        return weasyprint.HTML(string=html).write_pdf()
    except (ImportError, OSError):
        pass

    return None


def render_user_template(doc, client, settings) -> str:
    from jinja2 import Environment, FileSystemLoader

    template_path = "templates/quote_template.html"
    if not os.path.exists(template_path):
        return render_pdf_html_original(doc, client, settings)

    env = Environment(loader=FileSystemLoader("templates"))
    env.filters['zar'] = format_zar
    template = env.get_template("quote_template.html")

    status_class_map = {
        'draft': 'draft',
        'sent': 'sent',
        'accepted': 'accepted',
        'approved': 'approved',
        'paid': 'paid',
        'overdue': 'overdue',
    }
    status = status_class_map.get(doc.status, 'draft')

    doc_type_label = {
        'quote': 'QUOTE',
        'invoice': 'INVOICE',
        'paid_invoice': 'PAID INVOICE',
        'receipt': 'RECEIPT',
    }.get(doc.type, 'QUOTE')

    items = []
    for item in (doc.line_items or []):
        items.append({
            'description': item.service or '',
            'description_sub': item.description or '',
            'qty': f"{item.quantity:.2f}",
            'unit_price': f"R {item.unit_price:,.2f}",
            'vat_percent': f"{item.vat_rate:.0f}%",
            'amount': f"R {item.line_total:,.2f}",
        })

    context = {
        'logo_url': get_logo_base64(),
        'company_name': settings.company_name or 'ALUNAMDA',
        'company_sub': 'ACCOUNTING SERVICES (PTY) LTD,',
        'company_phone': settings.phone or '',
        'company_email': settings.email or '',
        'document_type': doc_type_label,
        'document_number': doc.document_number or '',
        'status': status,
        'status_badge': (doc.status.upper() if doc.status else 'DRAFT'),
        'issue_date': doc.issue_date.strftime('%d %b %Y') if doc.issue_date else '',
        'due_date': doc.due_date.strftime('%d %b %Y') if doc.due_date else '',
        'payment_terms': doc.payment_terms or '',
        'notes_text': doc.client_notes or settings.default_notes or '',
        'client_name': client.company_name if client else '',
        'client_contact': client.contact_name if client else '',
        'client_email': client.email if client else '',
        'client_phone': client.phone if client else '',
        'client_vat': client.vat_number if client else '',
        'items': items,
        'subtotal': f"R {doc.subtotal:,.2f}" if doc.subtotal else "R 0.00",
        'vat_rate': f"{doc.vat_rate:.0f}" if doc.vat_rate else "15",
        'vat_total': f"R {doc.vat_amount:,.2f}" if doc.vat_amount else "R 0.00",
        'grand_total': f"R {doc.grand_total:,.2f}" if doc.grand_total else "R 0.00",
        'bank_name': settings.bank_name or '',
        'account_name': settings.bank_account_name or '',
        'account_number': settings.bank_account or '',
        'branch_code': settings.bank_branch or '',
        'payment_reference': doc.document_number or '',
        'footer_text': f"Thank you for considering {settings.company_name or 'ALUNAMDA'}.",
    }

    return template.render(**context)


@router.get("/documents/{doc_id}/pdf")
async def generate_pdf(request: Request, doc_id: str):
    async with async_session() as db:
        result = await db.execute(
            select(Document).options(selectinload(Document.line_items)).where(Document.id == doc_id)
        )
        doc = result.scalar_one_or_none()
        if not doc:
            return RedirectResponse("/documents", status_code=302)

        client = await db.get(Client, doc.client_id)
        settings = await db.get(CompanySettings, app_settings.settings_id)

    html = render_pdf_html(doc, client, settings)
    pdf_bytes = generate_pdf_bytes(html)

    if pdf_bytes:
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f"inline; filename={doc.document_number}.pdf"}
        )

    return HTMLResponse(content=html)


@router.get("/documents/{doc_id}/print")
async def print_view(request: Request, doc_id: str):
    async with async_session() as db:
        result = await db.execute(
            select(Document).options(selectinload(Document.line_items)).where(Document.id == doc_id)
        )
        doc = result.scalar_one_or_none()
        if not doc:
            return RedirectResponse("/documents", status_code=302)

        client = await db.get(Client, doc.client_id)
        settings = await db.get(CompanySettings, app_settings.settings_id)

    html = render_pdf_html(doc, client, settings)
    return HTMLResponse(content=html)
