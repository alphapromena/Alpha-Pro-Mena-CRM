# backend/scripts - one-off tooling (not part of the app)

Ad-hoc import / audit / verification scripts used while building the CRM and loading
the Excel workbooks. They are **not** imported by the application and are excluded
from the Docker and Vercel bundles. Several still contain machine-specific paths.

Run them from `backend/` so `app.*` imports resolve:

```bash
cd backend
.venv\Scripts\python -m scripts.check_db_state
```

* `fix_db_integrity.py` - repairs orphan rows / test fixtures in an existing database
  (dry-run by default, `--apply` to execute; makes a backup first).
* `migrate_sqlite_to_postgres.py` - copies all data from the local SQLite file into the
  production PostgreSQL database before the first Vercel deploy.
* `migrations.py` - the *old* startup hook that auto-created `qusai@alphapro.com`;
  kept for reference only, it no longer runs.
