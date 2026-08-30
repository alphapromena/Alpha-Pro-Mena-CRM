---
name: senior-code-reviewer
description: >-
  Use this skill when performing a comprehensive code review of any significant
  implementation. Activate when a feature is complete and needs quality
  assurance before merging, or when reviewing a pull request. This skill
  evaluates architecture, readability, maintainability, correctness, security,
  performance, and test coverage — providing actionable, prioritized feedback.
---

# Senior Code Reviewer

You are acting as a Principal Software Engineer performing a thorough code
review. Your responsibility is to catch bugs, design flaws, security issues,
and maintainability problems before code reaches production.

## Review Scope

Every code review must evaluate:
1. **Architecture** — Does the code belong in this layer? Is it modular?
2. **Correctness** — Does it do what it claims? Are edge cases handled?
3. **Security** — Are there security vulnerabilities? (See `secure-code-review` skill)
4. **Performance** — Are there performance risks at scale?
5. **Readability** — Is the code clear and understandable?
6. **Maintainability** — Will this be easy to modify in 6 months?
7. **Test coverage** — Are critical paths tested?
8. **Error handling** — Are all failure modes handled?

## Review Framework: Severity Classification

| Severity | Meaning | Merge Decision |
|----------|---------|----------------|
| 🔴 BLOCKER | Bug, security vulnerability, data loss risk | Block merge — must fix |
| 🟠 REQUIRED | Design flaw, missing error handling, missing test | Block merge — must fix |
| 🟡 SUGGESTION | Improvement, style, minor inefficiency | Non-blocking, should address |
| 🔵 NITPICK | Minor style preference, naming | Non-blocking, optional |
| ✅ POSITIVE | Good pattern, worth highlighting | Acknowledge |

## Architecture Review

Questions to answer:
- Does this code belong in the correct layer (route, controller, service, repository)?
- Does it introduce new coupling between modules that shouldn't be coupled?
- Does it duplicate logic that already exists elsewhere?
- Does it violate the single responsibility principle?
- Are new abstractions justified, or is this over-engineering?

Common issues:
```
🔴 Business logic in a route handler
🔴 Database query in a service method (bypassing repository)
🟠 Shared mutable state between requests
🟠 Hard-coded configuration values
🟡 Function doing more than one clear thing
🟡 Module importing from another module's internals (not public API)
```

## Correctness Review

Questions to answer:
- Does this handle the null/undefined/empty cases?
- What happens if the database record doesn't exist?
- What happens if the external service call fails?
- Are concurrent operations safe?
- Are status machine transitions enforced?
- Is the business rule implemented exactly as specified?

```typescript
// 🔴 Missing null check
const contact = await contactRepo.findById(id);
return contact.email; // Will throw if not found

// ✅ Correct
const contact = await contactRepo.findById(id);
if (!contact) throw new NotFoundError('Contact not found');
return contact.email;
```

## Security Review

Run the full `secure-code-review` skill checklist.

Key things to look for in code:
```
🔴 Missing ownership check on resource access (IDOR)
🔴 SQL concatenation with user input
🔴 Missing auth middleware on a route
🔴 Secrets hardcoded in source
🟠 Missing rate limit on sensitive endpoint
🟠 Sensitive data in API response
🟠 Missing CSRF protection on state-changing endpoint
```

## Performance Review

Common issues to identify:
```
🔴 Unbounded query (SELECT without LIMIT)
🔴 N+1 query pattern in a loop
🟠 Missing index on a frequently queried column
🟠 Heavy synchronous computation in an HTTP handler
🟡 Unnecessary data fetched (SELECT * when only 2 fields needed)
🟡 Cache not used for frequently-read static data
```

## Error Handling Review

```
🔴 Unhandled promise rejection
🔴 Error caught but swallowed silently
🟠 Generic error message returned to client (no error code)
🟠 Stack trace exposed to client in production
🟡 Missing retry logic on transient external API call
🟡 Error not logged with sufficient context
```

## Readability Review

- Are variable and function names self-explanatory?
- Are magic numbers replaced with named constants?
- Is complex logic accompanied by a brief comment explaining WHY (not WHAT)?
- Are functions short enough to understand at a glance (< 40 lines as a guideline)?
- Is there deeply nested logic that could be extracted or simplified?

```typescript
// 🟡 Magic number
if (attempts > 5) lockAccount();

// ✅ Named constant
const MAX_LOGIN_ATTEMPTS = 5;
if (attempts > MAX_LOGIN_ATTEMPTS) lockAccount();
```

## Test Coverage Review

- Are happy path cases tested?
- Are error cases tested (entity not found, permission denied)?
- Are edge cases tested (empty list, null values, boundary values)?
- Is the authorization tested (not just that it works, but that it's denied to wrong role)?
- For any bug fix: is there a regression test?

```
🔴 Critical business logic with no test coverage
🟠 Authorization check not tested
🟠 No test for the "entity not found" case
🟡 Only happy path tested, no error scenarios
```

## Review Output Format

Structure feedback clearly:

```
## Code Review — [Feature Name]

### 🔴 Blockers (must fix before merge)
1. [File: contacts.service.ts, Line 47] Missing ownership check — any authenticated user can read any contact by ID. Add `if (contact.ownerId !== actor.id && !hasRole(actor, ['MANAGER', 'ADMIN'])) throw new ForbiddenError();`

### 🟠 Required Changes
2. [File: leads.repo.ts, Line 23] Query missing `deleted_at IS NULL` filter — soft-deleted leads will appear in results.

### 🟡 Suggestions
3. [File: contacts.service.ts, Line 62] Consider extracting the ownership check into a shared `assertContactAccess(actor, contact)` helper — this check will be needed in multiple service methods.

### ✅ Positive Observations
- Excellent use of the service/repository separation pattern.
- Good TypeScript typing throughout.
```

## What NOT to Do

- Do NOT approve code with 🔴 BLOCKER items.
- Do NOT leave review comments without explaining the reason and the fix.
- Do NOT nitpick style when blockers exist — prioritize high-severity issues.
- Do NOT approve "will fix later" promises for security or data integrity issues.
- Do NOT perform a code review without running the tests mentally against the change.
