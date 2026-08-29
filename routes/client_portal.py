import logging
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from database import async_session
from models import Document, Client, DocumentLineItem
from app_templates import templates

router = APIRouter(prefix="/portal", tags=["client_portal"])
logger = logging.getLogger("alunamda.portal")


@router.get("/document/{doc_number}", response_class=HTMLResponse)
async def client_view_document(request: Request, doc_number: str):
    async with async_session() as db:
        result = await db.execute(
            select(Document).where(Document.document_number == doc_number)
        )
        doc = result.scalar_one_or_none()
        if not doc:
            return templates.TemplateResponse(request, "errors/404.html", {"request": request}, status_code=404)

        client = await db.get(Client, doc.client_id)
        li_result = await db.execute(
            select(DocumentLineItem).where(DocumentLineItem.document_id == doc.id).order_by(DocumentLineItem.sort_order)
        )
        line_items = list(li_result.scalars().all())

    return templates.TemplateResponse(request, "client_portal/document_view.html", {
        "request": request,
        "document": doc,
        "client": client,
        "line_items": line_items,
    })
