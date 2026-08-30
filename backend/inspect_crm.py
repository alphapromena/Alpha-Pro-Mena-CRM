import openpyxl
from collections import defaultdict

wb = openpyxl.load_workbook('f:\\New folder\\CRM.xlsx', read_only=True, data_only=True)
ws = wb['Sheet1']

# Sample first 3 rows per rep to understand column order
rep_samples = defaultdict(list)
for i, row in enumerate(ws.iter_rows(values_only=True), start=1):
    if all(v is None or str(v).strip() == '' for v in row):
        continue
    sp = str(row[5]).strip() if len(row) > 5 and row[5] is not None else 'UNKNOWN'
    if len(rep_samples[sp]) < 3:
        rep_samples[sp].append({
            'row': i,
            'name': row[0],
            'col1': row[1],  # Could be Company or Position
            'col2': row[2],  # Could be Position or Company
            'phone': row[3],
            'email': row[4],
        })

wb.close()

print("Sample rows per rep to understand column layout:\n")
for rep in sorted(rep_samples.keys()):
    print(f"=== {rep} ===")
    for s in rep_samples[rep]:
        print(f"  Row {s['row']}: {s['name']} | col1='{s['col1']}' | col2='{s['col2']}'")
    print()
