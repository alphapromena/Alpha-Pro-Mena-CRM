# Security Engineering & RBAC Architecture

## 1. Authentication & Session Security

* **Password Hashing**: Passwords are encrypted using **bcrypt** with a work factor of 12. Plaintext passwords are never logged or stored.
* **JWT Storage**: JWT access (15 min) and refresh (7 days) tokens are delivered in `HttpOnly`, `SameSite=Lax`, `Secure` cookies to completely eliminate XSS token theft.
* **Account Lockout**: 5 consecutive failed login attempts trigger a 15-minute temporary lockout to mitigate brute-force attacks.
* **Timing-Safe Responses**: The authentication service executes password verification on dummy hashes even if the user is not found to prevent timing-based user enumeration.

## 2. Two-Layer Role-Based Access Control (RBAC)

Authorization is strictly enforced on **both layers**:
1. **Route Guard Middleware**: Validates role hierarchy (`require_admin`, `require_manager_or_above`).
2. **Service Layer Resource Authorization**: Validates whether the authenticated user has ownership rights over the specific record.

### Permissions Matrix

| Capability | Sales Agent | Team Leader | Manager | Admin |
| :--- | :---: | :---: | :---: | :---: |
| View Assigned Leads | ✅ | ✅ | ✅ | ✅ |
| View Team Leads | ❌ | ✅ | ✅ | ✅ |
| View All Leads | ❌ | ❌ | ✅ | ✅ |
| Reassign Leads | ❌ | ✅ (Team) | ✅ | ✅ |
| Soft Delete Records | ❌ | ❌ | ✅ | ✅ |
| Management Reports | ❌ | Limited | ✅ | ✅ |
| Manage Users & Roles | ❌ | ❌ | ❌ | ✅ |
| Google Sheets Sync | ❌ | ❌ | ❌ | ✅ |
| View Audit Logs | ❌ | ❌ | ✅ | ✅ |

## 3. Defense Against OWASP Top 10

* **SQL Injection**: Prevented via parameterized queries using SQLAlchemy ORM.
* **Cross-Site Scripting (XSS)**: Handled via React's default auto-escaping and strict Content-Security-Policy (CSP) headers.
* **Broken Object Level Authorization (IDOR)**: Service-layer ownership verification on all resource fetch/mutation endpoints.
* **Security Headers**: `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Strict-Transport-Security`, `Referrer-Policy`.
