from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from database import async_session
from models import ServiceItem, ActivityLog, gen_id
from app_templates import templates
import logging

router = APIRouter()
logger = logging.getLogger("alunamda.services")


@router.get("/services", response_class=HTMLResponse)
async def services_list(request: Request):
    user = request.state.user
    category = request.query_params.get("category", "")
    search = request.query_params.get("search", "")

    async with async_session() as db:
        query = select(ServiceItem)
        if category:
            query = query.where(ServiceItem.category == category)
        if search:
            query = query.where(ServiceItem.name.ilike(f"%{search}%"))
        query = query.order_by(ServiceItem.category, ServiceItem.name)
        result = await db.execute(query)
        services = list(result.scalars().all())

    return templates.TemplateResponse(request, "services/list.html", {
        "request": request,
        "user": user, "services": services,
        "selected_category": category, "search_query": search,
    })


@router.post("/services", response_class=HTMLResponse)
async def service_create(
    request: Request,
    name: str = Form(...),
    description: str = Form(""),
    unit_price: float = Form(0.0),
    vat_rate: float = Form(15.0),
    category: str = Form("General"),
):
    user = request.state.user
    async with async_session() as db:
        svc = ServiceItem(id=gen_id(), name=name, description=description,
                          unit_price=unit_price, vat_rate=vat_rate, category=category)
        db.add(svc)
        logger.info("Service created: %s", name)
        await db.commit()

    return RedirectResponse(url="/services?created=1", status_code=302)


@router.get("/services/{svc_id}/edit", response_class=HTMLResponse)
async def service_edit_form(request: Request, svc_id: str):
    async with async_session() as db:
        svc = await db.get(ServiceItem, svc_id)
        if not svc:
            return HTMLResponse("<div>Service not found</div>", status_code=404)

    return templates.TemplateResponse(request, "services/edit_modal.html", {
        "request": request,
        "svc": svc,
    })


@router.post("/services/{svc_id}/edit")
async def service_edit(
    request: Request, svc_id: str,
    name: str = Form(...),
    description: str = Form(""),
    unit_price: float = Form(0.0),
    vat_rate: float = Form(15.0),
    category: str = Form("General"),
    is_active: bool = Form(True),
):
    user = request.state.user
    async with async_session() as db:
        svc = await db.get(ServiceItem, svc_id)
        if svc:
            svc.name = name
            svc.description = description
            svc.unit_price = unit_price
            svc.vat_rate = vat_rate
            svc.category = category
            svc.is_active = is_active
            db.add(ActivityLog(
                user_id=user.id if user else "system", action="updated", entity_type="service",
                entity_id=svc_id, description=f"Updated service: {name}",
            ))
            logger.info("Service updated: %s", name)
            await db.commit()

    return RedirectResponse(url="/services?saved=1", status_code=302)


@router.post("/services/{svc_id}/delete")
async def service_delete(request: Request, svc_id: str):
    user = request.state.user
    async with async_session() as db:
        svc = await db.get(ServiceItem, svc_id)
        if svc:
            db.add(ActivityLog(
                user_id=user.id if user else "system", action="deleted", entity_type="service",
                entity_id=svc_id, description=f"Deleted service: {svc.name}",
            ))
            logger.info("Service deleted: %s", svc.name)
            await db.delete(svc)
            await db.commit()

    return RedirectResponse(url="/services?deleted=1", status_code=302)


@router.post("/services/{svc_id}/toggle")
async def service_toggle(request: Request, svc_id: str):
    user = request.state.user
    async with async_session() as db:
        svc = await db.get(ServiceItem, svc_id)
        if svc:
            svc.is_active = not svc.is_active
            state = "activated" if svc.is_active else "deactivated"
            db.add(ActivityLog(
                user_id=user.id if user else "system", action="toggled", entity_type="service",
                entity_id=svc_id, description=f"{state.title()} service: {svc.name}",
            ))
            logger.info("Service toggled: %s -> %s", svc.name, state)
            await db.commit()

    return RedirectResponse(url="/services?saved=1", status_code=302)
