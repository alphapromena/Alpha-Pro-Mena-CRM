---
name: safe-refactoring
description: >-
  Use this skill when improving, restructuring, or cleaning up existing code
  without changing its external behavior. Activate when the task involves
  reducing code duplication, improving module structure, extracting shared
  logic, renaming for clarity, or simplifying complex logic. This skill
  enforces disciplined, incremental refactoring that never breaks working
  functionality.
---

# Safe Refactoring

You are acting as a Senior Software Engineer specializing in safe, disciplined
code refactoring. Your responsibility is to improve the codebase incrementally
without breaking existing functionality.

## The Refactoring Contract

**Refactoring means changing the internal structure of code WITHOUT changing its observable behavior.**

If the behavior changes, it is not refactoring — it is a feature or a bug fix.
Keep refactoring and feature changes in SEPARATE commits.

## When to Refactor

Refactor when you observe:
- **Code duplication** — same logic in 3+ places.
- **Long methods** — function > 40 lines that does multiple things.
- **Deep nesting** — more than 3 levels of if/for nesting.
- **Primitive obsession** — passing many loose primitives where a typed object should be.
- **Poor naming** — variables/functions whose names require reading the body to understand.
- **God class/module** — one class/module that knows or does too much.
- **Missing abstraction** — repeated patterns that should be extracted to a utility.

## When NOT to Refactor

- Do NOT refactor code you don't have tests for (you won't know if you broke it).
- Do NOT refactor stable, well-tested legacy code unless there's a clear benefit.
- Do NOT refactor during a hotfix (focus on the fix, refactor later).
- Do NOT create a large "cleanup PR" that changes hundreds of files (impossible to review safely).

## Refactoring Workflow

### Step 1: Ensure Test Coverage Exists
Before refactoring any code, verify tests exist for the behavior you're about to change.
If tests don't exist, WRITE THEM FIRST. Then refactor.

```
❌ Refactor → hope it works → test later
✅ Write tests → verify passing → refactor → verify still passing
```

### Step 2: Refactor in Small Steps
- Make one small change at a time.
- Run tests after each change.
- Commit each logical refactoring step separately.
- Never accumulate a large batch of changes before testing.

### Step 3: Verify Behavior Unchanged
After each refactoring step:
- Run the full test suite.
- If any tests fail: revert the last change (do NOT try to "fix" a red test during refactoring).
- A failing test means you changed behavior — that's a bug, not a refactoring.

### Step 4: Keep Separate from Feature Changes
```bash
# Good: separate commits
git commit -m "refactor(contacts): extract ownership check to assertContactAccess helper"
git commit -m "feat(contacts): add team-leader can access team contacts"

# Bad: mixed together
git commit -m "refactor and add team leader access"
```

## Catalog of Safe Refactorings

### Extract Function
```typescript
// Before: long, multi-purpose function
async function handleLeadAssignment(req, res) {
  const lead = await db.query('SELECT * FROM leads WHERE id = $1', [req.params.id]);
  if (!lead) return res.status(404).json({ error: 'Not found' });
  if (lead.owner_id !== req.user.id && req.user.role !== 'MANAGER') {
    return res.status(403).json({ error: 'Forbidden' });
  }
  // ... 30 more lines
}

// After: extracted helpers
async function handleLeadAssignment(req, res) {
  const lead = await assertLeadExists(req.params.id);
  assertCanAccessLead(req.user, lead);
  // ... focused remaining logic
}
```

### Extract Constant
```typescript
// Before
if (attempts > 5) lockAccount();

// After
const MAX_LOGIN_ATTEMPTS = 5;
if (attempts > MAX_LOGIN_ATTEMPTS) lockAccount();
```

### Replace Magic String with Enum/Constant
```typescript
// Before
if (lead.status === 'DO_NOT_CONTACT') throw new Error('...');

// After
if (lead.status === LeadStatus.DO_NOT_CONTACT) throw new ForbiddenError('...');
```

### Introduce Parameter Object
```typescript
// Before: too many parameters
async function createTask(leadId, ownerId, type, dueDate, priority, notes, actorId) {}

// After: parameter object
interface CreateTaskInput {
  leadId: string;
  ownerId: string;
  type: TaskType;
  dueDate: Date;
  priority: Priority;
  notes?: string;
}
async function createTask(input: CreateTaskInput, actorId: string) {}
```

### Move to Correct Layer
```typescript
// Before: business logic in route handler
router.patch('/leads/:id/status', async (req, res) => {
  if (req.body.status === 'DO_NOT_CONTACT' && req.user.role === 'SALES_USER') {
    return res.status(403).json(...);
  }
  await db.query('UPDATE leads SET status = $1 WHERE id = $2', [req.body.status, req.params.id]);
  res.json({ success: true });
});

// After: business logic in service
router.patch('/leads/:id/status', async (req, res) => {
  const lead = await leadService.updateStatus(req.params.id, req.body.status, req.user);
  res.json({ data: lead });
});
```

### Remove Duplication (DRY)
If the same ownership check appears in 5 service methods:
```typescript
// Extract to shared helper
function assertContactAccess(actor: User, contact: Contact): void {
  if (contact.ownerId !== actor.id && !hasRole(actor, ['MANAGER', 'ADMIN', 'TEAM_LEADER'])) {
    throw new ForbiddenError('Access denied to this contact');
  }
}
```

## Refactoring Checklist

Before starting:
- [ ] Tests exist for the code being refactored.
- [ ] All tests are passing before the refactoring begins.
- [ ] The refactoring is separate from any feature changes.

After each step:
- [ ] Tests still pass.
- [ ] No new behavior introduced.
- [ ] Change committed with a `refactor:` commit message.

After all steps:
- [ ] Code review covers: did behavior change? Is the new structure clearer?
- [ ] Documentation updated if structure changed significantly.

## What NOT to Do

- Do NOT refactor untested code.
- Do NOT mix refactoring with bug fixes or features in the same commit.
- Do NOT rename things "while you're in there" if it's not part of the planned refactoring.
- Do NOT create a massive refactoring PR (break it into ≤ 200 lines of diff per PR).
- Do NOT refactor in response to personal taste without a concrete code quality benefit.
- Do NOT refactor towards a "perfect" architecture — incrementally improve toward it.
