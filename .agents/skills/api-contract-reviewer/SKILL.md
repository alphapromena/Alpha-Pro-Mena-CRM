---
name: api-contract-reviewer
description: >-
  Use this skill when reviewing or designing API contracts — the formal
  definition of request and response structures, validation rules, error
  responses, and versioning strategy. Activate when checking whether an API
  endpoint has consistent request schemas, proper validation, correct error
  codes, complete response shapes, or when evaluating backward compatibility
  of API changes.
---

# API Contract Reviewer

You are acting as a Senior API Design Engineer specializing in API contract
quality. Your responsibility is to ensure every API endpoint has a clear,
consistent, well-validated, and backward-compatible contract.

## API Contract Elements

A complete API contract must specify:
1. **Endpoint** — Method + URL path.
2. **Authentication** — Required? Which method?
3. **Request** — Headers, path params, query params, body schema.
4. **Response** — Success body schema(s), with all fields defined.
5. **Errors** — All possible error responses with codes and messages.
6. **Side effects** — What state changes does this endpoint cause?

## Request Schema Checklist

For every request body:
- [ ] All fields are explicitly typed (string, number, boolean, UUID, ISO date).
- [ ] Required vs. optional fields are clearly specified.
- [ ] String fields have `maxLength` constraints.
- [ ] Numeric fields have `minimum` / `maximum` where applicable.
- [ ] Enum fields list all valid values.
- [ ] UUID fields use `format: uuid`.
- [ ] Date fields use `format: date-time` (ISO 8601 UTC).
- [ ] No unknown fields are accepted (use `additionalProperties: false` in OpenAPI).

## Response Schema Checklist

For every success response:
- [ ] All returned fields are documented (no surprise fields).
- [ ] Nullable fields are explicitly marked nullable.
- [ ] Date fields are in ISO 8601 UTC format.
- [ ] IDs are UUIDs (strings), not integers.
- [ ] Nested objects are typed (not `object` without schema).
- [ ] List responses include pagination metadata.
- [ ] The response schema matches what the code actually returns.

## Error Response Consistency

Every error response must follow the same envelope:
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "The request contains invalid fields.",
    "details": [
      { "field": "email", "message": "Must be a valid email address." }
    ]
  },
  "meta": {
    "request_id": "req_abc123"
  }
}
```

### Error Code Registry

Each error must have a machine-readable code (for client programmatic handling):

| HTTP Status | Code | Meaning |
|-------------|------|---------|
| 400 | `VALIDATION_ERROR` | Request schema validation failed |
| 401 | `UNAUTHORIZED` | Authentication required or invalid |
| 403 | `FORBIDDEN` | Authenticated but insufficient permission |
| 404 | `NOT_FOUND` | Resource does not exist |
| 409 | `CONFLICT` | State conflict (duplicate, status conflict) |
| 422 | `BUSINESS_RULE_VIOLATION` | Passes validation but violates a business rule |
| 429 | `RATE_LIMITED` | Too many requests |
| 500 | `INTERNAL_ERROR` | Unexpected server error |

Entity-specific error codes:
| Code | Meaning |
|------|---------|
| `CONTACT_NOT_FOUND` | Specific contact ID doesn't exist |
| `LEAD_STATUS_INVALID_TRANSITION` | Status transition not allowed |
| `CONTACT_IS_DNC` | Cannot perform action on DNC contact |
| `DUPLICATE_EMAIL` | Email already exists |
| `INSUFFICIENT_ROLE` | Role hierarchy violation |
| `LEAD_POOL_EMPTY` | No leads in pool to assign |

## Validation Rules Documentation

For each field with business validation:
```yaml
# Example: Phone field
phone:
  type: string
  nullable: true
  maxLength: 20
  pattern: '^\+?[1-9]\d{6,14}$'  # E.164-compatible
  description: >
    Phone number in international format.
    Stored normalized (digits only, no spaces/dashes).
    Used for duplicate detection (normalized comparison).
```

## Pagination Contract

All list endpoints MUST follow this contract:

**Request query parameters:**
```
?page=1          (1-indexed, default: 1)
&per_page=25     (default: 25, maximum: 100)
&sort_by=created_at   (default varies per endpoint)
&sort_dir=desc   (asc | desc)
```

**Response meta:**
```json
{
  "data": [...],
  "meta": {
    "page": 1,
    "per_page": 25,
    "total": 1523,
    "total_pages": 62,
    "has_next": true,
    "has_prev": false,
    "request_id": "req_abc123"
  }
}
```

## Backward Compatibility Rules

### Non-Breaking Changes (allowed in same version)
- ✅ Adding new optional response fields.
- ✅ Adding new optional request fields (with sensible defaults).
- ✅ Adding new enum values to response fields.
- ✅ Adding new endpoints.
- ✅ Relaxing validation (e.g., making a required field optional).

### Breaking Changes (require version bump)
- ❌ Removing response fields.
- ❌ Renaming fields.
- ❌ Changing field types.
- ❌ Making optional fields required.
- ❌ Removing valid enum values.
- ❌ Changing HTTP method for an endpoint.
- ❌ Changing URL structure.

### Versioning Strategy
```
/api/v1/contacts   ← Current stable version
/api/v2/contacts   ← New version with breaking changes (run both in parallel during transition)
```

Deprecation process:
1. Mark old version as deprecated in API docs.
2. Add `Deprecation: date` and `Sunset: date` headers.
3. Give clients 3+ months before removing the old version.

## API Contract Review Template

When reviewing a new API:
```
Endpoint: PATCH /api/v1/leads/:id/status

✅ Authentication: Requires Bearer token
✅ Path param: id — UUID format
✅ Request body: { status: LeadStatus } — enum validated
⚠️ Response: Missing audit timestamp in response — add updated_at field
❌ Error: Missing 422 BUSINESS_RULE_VIOLATION for DNC transition attempt
❌ Error: Missing documentation for valid status transitions
✅ Backward compatible: yes
```

## What NOT to Do

- Do NOT leave `object` type without specifying the object's schema.
- Do NOT use different error envelope structures on different endpoints.
- Do NOT make breaking changes without a version bump.
- Do NOT accept unbounded string lengths without `maxLength`.
- Do NOT return different fields from the same endpoint depending on conditions (unpredictable contract).
- Do NOT forget to document all possible error codes for each endpoint.
