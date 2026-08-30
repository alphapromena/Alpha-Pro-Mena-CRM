# Production Deployment & Docker Guide

## 1. Single-Command Docker Compose

```bash
docker compose up -d --build
```

### Services Deployed
1. **`postgres`**: PostgreSQL 15 Database container with health checks and persistent volume.
2. **`backend`**: FastAPI production container with automated migrations, seed data check, and multi-worker Uvicorn.
3. **`frontend`**: React + Vite frontend serving the production application.

## 2. Production Checklist
* [ ] Generate strong, random 256-bit secrets for `APP_SECRET_KEY` and `JWT_SECRET_KEY`.
* [ ] Set `APP_DEBUG=false` in production `.env`.
* [ ] Enforce SSL/TLS certificates (HTTPS) via reverse proxy (Nginx or Cloudflare).
* [ ] Configure scheduled PostgreSQL dump backups to external object storage (AWS S3 or Cloudflare R2).
* [ ] Set appropriate CORS origins restricting requests exclusively to production domain.
