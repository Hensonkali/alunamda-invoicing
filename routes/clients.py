from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from database import async_session
from models import Client, Document, ActivityLog, gen_id
from config import get_settings
from app_templates import templates
import logging

router = APIRouter()
logger = logging.getLogger("alunamda.clients")
app_settings = get_settings()


@router.get("/clients", response_class=HTMLResponse)
async def clients_list(request: Request):
    user = request.state.user
    async with async_session() as db:
        result = await db.execute(select(Client).order_by(Client.company_name))
        clients = list(result.scalars().all())

        client_ids = [c.id for c in clients]
        doc_counts = {}
        outstanding_map = {}

        if client_ids:
            count_result = await db.execute(
                select(Document.client_id, func.count(Document.id))
                .where(Document.client_id.in_(client_ids))
                .group_by(Document.client_id)
            )
            for cid, cnt in count_result.all():
                doc_counts[cid] = cnt

            outstanding_result = await db.execute(
                select(Document.client_id, func.coalesce(func.sum(Document.grand_total), 0.0))
                .where(Document.client_id.in_(client_ids))
                .where(Document.status.in_(["sent", "overdue"]))
                .group_by(Document.client_id)
            )
            for cid, amt in outstanding_result.all():
                outstanding_map[cid] = amt

        client_stats = {}
        for client in clients:
            client_stats[client.id] = {
                "doc_count": doc_counts.get(client.id, 0),
                "outstanding": outstanding_map.get(client.id, 0.0),
            }

    return templates.TemplateResponse(request, "clients/list.html", {
        "request": request,
        "user": user, "clients": clients, "client_stats": client_stats,
    })


@router.get("/clients/{client_id}", response_class=HTMLResponse)
async def client_detail(request: Request, client_id: str):
    user = request.state.user
    async with async_session() as db:
        client = await db.get(Client, client_id)
        if not client:
            return RedirectResponse(url="/clients", status_code=302)
        result = await db.execute(
            select(Document).where(Document.client_id == client_id).order_by(Document.created_at.desc())
        )
        documents = list(result.scalars().all())

    return templates.TemplateResponse(request, "clients/detail.html", {
        "request": request,
        "user": user, "client": client, "documents": documents,
    })


@router.post("/clients", response_class=HTMLResponse)
async def client_create(
    request: Request,
    company_name: str = Form(...),
    contact_name: str = Form(""),
    email: str = Form(""),
    phone: str = Form(""),
    address: str = Form(""),
    city: str = Form(""),
    postal_code: str = Form(""),
    country: str = Form("South Africa"),
    vat_number: str = Form(""),
):
    user = request.state.user
    async with async_session() as db:
        client = Client(
            id=gen_id(), company_name=company_name, contact_name=contact_name,
            email=email, phone=phone, address=address, city=city,
            postal_code=postal_code, country=country, vat_number=vat_number,
        )
        db.add(client)
        logger.info("Client created: %s", company_name)
        await db.commit()

    return RedirectResponse(url="/clients?created=1", status_code=302)


@router.post("/clients/{client_id}/edit")
async def client_edit(
    request: Request, client_id: str,
    company_name: str = Form(...),
    contact_name: str = Form(""),
    email: str = Form(""),
    phone: str = Form(""),
    address: str = Form(""),
    city: str = Form(""),
    postal_code: str = Form(""),
    country: str = Form("South Africa"),
    vat_number: str = Form(""),
):
    user = request.state.user
    async with async_session() as db:
        client = await db.get(Client, client_id)
        if client:
            client.company_name = company_name
            client.contact_name = contact_name
            client.email = email
            client.phone = phone
            client.address = address
            client.city = city
            client.postal_code = postal_code
            client.country = country
            client.vat_number = vat_number
            logger.info("Client updated: %s", company_name)
            await db.commit()

    return RedirectResponse(url=f"/clients/{client_id}?saved=1", status_code=302)


@router.post("/clients/{client_id}/delete")
async def client_delete(request: Request, client_id: str):
    user = request.state.user
    async with async_session() as db:
        client = await db.get(Client, client_id)
        if client:
            result = await db.execute(
                select(Document).where(Document.client_id == client_id)
            )
            documents = list(result.scalars().all())
            for doc in documents:
                doc.client_id = ""

            db.add(ActivityLog(
                user_id=user.id if user else "system", action="deleted", entity_type="client",
                entity_id=client_id, description=f"Deleted client: {client.company_name}",
            ))
            logger.info("Client deleted: %s", client.company_name)
            await db.delete(client)
            await db.commit()

    return RedirectResponse(url="/clients?deleted=1", status_code=302)
