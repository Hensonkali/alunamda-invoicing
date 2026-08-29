import json
import logging
from fastapi import APIRouter, Request, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from database import async_session
from models import Document, DocumentLineItem, Client, CompanySettings, ServiceItem, ActivityLog, DocumentVersion, Attachment, Payment, gen_id
from datetime import date
from typing import Optional
from config import get_settings
from app_templates import templates

router = APIRouter()
logger = logging.getLogger("alunamda.documents")
app_settings = get_settings()


def serialize_services(services):
    return json.dumps([
        {"id": s.id, "name": s.name, "description": s.description, "unit_price": s.unit_price, "vat_rate": s.vat_rate, "category": s.category}
        for s in services
    ])

VALID_TRANSITIONS = {
    "draft": ["sent", "cancelled"],
    "sent": ["draft", "accepted", "rejected", "expired", "overdue", "cancelled"],
    "accepted": ["draft", "cancelled"],
    "rejected": ["draft"],
    "expired": ["draft"],
    "overdue": ["sent", "paid", "cancelled"],
    "paid": ["cancelled"],
    "cancelled": ["draft"],
}

PREFIX_MAP = {
    "quote": "quote_prefix",
    "invoice": "invoice_prefix",
    "paid_invoice": "paid_invoice_prefix",
    "receipt": "receipt_prefix",
}

COUNTER_MAP = {
    "quote": "next_quote_number",
    "invoice": "next_invoice_number",
    "paid_invoice": "next_paid_invoice_number",
    "receipt": "next_receipt_number",
}


def calc_line_total(quantity: float, unit_price: float, discount: float) -> float:
    return round(quantity * unit_price - discount, 2)


def calculate_totals(line_items_data: list, vat_mode: str, discount_amount: float, vat_rate: float):
    subtotal = 0.0
    for li in line_items_data:
        subtotal += calc_line_total(li["quantity"], li["unit_price"], li["discount"])

    if vat_mode == "inclusive":
        vat_amount = round((subtotal - discount_amount) * vat_rate / (100 + vat_rate), 2)
        subtotal_after_discount = round(subtotal - discount_amount, 2)
        grand_total = subtotal_after_discount
    elif vat_mode == "exclusive":
        subtotal_after_discount = round(subtotal - discount_amount, 2)
        vat_amount = round(subtotal_after_discount * vat_rate / 100, 2)
        grand_total = round(subtotal_after_discount + vat_amount, 2)
    else:
        subtotal_after_discount = round(subtotal - discount_amount, 2)
        vat_amount = 0.0
        grand_total = subtotal_after_discount

    return subtotal, vat_amount, grand_total


async def generate_doc_number(db, doc_type: str) -> str:
    settings = await db.get(CompanySettings, app_settings.settings_id)
    if not settings:
        settings = CompanySettings(id=app_settings.settings_id)
        db.add(settings)
        await db.flush()

    current_year = date.today().year

    if settings.counter_year != current_year:
        settings.counter_year = current_year
        settings.next_quote_number = 1
        settings.next_invoice_number = 1
        settings.next_paid_invoice_number = 1
        settings.next_receipt_number = 1

    prefix_attr = PREFIX_MAP.get(doc_type, "invoice_prefix")
    counter_attr = COUNTER_MAP.get(doc_type, "next_invoice_number")
    prefix = getattr(settings, prefix_attr)
    num = getattr(settings, counter_attr)
    setattr(settings, counter_attr, num + 1)
    await db.flush()
    return f"{prefix}-{current_year}-{num:06d}"


def parse_line_items(request_data: dict) -> list:
    line_items = []
    services = request_data.get("line_service", [])
    descriptions = request_data.get("line_description", [])
    quantities = request_data.get("line_quantity", [])
    unit_prices = request_data.get("line_unit_price", [])
    discounts = request_data.get("line_discount", [])

    if isinstance(services, str):
        services = [services]
    if isinstance(descriptions, str):
        descriptions = [descriptions]
    if isinstance(quantities, str):
        quantities = [quantities]
    if isinstance(unit_prices, str):
        unit_prices = [unit_prices]
    if isinstance(discounts, str):
        discounts = [discounts]

    for i in range(len(services)):
        service = (services[i] if i < len(services) else "").strip()
        if not service:
            continue
        desc = (descriptions[i] if i < len(descriptions) else "").strip()
        try:
            qty = float(quantities[i] if i < len(quantities) else 1)
        except (ValueError, TypeError):
            qty = 1.0
        try:
            up = float(unit_prices[i] if i < len(unit_prices) else 0)
        except (ValueError, TypeError):
            up = 0.0
        try:
            disc = float(discounts[i] if i < len(discounts) else 0)
        except (ValueError, TypeError):
            disc = 0.0

        line_items.append({
            "service": service,
            "description": desc,
            "quantity": qty,
            "unit_price": up,
            "discount": disc,
            "line_total": calc_line_total(qty, up, disc),
        })
    return line_items


@router.get("/documents", response_class=HTMLResponse)
async def documents_list(
    request: Request,
    type: str = "",
    status: str = "",
    search: str = "",
    page: int = Query(1, ge=1),
):
    user = request.state.user
    per_page = app_settings.items_per_page
    async with async_session() as db:
        query = select(Document)
        count_query = select(func.count(Document.id))

        if type:
            query = query.where(Document.type == type)
            count_query = count_query.where(Document.type == type)
        if status:
            query = query.where(Document.status == status)
            count_query = count_query.where(Document.status == status)
        if search:
            query = query.where(Document.document_number.ilike(f"%{search}%"))
            count_query = count_query.where(Document.document_number.ilike(f"%{search}%"))

        total = (await db.execute(count_query)).scalar() or 0
        total_pages = max(1, (total + per_page - 1) // per_page)

        result = await db.execute(
            query.options(selectinload(Document.client))
            .order_by(Document.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        documents = list(result.scalars().all())

        doc_clients = {doc.client_id: doc.client for doc in documents}

    return templates.TemplateResponse(request, "documents/list.html", {
        "request": request,
        "user": user,
        "documents": documents,
        "doc_clients": doc_clients,
        "filter_type": type,
        "filter_status": status,
        "search_query": search,
        "current_page": page,
        "total_pages": total_pages,
        "total_docs": total,
    })


@router.get("/documents/new", response_class=HTMLResponse)
async def document_new(request: Request, type: str = "invoice"):
    user = request.state.user
    if type not in ("quote", "invoice"):
        type = "invoice"

    async with async_session() as db:
        result = await db.execute(select(Client).where(Client.is_active == True).order_by(Client.company_name))
        clients = list(result.scalars().all())
        settings = await db.get(CompanySettings, app_settings.settings_id)
        svc_result = await db.execute(select(ServiceItem).where(ServiceItem.is_active == True).order_by(ServiceItem.name))
        services = list(svc_result.scalars().all())

    return templates.TemplateResponse(request, "documents/form.html", {
        "request": request,
        "user": user,
        "document": None,
        "clients": clients,
        "services": services,
        "services_json": serialize_services(services),
        "doc_type": type,
        "settings": settings,
        "edit_mode": False,
        "today": date.today().isoformat(),
    })


@router.get("/documents/{doc_id}", response_class=HTMLResponse)
async def document_detail(request: Request, doc_id: str):
    user = request.state.user
    async with async_session() as db:
        result = await db.execute(
            select(Document).options(
                selectinload(Document.line_items),
                selectinload(Document.client),
                selectinload(Document.payments),
            ).where(Document.id == doc_id)
        )
        doc = result.scalar_one_or_none()
        if not doc:
            return RedirectResponse(url="/documents", status_code=302)

        client = doc.client

        att_result = await db.execute(
            select(Attachment).where(Attachment.document_id == doc_id).order_by(Attachment.created_at.desc())
        )
        attachments = list(att_result.scalars().all())

        ver_result = await db.execute(
            select(DocumentVersion).where(DocumentVersion.document_id == doc_id).order_by(DocumentVersion.created_at.desc())
        )
        versions = list(ver_result.scalars().all())

        allowed_transitions = VALID_TRANSITIONS.get(doc.status, [])
        line_items = sorted(doc.line_items, key=lambda x: x.sort_order)
        payments = sorted(doc.payments, key=lambda x: x.payment_date, reverse=True)
        total_paid = sum(p.amount for p in payments)
        balance = doc.grand_total - total_paid

    return templates.TemplateResponse(request, "documents/detail.html", {
        "request": request,
        "user": user,
        "document": doc,
        "client": client,
        "line_items": line_items,
        "allowed_transitions": allowed_transitions,
        "payments": payments,
        "total_paid": total_paid,
        "balance": balance,
        "attachments": attachments,
        "versions": versions,
    })


@router.get("/documents/{doc_id}/edit", response_class=HTMLResponse)
async def document_edit_form(request: Request, doc_id: str):
    user = request.state.user
    async with async_session() as db:
        doc = await db.get(Document, doc_id)
        if not doc:
            return RedirectResponse(url="/documents", status_code=302)
        result = await db.execute(select(Client).where(Client.is_active == True).order_by(Client.company_name))
        clients = list(result.scalars().all())
        li_result = await db.execute(
            select(DocumentLineItem).where(DocumentLineItem.document_id == doc_id).order_by(DocumentLineItem.sort_order)
        )
        line_items = list(li_result.scalars().all())
        settings = await db.get(CompanySettings, app_settings.settings_id)
        svc_result = await db.execute(select(ServiceItem).where(ServiceItem.is_active == True).order_by(ServiceItem.name))
        services = list(svc_result.scalars().all())

    return templates.TemplateResponse(request, "documents/form.html", {
        "request": request,
        "user": user,
        "document": doc,
        "clients": clients,
        "services": services,
        "services_json": serialize_services(services),
        "doc_type": doc.type,
        "line_items": line_items,
        "settings": settings,
        "edit_mode": True,
        "today": date.today().isoformat(),
    })


@router.post("/documents", response_class=HTMLResponse)
async def document_create(request: Request):
    user = request.state.user
    form = await request.form()
    doc_type = form.get("type", "invoice")
    if doc_type not in ("quote", "invoice"):
        doc_type = "invoice"

    client_id = form.get("client_id", "")
    issue_date = form.get("issue_date", "")
    due_date = form.get("due_date", "")
    valid_until = form.get("valid_until", "")
    payment_terms = form.get("payment_terms", "Due within 30 days")
    vat_mode = form.get("vat_mode", "exclusive")
    client_notes = form.get("client_notes", "")
    internal_notes = form.get("internal_notes", "")
    terms_and_conditions = form.get("terms_and_conditions", "")

    try:
        discount_amount = float(form.get("discount_amount", 0) or 0)
    except (ValueError, TypeError):
        discount_amount = 0.0

    line_items_data = parse_line_items(dict(form))

    if not client_id or not issue_date:
        async with async_session() as db:
            result = await db.execute(select(Client).where(Client.is_active == True).order_by(Client.company_name))
            clients = list(result.scalars().all())
            settings = await db.get(CompanySettings, app_settings.settings_id)
            svc_result = await db.execute(select(ServiceItem).where(ServiceItem.is_active == True).order_by(ServiceItem.name))
            services = list(svc_result.scalars().all())
        return templates.TemplateResponse(request, "documents/form.html", {
            "request": request,
            "user": user,
            "document": None,
            "clients": clients,
            "services": services,
            "services_json": serialize_services(services),
            "doc_type": doc_type,
            "settings": settings,
            "edit_mode": False,
            "today": date.today().isoformat(),
            "error": "Client and issue date are required.",
        })

    async with async_session() as db:
        settings = await db.get(CompanySettings, app_settings.settings_id)
        vat_rate = settings.default_vat_rate if settings else 15.0

        subtotal, vat_amount, grand_total = calculate_totals(line_items_data, vat_mode, discount_amount, vat_rate)

        company_details = None
        if settings:
            company_details = json.dumps({
                "company_name": settings.company_name,
                "trading_as": settings.trading_as,
                "registration_number": settings.registration_number,
                "vat_number": settings.vat_number,
                "email": settings.email,
                "phone": settings.phone,
                "whatsapp": settings.whatsapp,
                "website": settings.website,
                "address": settings.address,
                "city": settings.city,
                "postal_code": settings.postal_code,
                "country": settings.country,
                "bank_name": settings.bank_name,
                "bank_account_name": settings.bank_account_name,
                "bank_account": settings.bank_account,
                "bank_branch": settings.bank_branch,
                "bank_swift": settings.bank_swift,
                "logo_url": settings.logo_url,
            })

        doc_number = await generate_doc_number(db, doc_type)
        doc = Document(
            id=gen_id(),
            document_number=doc_number,
            type=doc_type,
            status="draft",
            client_id=client_id,
            issue_date=date.fromisoformat(issue_date),
            due_date=date.fromisoformat(due_date) if due_date else None,
            valid_until=date.fromisoformat(valid_until) if valid_until else None,
            payment_terms=payment_terms,
            vat_mode=vat_mode,
            vat_rate=vat_rate,
            subtotal=subtotal,
            vat_amount=vat_amount,
            discount_amount=discount_amount,
            grand_total=grand_total,
            client_notes=client_notes,
            internal_notes=internal_notes,
            terms_and_conditions=terms_and_conditions,
            company_details=company_details,
        )
        db.add(doc)
        await db.flush()

        for idx, li in enumerate(line_items_data):
            db.add(DocumentLineItem(
                id=gen_id(),
                document_id=doc.id,
                sort_order=idx,
                service=li["service"],
                description=li["description"],
                quantity=li["quantity"],
                unit_price=li["unit_price"],
                discount=li["discount"],
                line_total=li["line_total"],
                vat_rate=vat_rate,
                vat_mode=vat_mode,
            ))

        db.add(DocumentVersion(
            id=gen_id(),
            document_id=doc.id,
            version_number=1,
            snapshot=json.dumps({
                "line_items": line_items_data,
                "grand_total": grand_total,
                "vat_mode": vat_mode,
            }),
            change_summary="Document created",
            created_by=user.id if user else "system",
        ))

        db.add(ActivityLog(
            action="created", entity_type="document", entity_id=doc.id,
            description=f"Created {doc_number} ({doc_type})",
            user_id=user.id if user else "system",
        ))
        logger.info("Document created: %s", doc_number)
        await db.commit()

    return RedirectResponse(url=f"/documents/{doc.id}?created=1", status_code=302)


@router.post("/documents/{doc_id}/edit", response_class=HTMLResponse)
async def document_update(request: Request, doc_id: str):
    user = request.state.user
    form = await request.form()

    async with async_session() as db:
        doc = await db.get(Document, doc_id)
        if not doc:
            return RedirectResponse(url="/documents", status_code=302)

        client_id = form.get("client_id", doc.client_id)
        issue_date = form.get("issue_date", "")
        due_date = form.get("due_date", "")
        valid_until = form.get("valid_until", "")
        payment_terms = form.get("payment_terms", doc.payment_terms)
        vat_mode = form.get("vat_mode", doc.vat_mode)
        client_notes = form.get("client_notes", "")
        internal_notes = form.get("internal_notes", "")
        terms_and_conditions = form.get("terms_and_conditions", "")

        try:
            discount_amount = float(form.get("discount_amount", 0) or 0)
        except (ValueError, TypeError):
            discount_amount = 0.0

        line_items_data = parse_line_items(dict(form))

        if not client_id or not issue_date:
            result = await db.execute(select(Client).where(Client.is_active == True).order_by(Client.company_name))
            clients = list(result.scalars().all())
            li_result = await db.execute(
                select(DocumentLineItem).where(DocumentLineItem.document_id == doc_id).order_by(DocumentLineItem.sort_order)
            )
            line_items = list(li_result.scalars().all())
            settings = await db.get(CompanySettings, app_settings.settings_id)
            svc_result = await db.execute(select(ServiceItem).where(ServiceItem.is_active == True).order_by(ServiceItem.name))
            services = list(svc_result.scalars().all())
            return templates.TemplateResponse(request, "documents/form.html", {
                "request": request,
                "user": user,
                "document": doc,
                "clients": clients,
                "services": services,
                "services_json": serialize_services(services),
                "doc_type": doc.type,
                "line_items": line_items,
                "settings": settings,
                "edit_mode": True,
                "today": date.today().isoformat(),
                "error": "Client and issue date are required.",
            })

        settings = await db.get(CompanySettings, app_settings.settings_id)
        vat_rate = settings.default_vat_rate if settings else 15.0

        subtotal, vat_amount, grand_total = calculate_totals(line_items_data, vat_mode, discount_amount, vat_rate)

        doc.client_id = client_id
        doc.issue_date = date.fromisoformat(issue_date)
        doc.due_date = date.fromisoformat(due_date) if due_date else None
        doc.valid_until = date.fromisoformat(valid_until) if valid_until else None
        doc.payment_terms = payment_terms
        doc.vat_mode = vat_mode
        doc.vat_rate = vat_rate
        doc.subtotal = subtotal
        doc.vat_amount = vat_amount
        doc.discount_amount = discount_amount
        doc.grand_total = grand_total
        doc.client_notes = client_notes
        doc.internal_notes = internal_notes
        doc.terms_and_conditions = terms_and_conditions

        company_details = None
        if settings:
            company_details = json.dumps({
                "company_name": settings.company_name,
                "trading_as": settings.trading_as,
                "registration_number": settings.registration_number,
                "vat_number": settings.vat_number,
                "email": settings.email,
                "phone": settings.phone,
                "whatsapp": settings.whatsapp,
                "website": settings.website,
                "address": settings.address,
                "city": settings.city,
                "postal_code": settings.postal_code,
                "country": settings.country,
                "bank_name": settings.bank_name,
                "bank_account_name": settings.bank_account_name,
                "bank_account": settings.bank_account,
                "bank_branch": settings.bank_branch,
                "bank_swift": settings.bank_swift,
                "logo_url": settings.logo_url,
            })
        doc.company_details = company_details

        old_items = await db.execute(
            select(DocumentLineItem).where(DocumentLineItem.document_id == doc_id)
        )
        for li in old_items.scalars().all():
            await db.delete(li)
        await db.flush()

        for idx, li in enumerate(line_items_data):
            db.add(DocumentLineItem(
                id=gen_id(),
                document_id=doc.id,
                sort_order=idx,
                service=li["service"],
                description=li["description"],
                quantity=li["quantity"],
                unit_price=li["unit_price"],
                discount=li["discount"],
                line_total=li["line_total"],
                vat_rate=vat_rate,
                vat_mode=vat_mode,
            ))

        ver_result = await db.execute(
            select(func.max(DocumentVersion.version_number)).where(DocumentVersion.document_id == doc_id)
        )
        max_ver = ver_result.scalar() or 0

        db.add(DocumentVersion(
            id=gen_id(),
            document_id=doc.id,
            version_number=max_ver + 1,
            snapshot=json.dumps({
                "line_items": line_items_data,
                "grand_total": grand_total,
                "vat_mode": vat_mode,
            }),
            change_summary=f"Document updated (v{max_ver + 1})",
            created_by=user.id if user else "system",
        ))

        db.add(ActivityLog(
            action="updated", entity_type="document", entity_id=doc.id,
            description=f"Updated {doc.document_number}",
            user_id=user.id if user else "system",
        ))
        logger.info("Document updated: %s", doc.document_number)
        await db.commit()

    return RedirectResponse(url=f"/documents/{doc.id}?saved=1", status_code=302)


@router.post("/documents/{doc_id}/status")
async def document_update_status(request: Request, doc_id: str, status: str = Form(...)):
    user = request.state.user
    async with async_session() as db:
        doc = await db.get(Document, doc_id)
        if not doc:
            return RedirectResponse(url="/documents", status_code=302)

        allowed = VALID_TRANSITIONS.get(doc.status, [])
        if status not in allowed:
            return RedirectResponse(url=f"/documents/{doc_id}", status_code=302)

        doc.status = status
        if status == "paid":
            doc.paid_date = date.today()
            if doc.type == "invoice":
                doc.type = "paid_invoice"

        db.add(ActivityLog(
            action=status, entity_type="document", entity_id=doc_id,
            description=f"Updated {doc.document_number} to {status}",
            user_id=user.id if user else "system",
        ))
        logger.info("Document %s status changed to %s", doc.document_number, status)
        await db.commit()

    return RedirectResponse(url=f"/documents/{doc_id}?saved=1", status_code=302)


@router.post("/documents/{doc_id}/duplicate")
async def document_duplicate(request: Request, doc_id: str):
    user = request.state.user
    async with async_session() as db:
        original = await db.get(Document, doc_id)
        if not original:
            return RedirectResponse(url="/documents", status_code=302)

        settings = await db.get(CompanySettings, app_settings.settings_id)
        vat_rate = settings.default_vat_rate if settings else 15.0

        doc_number = await generate_doc_number(db, original.type)
        new_doc = Document(
            id=gen_id(),
            document_number=doc_number,
            type=original.type,
            status="draft",
            client_id=original.client_id,
            issue_date=date.today(),
            due_date=original.due_date,
            valid_until=original.valid_until,
            payment_terms=original.payment_terms,
            vat_mode=original.vat_mode,
            vat_rate=vat_rate,
            subtotal=original.subtotal,
            vat_amount=original.vat_amount,
            discount_amount=original.discount_amount,
            grand_total=original.grand_total,
            client_notes=original.client_notes,
            internal_notes=original.internal_notes,
            terms_and_conditions=original.terms_and_conditions,
            company_details=original.company_details,
        )
        db.add(new_doc)
        await db.flush()

        orig_items = await db.execute(
            select(DocumentLineItem).where(DocumentLineItem.document_id == doc_id).order_by(DocumentLineItem.sort_order)
        )
        for idx, orig_li in enumerate(orig_items.scalars().all()):
            db.add(DocumentLineItem(
                id=gen_id(),
                document_id=new_doc.id,
                sort_order=idx,
                service=orig_li.service,
                description=orig_li.description,
                quantity=orig_li.quantity,
                unit_price=orig_li.unit_price,
                discount=orig_li.discount,
                line_total=orig_li.line_total,
                vat_rate=orig_li.vat_rate,
                vat_mode=orig_li.vat_mode,
            ))

        db.add(ActivityLog(
            action="duplicated", entity_type="document", entity_id=new_doc.id,
            description=f"Duplicated {original.document_number} as {doc_number}",
            user_id=user.id if user else "system",
        ))
        logger.info("Document duplicated: %s -> %s", original.document_number, doc_number)
        await db.commit()

    return RedirectResponse(url=f"/documents/{new_doc.id}/edit?created=1", status_code=302)


@router.post("/documents/{doc_id}/convert")
async def document_convert(request: Request, doc_id: str, target_type: str = Form(...)):
    user = request.state.user
    conversion_map = {
        ("quote", "invoice"): {"status": "draft"},
        ("invoice", "paid_invoice"): {"status": "paid", "paid_date": date.today()},
        ("paid_invoice", "receipt"): {"status": "draft"},
    }

    async with async_session() as db:
        doc = await db.get(Document, doc_id)
        if not doc:
            return RedirectResponse(url="/documents", status_code=302)

        key = (doc.type, target_type)
        if key not in conversion_map:
            return RedirectResponse(url=f"/documents/{doc_id}", status_code=302)

        updates = conversion_map[key]
        doc.type = target_type
        doc.status = updates.get("status", doc.status)
        if "paid_date" in updates:
            doc.paid_date = updates["paid_date"]
        doc.parent_document_id = doc_id

        doc_number = await generate_doc_number(db, target_type)
        old_number = doc.document_number
        doc.document_number = doc_number

        db.add(ActivityLog(
            action="converted", entity_type="document", entity_id=doc_id,
            description=f"Converted {old_number} ({key[0]}) to {doc_number} ({target_type})",
            user_id=user.id if user else "system",
        ))
        logger.info("Document converted: %s -> %s", old_number, doc_number)
        await db.commit()

    return RedirectResponse(url=f"/documents/{doc_id}?saved=1", status_code=302)


@router.post("/documents/{doc_id}/delete")
async def document_delete(request: Request, doc_id: str):
    user = request.state.user
    async with async_session() as db:
        doc = await db.get(Document, doc_id)
        if doc:
            result = await db.execute(
                select(DocumentLineItem).where(DocumentLineItem.document_id == doc_id)
            )
            for li in result.scalars().all():
                await db.delete(li)
            db.add(ActivityLog(
                action="deleted", entity_type="document", entity_id=doc_id,
                description=f"Deleted {doc.document_number}",
                user_id=user.id if user else "system",
            ))
            logger.info("Document deleted: %s", doc.document_number)
            await db.delete(doc)
            await db.commit()

    return RedirectResponse(url="/documents?deleted=1", status_code=302)


@router.post("/documents/bulk-status")
async def document_bulk_status(request: Request):
    user = request.state.user
    form = await request.form()
    status = form.get("status", "")
    doc_ids = form.getlist("doc_ids")

    if status not in ("sent", "cancelled", "draft", "paid", "accepted", "rejected"):
        return RedirectResponse(url="/documents", status_code=302)

    async with async_session() as db:
        for doc_id in doc_ids:
            doc = await db.get(Document, doc_id)
            if doc:
                old_status = doc.status
                doc.status = status
                if status == "paid":
                    doc.paid_date = date.today()
                    if doc.type == "invoice":
                        doc.type = "paid_invoice"
                db.add(ActivityLog(
                    action="bulk_status", entity_type="document", entity_id=doc_id,
                    description=f"Changed {doc.document_number} from {old_status} to {status}",
                    user_id=user.id if user else "system",
                ))
                logger.info("Bulk status: %s -> %s for %s", old_status, status, doc.document_number)
        await db.commit()

    return RedirectResponse(url="/documents?saved=1", status_code=302)
