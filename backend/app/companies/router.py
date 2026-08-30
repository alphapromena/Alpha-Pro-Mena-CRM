"""
Companies (Accounts) router — full CRUD and related data.
"""
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from pydantic import BaseModel

from app.auth.dependencies import get_current_user, require_manager_or_above
from app.database import get_db
from app.models.company import Company
from app.models.contact import Contact
from app.models.opportunity import Opportunity
from app.models.user import User
from app.core.exceptions import NotFoundError, ForbiddenError
from app.audit.service import AuditService

router = APIRouter(prefix="/companies", tags=["Companies"])


class CompanyCreateBody(BaseModel):
    name: str
    domain: Optional[str] = None
    industry: Optional[str] = None
    country: Optional[str] = None
    website: Optional[str] = None
    address: Optional[str] = None
    account_owner_id: Optional[str] = None
    status: str = "ACTIVE"
    notes: Optional[str] = None
    tags: Optional[str] = None


class CompanyUpdateBody(BaseModel):
    name: Optional[str] = None
    domain: Optional[str] = None
    industry: Optional[str] = None
    country: Optional[str] = None
    website: Optional[str] = None
    address: Optional[str] = None
    account_owner_id: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None
    tags: Optional[str] = None


def _company_dict(c: Company) -> dict:
    return {
        "id": str(c.id),
        "name": c.name,
        "domain": c.domain,
        "industry": c.industry,
        "country": c.country,
        "website": c.website,
        "address": c.address,
        "account_owner_id": str(c.account_owner_id) if c.account_owner_id else None,
        "account_owner_name": c.account_owner.full_name if c.account_owner else None,
        "status": c.status,
        "notes": c.notes,
        "tags": c.tags,
        "created_at": c.created_at.isoformat(),
        "updated_at": c.updated_at.isoformat(),
    }


@router.get("")
async def list_companies(
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=500),
    search: Optional[str] = Query(None),
    industry: Optional[str] = Query(None),
    country: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    sort_by: str = Query("name"),
    sort_dir: str = Query("asc"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Company)
        .where(Company.deleted_at.is_(None))
        .options(
            selectinload(Company.account_owner),
            selectinload(Company.contacts),
        )
    )

    if search:
        q = f"%{search}%"
        stmt = stmt.where(
            or_(
                Company.name.ilike(q),
                Company.domain.ilike(q),
                Company.country.ilike(q),
                Company.industry.ilike(q),
                Company.contacts.any(
                    or_(
                        Contact.first_name.ilike(q),
                        Contact.last_name.ilike(q),
                        Contact.phone.ilike(q),
                        Contact.email.ilike(q),
                    )
                ),
            )
        )
    if industry:
        stmt = stmt.where(Company.industry.ilike(f"%{industry}%"))
    if country:
        stmt = stmt.where(Company.country.ilike(f"%{country}%"))
    if status:
        stmt = stmt.where(Company.status == status)

    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()

    # Alphabetical sorting (A-Z / أ-ي) or timestamp sorting
    col = getattr(Company, sort_by, Company.name)
    stmt = stmt.order_by(col.desc() if sort_dir == "desc" else col.asc())
    stmt = stmt.offset((page - 1) * per_page).limit(per_page)
    companies = (await db.execute(stmt)).scalars().all()

    company_list = []
    for c in companies:
        d = _company_dict(c)
        d["total_contacts"] = len([ct for ct in c.contacts if not ct.deleted_at])
        company_list.append(d)

    return {
        "data": company_list,
        "meta": {"total": total, "page": page, "per_page": per_page, "total_pages": -(-total // per_page)},
    }


@router.post("", status_code=201)
async def create_company(
    body: CompanyCreateBody,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    owner_id = uuid.UUID(body.account_owner_id) if body.account_owner_id else current_user.id
    company = Company(
        name=body.name,
        domain=body.domain,
        industry=body.industry,
        country=body.country,
        website=body.website,
        address=body.address,
        account_owner_id=owner_id,
        status=body.status,
        notes=body.notes,
        tags=body.tags,
    )
    db.add(company)
    await db.flush()

    audit = AuditService(db)
    await audit.log(
        action="company.created",
        entity_type="company",
        actor_id=current_user.id,
        entity_id=company.id,
        new_value={"name": company.name, "domain": company.domain},
    )

    return {"data": _company_dict(company)}


@router.get("/{company_id}")
async def get_company(
    company_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Company)
        .where(Company.id == company_id, Company.deleted_at.is_(None))
        .options(
            selectinload(Company.account_owner),
            selectinload(Company.contacts).selectinload(Contact.owner),
            selectinload(Company.opportunities),
        )
    )
    company = (await db.execute(stmt)).scalar_one_or_none()
    if not company:
        raise NotFoundError("Company not found.")

    res = _company_dict(company)
    res["contacts"] = [
        {
            "id": str(ct.id),
            "full_name": ct.full_name,
            "position": ct.position,
            "email": ct.email,
            "phone": ct.phone,
            "status": ct.status,
            "owner_id": str(ct.owner_id) if ct.owner_id else None,
            "owner_name": ct.owner.full_name if ct.owner else "Unassigned",
            "attempt_count": ct.attempt_count or 0,
            "last_contact_at": ct.last_contact_at.isoformat() if ct.last_contact_at else None,
            "last_outcome": ct.last_outcome,
            "notes": ct.notes,
            "can_edit": current_user.is_manager_or_above or (ct.owner_id == current_user.id),
        }
        for ct in company.contacts
        if not ct.deleted_at
    ]
    res["opportunities"] = [
        {"id": str(op.id), "title": op.title, "value": op.value, "stage": op.stage}
        for op in company.opportunities
        if not op.deleted_at
    ]
    return {"data": res}


@router.patch("/{company_id}")
async def update_company(
    company_id: uuid.UUID,
    body: CompanyUpdateBody,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Company).where(Company.id == company_id, Company.deleted_at.is_(None)).options(selectinload(Company.account_owner))
    company = (await db.execute(stmt)).scalar_one_or_none()
    if not company:
        raise NotFoundError("Company not found.")

    for field, val in body.model_dump(exclude_unset=True).items():
        if field == "account_owner_id":
            company.account_owner_id = uuid.UUID(val) if val else None
        else:
            setattr(company, field, val)

    db.add(company)
    await db.flush()

    audit = AuditService(db)
    await audit.log(
        action="company.updated",
        entity_type="company",
        actor_id=current_user.id,
        entity_id=company.id,
    )
    return {"data": _company_dict(company)}


@router.delete("/{company_id}", status_code=204)
async def delete_company(
    company_id: uuid.UUID,
    current_user: User = Depends(require_manager_or_above),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Company).where(Company.id == company_id, Company.deleted_at.is_(None))
    company = (await db.execute(stmt)).scalar_one_or_none()
    if not company:
        raise NotFoundError("Company not found.")

    company.soft_delete()
    db.add(company)
    await db.flush()

    audit = AuditService(db)
    await audit.log(
        action="company.deleted",
        entity_type="company",
        actor_id=current_user.id,
        entity_id=company.id,
    )


@router.get("/{company_id}/contacts")
async def list_company_contacts(
    company_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all contacts belonging to a specific company with RBAC permissions."""
    stmt = (
        select(Contact)
        .where(Contact.company_id == company_id, Contact.deleted_at.is_(None))
        .options(selectinload(Contact.owner), selectinload(Contact.company))
        .order_by(Contact.created_at.desc())
    )
    contacts = (await db.execute(stmt)).scalars().all()
    return {
        "data": [
            {
                "id": str(ct.id),
                "full_name": ct.full_name,
                "position": ct.position,
                "email": ct.email,
                "phone": ct.phone,
                "status": ct.status,
                "owner_id": str(ct.owner_id) if ct.owner_id else None,
                "owner_name": ct.owner.full_name if ct.owner else "Unassigned",
                "attempt_count": ct.attempt_count or 0,
                "last_contact_at": ct.last_contact_at.isoformat() if ct.last_contact_at else None,
                "last_outcome": ct.last_outcome,
                "notes": ct.notes,
                "can_edit": current_user.is_manager_or_above or (ct.owner_id == current_user.id),
            }
            for ct in contacts
        ]
    }
