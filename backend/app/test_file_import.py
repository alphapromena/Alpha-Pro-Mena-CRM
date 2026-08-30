"""
Automated Verification Suite for Aseel Drag & Drop File Import:
1. CSV File Preview & Column Mapping Auto-Detection.
2. CSV File Ingestion into Unassigned Leads Pool.
3. Excel (.xlsx) File Preview & Ingestion.
4. Duplicate Detection & Idempotency.
"""
import asyncio
import io
import sys
import uuid
import openpyxl
import httpx
import structlog

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.main import create_app

logger = structlog.get_logger(__name__)


async def run_file_import_tests():
    print("=" * 70)
    print("RUNNING FILE IMPORT & INGESTION VERIFICATION SUITE")
    print("=" * 70)

    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test/api/v1") as client:

        # 1. Login as Aseel
        login_res = await client.post("/auth/login", json={"email": "aseel@alphapromena.com", "password": "Sales123!"})
        assert login_res.status_code == 200, f"Aseel login failed: {login_res.text}"
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        print("[PASS] Aseel authenticated successfully")

        # 2. Test CSV Preview
        uid = uuid.uuid4().hex[:6]
        csv_data = f"""First Name,Last Name,Email,Phone,Company,Position,Country,Industry,1st Attempt
Tariq_{uid},Al-Otaibi,tariq_{uid}@sauditech.com,+96654{uuid.uuid4().int % 10000000:07d},Saudi Tech,CTO,Saudi Arabia,Technology,No Answer
Noura_{uid},Al-Shehri,noura_{uid}@riyadhco.com,+96655{uuid.uuid4().int % 10000000:07d},Riyadh Co,Manager,Saudi Arabia,Consulting,Asked for email
"""
        csv_file = io.BytesIO(csv_data.encode("utf-8"))

        preview_res = await client.post(
            "/admin/import/preview",
            headers=headers,
            files={"file": (f"test_leads_{uid}.csv", csv_file, "text/csv")}
        )
        assert preview_res.status_code == 200, f"CSV preview failed: {preview_res.text}"
        p_data = preview_res.json()["data"]
        assert p_data["total_rows"] == 2
        assert len(p_data["preview_rows"]) == 2
        assert p_data["detected_mapping"]["first_name"] == "First Name"
        assert p_data["detected_mapping"]["email"] == "Email"
        print(f"[PASS] CSV preview succeeded: {p_data['total_rows']} rows detected, auto-mapping verified")

        # 3. Test CSV Commit
        csv_file.seek(0)
        commit_res = await client.post(
            "/admin/import/commit",
            headers=headers,
            files={"file": (f"test_leads_{uid}.csv", csv_file, "text/csv")}
        )
        assert commit_res.status_code == 200, f"CSV commit failed: {commit_res.text}"
        c_data = commit_res.json()["data"]
        assert c_data["rows_ready"] == 2
        assert c_data["rows_duplicate"] == 0
        print(f"[PASS] CSV commit succeeded: {c_data['rows_ready']} leads imported into New Leads Pool")

        # 4. Test Excel (.xlsx) Generation, Preview & Commit
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Leads"
        ws.append(["First Name", "Last Name", "Email", "Phone", "Company", "Position", "Country", "Industry"])
        excel_uid = uuid.uuid4().hex[:6]
        ws.append([f"Majed_{excel_uid}", "Al-Ghamdi", f"majed_{excel_uid}@jeddahcorp.com", f"+96656{uuid.uuid4().int % 10000000:07d}", "Jeddah Corp", "Director", "Saudi Arabia", "Logistics"])
        ws.append([f"Lama_{excel_uid}", "Al-Mutairi", f"lama_{excel_uid}@dammanholdings.com", f"+96657{uuid.uuid4().int % 10000000:07d}", "Dammam Holdings", "VP", "Saudi Arabia", "Energy"])

        excel_buf = io.BytesIO()
        wb.save(excel_buf)
        excel_buf.seek(0)

        # Excel Preview
        xlsx_preview = await client.post(
            "/admin/import/preview",
            headers=headers,
            files={"file": (f"test_excel_{excel_uid}.xlsx", excel_buf, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        )
        assert xlsx_preview.status_code == 200, f"Excel preview failed: {xlsx_preview.text}"
        assert xlsx_preview.json()["data"]["total_rows"] == 2
        print(f"[PASS] Excel (.xlsx) preview succeeded: 2 rows detected")

        # Excel Commit
        excel_buf.seek(0)
        xlsx_commit = await client.post(
            "/admin/import/commit",
            headers=headers,
            files={"file": (f"test_excel_{excel_uid}.xlsx", excel_buf, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        )
        assert xlsx_commit.status_code == 200, f"Excel commit failed: {xlsx_commit.text}"
        assert xlsx_commit.json()["data"]["rows_ready"] == 2
        print(f"[PASS] Excel (.xlsx) commit succeeded: 2 leads imported into New Leads Pool")

        # 5. Test Duplicate Detection (Re-importing exact same Excel file)
        excel_buf.seek(0)
        xlsx_recommit = await client.post(
            "/admin/import/commit",
            headers=headers,
            files={"file": (f"test_excel_{excel_uid}.xlsx", excel_buf, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        )
        assert xlsx_recommit.status_code == 200
        recommit_data = xlsx_recommit.json()["data"]
        assert recommit_data["rows_ready"] == 0, f"Expected 0 new rows, got {recommit_data['rows_ready']}"
        assert recommit_data["rows_duplicate"] == 2, f"Expected 2 duplicates, got {recommit_data['rows_duplicate']}"
        print(f"[PASS] Re-upload idempotency verified: 0 new rows, 2 duplicates skipped")

    print("\n" + "=" * 70)
    print("ALL FILE IMPORT VERIFICATION TESTS PASSED WITH 100% SUCCESS!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(run_file_import_tests())
