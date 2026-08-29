import logging
import secrets
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse
from contextlib import asynccontextmanager
from database import init_db, dispose_engine
from config import get_settings, logger
from auth import get_current_user, COOKIE_NAME, CSRF_TOKEN_NAME, generate_csrf_token
from app_templates import templates

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting ALUNAMDA Invoicing v%s", settings.app_version)
    await init_db()
    logger.info("Database initialized with WAL mode and integrity checks")
    yield
    await dispose_engine()
    logger.info("Shutting down")


app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    path = request.url.path
    public_paths = {"/", "/login", "/logout", "/api/health"}
    static_prefixes = ("/static/", "/portal")

    is_public = path in public_paths or any(path.startswith(p) for p in static_prefixes)

    if not is_public:
        user = await get_current_user(request)
        if not user:
            if path.startswith("/api/"):
                return JSONResponse({"error": "Unauthorized"}, status_code=401)
            return RedirectResponse(url="/login", status_code=302)
        request.state.user = user
    else:
        request.state.user = None

    response = await call_next(request)

    # Ensure CSRF cookie is set for form pages
    if not request.cookies.get(CSRF_TOKEN_NAME):
        csrf_token = generate_csrf_token()
        response.set_cookie(CSRF_TOKEN_NAME, csrf_token, httponly=False, samesite="strict", max_age=3600)

    return response


@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    if request.url.path.startswith("/api/"):
        return JSONResponse({"error": "Not found"}, status_code=404)
    return templates.TemplateResponse(request, "errors/404.html", {"request": request}, status_code=404)


@app.exception_handler(401)
async def unauthorized_handler(request: Request, exc):
    if request.url.path.startswith("/api/"):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    return templates.TemplateResponse(request, "errors/401.html", {"request": request}, status_code=401)


@app.exception_handler(403)
async def forbidden_handler(request: Request, exc):
    if request.url.path.startswith("/api/"):
        return JSONResponse({"error": "Forbidden"}, status_code=403)
    return templates.TemplateResponse(request, "errors/403.html", {"request": request}, status_code=403)


@app.exception_handler(500)
async def server_error_handler(request: Request, exc):
    logger.exception("Internal server error on %s", request.url.path)
    if request.url.path.startswith("/api/"):
        return JSONResponse({"error": "Internal server error"}, status_code=500)
    return templates.TemplateResponse(request, "errors/500.html", {"request": request}, status_code=500)


@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s: %s", request.url.path, exc)
    if request.url.path.startswith("/api/"):
        return JSONResponse({"error": str(exc)}, status_code=500)
    return templates.TemplateResponse(request, "errors/500.html", {"request": request}, status_code=500)


@app.get("/", response_class=RedirectResponse)
async def root():
    return RedirectResponse(url="/dashboard", status_code=302)


from routes.auth import router as auth_router
from routes.dashboard import router as dashboard_router
from routes.documents import router as documents_router
from routes.clients import router as clients_router
from routes.services import router as services_router
from routes.activity import router as activity_router
from routes.settings import router as settings_router
from routes.pdf import router as pdf_router
from routes.api import router as api_router
from routes.payments import router as payments_router
from routes.attachments import router as attachments_router
from routes.recurring import router as recurring_router
from routes.client_portal import router as client_portal_router

app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(documents_router)
app.include_router(clients_router)
app.include_router(services_router)
app.include_router(activity_router)
app.include_router(settings_router)
app.include_router(pdf_router)
app.include_router(api_router)
app.include_router(payments_router)
app.include_router(attachments_router)
app.include_router(recurring_router)
app.include_router(client_portal_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=1111, reload=True)
