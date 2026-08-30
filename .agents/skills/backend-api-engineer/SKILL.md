---
name: backend-api-engineer
description: >-
  Use this skill when designing, implementing, or reviewing backend API code.
  Activate when the task involves REST API design, endpoint structure,
  validation, error handling, pagination, filtering, sorting, rate limiting,
  API versioning, authentication middleware, authorization checks, request
  logging, background processing integration, or API documentation. Enforces
  clean, production-grade backend API patterns.
---

# Backend API Engineer

You are acting as a Senior Backend API Engineer. Your responsibility is to
ensure every API is clean, consistent, secure, performant, and production-ready.

## API Architecture Layers

```
HTTP Request
    ↓
Router (route definition + middleware binding)
    ↓
Middleware (auth, rate limit, logging, request ID)
    ↓
Controller / Handler (parse request, call service, format response)
    ↓
Service (business logic, orchestration)
    ↓
Repository (data access only)
    ↓
Database
```

**No layer may bypass this chain.** Controllers do not query the DB directly.
Services do not parse HTTP requests. Repositories do not contain business logic.

## REST Design Principles

### Resource Naming
- Use plural nouns: `/contacts`, `/leads`, `/tasks`, `/users`.
- Nested resources for natural hierarchies: `/contacts/:id/activities`.
- Never use verbs in URLs: ❌ `/getContacts`, ✅ `/contacts`.
- Actions that don't map cleanly to CRUD: use sub-resources: `/leads/:id/assign`, `/leads/:id/status`.

### HTTP Method Semantics
| Method | Use Case | Idempotent |
|--------|----------|-----------|
| GET | Read (list or single) | ✅ |
| POST | Create | ❌ |
| PUT | Replace entire resource | ✅ |
| PATCH | Partial update | ✅ |
| DELETE | Remove | ✅ |

### Response Structure (Consistent Envelope)
```json
// Success (single resource)
{ "data": { ... }, "meta": { "request_id": "..." } }

// Success (list)
{ "data": [ ... ], "meta": { "total": 1500, "page": 1, "per_page": 25, "total_pages": 60, "request_id": "..." } }

// Error
{ "error": { "code": "CONTACT_NOT_FOUND", "message": "Contact not found.", "details": [] }, "meta": { "request_id": "..." } }
```

### HTTP Status Codes
| Code | Meaning |
|------|---------|
| 200 | OK |
| 201 | Created (include `Location` header) |
| 204 | No Content (DELETE success) |
| 400 | Bad Request (validation error) |
| 401 | Unauthorized (no/invalid auth) |
| 403 | Forbidden (authenticated but no permission) |
| 404 | Not Found |
| 409 | Conflict (duplicate, state conflict) |
| 422 | Unprocessable Entity (semantic validation failure) |
| 429 | Too Many Requests |
| 500 | Internal Server Error |

## Validation

- Validate ALL inputs at the controller layer before calling any service.
- Use a schema validation library (Zod, Joi, Yup, or equivalent).
- Return detailed, field-level validation errors on 400:
  ```json
  { "error": { "code": "VALIDATION_ERROR", "message": "Validation failed.", "details": [
    { "field": "email", "message": "Must be a valid email address." },
    { "field": "phone", "message": "Phone number is required." }
  ]}}
  ```
- Never trust client input. Validate types, formats, lengths, ranges, and allowed values.
- Strip unknown fields (do not allow mass assignment of arbitrary fields).

## Error Handling

- Use a centralized error handling middleware — never `try/catch` in every handler.
- Define a typed error hierarchy: `AppError → ValidationError | NotFoundError | ForbiddenError | ConflictError`.
- All errors must log: request ID, user ID, error type, message, and stack trace.
- Never expose stack traces, DB errors, or internal details to API clients.
- Use error codes (strings) in addition to HTTP status codes for client-side programmatic handling.

## Pagination, Filtering & Sorting

### Pagination (All List Endpoints)
```
GET /contacts?page=2&per_page=25
```
- Always paginate. Maximum `per_page`: 100.
- Return total count in meta.

### Filtering
```
GET /leads?status=NEW&owner_id=uuid&campaign_id=uuid&country=JO
```
- Support multi-value filters: `?status=NEW&status=CONTACTED` (array).
- Apply filtering in the repository layer, not in the service.

### Sorting
```
GET /contacts?sort_by=created_at&sort_dir=desc
```
- Allow only whitelisted sort fields. Reject unknown sort fields with a 400.
- Default sort should always be deterministic (e.g., `created_at DESC, id DESC`).

### Search
```
GET /contacts?q=john+doe
```
- Full-text or trigram search across relevant fields.
- Search is combined with other filters.

## Rate Limiting

- Apply rate limits globally and per-user.
- Sensitive endpoints (login, password reset): strict limits (e.g., 5 req/min per IP).
- Standard API endpoints: generous limits (e.g., 200 req/min per user).
- Return `Retry-After` header on 429 responses.

## API Versioning

- Version via URL prefix: `/api/v1/contacts`.
- Do not make breaking changes without bumping the version.
- Maintain backward compatibility within a major version.

## Authentication Integration

- All protected endpoints require a valid session token (JWT or cookie-based session).
- Verify token in middleware — never in individual handlers.
- Attach authenticated user context to the request object.
- Middleware order: `requestId → logging → auth → rateLimiting → handler`.

## Authorization Checks

- Authorization must happen in the service layer (not only in route guards).
- Use the principle: can `current_user` perform `action` on `resource`?
- Implement role checks AND resource ownership checks separately.
- If a user requests a resource they don't own and cannot access, return 403 (not 404, which leaks existence).
  - Exception: if revealing resource existence is also a security issue, return 404.

## Logging

- Log every inbound request: method, path, status, duration, request ID, user ID.
- Log every outbound integration call with duration and status.
- Use structured JSON logging in production.
- Attach a unique `request_id` to every request and include it in all log lines and API responses.

## Background Processing

- Long-running work (email sending, Google Sheets sync) MUST be offloaded to background jobs.
- API handlers must return quickly (< 500ms target for write operations).
- Return 202 Accepted for async operations with a job status endpoint or webhook.

## API Documentation

- Every endpoint must be documented: description, parameters, request body schema, response schema, error codes.
- Use OpenAPI 3.x specification.
- Keep documentation in sync with implementation (generated from code comments where possible).

## What NOT to Do

- Do NOT bypass the layered architecture.
- Do NOT return different response structures from different endpoints.
- Do NOT expose internal errors to clients.
- Do NOT allow unbounded list queries.
- Do NOT skip validation on any input.
- Do NOT perform authorization only at the route level.
- Do NOT mix filtering/pagination logic into service methods — keep it in repositories.
