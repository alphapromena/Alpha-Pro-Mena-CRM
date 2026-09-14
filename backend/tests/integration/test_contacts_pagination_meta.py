"""
Pagination metadata and global sequential numbering for the contacts list.

The restore bug this guards against: the page compared a saved page number
against total_pages, but total_pages is computed for whatever per_page the
request used. A restore asks for one large page, so the two numbers are in
different units. Restoring 41 pages of 50 requested 2050 records, received
total_pages = 2, concluded 41 >= 2, and marked the list fully loaded while
records were still missing.

meta.offset, meta.returned and meta.has_more are derived from what was actually
returned, so a client never has to do that arithmetic.
"""
import uuid

import pytest
import pytest_asyncio

from app.core.security import hash_password, normalize_email
from app.models.user import User, UserRole


async def seed_contacts(db, owner, count: int):
    from app.models.contact import Contact

    made = []
    for i in range(count):
        email = f"p{i:05d}_{uuid.uuid4().hex[:5]}@alphapromena.com"
        c = Contact(
            first_name=f"Person{i:05d}",
            last_name="Test",
            email=email,
            normalized_email=normalize_email(email),
            owner_id=owner.id,
            status="NEW",
            priority="MEDIUM",
            is_dnc=False,
            attempt_count=0,
            sheet_order=i + 1,
            source_sheet="Sheet16",
        )
        db.add(c)
        made.append(c)
    await db.flush()
    return made


@pytest_asyncio.fixture
async def owner(db_session):
    email = f"owner_{uuid.uuid4().hex[:6]}@alphapromena.com"
    u = User(
        email=email,
        normalized_email=normalize_email(email),
        first_name="Owner",
        last_name="User",
        password_hash=hash_password("OwnerPass123!"),
        role=UserRole.ADMIN,
        is_active=True,
        email_verified=True,
    )
    db_session.add(u)
    await db_session.flush()
    return u


def auth(user):
    from app.core.security import create_access_token

    return {"Authorization": f"Bearer {create_access_token(user_id=user.id, role=user.role)}"}


@pytest.mark.asyncio
async def test_meta_reports_offset_returned_and_has_more(client, db_session, owner):
    await seed_contacts(db_session, owner, 120)

    res = await client.get("/api/v1/contacts?page=1&per_page=50", headers=auth(owner))
    assert res.status_code == 200
    meta = res.json()["meta"]

    assert meta["offset"] == 0
    assert meta["returned"] == 50
    assert meta["has_more"] is True
    assert meta["total"] >= 120


@pytest.mark.asyncio
async def test_has_more_is_false_on_the_final_page(client, db_session, owner):
    await seed_contacts(db_session, owner, 120)

    res = await client.get("/api/v1/contacts?page=3&per_page=50", headers=auth(owner))
    meta = res.json()["meta"]

    assert meta["offset"] == 100
    assert meta["has_more"] is False, "the last page must not claim more remains"


@pytest.mark.asyncio
async def test_one_large_page_reports_no_more_left(client, db_session, owner):
    """
    The exact restore shape. Asking for everything in one page must report
    has_more false, even though total_pages for that page size is 1 and a naive
    comparison of a saved page number against it is meaningless.
    """
    await seed_contacts(db_session, owner, 120)

    res = await client.get("/api/v1/contacts?page=1&per_page=500", headers=auth(owner))
    meta = res.json()["meta"]

    assert meta["returned"] == meta["total"]
    assert meta["has_more"] is False


@pytest.mark.asyncio
async def test_a_partial_large_page_still_reports_more(client, db_session, owner):
    """Restoring part of a long list must not mark it complete."""
    await seed_contacts(db_session, owner, 500)

    res = await client.get("/api/v1/contacts?page=1&per_page=200", headers=auth(owner))
    meta = res.json()["meta"]

    assert meta["returned"] == 200
    assert meta["has_more"] is True, "200 of 500 loaded is not the whole list"


@pytest.mark.asyncio
async def test_paging_beyond_430_records_covers_everything_once(client, db_session, owner):
    """
    Walk a list larger than a single page repeatedly and check that every record
    appears exactly once. Skips and repeats are the two ways pagination breaks.
    """
    await seed_contacts(db_session, owner, 470)

    seen, page = [], 1
    while True:
        res = await client.get(
            f"/api/v1/contacts?page={page}&per_page=50&sort_by=sheet_order&sort_dir=asc",
            headers=auth(owner),
        )
        body = res.json()
        seen.extend(c["id"] for c in body["data"])
        if not body["meta"]["has_more"]:
            break
        page += 1
        assert page < 40, "pagination did not terminate"

    assert len(seen) == len(set(seen)), "a record was returned on two pages"
    assert len(seen) == body["meta"]["total"]


@pytest.mark.asyncio
async def test_offset_gives_correct_display_numbers_across_pages(client, db_session, owner):
    """
    The # column is offset + index + 1. Page 2 must continue from where page 1
    stopped rather than restarting at 1.
    """
    await seed_contacts(db_session, owner, 120)

    first = await client.get(
        "/api/v1/contacts?page=1&per_page=50&sort_by=sheet_order&sort_dir=asc", headers=auth(owner)
    )
    second = await client.get(
        "/api/v1/contacts?page=2&per_page=50&sort_by=sheet_order&sort_dir=asc", headers=auth(owner)
    )

    m1, m2 = first.json()["meta"], second.json()["meta"]
    assert m1["offset"] + 1 == 1
    assert m2["offset"] + 1 == 51, "page 2 numbering must continue from 51"

    # And the two pages hold different people.
    ids1 = {c["id"] for c in first.json()["data"]}
    ids2 = {c["id"] for c in second.json()["data"]}
    assert ids1.isdisjoint(ids2)


@pytest.mark.asyncio
async def test_numbering_follows_the_requested_sort(client, db_session, owner):
    await seed_contacts(db_session, owner, 60)

    asc = await client.get(
        "/api/v1/contacts?page=1&per_page=10&sort_by=sheet_order&sort_dir=asc", headers=auth(owner)
    )
    desc = await client.get(
        "/api/v1/contacts?page=1&per_page=10&sort_by=sheet_order&sort_dir=desc", headers=auth(owner)
    )

    assert asc.json()["meta"]["offset"] == 0
    assert desc.json()["meta"]["offset"] == 0
    assert [c["id"] for c in asc.json()["data"]] != [c["id"] for c in desc.json()["data"]]


@pytest.mark.asyncio
async def test_filtered_results_renumber_from_zero(client, db_session, owner):
    await seed_contacts(db_session, owner, 80)

    res = await client.get(
        "/api/v1/contacts?page=1&per_page=25&search=Person0001", headers=auth(owner)
    )
    meta = res.json()["meta"]
    assert meta["offset"] == 0
    assert meta["returned"] == len(res.json()["data"])
    assert meta["returned"] <= meta["total"]
