from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from database import async_session
from models import CompanySettings
from config import get_settings
from app_templates import templates
import logging

router = APIRouter()
logger = logging.getLogger("alunamda.settings")
app_settings = get_settings()


async def _get_settings():
    async with async_session() as db:
        result = await db.execute(select(CompanySettings).where(CompanySettings.id == app_settings.settings_id))
        settings = result.scalar_one_or_none()
        if not settings:
            settings = CompanySettings(id=app_settings.settings_id)
            db.add(settings)
            await db.commit()
        return settings


async def _update_settings(updates: dict):
    async with async_session() as db:
        result = await db.execute(select(CompanySettings).where(CompanySettings.id == app_settings.settings_id))
        settings = result.scalar_one_or_none()
        if not settings:
            settings = CompanySettings(id=app_settings.settings_id)
            db.add(settings)

        for key, value in updates.items():
            if hasattr(settings, key):
                setattr(settings, key, value)

        logger.info("Settings updated: %s", ", ".join(updates.keys()))
        await db.commit()


@router.get("/settings")
async def settings_page(request: Request):
    user = request.state.user
    settings = await _get_settings()
    return templates.TemplateResponse(request, "settings.html", {"request": request, "user": user, "settings": settings})


@router.post("/settings/company")
async def update_company(
    request: Request,
    company_name: str = Form(...),
    trading_as: str = Form(""),
    registration_number: str = Form(""),
    vat_number: str = Form(""),
    email: str = Form(""),
    phone: str = Form(""),
    whatsapp: str = Form(""),
    website: str = Form(""),
    address: str = Form(""),
    city: str = Form(""),
    postal_code: str = Form(""),
    postal_address: str = Form(""),
):
    await _update_settings({
        "company_name": company_name, "trading_as": trading_as,
        "registration_number": registration_number, "vat_number": vat_number,
        "email": email, "phone": phone, "whatsapp": whatsapp, "website": website,
        "address": address, "city": city, "postal_code": postal_code,
        "postal_address": postal_address,
    })
    return RedirectResponse("/settings?saved=1", status_code=302)


@router.post("/settings/bank")
async def update_bank(
    request: Request,
    bank_name: str = Form(""),
    bank_account_name: str = Form(""),
    bank_account: str = Form(""),
    bank_branch: str = Form(""),
    bank_swift: str = Form(""),
):
    await _update_settings({
        "bank_name": bank_name, "bank_account_name": bank_account_name,
        "bank_account": bank_account, "bank_branch": bank_branch,
        "bank_swift": bank_swift,
    })
    return RedirectResponse("/settings?saved=1", status_code=302)


@router.post("/settings/branding")
async def update_branding(
    request: Request,
    primary_color: str = Form("#002060"),
    secondary_color: str = Form("#C9A227"),
    footer_text: str = Form(""),
    signature: str = Form(""),
):
    await _update_settings({
        "primary_color": primary_color, "secondary_color": secondary_color,
        "footer_text": footer_text, "signature": signature,
    })
    return RedirectResponse("/settings?saved=1", status_code=302)


@router.post("/settings/defaults")
async def update_defaults(
    request: Request,
    default_vat_rate: float = Form(15.0),
    default_payment_terms: str = Form("30_days"),
    default_quote_validity: str = Form("30_days"),
):
    await _update_settings({
        "default_vat_rate": default_vat_rate,
        "default_payment_terms": default_payment_terms,
        "default_quote_validity": default_quote_validity,
    })
    return RedirectResponse("/settings?saved=1", status_code=302)


@router.post("/settings/notes")
async def update_notes(
    request: Request,
    default_notes: str = Form(""),
    default_terms: str = Form(""),
):
    await _update_settings({
        "default_notes": default_notes,
        "default_terms": default_terms,
    })
    return RedirectResponse("/settings?saved=1", status_code=302)
