"""
inspect_workbook_details.py
Detailed analysis of Gulf Leads .xlsx sheets, headers, notes, demos, and companies with safe ASCII output.
"""
import openpyxl
import json
from pathlib import Path

wb = openpyxl.load_workbook("c:/Users/user/Alpha-Pro-Mena-CRM/Gulf Leads .xlsx", data_only=True)

print("=== ALL SHEETS OVERVIEW ===")
sheet_summary = []
for sname in wb.sheetnames:
    ws = wb[sname]
    rows = list(ws.iter_rows(values_only=True))
    non_empty = [r for r in rows if any(c is not None for c in r)]
    header = [str(c)[:30] if c is not None else "" for c in non_empty[0][:10]] if non_empty else []
    sample = [str(c)[:30] if c is not None else "" for c in non_empty[1][:10]] if len(non_empty) > 1 else []
    sheet_summary.append({
        "sheet": sname,
        "total_rows": len(rows),
        "non_empty_rows": len(non_empty),
        "header": header,
        "sample": sample
    })

print(json.dumps(sheet_summary, ensure_ascii=True, indent=2))

print("\n=== DEMO SHEET STRUCTURE ===")
ws_demo = wb["Demo"]
demo_rows = list(ws_demo.iter_rows(values_only=True))
print(f"Total Demo rows: {len(demo_rows)}")
demo_sample = []
for i in range(min(30, len(demo_rows))):
    r = demo_rows[i]
    if any(c is not None for c in r):
        demo_sample.append([str(c)[:30] if c is not None else "" for c in r[:10]])

print(json.dumps(demo_sample, ensure_ascii=True, indent=2))

print("\n=== COMPANIES COUNT AUDIT ===")
all_companies = set()
ws_comp = wb["Companies"]
comp_rows = list(ws_comp.iter_rows(values_only=True))
for r in comp_rows[1:]:
    if r[0] and str(r[0]).strip():
        all_companies.add(str(r[0]).strip().lower())

print(f"Distinct companies in 'Companies' sheet: {len(all_companies)}")

leads_companies = set()
ws_leads = wb["Leads"]
for r in list(ws_leads.iter_rows(values_only=True))[1:]:
    if len(r) > 1 and r[1] and str(r[1]).strip():
        c_name = str(r[1]).strip().lower()
        leads_companies.add(c_name)
        all_companies.add(c_name)

print(f"Distinct companies in 'Leads' sheet: {len(leads_companies)}")
print(f"Combined distinct companies (Companies + Leads): {len(all_companies)}")
