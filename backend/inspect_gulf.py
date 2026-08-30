import openpyxl
from collections import defaultdict

wb = openpyxl.load_workbook('f:\\New folder\\Gulf Leads .xlsx', read_only=True, data_only=True)
ws = wb['Leads']

rep_samples = defaultdict(list)
skip_header = True
for i, row in enumerate(ws.iter_rows(values_only=True), start=1):
    if skip_header:
        skip_header = False
        continue
    if all(v is None or str(v).strip() == '' for v in row):
        continue
    sp = str(row[5]).strip() if len(row) > 5 and row[5] is not None else 'UNKNOWN'
    if len(rep_samples[sp]) < 2:
        rep_samples[sp].append({
            'row': i,
            'name': row[0],
            'col1': row[1],
            'col2': row[2],
            'phone': row[3],
        })

wb.close()

print("Gulf Leads - Leads sheet column layout per rep:\n")
for rep in ['Saleh', 'Amin', 'Hassan', 'Ghaida']:
    samples = rep_samples.get(rep, [])
    print(f"=== {rep} ===")
    for s in samples:
        print(f"  Row {s['row']}: {s['name']} | col1='{s['col1']}' | col2='{s['col2']}' | phone={s['phone']}")
    print()
