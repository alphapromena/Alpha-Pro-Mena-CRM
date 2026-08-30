"""
audit_sheet_and_phones.py

Audits:
1. Scientific notation phones in DB and in the source .xlsx file.
2. Kush Goel record in DB and its ownership & sheet_order.
3. First leads for Saleh, Amin, Hasan, Ghaida in DB vs Excel.
4. Total distinct companies in .xlsx vs DB vs /companies.
5. Demo sheet inspection (stages, notes, completed demos).
"""
import asyncio
from pathlib import Path
import openpyxl
from sqlalchemy import text, select
from app.database import engine, AsyncSessionLocal
from app.models.contact import Contact
from app.models.user import User
from app.models.company import Company
from app.models.demo import Demo

XLSX_PATH = Path("F:/New folder/Gulf Leads .xlsx")

async def run_audit():
    print("=== 1. AUDITING DATABASE PHONE NUMBERS ===")
    async with engine.begin() as conn:
        res = await conn.execute(text("SELECT id, first_name, last_name, phone, normalized_phone FROM contacts WHERE phone LIKE '%E+%' OR normalized_phone LIKE '%E+%' OR phone LIKE '%e+%'"))
        corrupted = res.fetchall()
        print(f"Corrupted phones count in DB: {len(corrupted)}")
        for r in corrupted[:5]:
            print("  Example in DB:", r)

        print("\n=== 2. CHECKING KUSH GOEL IN DB ===")
        res_kg = await conn.execute(text("""
            SELECT c.id, c.first_name, c.last_name, c.phone, c.email, c.owner_id, c.sheet_order, u.first_name as owner_name
            FROM contacts c
            LEFT JOIN users u ON c.owner_id = u.id
            WHERE c.first_name LIKE '%Kush%' OR c.last_name LIKE '%Goel%'
        """))
        kg_rows = res_kg.fetchall()
        for r in kg_rows:
            print("  Kush Goel in DB:", r)

        print("\n=== 3. CHECKING FIRST LEADS BY SALESPERSON IN DB (BY SHEET_ORDER) ===")
        for rep_name in ["Saleh", "Amin", "Hasan", "Ghaida"]:
            res_rep = await conn.execute(text("""
                SELECT c.sheet_order, c.first_name, c.last_name, c.phone, c.email, comp.name as company_name
                FROM contacts c
                JOIN users u ON c.owner_id = u.id
                LEFT JOIN companies comp ON c.company_id = comp.id
                WHERE u.first_name = :rep
                ORDER BY c.sheet_order ASC
                LIMIT 3
            """), {"rep": rep_name})
            print(f"  First 3 leads for {rep_name}:")
            for r in res_rep.fetchall():
                print(f"    sheet_order={r[0]}: {r[1]} {r[2]} ({r[5]}) - Phone: {r[3]}")

        print("\n=== 4. CHECKING COMPANIES IN DB ===")
        res_comp_count = await conn.execute(text("SELECT count(*) FROM companies WHERE deleted_at IS NULL"))
        print(f"  Total companies in DB: {res_comp_count.scalar_one()}")

    print("\n=== 5. CHECKING EXCEL FILE ===")
    wb = openpyxl.load_workbook(XLSX_PATH, data_only=True)
    
    # Check phone corruption in Excel
    ws_leads = wb["Leads"]
    excel_e_phones = []
    all_companies_set = set()

    for idx, row in enumerate(ws_leads.iter_rows(values_only=True)):
        if idx == 0:
            continue
        phone = row[3]
        if phone is not None:
            p_str = str(phone)
            if "E+" in p_str or "e+" in p_str:
                excel_e_phones.append((idx, row[0], row[1], p_str))
        comp = row[1]
        if comp and str(comp).strip():
            all_companies_set.add(str(comp).strip().lower())

    print(f"  Phones with E+ in Excel data_only reading: {len(excel_e_phones)}")
    if excel_e_phones:
        print("  Sample E+ in Excel:", excel_e_phones[:5])

    # Check companies across all sheets
    for sname in wb.sheetnames:
        ws = wb[sname]
        for row in ws.iter_rows(values_only=True):
            for cell in row:
                if cell and isinstance(cell, str) and len(cell) > 2:
                    # check if this sheet has company column
                    pass

    # Check Companies sheet specifically
    ws_comp = wb["Companies"]
    comp_sheet_companies = set()
    for idx, row in enumerate(ws_comp.iter_rows(values_only=True)):
        if idx == 0:
            continue
        if row[0] and str(row[0]).strip():
            comp_sheet_companies.add(str(row[0]).strip().lower())
    print(f"  Companies sheet distinct count: {len(comp_sheet_companies)}")
    print(f"  Leads sheet distinct companies count: {len(all_companies_set)}")

    # Check Demo sheet
    print("\n=== 6. CHECKING DEMO SHEET ===")
    ws_demo = wb["Demo"]
    demo_rows_data = []
    for idx, row in enumerate(ws_demo.iter_rows(values_only=True)):
        demo_rows_data.append(row)
    print(f"  Total rows in Demo sheet: {len(demo_rows_data)}")
    for r in demo_rows_data[:15]:
        print("    Demo row:", r[:8])

if __name__ == "__main__":
    asyncio.run(run_audit())
