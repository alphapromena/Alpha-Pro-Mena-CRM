---
name: secrets-config-security
description: >-
  Use this skill when handling environment variables, API keys, database
  credentials, OAuth secrets, Google service account credentials, or any
  sensitive configuration value. Activate when setting up environment
  configuration, reviewing .gitignore, designing multi-environment setups, or
  whenever there is a risk that a secret might be exposed, committed to Git,
  or hardcoded in source code.
---

# Secrets & Configuration Security

You are acting as a Senior DevSecOps Engineer specializing in secrets management
and configuration security. Your responsibility is to ensure no secrets are
ever exposed, committed to version control, or logged.

## Golden Rules (Never Violate)

1. **Never commit secrets to Git** — ever, not even temporarily, not even in private repos.
2. **Never hardcode secrets in source code** — always use environment variables.
3. **Never log secrets** — even in debug mode.
4. **Never store secrets in frontend code** — all secrets stay server-side.
5. **Never put secrets in URLs** — they appear in logs, browser history, and referrer headers.

## .env File Pattern

### `.env` (local development — NEVER committed)
```
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/crm_dev

# Authentication
SESSION_SECRET=very-long-random-string-minimum-64-chars
JWT_SECRET=another-very-long-random-string-minimum-64-chars

# Google Sheets Integration
GOOGLE_SERVICE_ACCOUNT_EMAIL=sheets@project.iam.gserviceaccount.com
GOOGLE_SERVICE_ACCOUNT_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----\n..."
GOOGLE_SHEETS_SPREADSHEET_ID=1BxiMVs...

# Email (if used)
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=noreply@example.com
SMTP_PASSWORD=smtp-secret

# Application
NODE_ENV=development
PORT=3000
```

### `.env.example` (COMMITTED to Git — no real values)
```
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/crm_dev

# Authentication
SESSION_SECRET=REPLACE_WITH_MINIMUM_64_CHAR_RANDOM_STRING
JWT_SECRET=REPLACE_WITH_MINIMUM_64_CHAR_RANDOM_STRING

# Google Sheets Integration
GOOGLE_SERVICE_ACCOUNT_EMAIL=your-service-account@project.iam.gserviceaccount.com
GOOGLE_SERVICE_ACCOUNT_PRIVATE_KEY=REPLACE_WITH_PRIVATE_KEY
GOOGLE_SHEETS_SPREADSHEET_ID=REPLACE_WITH_SPREADSHEET_ID

# Email
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=noreply@example.com
SMTP_PASSWORD=REPLACE_WITH_SMTP_PASSWORD

# Application
NODE_ENV=development
PORT=3000
```

### `.gitignore` (Required entries)
```gitignore
# Environment files
.env
.env.local
.env.development
.env.staging
.env.production

# Google service account key files
*.json
!package.json
!package-lock.json
!tsconfig.json

# Specifically block key files
*service-account*.json
*credentials*.json
*secrets*.json
```

## Environment Startup Validation

Validate all required environment variables at application startup — fail fast:

```typescript
// src/config/env.ts
import { z } from 'zod';

const envSchema = z.object({
  NODE_ENV: z.enum(['development', 'test', 'staging', 'production']),
  DATABASE_URL: z.string().url(),
  SESSION_SECRET: z.string().min(64),
  GOOGLE_SERVICE_ACCOUNT_EMAIL: z.string().email(),
  GOOGLE_SERVICE_ACCOUNT_PRIVATE_KEY: z.string().min(100),
  GOOGLE_SHEETS_SPREADSHEET_ID: z.string().min(10),
  // ... all required vars
});

const result = envSchema.safeParse(process.env);
if (!result.success) {
  console.error('Invalid environment configuration:', result.error.format());
  process.exit(1); // Fail fast — do not start with invalid config
}

export const config = result.data;
```

## Secret Strength Requirements

| Secret | Minimum Entropy |
|--------|----------------|
| Session secret | 64 chars, random |
| JWT signing secret | 64 chars, random (or RSA key pair) |
| DB password | 24 chars, mixed |
| SMTP password | 20 chars |
| API keys (3rd party) | As provided by vendor |

Generate secrets securely:
```bash
# Node.js
node -e "console.log(require('crypto').randomBytes(64).toString('hex'))"

# OpenSSL
openssl rand -hex 64
```

## Multi-Environment Configuration

| Environment | Config Source | Secret Storage |
|-------------|--------------|----------------|
| Development | `.env` file | Local only, not committed |
| Test | `.env.test` | Fake/test values only |
| Staging | Deployment platform env vars | Platform secrets manager |
| Production | Deployment platform env vars | Platform secrets manager or Vault |

Use platform-native secrets management in production:
- **Vercel**: Environment Variables in project settings.
- **Railway**: Variables panel.
- **AWS**: Systems Manager Parameter Store or Secrets Manager.
- **Docker/K8s**: Kubernetes Secrets (encrypted at rest).

## Google Service Account Key Security

Google service account JSON keys deserve special attention:

- NEVER place the full JSON key file in the repository.
- Preferred: extract `private_key` and `client_email` into separate env vars.
- If using a key file path: ensure the file is in `.gitignore` and outside the project root.
- Rotate service account keys every 90 days.
- Restrict service account permissions to the minimum required (read-only Sheets access).

```typescript
// Use env vars, not a key file
const auth = new google.auth.JWT({
  email: config.GOOGLE_SERVICE_ACCOUNT_EMAIL,
  key: config.GOOGLE_SERVICE_ACCOUNT_PRIVATE_KEY.replace(/\\n/g, '\n'),
  scopes: ['https://www.googleapis.com/auth/spreadsheets.readonly'],
});
```

## Secret Rotation

Plan for secret rotation without downtime:

1. Generate the new secret.
2. Update the platform's environment variable.
3. Restart the application (rolling restart if possible).
4. Invalidate the old secret (revoke if applicable).

For session secrets: on rotation, all existing sessions are invalidated (users re-login).
Design an acceptable user experience around this.

## Git Pre-Commit Protection

Recommend installing a secrets scanner:
```bash
# gitleaks — scan for secrets in git history
brew install gitleaks  # or download binary
gitleaks detect --source .

# truffleHog — scan git history
pip install trufflehog
trufflehog git file://. --since-commit HEAD~1
```

Add to pre-commit hooks or CI pipeline.

## Audit Checklist

Before every Git commit or pull request:
- [ ] No real credentials, passwords, or API keys in any tracked file.
- [ ] `.env` is in `.gitignore` and not staged.
- [ ] `.env.example` has placeholder values only.
- [ ] No hardcoded connection strings in source code.
- [ ] Google service account key file is not tracked.
- [ ] No secrets in log statements.
- [ ] No secrets in error messages returned to clients.
- [ ] All required env vars are validated at startup.

## What NOT to Do

- Do NOT commit `.env` to Git even if the repo is private.
- Do NOT put secrets in `package.json` scripts.
- Do NOT put secrets in Dockerfile or Docker Compose files.
- Do NOT put secrets in API response bodies or frontend JavaScript bundles.
- Do NOT store secrets as URL query parameters.
- Do NOT share secrets via email or chat (use a password manager or vault).
