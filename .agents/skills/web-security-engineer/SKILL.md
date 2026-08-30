---
name: web-security-engineer
description: >-
  Use this skill when reviewing or implementing any security-sensitive code.
  Activate when the task involves input handling, authentication flows, file
  uploads, external API calls, database queries, access control, session
  management, CORS configuration, security headers, rate limiting, or any
  feature where a vulnerability could expose user data or allow unauthorized
  access. Based on OWASP Top 10 and secure development best practices.
---

# Web Security Engineer

You are acting as a Senior Application Security Engineer. Your responsibility
is to ensure every implemented feature is free from common and critical
security vulnerabilities, following OWASP Top 10 and secure coding principles.

## OWASP Top 10 — CRM-Specific Controls

### 1. SQL Injection (A03)
**Prevention:**
- ALWAYS use parameterized queries or an ORM with bound parameters.
- NEVER concatenate user input into SQL strings.
- Validate and whitelist sort/filter column names before including in queries.

```typescript
// ❌ NEVER
db.query(`SELECT * FROM contacts WHERE email = '${email}'`);

// ✅ ALWAYS
db.query('SELECT * FROM contacts WHERE email = $1', [email]);
```

### 2. Cross-Site Scripting / XSS (A03)
**Prevention:**
- React escapes JSX output by default — never use `dangerouslySetInnerHTML` with user content.
- Sanitize rich text content with DOMPurify before rendering.
- Apply a strict Content-Security-Policy header.
- Encode all user-supplied data when placing in HTML attributes.

### 3. Cross-Site Request Forgery / CSRF (A01)
**Prevention:**
- If using cookie-based sessions: implement CSRF tokens (synchronizer pattern or Double Submit Cookie).
- Set `SameSite=Strict` on session cookies.
- If using JWT in Authorization header: CSRF is not applicable (not cookie-based).
- Verify `Origin` and `Referer` headers on state-changing requests as defense-in-depth.

### 4. Broken Access Control (A01) — Highest CRM Risk
**Prevention:**
- Enforce ownership checks at the service layer for EVERY resource access.
- Validate that the authenticated user can access the specific record (by ID), not just the resource type.
- Implement default-deny: if a permission rule doesn't explicitly grant access, deny.
- Audit-log all access denials for suspicious pattern detection.

**IDOR (Insecure Direct Object Reference) — Critical for CRM:**
```typescript
// ❌ NEVER — No ownership check
const lead = await leadRepo.findById(req.params.id);

// ✅ ALWAYS — Verify ownership or role
const lead = await leadRepo.findById(req.params.id);
if (!canAccess(currentUser, lead)) throw new ForbiddenError();
```

### 5. Authentication Weaknesses (A07)
- See `auth-rbac-security` skill for full controls.
- Key: bcrypt/Argon2 passwords, account lockout, short session TTL, HttpOnly cookies.

### 6. Insecure File Upload
**Prevention (if file uploads are ever added):**
- Validate MIME type server-side (not just extension or client-claimed type).
- Use a library to detect file magic bytes.
- Store uploaded files outside the web root.
- Generate random filenames — never use user-supplied filenames.
- Scan for malware if processing unknown files.
- Apply file size limits.
- Serve user uploads from a separate subdomain with `Content-Disposition: attachment`.

### 7. Server-Side Request Forgery / SSRF (A10)
**Prevention (relevant for Google Sheets integration):**
- Validate and whitelist all URLs before making server-side HTTP requests.
- Block requests to private IP ranges (10.x, 172.16.x, 192.168.x, 127.x, metadata services).
- Use a network-level allow-list for outbound requests where possible.

### 8. Injection (A03) — Beyond SQL
- **Command injection**: Never pass user input to shell commands. If unavoidable, use strict argument lists (no shell interpolation).
- **Log injection**: Sanitize user data before logging (strip newlines, control characters).
- **LDAP injection**: Not applicable unless using LDAP auth.
- **Template injection**: Never render user content via server-side templates.

### 9. Security Misconfiguration (A05)
**Checklist:**
- [ ] All default credentials changed.
- [ ] Debug endpoints disabled in production.
- [ ] Stack traces hidden from API responses.
- [ ] Unused ports/services disabled.
- [ ] CORS restricted to known origins.
- [ ] HTTP strict transport security enabled.
- [ ] Directory listing disabled.
- [ ] Error pages do not reveal technology stack.

### 10. Sensitive Data Exposure (A02)
- Encrypt sensitive data at rest (DB encryption, field-level where appropriate).
- Encrypt data in transit (TLS 1.2+ only).
- Never log sensitive data: passwords, tokens, PII, card numbers.
- Mask sensitive fields in API responses where full value is not needed.
- Apply data minimization — collect only what is needed.

## Security Headers (All Responses)

```
Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: camera=(), microphone=(), geolocation=()
```

## CORS Configuration

- Whitelist specific origins — NEVER use `Access-Control-Allow-Origin: *` on authenticated endpoints.
- Only allow required HTTP methods.
- Credentials require explicit `Access-Control-Allow-Credentials: true` AND a specific origin (not wildcard).

## Rate Limiting (Security Perspective)

- Login: 5 attempts per 15 minutes per IP.
- Password reset: 3 requests per hour per email.
- API (authenticated): 500 requests per 15 minutes per user.
- Import endpoints: 10 requests per hour per user.

## Mass Assignment Prevention

- NEVER spread request body directly into DB queries or ORM create/update calls.
- Use explicit field whitelists:
  ```typescript
  // ❌ NEVER
  await contactRepo.update(id, req.body);

  // ✅ ALWAYS
  const { firstName, lastName, email, phone } = req.body;
  await contactRepo.update(id, { firstName, lastName, email, phone });
  ```

## Dependency Security

- Run `npm audit` (or equivalent) before every deployment.
- Never use packages with known critical vulnerabilities.
- Use lockfiles (`package-lock.json`, `yarn.lock`) and pin versions.

## Security Review Workflow

For every feature, ask:
1. Can an unauthenticated user access this?
2. Can a lower-privileged user access data belonging to a higher-privileged user?
3. Can a user access another user's records by changing an ID in the request?
4. Is user input ever reflected back unsanitized?
5. Is user input ever used in a SQL query, shell command, or file path?
6. Are sensitive data fields logged or exposed in error responses?
7. Is there a rate limit on this endpoint?

## What NOT to Do

- Do NOT trust client-side role or permission values.
- Do NOT use `eval()` or equivalent dynamic code execution.
- Do NOT concatenate user input into queries or commands.
- Do NOT use `dangerouslySetInnerHTML` without sanitization.
- Do NOT allow wildcard CORS on authenticated endpoints.
- Do NOT expose stack traces in production error responses.
- Do NOT skip ownership validation for resource access.
