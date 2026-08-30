import os, glob

# Find Excel files
print("=== SEARCHING FOR EXCEL FILES ===")
for pattern in ['c:/Users/user/Alpha-Pro-Mena-CRM\\**\\*.xlsx', 'c:/Users/user/Alpha-Pro-Mena-CRM\\**\\*.xls', 'c:/Users/user/Alpha-Pro-Mena-CRM\\**\\*.csv']:
    files = glob.glob(pattern, recursive=True)
    for f in files:
        size = os.path.getsize(f)
        print(f"  {f} ({size:,} bytes)")
