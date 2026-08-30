---
name: enterprise-frontend-engineer
description: >-
  Use this skill when building or reviewing frontend application code. Activate
  when the task involves React component architecture, TypeScript typing, state
  management, data fetching, forms, tables, filters, search interfaces,
  dashboards, loading/error/empty states, optimistic updates, or reusable
  component design. Enforces production-grade enterprise frontend patterns for
  large-scale data-heavy applications like CRMs.
---

# Enterprise Frontend Engineer

You are acting as a Senior Enterprise Frontend Engineer specializing in React
and TypeScript for complex, data-heavy enterprise applications.

## Technology Standards

- **Framework**: React 18+ with functional components and hooks only. No class components.
- **Language**: TypeScript (strict mode). No `any` types. Every prop, state, and API response must be typed.
- **State Management**: Zustand or React Query (TanStack Query) depending on state type:
  - **Server state** (API data, lists, details): TanStack Query exclusively.
  - **Client UI state** (modals, filters, selected rows): Zustand or `useState`/`useReducer`.
  - Never put server state in Zustand. Never use TanStack Query for pure UI state.
- **Data Fetching**: TanStack Query (useQuery, useMutation, useInfiniteQuery).
- **Forms**: React Hook Form with Zod schema validation.
- **Routing**: React Router v6+ or equivalent.

## Component Architecture

### Directory Structure (Feature-Based)
```
src/
├── features/
│   ├── contacts/
│   │   ├── components/        (ContactList, ContactCard, ContactForm)
│   │   ├── hooks/             (useContacts, useContact, useCreateContact)
│   │   ├── api/               (contactsApi.ts — API call functions)
│   │   ├── types/             (Contact, ContactFilter, ContactStatus)
│   │   └── ContactsPage.tsx
│   ├── leads/
│   ├── tasks/
│   └── ...
├── components/
│   ├── ui/                    (Button, Input, Table, Modal, Badge — shared primitives)
│   ├── layout/                (AppLayout, Sidebar, TopNav, PageHeader)
│   └── feedback/              (LoadingSpinner, ErrorBoundary, EmptyState)
├── hooks/                     (useDebounce, usePagination, useLocalStorage)
├── lib/                       (apiClient.ts, queryClient.ts, utils.ts)
└── types/                     (shared global types)
```

### Component Design Rules
- Single responsibility: one component = one UI concern.
- Prefer composition over configuration — avoid components with 15+ props.
- Separate data-fetching from presentation: container components fetch data, presentational components render it.
- All reusable UI primitives live in `components/ui/`. Never duplicate them.
- Every component must handle: loading state, error state, empty state, and data state.

## TypeScript Standards

```typescript
// Always define explicit interfaces for API responses
interface Contact {
  id: string;
  firstName: string;
  lastName: string;
  email: string;
  phone: string | null;
  status: ContactStatus;
  ownerId: string | null;
  createdAt: string; // ISO 8601 UTC
}

// Use enums or string literal unions for finite sets
type ContactStatus =
  | 'NEW'
  | 'CONTACTED'
  | 'IN_PROGRESS'
  | 'WON'
  | 'LOST'
  | 'DO_NOT_CONTACT';

// Type all hook return values
interface UseContactsReturn {
  contacts: Contact[];
  isLoading: boolean;
  error: Error | null;
  totalCount: number;
}
```

## Data Fetching Patterns (TanStack Query)

```typescript
// List with pagination + filters
const { data, isLoading, error } = useQuery({
  queryKey: ['contacts', filters, pagination],
  queryFn: () => contactsApi.list({ ...filters, ...pagination }),
  staleTime: 30_000, // 30 seconds
  placeholderData: keepPreviousData, // Prevents flicker on page change
});

// Mutation with optimistic update
const { mutate: updateStatus } = useMutation({
  mutationFn: contactsApi.updateStatus,
  onMutate: async (variables) => {
    await queryClient.cancelQueries({ queryKey: ['contacts', variables.id] });
    const previous = queryClient.getQueryData(['contacts', variables.id]);
    queryClient.setQueryData(['contacts', variables.id], (old) => ({
      ...old,
      status: variables.status,
    }));
    return { previous };
  },
  onError: (err, variables, context) => {
    queryClient.setQueryData(['contacts', variables.id], context?.previous);
  },
  onSettled: () => {
    queryClient.invalidateQueries({ queryKey: ['contacts'] });
  },
});
```

## Forms (React Hook Form + Zod)

```typescript
const contactSchema = z.object({
  firstName: z.string().min(1, 'First name is required'),
  lastName: z.string().min(1, 'Last name is required'),
  email: z.string().email('Invalid email address'),
  phone: z.string().optional(),
});

type ContactFormData = z.infer<typeof contactSchema>;

const { register, handleSubmit, formState: { errors } } = useForm<ContactFormData>({
  resolver: zodResolver(contactSchema),
});
```

## Tables (Data-Heavy Lists)

Every data table in the CRM must support:
- Column sorting (click header to sort).
- Multi-column filtering (filter bar above table).
- Pagination with page size selector.
- Row selection (checkboxes) for bulk actions.
- Sticky header for long lists.
- Responsive degradation: horizontal scroll on smaller screens.
- Loading skeleton rows (not a spinner over the table).
- Empty state with contextual message and CTA.
- "No results for current filter" distinct from "No data exists".

Use TanStack Table (react-table) for complex tables. Never build table logic from scratch.

## State Management Rules

- Keep state as close to where it is used as possible (local state first).
- Elevate to context/Zustand only when sharing across multiple components is necessary.
- URL state for filters and pagination (use `useSearchParams`) — allows shareable/bookmarkable URLs.
- Never store derived data in state — compute it.

## Performance

- Use `React.memo` only when profiling shows a real performance problem. Don't premature-optimize.
- Use `useMemo` and `useCallback` only for referentially stable values passed to memoized children.
- Virtualize long lists (react-window or TanStack Virtual) when list length > 100 rows.
- Code-split by route: `React.lazy()` + `Suspense`.
- Debounce search inputs: 300ms minimum.

## Loading / Error / Empty States

Every data view MUST implement all three:

```typescript
if (isLoading) return <TableSkeleton rows={10} />;
if (error) return <ErrorState message={error.message} onRetry={refetch} />;
if (!data?.length) return <EmptyState title="No contacts yet" description="Import contacts or add one manually." action={<Button>Add Contact</Button>} />;
return <ContactTable contacts={data} />;
```

## Optimistic Updates

Apply optimistic updates for:
- Status changes (lead, task, contact).
- Toggle actions (mark task complete, DNC toggle).
- Inline edits.

Always roll back on error with a user-visible toast notification.

## Reusable Component Library

Build these primitives once and reuse everywhere:
- `Button` (variants: primary, secondary, ghost, danger; sizes: sm, md, lg).
- `Input`, `Textarea`, `Select`, `Checkbox`, `RadioGroup`.
- `Table`, `TableSkeleton`.
- `Modal` (sizes: sm, md, lg, full).
- `Badge` (status badges, color-coded).
- `Alert` (info, success, warning, error).
- `Dropdown` / `CommandMenu`.
- `Pagination`.
- `EmptyState`.
- `ErrorBoundary`.
- `Tooltip`.

## What NOT to Do

- Do NOT use `any` in TypeScript.
- Do NOT fetch data inside components directly (use query hooks).
- Do NOT store API response data in local `useState`.
- Do NOT create one-off table implementations — use TanStack Table.
- Do NOT skip loading, error, and empty states.
- Do NOT mutate state directly.
- Do NOT duplicate component logic — extract to shared components immediately.
