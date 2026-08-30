import os, glob

# Find Excel files
print("=== SEARCHING FOR EXCEL FILES ===")
for pattern in ['f:\\New folder\\**\\*.xlsx', 'f:\\New folder\\**\\*.xls', 'f:\\New folder\\**\\*.csv']:
    files = glob.glob(pattern, recursive=True)
    for f in files:
        size = os.path.getsize(f)
        print(f"  {f} ({size:,} bytes)")
