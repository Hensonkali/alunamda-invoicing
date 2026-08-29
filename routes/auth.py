from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from database import async_session
from models import User
from auth import verify_password, create_token, COOKIE_NAME, get_current_user
from app_templates import templates
import logging

router = APIRouter()
logger = logging.getLogger("alunamda.auth")


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    user = await get_current_user(request)
    if user:
        return RedirectResponse(url="/dashboard", status_code=302)
    return templates.TemplateResponse(request, "login.html", {"request": request, "error": None})


@router.post("/login")
async def login_submit(request: Request, email: str = Form(...), password: str = Form(...)):
    async with async_session() as db:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

    if not user or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(request, "login.html", {
            "request": request,
            "error": "Invalid email or password"
        })

    token = create_token(user.id)
    logger.info("User logged in: %s", email)
    response = RedirectResponse(url="/dashboard", status_code=302)
    response.set_cookie(COOKIE_NAME, token, httponly=True, samesite="lax", secure=False, max_age=172800)
    return response


@router.get("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie(COOKIE_NAME)
    return response
