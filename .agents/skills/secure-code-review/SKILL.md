---
name: secure-code-review
description: >-
  Use this skill when performing a security-focused review of any completed
  implementation. Activate after any significant feature is built, before it is
  considered production-ready. This skill provides a systematic checklist to
  catch security defects including access control gaps, injection risks, data
  leakage, insecure configurations, and authentication weaknesses that may have
  been missed during development.
---

# Secure Code Review

You are acting as a Senior Application Security Reviewer. Your responsibility
is to systematically review implemented code for security defects before it
ships to production.

## Review Methodology

Perform a layered review following this sequence:
1. **Authentication & Authorization** — Can the right people access the right things?
2. **Input Handling** — Is all input validated and sanitized?
3. **Data Access** — Are database queries safe from injection?
4. **Data Exposure** — Is sensitive data adequately protected?
5. **Business Logic** — Are security-relevant rules correctly enforced?
6. **Configuration** — Are secrets and config handled safely?
7. **Error Handling** — Do errors leak internal information?
8. **Dependency Risk** — Are third-party packages safe?

---

## Layer 1: Authentication & Authorization Review

Checklist:
- [ ] Every protected route has authentication middleware applied.
- [ ] Every resource access has an ownership/role check at the SERVICE layer (not only routes).
- [ ] IDOR check: does every query filter by `owner_id` or equivalent ownership constraint?
- [ ] Role hierarchy is correctly enforced (lower role cannot access higher-role endpoints).
- [ ] Passwords are hashed with bcrypt/Argon2 — not stored plain.
- [ ] Session tokens are `HttpOnly`, `Secure`, `SameSite=Strict`.
- [ ] JWTs (if used) are verified with correct algorithm and secret.
- [ ] No sensitive data stored in localStorage.
- [ ] Account lockout is implemented for login failures.
- [ ] Password reset tokens are time-limited and single-use.

---

## Layer 2: Input Handling Review

Checklist:
- [ ] Every API endpoint validates its input with a schema.
- [ ] Validation errors return 400 with field-level detail (no schema internals exposed).
- [ ] No user input is reflected back without sanitization (XSS).
- [ ] `dangerouslySetInnerHTML` is not used (or sanitized with DOMPurify if unavoidable).
- [ ] File uploads (if any) validate MIME type server-side.
- [ ] Sort/filter field names are whitelisted before use in queries.
- [ ] Pagination parameters have maximum limits enforced.
- [ ] Request body does not contain extra fields that are silently accepted (mass assignment).

---

## Layer 3: Data Access Review

Checklist:
- [ ] All database queries use parameterized queries or ORM bound parameters.
- [ ] No user input is concatenated into SQL strings.
- [ ] No user-controlled values are used in file paths without sanitization.
- [ ] No user-controlled values are passed to shell commands.
- [ ] JSONB stored data is not later interpolated unsafely.

---

## Layer 4: Data Exposure Review

Checklist:
- [ ] API responses do not include fields the client doesn't need (e.g., password hash, internal IDs).
- [ ] Error messages do not include stack traces, DB errors, or internal paths.
- [ ] Logs do not contain passwords, tokens, PII, or secrets.
- [ ] Database credentials are not committed to source control.
- [ ] Audit logs are not exposed to unauthorized users.
- [ ] Sensitive fields (email, phone) are not returned on list endpoints when not needed.

---

## Layer 5: Business Logic Review

Checklist:
- [ ] Lead status transitions are validated server-side (not only client-side).
- [ ] DNC contacts cannot receive outbound activities (enforced in service layer).
- [ ] Ownership changes are audit-logged.
- [ ] Duplicate contacts cannot be silently auto-merged.
- [ ] Admin operations (delete, config change) require admin role and are audit-logged.
- [ ] Google Sheets sync does not execute arbitrary content from spreadsheet cells.
- [ ] Automation rules cannot trigger infinite execution chains.
- [ ] Rate limits are applied to high-risk endpoints (login, import, etc.).

---

## Layer 6: Configuration Review

Checklist:
- [ ] No secrets, API keys, or DB credentials in source code.
- [ ] `.env` file is in `.gitignore`.
- [ ] `.env.example` has all keys listed without real values.
- [ ] All required env vars are validated at startup (app fails fast if missing).
- [ ] CORS is restricted to known origins (no wildcard on authenticated endpoints).
- [ ] Security headers are set on all responses.
- [ ] Debug mode / verbose logging is disabled in production.
- [ ] Error pages do not reveal technology stack.

---

## Layer 7: Error Handling Review

Checklist:
- [ ] A centralized error handler catches all unhandled errors.
- [ ] All errors return consistent, structured error responses.
- [ ] HTTP 500 responses never include stack traces in production.
- [ ] 404 responses do not reveal whether a resource exists for unauthorized users.
- [ ] All async operations have error handling (no unhandled promise rejections).
- [ ] Background job failures are logged and alerted.

---

## Layer 8: Dependency Review

Checklist:
- [ ] `npm audit` shows no critical or high vulnerabilities.
- [ ] All packages are from reputable sources (npm official, not GitHub-only installs).
- [ ] No packages with < 100 weekly downloads or last published > 2 years ago (unless well-known).
- [ ] lockfile committed to Git.
- [ ] No packages that execute postinstall scripts from unknown authors.

---

## Findings Documentation

For each finding, record:
```
Severity: CRITICAL | HIGH | MEDIUM | LOW | INFO
Location: file:line
Issue: Description of the vulnerability
Impact: What an attacker could do
Recommendation: Specific fix
```

Severity definitions:
- **CRITICAL**: Remote code execution, authentication bypass, data breach risk.
- **HIGH**: IDOR, privilege escalation, sensitive data exposure.
- **MEDIUM**: XSS (stored), CSRF, missing rate limit on sensitive endpoint.
- **LOW**: Missing security header, verbose error, low-impact information disclosure.
- **INFO**: Best practice improvement, not a direct vulnerability.

## What NOT to Do

- Do NOT approve code with CRITICAL or HIGH findings.
- Do NOT skip the service-layer authorization check.
- Do NOT mark "SQL concatenation is fine because input is sanitized elsewhere" — always use parameterized queries.
- Do NOT approve production secrets in code even if they're "temporary".
