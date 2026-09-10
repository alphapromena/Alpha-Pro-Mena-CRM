# Authentication & Email System Audit

**Branch:** `fix/auth-email-audit`
**Date:** 2026-09-10
**Scope:** FastAPI backend (`backend/app`), React frontend (`frontend/src`), Vercel serverless entrypoint (`api/index.py`), Neon Postgres.
**Method:** Full read of the auth and email call paths, cross-checked against the production log evidence supplied in the brief. Two findings were reproduced locally against a real database rather than inferred; those are marked REPRODUCED.

This document is the pre-change record. It lists what is broken. Fixes land in the commits that follow.

---

## Severity summary

| ID | Severity | Issue | Primary location |
|----|----------|-------|------------------|
| C1 | Critical | Email is never delivered in production, but the API reports success | `backend/app/core/email.py:55` |
| C2 | Critical | Account lockout never engages; the failed-attempt counter is rolled back | `backend/app/database.py:89` |
| C3 | Critical | A live password literal ships in the public frontend bundle | `frontend/src/features/auth/LoginPage.tsx:22` |
| C4 | Critical | Bootstrap failure inside auto-migrate rolls back the schema migration | `backend/app/core/auto_migrate.py:108` |
| H1 | High | `FRONTEND_URL` defaults to localhost and is never validated in production | `backend/app/config.py:75` |
| H2 | High | Email send failures are discarded by both callers | `backend/app/auth/service.py:210` |
| H3 | High | Migrations run on every single request | `backend/app/database.py:86` |
| H4 | High | Resend cooldown reveals whether an account exists | `backend/app/auth/service.py:290` |
| H5 | High | Seven employees' names, emails and roles are published to anonymous visitors | `frontend/src/features/auth/LoginPage.tsx:85` |
| M1 | Medium | The 401 flood: anonymous page loads fire `/auth/me` then `/auth/refresh` | `frontend/src/App.tsx:21` |
| M2 | Medium | Logout requires a valid access token, so an expired session cannot log out | `backend/app/auth/router.py:93` |
| M3 | Medium | Cookie deletion omits the attributes the cookies were set with | `backend/app/auth/router.py:95` |
| M4 | Medium | The dev mailbox endpoint is reachable in production if `APP_DEBUG` is ever set | `backend/app/auth/router.py:296` |
| M5 | Medium | The bootstrap-password guard compares against a stale hardcoded literal | `backend/app/auth/service.py:169` |
| M6 | Medium | Email addresses are interpolated into links without URL encoding | `backend/app/core/email.py:96` |
| M7 | Medium | `smtplib` blocks the event loop inside async handlers | `backend/app/core/email.py:80` |
| M8 | Medium | In-memory rate limits reset on every serverless invocation | `backend/app/core/ratelimit.py:26` |
| M9 | Medium | The verify page never reads the `email` query parameter the backend sends | `frontend/src/features/auth/VerifyEmailPage.tsx:16` |
| L1 | Low | The verify-email endpoint has no rate limit | `backend/app/auth/router.py:228` |
| L2 | Low | The dev mailbox is per-process and meaningless on serverless | `backend/app/core/email.py:21` |
| L3 | Low | Expired-token cleanup writes are rolled back by the same pattern as C2 | `backend/app/auth/service.py:245` |
| L4 | Low | Dead bearer-token-from-localStorage path in the import widget | `frontend/src/components/leads/DragDropDataImport.tsx:126` |
| L5 | Low | The reset page only discovers an expired token after the form is filled | `frontend/src/features/auth/ResetPasswordPage.tsx:36` |

---

## Critical

### C1 — Email is never delivered in production, and the API reports success anyway

`backend/app/core/email.py:55`

```python
if not settings.smtp_configured or settings.app_env in ("development", "test"):
    _DEV_MAILBOX.append(msg_record)
    ...
    logger.info("email.mock_delivered", ...)
    return True
```

The `smtp_configured` property at `backend/app/config.py:112` is true only when `SMTP_HOST` is set. No SMTP variables exist on Vercel, so every production send takes the mock branch, appends to an in-process list, and returns `True`. Production logs confirm it: `email.mock_delivered` is emitted for `POST /api/v1/auth/resend-verification`.

The caller chain then reports success to the user. Nobody receives a verification email, a password reset, or a first-login link, and no error is ever surfaced. Every account recovery path in the product is silently dead.

### C2 — Account lockout never engages (REPRODUCED)

`backend/app/database.py:89` combined with `backend/app/auth/service.py:414`.

The failed-attempt recorder increments the counter and flushes, which writes inside the transaction without committing:

```python
async def _record_failed_attempt(self, user: User) -> None:
    user.login_attempts = (user.login_attempts or 0) + 1
    ...
    await self.db.flush()
```

The login endpoint then raises `UnauthorizedError`. That exception propagates into the `get_db` dependency, which does:

```python
except Exception:
    await session.rollback()
    raise
```

The rollback discards the increment. The counter never advances, the locked flag is never set, and the maximum-attempts threshold is unreachable.

Reproduced against a file-backed SQLite database driving the real endpoint through the real dependency. After seven wrong-password requests:

```
7 bad-password attempts -> [401, 401, 401, 401, 401, 429, 429]

PERSISTED login_attempts = 0
PERSISTED is_locked      = False
PERSISTED locked_until   = None
```

The only thing standing between an attacker and unlimited password guessing is the in-memory rate limiter, which resets per serverless invocation (M8). Brute-force protection is effectively absent in production.

### C3 — A live password literal ships in the public frontend bundle

`frontend/src/features/auth/LoginPage.tsx:22`

The password field's initial state is a hardcoded plaintext account password. It is compiled into the client bundle Vercel serves to anonymous visitors, and because it is the field's initial state the login form arrives pre-filled and one click from submission. Line 21 does the same for a named employee's corporate email address.

The value is deliberately not reproduced in this document. Treat the credential as compromised and rotate it.

### C4 — A bootstrap failure rolls back the schema migration

`backend/app/core/auto_migrate.py:108`

The migration runner performs DDL, the Alembic stamp, and the team bootstrap, then commits once at the end. Any exception in the bootstrap step reaches the handler at `:132`, which rolls the whole transaction back and discards schema changes that had nothing to do with the failure.

This caused both of today's production outages: first a primary-key violation in the stamp step, then a missing bootstrap password. In each case a failure in one concern destroyed the work of another.

The stamp half is already fixed on this branch by the cherry-picked stamp helper, which no longer writes a colliding row. The transaction-boundary half is addressed in commit C.

---

## High

### H1 — The frontend URL defaults to localhost and is never validated

`backend/app/config.py:75` declares the default as `http://localhost:5173`. The production validator at `:170` checks the app secret, the JWT secret and the database URL, but not this.

`backend/app/core/email.py:96` and `:126` build every verification and reset link from it. If the variable is unset on Vercel, every link in every email points at the recipient's own machine. Because of C1 nobody sees these links today, so fixing delivery without fixing this would ship broken links to real users on day one.

### H2 — Email send failures are discarded

`backend/app/auth/service.py:210` and `:341` both await a send function that returns a boolean and then ignore the result:

```python
await send_verification_email(
    to_email=user.email,
    recipient_name=user.first_name,
    token=raw_token,
)
```

Even once a real provider is wired in, a transport failure would still surface to the user as success. The token has already been flushed to the database at that point, so the account ends up holding a token that was never delivered.

### H3 — Migrations run on every request

`backend/app/database.py:86` calls the migration entrypoint inside `get_db`, which is a dependency of essentially every endpoint. The module-level completion flag limits this to once per process, but serverless processes are short-lived and numerous, so a large share of requests pay for a migration attempt and, more importantly, are exposed to its failure modes. A migration concern should not sit in the request path at all.

### H4 — The resend cooldown reveals whether an account exists

`backend/app/auth/service.py:290` and `:328`.

For an unknown address the resend path returns silently and the endpoint answers with the neutral "if an account exists" message. For a known, unverified address inside the cooldown window it raises a rate-limit error, which the client receives as HTTP 429 with a specific message. The two responses are trivially distinguishable, so the endpoint confirms which addresses are registered. The password reset request has the identical shape.

### H5 — The team roster is published to anonymous visitors

`frontend/src/features/auth/LoginPage.tsx:85` defines a quick-accounts array holding seven real employees' names, corporate email addresses and role assignments, rendered as clickable quick-login buttons at `:495`. Anyone who opens the login page receives a usable org chart and a list of valid usernames to target.

Removing this changes what users see on the login page, so it is raised as an open question rather than changed unilaterally. See the end of this document.

---

## Medium

### M1 — The 401 flood

Three things combine.

`frontend/src/App.tsx:21` fetches the current user on every mount with no session guard:

```tsx
useEffect(() => {
  fetchMe();
}, []);
```

`frontend/src/lib/apiClient.ts:14` lists the endpoints that must not trigger a refresh attempt, and the current-user endpoint is absent from it:

```ts
const NO_REFRESH = ['/auth/login', '/auth/refresh', '/auth/logout'];
```

So an anonymous load calls the current-user endpoint, receives 401, and the client responds by posting to the refresh endpoint, which also 401s. That is the exact pair visible in the logs.

It is amplitude, not recursion. The refresh call bypasses the interceptor by using raw `fetch`, and the retry is one-shot, so there is no runaway loop. The volume comes from repetition: the notification poller at `frontend/src/components/layout/TopNav.tsx:36` fires every sixty seconds and is never stopped when the session expires; the language and theme toggles on the login page itself call authenticated endpoints; and logout at `frontend/src/store/authStore.ts:98` navigates with a full page reload, remounting the app and starting the cycle again.

### M2 — Logout requires a valid access token

`backend/app/auth/router.py:93` declares logout with a current-user dependency. Once the fifteen-minute access token has expired the endpoint returns 401 and the cookie-clearing code never runs, so the stale cookies stay in the browser. Logout is exactly the operation that must work when the session is already broken.

### M3 — Cookie deletion omits the attributes the cookies were set with

`backend/app/auth/router.py:95` and `:288` delete by name and path only. The cookies were set at `:43` with `httponly`, `samesite=lax` and, in production, `secure`. A deletion cookie whose attributes do not match may be treated as a different cookie, leaving the original in place.

### M4 — The dev mailbox endpoint has a debug escape hatch

`backend/app/auth/router.py:296`:

```python
if settings.app_env not in ("development", "test") and not settings.app_debug:
    return {"error": "Not available in production"}
```

Two problems. The condition passes if `APP_DEBUG` is ever set in production, which would expose raw verification and reset tokens for every recent recipient. And the refusal is a 200 response with an error body rather than a 404, so the endpoint's existence is confirmed to anyone probing.

### M5 — The bootstrap-password guard compares against a stale literal

`backend/app/auth/service.py:169` and `:360` reject a new password by comparing it to a hardcoded string rather than to the configured bootstrap password. Since the bootstrap password moved to an environment variable the guard no longer matches the real value, so it protects nothing while implying it does.

### M6 — Email addresses are not URL encoded into links

`backend/app/core/email.py:96` and `:126` interpolate the raw address into a query string. Any address containing a plus sign, which is common and valid, produces a link the browser decodes as a space.

### M7 — Blocking SMTP inside async handlers

`backend/app/core/email.py:80` opens a synchronous `smtplib` connection with a ten-second timeout directly inside an async function, blocking the event loop for the duration.

### M8 — In-memory rate limits reset per invocation

`backend/app/core/ratelimit.py:26` constructs the limiter with default in-memory storage. Each serverless invocation may be a fresh process, so the counters start from zero. The durable protection is the database-backed cooldown in the service layer, which does survive; the decorator limits should be understood as best-effort only.

### M9 — The verify page ignores the email parameter

The backend sends both a token and an email parameter. `frontend/src/features/auth/VerifyEmailPage.tsx:16` seeds its email state from the auth store instead of the URL, and a user arriving from an email link has no session. No email input is rendered and the setter is never called, so when verification fails the resend button dead-ends telling the user to specify an address they cannot enter.

---

## Low

- **L1** `backend/app/auth/router.py:228` has no rate limit on verify-email, unlike its neighbours. Tokens are 32 random bytes so guessing is impractical, but the asymmetry is unintended.
- **L2** `backend/app/core/email.py:21` keeps the dev mailbox in a module-level list. On serverless each invocation has its own, so it cannot be relied on even in preview environments.
- **L3** `backend/app/auth/service.py:245` and `:385` clear an expired token and flush, then raise. The same rollback described in C2 discards the cleanup. Harmless, since the token is already expired, but it is the same latent pattern.
- **L4** `frontend/src/components/leads/DragDropDataImport.tsx:126` reads a bearer token from local storage that nothing in the codebase ever writes, and omits credentials from the request. Dead architecture from a pre-cookie auth model.
- **L5** `frontend/src/features/auth/ResetPasswordPage.tsx:36` does not probe the token on mount, so an expired link is only discovered after the user has composed and confirmed a new password.

---

## What was checked and found correct

Recording these so the next reader does not re-derive them.

- Verification and reset tokens are 32 random bytes from `secrets.token_urlsafe`, and only the SHA-256 hash is stored. The raw token goes in the email and is never persisted. See `backend/app/core/security.py:125` and `:138`.
- One-time use is enforced on both flows by nulling the stored hash on success, at `backend/app/auth/service.py:253` and `:393`.
- Expiry is enforced on both flows, with naive timestamps coerced to UTC, at `:239` and `:380`.
- Login is timing-safe against enumeration: an unknown address still runs a real bcrypt verification against a dummy hash, at `backend/app/auth/service.py:66`.
- The forced-password-change guard is enforced server-side, not just in the UI, at `backend/app/auth/dependencies.py:60`.
- Cookies are HttpOnly, and secure is correctly bound to the production environment at `backend/app/auth/router.py:43`.
- The routes the email links point at exist with exactly the expected paths, at `frontend/src/router.tsx:76` and `:88`.
- No token is persisted to browser storage by the auth code; the client is cookie-based with credentials included.

---

## Addendum: found while fixing, not while auditing

Two further defects surfaced during implementation. Both are fixed in the commits on
this branch.

### A1 — A locked account leaked a password oracle (High)

`backend/app/auth/service.py`, login path.

The lockout check ran after the password check. A locked account therefore answered
401 for a wrong password and 423 for the correct one. An attacker who had already
tripped the lockout could keep guessing and read the status code to confirm a hit, so
locking the account made the credential easier to find rather than harder.

Lockout is now resolved before the credential result is used, and both cases answer
423 identically. There is a regression test for it.

### A2 — The lockout comparison crashed on a naive timestamp (High, latent)

Comparing `locked_until` to an aware "now" raises `TypeError: can't compare
offset-naive and offset-aware datetimes` when the backend returns a naive value. The
token paths already coerced to UTC inline; the lockout path did not.

This was unreachable while C2 was live, because the account never actually locked.
Fixing C2 made it reachable, so it would have become a 500 on every login attempt
against a locked account. Caught by the new lockout test, then fixed with a shared
coercion helper.

---

## Resolved question

H5 was raised for a decision because deleting the quick-login buttons is a visible
product change beyond the flows in scope. The maintainer chose full removal, and it is
done: the roster array, the button rows and their handler are gone, confirmed against a
production build.

C3, the pre-filled password, was fixed regardless, because emptying a form field is not
a feature change and the credential was already exposed.

One deliberate behaviour change inside the flows in scope was also confirmed. A repeat
forgot-password or resend-verification request inside the cooldown now returns the same
neutral message as the first rather than a 429 naming the remaining seconds. The email
is still suppressed. The countdown answered only for addresses that exist, which is what
made it an oracle.

## Still open

**H3, migrations in the request path**, is unchanged. `get_db` still calls the migration
entrypoint on every request. The per-process flag limits the cost, but serverless
processes are numerous and short-lived, so a large share of requests still carry the
exposure. Moving it to startup and the admin endpoint is the right fix and is a larger
behavioural change than this branch should carry.

**The credential exposed by C3 has been served publicly** and must be rotated. Removing
it from the source does not undo the distribution.
