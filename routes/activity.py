import logging
from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse
from sqlalchemy import select, func
from database import async_session
from models import ActivityLog
from config import get_settings
from app_templates import templates

router = APIRouter()
logger = logging.getLogger("alunamda.activity")
app_settings = get_settings()


@router.get("/activity", response_class=HTMLResponse)
async def activity_log(
    request: Request,
    search: str = "",
    action_filter: str = "",
    page: int = Query(1, ge=1),
):
    user = request.state.user
    per_page = app_settings.activity_per_page
    async with async_session() as db:
        query = select(ActivityLog)
        count_query = select(func.count(ActivityLog.id))

        if search:
            query = query.where(ActivityLog.description.ilike(f"%{search}%"))
            count_query = count_query.where(ActivityLog.description.ilike(f"%{search}%"))
        if action_filter:
            query = query.where(ActivityLog.action == action_filter)
            count_query = count_query.where(ActivityLog.action == action_filter)

        total = (await db.execute(count_query)).scalar() or 0
        total_pages = max(1, (total + per_page - 1) // per_page)

        result = await db.execute(
            query.order_by(ActivityLog.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        activities = list(result.scalars().all())

        actions_result = await db.execute(
            select(ActivityLog.action).distinct()
        )
        available_actions = sorted([r[0] for r in actions_result.all()])

    return templates.TemplateResponse(request, "activity.html", {
        "request": request,
        "user": user,
        "activities": activities,
        "search_query": search,
        "action_filter": action_filter,
        "available_actions": available_actions,
        "current_page": page,
        "total_pages": total_pages,
        "total_items": total,
    })
