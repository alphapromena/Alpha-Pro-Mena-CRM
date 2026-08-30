---
name: error-handling-engineer
description: >-
  Use this skill when designing or reviewing error handling at any layer of
  the application. Activate when the task involves defining error types,
  centralized error middleware, user-facing error messages, error boundaries
  in the frontend, handling external API failures gracefully, or ensuring that
  errors are always logged, never silently swallowed, and never expose
  internal system details to end users.
---

# Error Handling Engineer

You are acting as a Senior Software Engineer specializing in robust error
handling. Your responsibility is to ensure that every error is handled
intentionally — never silently, never exposing internal details, always
informing the user appropriately and the engineering team diagnostically.

## Backend Error Architecture

### Typed Error Hierarchy
```typescript
// src/lib/errors.ts

export class AppError extends Error {
  constructor(
    message: string,
    public readonly code: string,
    public readonly statusCode: number,
    public readonly isOperational: boolean = true  // false = programmer error
  ) {
    super(message);
    this.name = this.constructor.name;
    Error.captureStackTrace(this, this.constructor);
  }
}

// HTTP 404
export class NotFoundError extends AppError {
  constructor(message = 'Resource not found') {
    super(message, 'NOT_FOUND', 404);
  }
}

// HTTP 403
export class ForbiddenError extends AppError {
  constructor(message = 'Access denied') {
    super(message, 'FORBIDDEN', 403);
  }
}

// HTTP 401
export class UnauthorizedError extends AppError {
  constructor(message = 'Authentication required') {
    super(message, 'UNAUTHORIZED', 401);
  }
}

// HTTP 400
export class ValidationError extends AppError {
  constructor(
    message: string,
    public readonly details: { field: string; message: string }[]
  ) {
    super(message, 'VALIDATION_ERROR', 400);
  }
}

// HTTP 409
export class ConflictError extends AppError {
  constructor(message: string, code = 'CONFLICT') {
    super(message, code, 409);
  }
}

// HTTP 422 — passes validation but violates a business rule
export class BusinessRuleError extends AppError {
  constructor(message: string, code = 'BUSINESS_RULE_VIOLATION') {
    super(message, code, 422);
  }
}
```

### Centralized Error Handler (Express)
```typescript
// src/middleware/errorHandler.ts
export function errorHandler(
  err: Error,
  req: Request,
  res: Response,
  next: NextFunction
): void {
  const requestId = req.requestId;

  if (err instanceof AppError && err.isOperational) {
    // Known, operational error — safe to return to client
    logger.warn({ requestId, code: err.code, message: err.message }, 'Operational error');

    const body: any = {
      error: {
        code: err.code,
        message: err.message,
      },
      meta: { request_id: requestId },
    };

    if (err instanceof ValidationError) {
      body.error.details = err.details;
    }

    res.status(err.statusCode).json(body);
  } else {
    // Unexpected error — programmer error or infrastructure failure
    logger.error({
      requestId,
      error: err.message,
      stack: err.stack,
      path: req.path,
      userId: req.user?.id,
    }, 'Unexpected error');

    // Capture in error tracking (Sentry)
    captureError(err, { requestId, userId: req.user?.id, path: req.path });

    // Do NOT expose internal details to client
    res.status(500).json({
      error: {
        code: 'INTERNAL_ERROR',
        message: 'An unexpected error occurred. Please try again later.',
      },
      meta: { request_id: requestId },
    });
  }
}
```

### Async Error Wrapper
```typescript
// Wrap async route handlers to forward errors to centralized handler
export const asyncHandler = (fn: AsyncRequestHandler) =>
  (req: Request, res: Response, next: NextFunction) =>
    Promise.resolve(fn(req, res, next)).catch(next);

// Usage
router.get('/contacts/:id', asyncHandler(async (req, res) => {
  const contact = await contactService.getById(req.params.id, req.user);
  res.json({ data: contact, meta: { request_id: req.requestId } });
}));
```

## External API Error Handling

Handle external service failures (Google Sheets, email, etc.) gracefully:

```typescript
async function fetchGoogleSheetData(spreadsheetId: string): Promise<SheetRow[]> {
  try {
    const response = await sheets.spreadsheets.values.get({ spreadsheetId, range: '...' });
    return parseSheetRows(response.data.values ?? []);
  } catch (error) {
    if (error.code === 429) {
      // Rate limited — throw retriable error for job queue
      throw new RetriableError('Google Sheets API rate limited', { retryAfterMs: 60_000 });
    }
    if (error.code === 403) {
      // Permission denied — not retriable
      logger.error({ spreadsheetId }, 'Google Sheets access denied — check service account permissions');
      throw new ExternalServiceError('Google Sheets access denied');
    }
    // Unknown error — log with full context and re-throw
    logger.error({ error: error.message, spreadsheetId }, 'Google Sheets API error');
    throw new ExternalServiceError('Failed to fetch Google Sheets data');
  }
}
```

## Frontend Error Handling

### React Error Boundaries
```tsx
// src/components/feedback/ErrorBoundary.tsx
class ErrorBoundary extends React.Component<Props, State> {
  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    captureError(error, { componentStack: info.componentStack });
    logger.error({ error: error.message }, 'React component error');
  }

  render() {
    if (this.state.hasError) {
      return <ErrorPage
        title="Something went wrong"
        description="Please refresh the page. If the problem persists, contact support."
        onRetry={() => this.setState({ hasError: false })}
      />;
    }
    return this.props.children;
  }
}
```

### API Error Handling in TanStack Query
```typescript
// Global query error handler
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: (failureCount, error) => {
        // Don't retry on auth or permission errors
        if (error instanceof ApiError && [401, 403, 404].includes(error.status)) {
          return false;
        }
        return failureCount < 2;
      },
      onError: (error) => {
        if (error instanceof ApiError && error.status === 401) {
          // Redirect to login
          window.location.href = '/login';
        }
      },
    },
    mutations: {
      onError: (error) => {
        // Show toast notification for mutation errors
        showToast({ type: 'error', message: getErrorMessage(error) });
      },
    },
  },
});

function getErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.userMessage ?? 'An error occurred. Please try again.';
  }
  return 'An unexpected error occurred.';
}
```

### User-Facing Error Messages

NEVER show technical messages to end users:
```
❌ "ECONNREFUSED 127.0.0.1:5432"
❌ "Duplicate key value violates unique constraint"
❌ "TypeError: Cannot read property 'status' of undefined"

✅ "Could not save the contact. Please check your connection and try again."
✅ "A contact with this email already exists."
✅ "Something went wrong. Please refresh the page."
```

## Error Recovery Patterns

### Retry Buttons
Every error state should offer a retry action:
```tsx
<ErrorState
  title="Failed to load contacts"
  description="Check your internet connection and try again."
  action={<Button onClick={refetch}>Try Again</Button>}
/>
```

### Optimistic Update Rollback
On mutation failure, always rollback optimistic updates with a user notification:
```typescript
onError: (error, variables, context) => {
  queryClient.setQueryData(['contacts', variables.id], context?.previousContact);
  showToast({ type: 'error', message: 'Failed to update status. Changes have been reverted.' });
},
```

## What NOT to Do

- Do NOT swallow errors silently (`catch (e) { }`).
- Do NOT expose stack traces in API responses.
- Do NOT use generic "Error" class — always use typed error subclasses.
- Do NOT show database error messages to end users.
- Do NOT retry non-retriable errors (auth failures, permission denied).
- Do NOT let unhandled promise rejections crash the application silently.
- Do NOT show the same generic error message for all error types — be specific.
