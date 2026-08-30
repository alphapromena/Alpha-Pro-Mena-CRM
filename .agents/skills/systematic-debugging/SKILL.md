---
name: systematic-debugging
description: >-
  Use this skill whenever a bug, unexpected behavior, error, or system
  malfunction needs to be investigated. Activate before attempting any fix.
  This skill enforces a disciplined reproduce → investigate → identify root
  cause → fix → regression test workflow. It prevents random trial-and-error
  changes that can introduce new bugs or mask the real problem.
---

# Systematic Debugging

You are acting as a Senior Software Engineer with expertise in methodical
debugging. Your responsibility is to find and fix the root cause of issues, not
to apply random patches until the symptom disappears.

## The Non-Negotiable Debugging Workflow

**Always follow this exact sequence. Never skip steps.**

```
1. REPRODUCE  →  2. INVESTIGATE  →  3. ROOT CAUSE  →  4. FIX  →  5. REGRESSION TEST
```

---

## Step 1: REPRODUCE

Before touching any code, reproduce the problem reliably:

- What is the exact sequence of steps that produces the bug?
- On which data, input, or state does it occur?
- Does it occur consistently or intermittently?
- In which environment does it occur? (dev only? staging? production?)
- What is the actual behavior vs. expected behavior?

**Do not proceed to Step 2 until you can reproduce the bug on demand.**

If you cannot reproduce it:
- Add detailed logging at the suspected failure point.
- Gather more information from error logs, monitoring, or user reports.
- Narrow down the triggering conditions.

---

## Step 2: INVESTIGATE

With a reproducible case, gather information:

### Check Error Logs
- What error message is logged server-side?
- What is the full stack trace?
- What was the request context (user ID, entity ID, request body)?

### Check Network Requests (Frontend)
- What HTTP request was made? (method, URL, headers, body)
- What response was returned? (status code, body)
- Is the issue on the frontend side or backend side?

### Check Database State
- What is the current state of the relevant records?
- Are constraints being violated?
- Are there related records in unexpected states?

### Narrow Down the Layer
Answer: in which layer does the failure occur?
- Route/middleware
- Controller (request parsing, validation)
- Service (business logic)
- Repository (data access)
- Database (constraint, query)
- Frontend (state, rendering, API call)
- External service (Google Sheets, email)

### Binary Search the Code
When the failing layer is identified:
- Find the earliest point where the wrong result/state is observable.
- Add logging/assertions to narrow down further.
- Work from input → output, not output → input.

---

## Step 3: IDENTIFY ROOT CAUSE

A root cause is the specific, underlying reason for the bug — not just a symptom.

**Ask "why" 5 times to reach the root cause:**

Example:
- Bug: Contact assignment fails.
- Why? The service throws "Contact not found".
- Why? The query filters by `deleted_at IS NULL` but the contact was soft-deleted.
- Why? The admin soft-deleted the contact, but the UI still shows it.
- Why? The frontend cache was not invalidated after deletion.
- Root cause: Cache invalidation missing after soft-delete operation.

**Do NOT fix the symptom.** Fix the root cause.

---

## Step 4: FIX

With the root cause identified:

1. Design the fix — what is the minimal, correct change?
2. Consider side effects — will this change break anything else?
3. Consider edge cases — are there related cases not covered by this fix?
4. Implement the fix.
5. Manually verify the bug is fixed using the reproduction steps from Step 1.
6. Verify no regression in related functionality.

### Fix Quality Rules
- Prefer the minimal correct fix over a sweeping refactor.
- Do NOT add "just in case" defensive code without understanding the cause.
- Do NOT apply random code changes until the error goes away.
- If the fix requires a refactor, note it and plan it separately — fix the bug first.

---

## Step 5: REGRESSION TEST

After fixing, write a test that:
1. Reproduces the exact failing scenario.
2. Verifies the correct behavior.
3. Would have caught this bug before it reached production.

```typescript
// Regression test — always label regression tests clearly
it('regression: contact assigned after soft-delete does not appear in active list', async () => {
  // Arrange
  const contact = await createTestContact();
  await contactService.softDelete(contact.id, adminUser.id);

  // Act
  const contacts = await contactService.list({ includeDeleted: false });

  // Assert
  expect(contacts.data.find((c) => c.id === contact.id)).toBeUndefined();
});
```

**Commit the regression test AND the fix in the same commit.**

---

## Logging Guidance

When investigating, add targeted temporary logging:

```typescript
// Temporary investigation log — remember to remove before commit
logger.debug('[DEBUG] leadService.assignLead called', {
  leadId,
  assigneeId,
  currentOwnerId: lead.ownerId,
  actorRole: actor.role,
});
```

**Remove all temporary debug logs before committing the fix.**

---

## Common Bug Patterns in CRM Systems

| Symptom | Likely Layer | Common Root Cause |
|---------|-------------|-------------------|
| "Not found" for existing record | Repository | Missing `deleted_at IS NULL` filter |
| 403 Forbidden unexpectedly | Service | Incorrect ownership check |
| Stale data shown in UI | Frontend | Cache not invalidated after mutation |
| Duplicate records created | Service | Race condition, missing unique constraint |
| Automation not triggering | Background job | Event not emitted, job not picked up |
| Wrong audit log actor | Service | Actor context not passed correctly |
| N+1 queries | Repository | Missing eager loading |
| Login bypass | Middleware | Auth middleware not applied to route |

---

## What NOT to Do

- Do NOT add console.log in random places without a hypothesis.
- Do NOT change code hoping it "might" fix the problem.
- Do NOT fix the symptom without understanding the root cause.
- Do NOT commit debug logging.
- Do NOT skip the regression test after a fix.
- Do NOT merge a fix that cannot be explained in one sentence of root cause.
