import logging
import json
import os
from datetime import datetime, timezone
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from sqlalchemy import select, func, text
from sqlalchemy.orm import selectinload
from database import async_session, db_path, BACKUP_DIR
from models import Document, Client, ServiceItem, CompanySettings, ActivityLog, Payment

router = APIRouter(prefix="/api", tags=["api"])
logger = logging.getLogger("alunamda.api")


def serialize_doc(doc, client=None, payments=None):
    return {
        "id": doc.id,
        "document_number": doc.document_number,
        "type": doc.type,
        "status": doc.status,
        "client_id": doc.client_id,
        "client_name": client.company_name if client else None,
        "issue_date": doc.issue_date.isoformat() if doc.issue_date else None,
        "due_date": doc.due_date.isoformat() if doc.due_date else None,
        "subtotal": doc.subtotal,
        "vat_amount": doc.vat_amount,
        "discount_amount": doc.discount_amount,
        "grand_total": doc.grand_total,
        "vat_mode": doc.vat_mode,
        "payments_total": sum(p.amount for p in (payments or [])),
        "balance_due": doc.grand_total - sum(p.amount for p in (payments or [])),
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
    }


@router.get("/documents")
async def api_documents(
    type: str = Query("", alias="type"),
    status: str = Query(""),
    search: str = Query(""),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
):
    async with async_session() as db:
        query = select(Document)
        count_query = select(func.count(Document.id))

        if type:
            query = query.where(Document.type == type)
            count_query = count_query.where(Document.type == type)
        if status:
            query = query.where(Document.status == status)
            count_query = count_query.where(Document.status == status)
        if search:
            query = query.where(Document.document_number.ilike(f"%{search}%"))
            count_query = count_query.where(Document.document_number.ilike(f"%{search}%"))

        total = (await db.execute(count_query)).scalar() or 0
        offset = (page - 1) * per_page
        query = query.options(
            selectinload(Document.client),
            selectinload(Document.payments),
        ).order_by(Document.created_at.desc()).offset(offset).limit(per_page)
        result = await db.execute(query)
        docs = list(result.scalars().all())

        data = []
        for doc in docs:
            data.append(serialize_doc(doc, doc.client, list(doc.payments)))

    return {
        "data": data,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "pages": (total + per_page - 1) // per_page,
        }
    }


@router.get("/documents/{doc_id}")
async def api_document_detail(doc_id: str):
    async with async_session() as db:
        result = await db.execute(
            select(Document).options(
                selectinload(Document.client),
                selectinload(Document.payments),
            ).where(Document.id == doc_id)
        )
        doc = result.scalar_one_or_none()
        if not doc:
            return JSONResponse({"error": "Document not found"}, status_code=404)

    return serialize_doc(doc, doc.client, list(doc.payments))


@router.get("/clients")
async def api_clients(
    search: str = Query(""),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
):
    async with async_session() as db:
        query = select(Client).where(Client.is_active == True)
        count_query = select(func.count(Client.id)).where(Client.is_active == True)

        if search:
            query = query.where(Client.company_name.ilike(f"%{search}%"))
            count_query = count_query.where(Client.company_name.ilike(f"%{search}%"))

        total = (await db.execute(count_query)).scalar() or 0
        offset = (page - 1) * per_page
        query = query.order_by(Client.company_name).offset(offset).limit(per_page)
        result = await db.execute(query)
        clients = list(result.scalars().all())

    return {
        "data": [
            {
                "id": c.id,
                "company_name": c.company_name,
                "contact_name": c.contact_name,
                "email": c.email,
                "phone": c.phone,
                "vat_number": c.vat_number,
            }
            for c in clients
        ],
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "pages": (total + per_page - 1) // per_page,
        }
    }


@router.get("/services")
async def api_services(
    category: str = Query(""),
    search: str = Query(""),
):
    async with async_session() as db:
        query = select(ServiceItem).where(ServiceItem.is_active == True)
        if category:
            query = query.where(ServiceItem.category == category)
        if search:
            query = query.where(ServiceItem.name.ilike(f"%{search}%"))
        query = query.order_by(ServiceItem.name)
        result = await db.execute(query)
        services = list(result.scalars().all())

    return {
        "data": [
            {
                "id": s.id,
                "name": s.name,
                "description": s.description,
                "unit_price": s.unit_price,
                "vat_rate": s.vat_rate,
                "category": s.category,
            }
            for s in services
        ]
    }


@router.get("/dashboard/stats")
async def api_dashboard_stats():
    async with async_session() as db:
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
        total_docs = await db.scalar(select(func.count()).select_from(Document)) or 0

    return {
        "total_paid": total_paid,
        "outstanding": outstanding,
        "total_clients": total_clients,
        "total_documents": total_docs,
    }


@router.get("/activity")
async def api_activity(limit: int = Query(50, ge=1, le=200)):
    async with async_session() as db:
        result = await db.execute(
            select(ActivityLog).order_by(ActivityLog.created_at.desc()).limit(limit)
        )
        activities = list(result.scalars().all())

    return {
        "data": [
            {
                "id": a.id,
                "action": a.action,
                "entity_type": a.entity_type,
                "entity_id": a.entity_id,
                "description": a.description,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in activities
        ]
    }


@router.get("/health")
async def api_health():
    try:
        async with async_session() as db:
            result = await db.execute(text("PRAGMA integrity_check"))
            integrity = result.scalar()

            result = await db.execute(text("PRAGMA journal_mode"))
            journal_mode = result.scalar()

            result = await db.execute(text("SELECT COUNT(*) FROM sqlite_master WHERE type='table'"))
            table_count = result.scalar()

        db_size = os.path.getsize(db_path) if db_path.exists() else 0

        backups = []
        if BACKUP_DIR.exists():
            for f in sorted(BACKUP_DIR.glob("alunamda_*.db"), key=os.path.getmtime, reverse=True)[:5]:
                backups.append({
                    "filename": f.name,
                    "size_bytes": os.path.getsize(f),
                    "created_at": datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc).isoformat(),
                })

        return {
            "status": "healthy" if integrity == "ok" else "degraded",
            "database": {
                "integrity": integrity,
                "journal_mode": journal_mode,
                "table_count": table_count,
                "size_bytes": db_size,
                "size_mb": round(db_size / (1024 * 1024), 2),
            },
            "backups": {
                "count": len(backups),
                "latest": backups[0] if backups else None,
                "recent": backups,
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.exception("Health check failed")
        return JSONResponse(
            {"status": "unhealthy", "error": str(e)},
            status_code=503,
        )
