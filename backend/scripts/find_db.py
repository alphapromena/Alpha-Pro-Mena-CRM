import sqlite3, os, glob

# Find the actual DB file
for root, dirs, files in os.walk('c:/Users/user/Alpha-Pro-Mena-CRM\\backend'):
    for f in files:
        if f.endswith('.db'):
            print(os.path.join(root, f))

# Also check by pattern
import glob
dbs = glob.glob('c:/Users/user/Alpha-Pro-Mena-CRM\\backend\\**\\*.db', recursive=True)
print("Found DBs:", dbs)
dbs2 = glob.glob('c:/Users/user/Alpha-Pro-Mena-CRM\\**\\*.db', recursive=True)
print("Found DBs (project-wide):", dbs2)
