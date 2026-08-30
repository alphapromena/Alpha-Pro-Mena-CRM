---
name: test-driven-development
description: >-
  Use this skill when writing tests for any feature, service, API endpoint, or
  business rule. Activate when the task involves unit tests, integration tests,
  API tests, or regression tests. Also activate when debugging a bug to ensure
  a regression test is written before the fix. Enforces test-first thinking
  and ensures critical business rules have verifiable test coverage.
---

# Test-Driven Development

You are acting as a Senior Software Engineer with deep commitment to test-driven
development. Your responsibility is to ensure all critical code paths are tested
and that tests serve as living documentation of system behavior.

## Testing Philosophy

- Write tests that describe **behavior**, not implementation details.
- Tests should break when behavior changes, not when refactoring internals.
- Aim for high confidence, not 100% coverage. Prioritize critical paths.
- A test that is hard to write usually signals a design problem.

## Test Types & When to Use Each

### Unit Tests
- Test a single function or class in isolation.
- Mock all external dependencies (DB, API calls, time).
- Fast (< 10ms each), numerous.
- Use for: service logic, validation functions, utility functions, business rules.

### Integration Tests
- Test multiple units working together.
- Use a real test database (not mocked).
- Test the service + repository layer together.
- Use for: data persistence, database constraints, transaction behavior.

### API (E2E API) Tests
- Test full HTTP request → response cycle.
- Start the actual server (or use supertest).
- Use a real test database, clean between tests.
- Test for: authentication, authorization, validation responses, business outcomes.
- Most valuable test type for a CRM — covers the most ground.

### Browser E2E Tests
- See `playwright-e2e-testing` skill.

## Test Framework Setup (Node.js / TypeScript)

```typescript
// Recommended stack:
// Test runner: Vitest (fast, TypeScript-native) or Jest
// HTTP testing: Supertest
// Mocking: Vitest mock utilities or jest.mock
// DB setup: Test database + database-cleaner or test transactions

// vitest.config.ts
export default defineConfig({
  test: {
    globals: true,
    environment: 'node',
    setupFiles: ['./tests/setup.ts'],
    coverage: {
      reporter: ['text', 'html'],
      exclude: ['**/node_modules/**', '**/tests/**'],
    },
  },
});
```

## Test Structure (AAA Pattern)

Every test follows: **Arrange → Act → Assert**

```typescript
describe('LeadService', () => {
  describe('assignLead', () => {
    it('assigns lead to a sales user and creates audit log entry', async () => {
      // Arrange
      const manager = await createTestUser({ role: 'MANAGER' });
      const salesUser = await createTestUser({ role: 'SALES_USER' });
      const lead = await createTestLead({ ownerId: null });

      // Act
      await leadService.assignLead({
        leadId: lead.id,
        assigneeId: salesUser.id,
        actorId: manager.id,
      });

      // Assert
      const updatedLead = await leadRepo.findById(lead.id);
      expect(updatedLead.ownerId).toBe(salesUser.id);

      const auditEntry = await auditLogRepo.findLastForEntity('lead', lead.id);
      expect(auditEntry.action).toBe('lead.assigned');
      expect(auditEntry.actorId).toBe(manager.id);
      expect(auditEntry.newValue.ownerId).toBe(salesUser.id);
    });
  });
});
```

## Critical CRM Test Scenarios

### Authentication Tests
- [ ] Valid credentials returns a session/token.
- [ ] Invalid credentials returns 401.
- [ ] After 5 failed attempts, account is locked.
- [ ] Unauthenticated request to protected endpoint returns 401.

### Authorization Tests
- [ ] Sales user cannot access another user's leads.
- [ ] Sales user cannot access manager-only endpoints.
- [ ] Manager can access all leads.
- [ ] Admin can manage users; sales user cannot.
- [ ] IDOR: changing a resource ID in the request to another user's resource returns 403.

### Lead Status Machine Tests
- [ ] New lead starts in NEW status.
- [ ] Valid status transitions succeed.
- [ ] Invalid status transitions are rejected with 422.
- [ ] Status change creates an audit log entry.
- [ ] DNC contact cannot have outbound activities created (blocked with appropriate error).

### Duplicate Detection Tests
- [ ] Importing a contact with an existing email is flagged as duplicate.
- [ ] Importing a contact with a normalized matching phone is flagged as duplicate.
- [ ] Confirmed duplicates are linked to the canonical record.

### Task Automation Tests
- [ ] Logging a call with NO_ANSWER outcome creates a RECALL task.
- [ ] Duplicate automation execution is prevented (idempotency).
- [ ] Overdue tasks appear in the overdue task list.

### Data Integrity Tests
- [ ] Soft-deleted contacts do not appear in list responses.
- [ ] Activities are retained after contact soft-deletion.
- [ ] Audit logs are append-only (update/delete on audit_logs is rejected).

## API Test Pattern (Supertest)

```typescript
describe('POST /api/v1/leads/:id/status', () => {
  it('returns 403 when a sales user tries to set DNC status', async () => {
    const { token } = await loginAs({ role: 'SALES_USER' });
    const lead = await createTestLead();

    const response = await request(app)
      .patch(`/api/v1/leads/${lead.id}/status`)
      .set('Authorization', `Bearer ${token}`)
      .send({ status: 'DO_NOT_CONTACT' })
      .expect(403);

    expect(response.body.error.code).toBe('FORBIDDEN');
  });
});
```

## Test Data Management

- Use factory functions for creating test entities:
  ```typescript
  const createTestContact = (overrides = {}) =>
    contactRepo.create({ firstName: 'Test', lastName: 'User', email: `test-${uuid()}@example.com`, ...overrides });
  ```
- Clean database between tests (use transactions that rollback, or truncate tables).
- Never share state between tests.
- Never test against production data.

## Test Coverage Priorities

Focus coverage on (in order of importance):
1. **Authorization logic** — highest security impact.
2. **Business rule enforcement** — status machines, DNC, ownership rules.
3. **Data integrity** — soft delete, audit logging, constraint enforcement.
4. **API contract** — correct response shapes, status codes, validation errors.
5. **Automation rules** — task creation, duplicate prevention.
6. **Import pipeline** — duplicate detection, validation, idempotency.

## Regression Tests for Bugs

Before fixing any bug:
1. Write a failing test that reproduces the bug.
2. Confirm the test fails.
3. Fix the bug.
4. Confirm the test passes.
5. Commit test + fix together.

This prevents regressions and serves as documentation of the root cause.

## What NOT to Do

- Do NOT test implementation details (internal function calls, private methods).
- Do NOT mock the database in integration tests — use a real test database.
- Do NOT write tests only for happy paths — always include error and edge cases.
- Do NOT skip authorization tests — they are the most critical.
- Do NOT share state between tests (order-dependent tests are fragile).
- Do NOT use production data for testing.
