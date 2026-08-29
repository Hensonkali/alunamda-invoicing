import logging
from datetime import date
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy import select, func
from database import async_session
from models import Document, Payment, ActivityLog, gen_id
from app_templates import templates

router = APIRouter()
logger = logging.getLogger("alunamda.payments")


@router.get("/documents/{doc_id}/payments", response_class=HTMLResponse)
async def payment_list(request: Request, doc_id: str):
    user = request.state.user
    async with async_session() as db:
        doc = await db.get(Document, doc_id)
        if not doc:
            return RedirectResponse(url="/documents", status_code=302)
        result = await db.execute(
            select(Payment).where(Payment.document_id == doc_id).order_by(Payment.payment_date.desc())
        )
        payments = list(result.scalars().all())
        total_paid = sum(p.amount for p in payments)
        balance = doc.grand_total - total_paid

    return templates.TemplateResponse(request, "payments/list.html", {
        "request": request,
        "user": user,
        "document": doc,
        "payments": payments,
        "total_paid": total_paid,
        "balance": balance,
    })


@router.post("/documents/{doc_id}/payments")
async def payment_create(
    request: Request, doc_id: str,
    amount: float = Form(...),
    payment_date: str = Form(...),
    payment_method: str = Form(""),
    reference: str = Form(""),
    notes: str = Form(""),
):
    user = request.state.user
    async with async_session() as db:
        doc = await db.get(Document, doc_id)
        if not doc:
            return RedirectResponse(url="/documents", status_code=302)

        existing = await db.execute(
            select(func.coalesce(func.sum(Payment.amount), 0.0)).where(Payment.document_id == doc_id)
        )
        total_paid = existing.scalar() or 0.0

        if amount <= 0:
            return RedirectResponse(url=f"/documents/{doc_id}/payments", status_code=302)

        payment = Payment(
            id=gen_id(),
            document_id=doc_id,
            amount=amount,
            payment_date=date.fromisoformat(payment_date),
            payment_method=payment_method,
            reference=reference,
            notes=notes,
        )
        db.add(payment)
        logger.info("Payment of R%.2f recorded for %s", amount, doc.document_number)

        new_total = total_paid + amount
        if new_total >= doc.grand_total:
            doc.status = "paid"
            doc.paid_date = date.fromisoformat(payment_date)
            if doc.type == "invoice":
                doc.type = "paid_invoice"
            logger.info("Document %s marked as paid", doc.document_number)

        db.add(ActivityLog(
            action="payment_recorded", entity_type="document", entity_id=doc_id,
            description=f"Recorded payment of R{amount:,.2f} for {doc.document_number}",
            user_id=user.id if user else "system",
        ))
        await db.commit()

    return RedirectResponse(url=f"/documents/{doc_id}/payments", status_code=302)


@router.post("/payments/{payment_id}/delete")
async def payment_delete(request: Request, payment_id: str):
    user = request.state.user
    doc_id = ""
    async with async_session() as db:
        payment = await db.get(Payment, payment_id)
        if payment:
            doc_id = payment.document_id
            doc = await db.get(Document, doc_id)
            if doc:
                remaining = await db.execute(
                    select(func.coalesce(func.sum(Payment.amount), 0.0))
                    .where(Payment.document_id == doc_id)
                    .where(Payment.id != payment_id)
                )
                new_total = remaining.scalar() or 0.0
                if new_total < doc.grand_total and doc.status == "paid":
                    doc.status = "sent"
                    doc.paid_date = None
                    if doc.type == "paid_invoice":
                        doc.type = "invoice"

            db.add(ActivityLog(
                action="payment_deleted", entity_type="document", entity_id=doc_id,
                description=f"Deleted payment of R{payment.amount:,.2f}",
                user_id=user.id if user else "system",
            ))
            await db.delete(payment)
            await db.commit()

    if doc_id:
        return RedirectResponse(url=f"/documents/{doc_id}/payments", status_code=302)
    return RedirectResponse(url="/documents", status_code=302)
