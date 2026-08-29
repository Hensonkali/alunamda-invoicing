import json
import logging
from datetime import date
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from database import async_session
from models import RecurringInvoice, Client, gen_id
from app_templates import templates

router = APIRouter()
logger = logging.getLogger("alunamda.recurring")


@router.get("/recurring", response_class=HTMLResponse)
async def recurring_list(request: Request):
    user = request.state.user
    async with async_session() as db:
        result = await db.execute(select(RecurringInvoice).order_by(RecurringInvoice.created_at.desc()))
        recurring = list(result.scalars().all())
        client_map = {}
        for r in recurring:
            if r.client_id not in client_map:
                client_map[r.client_id] = await db.get(Client, r.client_id)
        clients_result = await db.execute(select(Client).where(Client.is_active == True).order_by(Client.company_name))
        clients = list(clients_result.scalars().all())

    return templates.TemplateResponse(request, "recurring/list.html", {
        "request": request,
        "user": user,
        "recurring": recurring,
        "client_map": client_map,
        "clients": clients,
    })


@router.post("/recurring")
async def recurring_create(
    request: Request,
    client_id: str = Form(...),
    template_name: str = Form(...),
    frequency: str = Form("monthly"),
    day_of_month: int = Form(1),
    line_items_snapshot: str = Form("[]"),
    vat_mode: str = Form("exclusive"),
    payment_terms: str = Form("Due within 30 days"),
    notes: str = Form(""),
):
    user = request.state.user
    async with async_session() as db:
        rec = RecurringInvoice(
            id=gen_id(),
            client_id=client_id,
            template_name=template_name,
            frequency=frequency,
            day_of_month=day_of_month,
            is_active=True,
            next_run_date=_next_run_date(frequency, day_of_month),
            line_items_snapshot=line_items_snapshot,
            vat_mode=vat_mode,
            payment_terms=payment_terms,
            notes=notes,
        )
        db.add(rec)
        await db.commit()
        logger.info("Recurring invoice created: %s for client %s", template_name, client_id)

    return RedirectResponse(url="/recurring", status_code=302)


@router.post("/recurring/{rec_id}/toggle")
async def recurring_toggle(request: Request, rec_id: str):
    async with async_session() as db:
        rec = await db.get(RecurringInvoice, rec_id)
        if rec:
            rec.is_active = not rec.is_active
            rec.next_run_date = _next_run_date(rec.frequency, rec.day_of_month) if rec.is_active else None
            await db.commit()

    return RedirectResponse(url="/recurring", status_code=302)


@router.post("/recurring/{rec_id}/delete")
async def recurring_delete(request: Request, rec_id: str):
    async with async_session() as db:
        rec = await db.get(RecurringInvoice, rec_id)
        if rec:
            await db.delete(rec)
            await db.commit()

    return RedirectResponse(url="/recurring", status_code=302)


def _next_run_date(frequency: str, day_of_month: int) -> date:
    today = date.today()
    if frequency == "monthly":
        if today.day <= day_of_month:
            return date(today.year, today.month, min(day_of_month, 28))
        else:
            m = today.month + 1
            y = today.year
            if m > 12:
                m = 1
                y += 1
            return date(y, m, min(day_of_month, 28))
    elif frequency == "quarterly":
        m = today.month + 3
        y = today.year
        while m > 12:
            m -= 12
            y += 1
        return date(y, m, min(day_of_month, 28))
    elif frequency == "yearly":
        return date(today.year + 1, min(today.month, 12), min(day_of_month, 28))
    return date(today.year, today.month, min(day_of_month, 28))
