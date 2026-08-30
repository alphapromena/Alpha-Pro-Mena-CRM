"""
Global search router — searching contacts, companies, opportunities across multiple fields.
"""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.contact import Contact
from app.models.company import Company
from app.models.opportunity import Opportunity
from app.models.user import User

router = APIRouter(prefix="/search", tags=["Global Search"])


@router.get("")
async def global_search(
    q: str = Query(..., min_length=1, max_length=100),
    entity_type: Optional[str] = Query(None), # contacts, companies, opportunities or all
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query_str = f"%{q.strip()}%"
    results = {
        "contacts": [],
        "companies": [],
        "opportunities": [],
    }

    # 1. Search Contacts
    if not entity_type or entity_type == "contacts":
        c_stmt = (
            select(Contact)
            .where(
                Contact.deleted_at.is_(None),
                or_(
                    Contact.first_name.ilike(query_str),
                    Contact.last_name.ilike(query_str),
                    Contact.email.ilike(query_str),
                    Contact.phone.ilike(query_str),
                    Contact.position.ilike(query_str),
                    Contact.country.ilike(query_str),
                    Contact.industry.ilike(query_str),
                ),
            )
            .options(selectinload(Contact.company), selectinload(Contact.owner))
            .limit(10)
        )
        if not current_user.is_manager_or_above:
            if current_user.is_team_leader_or_above:
                c_stmt = c_stmt.where(or_(Contact.owner_id == current_user.id, Contact.team_id == current_user.team_id))
            else:
                c_stmt = c_stmt.where(Contact.owner_id == current_user.id)

        contacts = (await db.execute(c_stmt)).scalars().all()
        results["contacts"] = [
            {
                "id": str(c.id),
                "full_name": c.full_name,
                "email": c.email,
                "phone": c.phone,
                "position": c.position,
                "company_name": c.company.name if c.company else None,
                "status": c.status,
                "owner_name": c.owner.full_name if c.owner else None,
            }
            for c in contacts
        ]

    # 2. Search Companies
    if not entity_type or entity_type == "companies":
        comp_stmt = (
            select(Company)
            .where(
                Company.deleted_at.is_(None),
                or_(
                    Company.name.ilike(query_str),
                    Company.domain.ilike(query_str),
                    Company.country.ilike(query_str),
                    Company.industry.ilike(query_str),
                ),
            )
            .limit(10)
        )
        companies = (await db.execute(comp_stmt)).scalars().all()
        results["companies"] = [
            {
                "id": str(c.id),
                "name": c.name,
                "domain": c.domain,
                "country": c.country,
                "industry": c.industry,
                "status": c.status,
            }
            for c in companies
        ]

    # 3. Search Opportunities
    if not entity_type or entity_type == "opportunities":
        opp_stmt = (
            select(Opportunity)
            .where(
                Opportunity.deleted_at.is_(None),
                Opportunity.title.ilike(query_str),
            )
            .options(selectinload(Opportunity.company))
            .limit(10)
        )
        if not current_user.is_manager_or_above:
            opp_stmt = opp_stmt.where(Opportunity.owner_id == current_user.id)

        opps = (await db.execute(opp_stmt)).scalars().all()
        results["opportunities"] = [
            {
                "id": str(o.id),
                "title": o.title,
                "value": o.value,
                "stage": o.stage,
                "company_name": o.company.name if o.company else None,
            }
            for o in opps
        ]

    return {"data": results, "query": q}
