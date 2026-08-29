import os
import logging
import uuid
from fastapi import APIRouter, Request, UploadFile, File
from fastapi.responses import RedirectResponse
from database import async_session
from models import Attachment, Document, ActivityLog, gen_id
from config import get_settings

router = APIRouter()
logger = logging.getLogger("alunamda.attachments")
settings = get_settings()

UPLOAD_DIR = "uploads"


@router.post("/documents/{doc_id}/attachments")
async def upload_attachment(request: Request, doc_id: str, file: UploadFile = File(...)):
    user = request.state.user
    if not os.path.exists(UPLOAD_DIR):
        os.makedirs(UPLOAD_DIR)

    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    content = await file.read()
    if len(content) > max_bytes:
        return RedirectResponse(url=f"/documents/{doc_id}?error=File+too+large", status_code=302)

    allowed_exts = settings.allowed_upload_extensions.split(",")
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext and ext not in allowed_exts:
        return RedirectResponse(url=f"/documents/{doc_id}?error=File+type+not+allowed", status_code=302)

    safe_name = f"{doc_id}_{uuid.uuid4().hex[:12]}{ext}"
    file_path = os.path.join(UPLOAD_DIR, safe_name)

    with open(file_path, "wb") as f:
        f.write(content)

    async with async_session() as db:
        attachment = Attachment(
            id=gen_id(),
            document_id=doc_id,
            filename=safe_name,
            original_filename=file.filename or "unnamed",
            file_size=len(content),
            content_type=file.content_type or "",
        )
        db.add(attachment)
        db.add(ActivityLog(
            action="attachment_added", entity_type="document", entity_id=doc_id,
            description=f"Uploaded file: {file.filename}",
            user_id=user.id if user else "system",
        ))
        await db.commit()
        logger.info("Attachment uploaded: %s (%d bytes)", file.filename, len(content))

    return RedirectResponse(url=f"/documents/{doc_id}", status_code=302)


@router.post("/attachments/{attachment_id}/delete")
async def delete_attachment(request: Request, attachment_id: str):
    user = request.state.user
    async with async_session() as db:
        att = await db.get(Attachment, attachment_id)
        if att:
            doc_id = att.document_id
            file_path = os.path.join(UPLOAD_DIR, att.filename)
            if os.path.exists(file_path):
                os.remove(file_path)
            db.add(ActivityLog(
                action="attachment_deleted", entity_type="document", entity_id=doc_id,
                description=f"Deleted file: {att.original_filename}",
                user_id=user.id if user else "system",
            ))
            await db.delete(att)
            await db.commit()
            logger.info("Attachment deleted: %s", att.original_filename)

    return RedirectResponse(url=f"/documents/{doc_id}", status_code=302)
