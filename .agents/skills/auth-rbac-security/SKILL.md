---
name: auth-rbac-security
description: >-
  Use this skill when implementing or reviewing authentication, session
  management, JWT handling, password security, or role-based access control.
  Activate when the task involves login flows, session expiry, account
  lockouts, role checking, resource-level authorization, admin/manager/team
  leader/sales user permission boundaries, or any identity and access
  management concern in the CRM.
---

# Authentication & RBAC Security

You are acting as a Senior Identity and Access Management Engineer. Your
responsibility is to ensure authentication is secure, sessions are properly
managed, and access control is strictly enforced at every layer.

## Authentication Architecture

### Password Security
- Hash passwords with **bcrypt** (work factor ≥ 12) or **Argon2id** (memory ≥ 64MB, iterations ≥ 3).
- Never store plain-text or reversibly-encrypted passwords.
- Never log passwords, even in debug mode.
- Enforce minimum password complexity: ≥ 8 characters, mix of character types.

### Session Strategy
Choose ONE session approach and be consistent:

**Option A — Cookie-based sessions (recommended for CRM web apps)**
- Store session ID in an `HttpOnly`, `Secure`, `SameSite=Strict` cookie.
- Store session data server-side (Redis or DB).
- Regenerate session ID on login (prevent session fixation).
- Session expiry: 8 hours inactivity, 24 hours absolute maximum.

**Option B — JWT (if stateless is required)**
- Sign with RS256 (asymmetric) or at minimum HS256 with a strong secret (≥ 256-bit).
- Short access token TTL: 15 minutes.
- Refresh token: 7 days, stored in `HttpOnly` cookie (not localStorage).
- Maintain a refresh token revocation list (Redis) for logout/invalidation.
- Never store JWTs in localStorage — XSS vulnerability.

### Account Lockout
- After 5 consecutive failed login attempts: lock account for 15 minutes.
- After 10 consecutive failures: require admin unlock.
- Log all failed login attempts with: IP address, timestamp, username attempted.
- Alert on suspicious patterns (many failures across many accounts from one IP).

### Password Reset
- Use time-limited, single-use, opaque tokens (not JWTs) for password reset.
- Token validity: 1 hour maximum.
- Invalidate all existing sessions on password change.
- Send reset links only to the email on file — never reveal if email exists (timing-safe response).

## Role-Based Access Control (RBAC)

### CRM Role Hierarchy

```
Admin
  └── Manager
        └── Team Leader
              └── Sales User
```

### Role Permissions Matrix

| Permission | Sales User | Team Leader | Manager | Admin |
|------------|-----------|-------------|---------|-------|
| View own leads | ✅ | ✅ | ✅ | ✅ |
| View team leads | ❌ | ✅ | ✅ | ✅ |
| View all leads | ❌ | ❌ | ✅ | ✅ |
| Assign leads (own team) | ❌ | ✅ | ✅ | ✅ |
| Assign leads (any user) | ❌ | ❌ | ✅ | ✅ |
| Create/edit contacts | ✅ | ✅ | ✅ | ✅ |
| Delete contacts | ❌ | ❌ | ✅ | ✅ |
| View all activities | ❌ | Team only | ✅ | ✅ |
| Manage users | ❌ | ❌ | ❌ | ✅ |
| Manage campaigns | ❌ | ❌ | ✅ | ✅ |
| View audit logs | ❌ | ❌ | ✅ | ✅ |
| System configuration | ❌ | ❌ | ❌ | ✅ |
| Google Sheets sync | ❌ | ❌ | ✅ | ✅ |
| View reports/dashboards | Limited | Team | All | All |

### Authorization Implementation

**Two-layer authorization:**

1. **Route/Middleware layer** — coarse-grained role check:
   ```typescript
   requireRole(['MANAGER', 'ADMIN'])
   ```

2. **Service layer** — fine-grained resource authorization:
   ```typescript
   // Can this user access this specific lead?
   if (lead.ownerId !== currentUser.id && !hasRole(currentUser, ['MANAGER', 'ADMIN', 'TEAM_LEADER'])) {
     throw new ForbiddenError('Access denied.');
   }
   ```

- Both checks are MANDATORY. Skipping either is a security defect.
- Service-layer authorization is the authoritative check. Route guards are defense-in-depth.

### RBAC Rules
- Roles are stored in the database and attached to the user record.
- A user has exactly ONE role (no multi-role unless explicitly required).
- Role changes take effect on the NEXT request (invalidate cached role on change).
- Admin cannot demote themselves (prevent lockout).
- Always audit-log role changes.

## Session Management

- On successful login: create session, set cookie, log authentication event.
- On logout: destroy session server-side, clear cookie, log logout event.
- On password change: destroy ALL sessions for that user.
- On role change: invalidate session to force re-authentication.
- On account lockout: destroy all sessions immediately.

## Security Headers (Auth-Related)

Ensure these headers are set on all responses:
```
Content-Security-Policy: default-src 'self'; ...
X-Frame-Options: DENY
X-Content-Type-Options: nosniff
Strict-Transport-Security: max-age=31536000; includeSubDomains
Cache-Control: no-store  (on auth endpoints and sensitive pages)
```

## Frontend Auth Considerations

- Redirect to login on 401 (globally, via API client interceptor).
- Clear all cached query data on logout.
- Never expose role/permission data in the URL.
- Hide UI elements the user cannot access (defense-in-depth, not the primary control).
- Do NOT rely on frontend role checks as the security boundary — server enforces.

## Audit Events (Authentication)

Log all of the following:
- Successful login (user ID, IP, timestamp, user agent).
- Failed login (attempted username, IP, timestamp).
- Logout.
- Password change.
- Password reset requested / completed.
- Account locked / unlocked.
- Role changed (actor, target user, old role, new role).
- Session expired.

## What NOT to Do

- Do NOT store passwords in plain text or reversible encryption.
- Do NOT use weak JWT secrets (< 256 bits).
- Do NOT store tokens in localStorage (XSS risk).
- Do NOT skip service-layer authorization — route guards alone are insufficient.
- Do NOT return different errors for "user not found" vs "wrong password" (user enumeration).
- Do NOT allow unlimited login attempts.
- Do NOT skip invalidating sessions on password/role change.
