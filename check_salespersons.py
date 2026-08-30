import openpyxl
from collections import Counter

wb = openpyxl.load_workbook('f:/New folder/Gulf Leads .xlsx', read_only=True)
ws = wb['Leads']
salespersons = Counter()
total_rows = 0
for row in ws.iter_rows(min_row=2, values_only=True):
    if not any(row):
        continue
    total_rows += 1
    sp = row[5] if len(row) > 5 else None
    if sp:
        salespersons[str(sp).strip()] += 1
    else:
        salespersons['(Unassigned)'] += 1

print(f"Total non-empty leads rows: {total_rows}")
print("Salespersons breakdown in Leads sheet:")
for sp, count in salespersons.most_common():
    print(f"  {sp}: {count}")
