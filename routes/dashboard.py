from datetime import datetime, date
from calendar import month_abbr

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select, func, extract
from sqlalchemy.orm import selectinload
from database import async_session
from models import Document, Client, ActivityLog
from app_templates import templates

router = APIRouter()


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    user = request.state.user

    today = date.today()
    current_year = today.year
    current_month = today.month

    async with async_session() as db:
        total_quotes = await db.scalar(
            select(func.count()).select_from(Document).where(Document.type == "quote")
        ) or 0

        total_invoices = await db.scalar(
            select(func.count()).select_from(Document).where(
                Document.type.in_(["invoice", "paid_invoice"])
            )
        ) or 0

        total_paid = await db.scalar(
            select(func.sum(Document.grand_total)).where(Document.status == "paid")
        ) or 0

        outstanding = await db.scalar(
            select(func.sum(Document.grand_total)).where(
                Document.type.in_(["invoice", "paid_invoice"]),
                Document.status.notin_(["paid", "cancelled"])
            )
        ) or 0

        total_clients = await db.scalar(select(func.count()).select_from(Client)) or 0

        paid_this_month = await db.scalar(
            select(func.sum(Document.grand_total)).where(
                Document.status == "paid",
                extract("month", Document.paid_date) == current_month,
                extract("year", Document.paid_date) == current_year,
            )
        ) or 0

        result = await db.execute(
            select(Document)
            .options(selectinload(Document.client))
            .order_by(Document.created_at.desc())
            .limit(5)
        )
        recent_docs = list(result.scalars().all())

        result = await db.execute(
            select(ActivityLog).order_by(ActivityLog.created_at.desc()).limit(10)
        )
        activities = list(result.scalars().all())

        status_result = await db.execute(
            select(Document.status, func.count(Document.id)).group_by(Document.status)
        )
        docs_by_status = {s: c for s, c in status_result.all()}

        monthly_revenue = []
        for i in range(5, -1, -1):
            m = current_month - i
            y = current_year
            while m <= 0:
                m += 12
                y -= 1

            invoiced_amount = await db.scalar(
                select(func.sum(Document.grand_total)).where(
                    Document.type.in_(["invoice", "paid_invoice"]),
                    extract("month", Document.issue_date) == m,
                    extract("year", Document.issue_date) == y,
                )
            ) or 0

            paid_amount = await db.scalar(
                select(func.sum(Document.grand_total)).where(
                    Document.status == "paid",
                    extract("month", Document.paid_date) == m,
                    extract("year", Document.paid_date) == y,
                )
            ) or 0

            monthly_revenue.append({
                "month": month_abbr[m],
                "year": y,
                "invoiced": invoiced_amount,
                "paid": paid_amount,
            })

    return templates.TemplateResponse(request, "dashboard.html", {
        "request": request,
        "user": user,
        "total_quotes": total_quotes,
        "total_invoices": total_invoices,
        "total_paid": total_paid,
        "outstanding": outstanding,
        "total_clients": total_clients,
        "paid_this_month": paid_this_month,
        "recent_docs": recent_docs,
        "activities": activities,
        "docs_by_status": docs_by_status,
        "monthly_revenue": monthly_revenue,
    })
