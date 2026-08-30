import sqlite3, os

# Check both DBs
for db_path in ['c:/Users/user/Alpha-Pro-Mena-CRM\\backend\\crm.db', 'c:/Users/user/Alpha-Pro-Mena-CRM\\backend\\app\\crm.db']:
    print(f"\n=== DB: {db_path} ===")
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    c.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in c.fetchall()]
    print(f"Tables: {tables}")
    
    if 'contacts' in tables:
        c.execute("SELECT COUNT(*) FROM contacts")
        print(f"Total contacts: {c.fetchone()[0]}")
        
        c.execute("SELECT status, COUNT(*) FROM contacts GROUP BY status")
        for row in c.fetchall():
            print(f"  status={row[0]}: {row[1]}")
    
    conn.close()
