---
name: enterprise-search-engineer
description: >-
  Use this skill when designing or implementing search functionality across the
  CRM. Activate when the task involves contact search, lead search, full-text
  search, fuzzy matching, search performance optimization, search result
  ranking, combined search with filters, or any feature where a user needs to
  quickly find records across name, email, phone, company, or other CRM fields
  at scale.
---

# Enterprise Search Engineer

You are acting as a Senior Search Engineering Specialist. Your responsibility
is to ensure search across the CRM is fast, accurate, and usable at scale.

## Search Architecture Decision

For a CRM with up to 1M contacts, PostgreSQL full-text search is sufficient.
Elasticsearch/OpenSearch is NOT required unless the CRM exceeds 5M+ records
or requires advanced relevance tuning.

**Chosen approach**: PostgreSQL full-text search (`tsvector`) + `pg_trgm` for fuzzy matching.

## Searchable Fields (CRM)

| Field | Search Type | Priority |
|-------|-------------|---------|
| First name + Last name | Full-text + trigram | Highest |
| Email | Exact + prefix | Highest |
| Phone (normalized) | Exact digits | High |
| Company | Full-text + trigram | High |
| Position | Full-text | Medium |
| Country | Exact + prefix | Medium |
| Industry | Full-text | Medium |
| Tags | Exact match | Medium |
| Notes | Full-text (optional) | Low |

## Database Setup

### Search Vector Column
```sql
ALTER TABLE contacts ADD COLUMN search_vector tsvector;

-- Populate search vector (combining multiple fields with weights)
UPDATE contacts SET search_vector = 
  setweight(to_tsvector('english', coalesce(first_name, '') || ' ' || coalesce(last_name, '')), 'A') ||
  setweight(to_tsvector('english', coalesce(company, '')), 'B') ||
  setweight(to_tsvector('english', coalesce(position, '')), 'C') ||
  setweight(to_tsvector('english', coalesce(country, '')), 'D');

-- GIN index for full-text search
CREATE INDEX idx_contacts_fts ON contacts USING GIN(search_vector);
```

### Normalized Fields for Exact Search
```sql
-- Stored normalized for exact/prefix matching
ALTER TABLE contacts ADD COLUMN normalized_email TEXT;
ALTER TABLE contacts ADD COLUMN normalized_phone TEXT;

-- Index for exact/prefix matching
CREATE INDEX idx_contacts_email_norm ON contacts(normalized_email);
CREATE INDEX idx_contacts_phone_norm ON contacts(normalized_phone);

-- Trigram index for fuzzy name/company matching
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX idx_contacts_name_trgm ON contacts USING GIN((first_name || ' ' || last_name) gin_trgm_ops);
CREATE INDEX idx_contacts_company_trgm ON contacts USING GIN(company gin_trgm_ops);
```

### Auto-Update Trigger
```sql
CREATE OR REPLACE FUNCTION update_contact_search_vector()
RETURNS TRIGGER AS $$
BEGIN
  NEW.search_vector :=
    setweight(to_tsvector('english', coalesce(NEW.first_name, '') || ' ' || coalesce(NEW.last_name, '')), 'A') ||
    setweight(to_tsvector('english', coalesce(NEW.company, '')), 'B') ||
    setweight(to_tsvector('english', coalesce(NEW.position, '')), 'C');
  
  NEW.normalized_email := LOWER(TRIM(NEW.email));
  NEW.normalized_phone := REGEXP_REPLACE(NEW.phone, '[^0-9]', '', 'g');
  
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_contact_search_vector
BEFORE INSERT OR UPDATE ON contacts
FOR EACH ROW EXECUTE FUNCTION update_contact_search_vector();
```

## Search Query Implementation

```sql
-- Full search query combining all strategies
WITH search_results AS (
  SELECT
    c.id,
    c.first_name,
    c.last_name,
    c.email,
    c.phone,
    c.company,
    c.status,
    c.owner_id,
    -- Relevance scoring
    CASE
      WHEN c.normalized_email = LOWER($1) THEN 1.0          -- Exact email match
      WHEN c.normalized_phone = REGEXP_REPLACE($1, '[^0-9]', '', 'g') THEN 0.95  -- Exact phone
      WHEN c.normalized_email LIKE LOWER($1) || '%' THEN 0.9 -- Email prefix
      WHEN ts_rank(c.search_vector, query) > 0 THEN ts_rank(c.search_vector, query)
      ELSE similarity(c.first_name || ' ' || c.last_name, $1)  -- Trigram fallback
    END AS relevance,
    to_tsquery('english', $2) AS query
  FROM contacts c,
    to_tsquery('english', $2) query
  WHERE
    c.deleted_at IS NULL
    AND (
      -- Role-based filter
      c.owner_id = $actor_id  -- Sales user: own contacts only
      -- OR no filter for Manager/Admin
    )
    AND (
      -- Email exact/prefix
      c.normalized_email LIKE LOWER($1) || '%'
      -- OR phone exact
      OR c.normalized_phone LIKE REGEXP_REPLACE($1, '[^0-9]', '', 'g') || '%'
      -- OR full-text search
      OR c.search_vector @@ query
      -- OR trigram fuzzy (for short queries or typos)
      OR similarity(c.first_name || ' ' || c.last_name, $1) > 0.3
    )
)
SELECT * FROM search_results
ORDER BY relevance DESC, created_at DESC
LIMIT 25;
```

## Frontend Search UX

```typescript
// Debounced search hook
function useContactSearch() {
  const [query, setQuery] = useState('');
  const debouncedQuery = useDebounce(query, 300);

  const { data, isLoading } = useQuery({
    queryKey: ['contacts', 'search', debouncedQuery],
    queryFn: () => contactsApi.search({ q: debouncedQuery, per_page: 25 }),
    enabled: debouncedQuery.length >= 2, // Start searching at 2 chars
    staleTime: 30_000,
    placeholderData: keepPreviousData,
  });

  return { query, setQuery, results: data?.data ?? [], isLoading };
}
```

### Global Search (Command Palette)
- Accessible via `Ctrl+K` / `Cmd+K`.
- Searches: contacts, leads, tasks, users (if Manager/Admin).
- Results categorized by entity type.
- Recent searches stored in localStorage.
- Keyboard navigable (arrow keys, Enter to select, Escape to close).

## Search Performance Requirements

| Scenario | Target Latency |
|----------|---------------|
| Exact email search | < 20ms |
| Prefix search (name/email) | < 50ms |
| Full-text search (100K contacts) | < 100ms |
| Full-text search (1M contacts) | < 200ms |
| Trigram fuzzy search | < 150ms |

Monitor these with query timing logs. Alert if search latency exceeds 2× target.

## Search Ranking

Results should rank in this priority:
1. Exact email match.
2. Exact phone match.
3. Name exact match.
4. Email prefix match.
5. Full-text match (ranked by `ts_rank`).
6. Fuzzy name match (trigram similarity).

## Pagination & Search

- Paginate search results (default 25 per page).
- Always combine search with the user's access filter (ownership or role).
- Combine search with column filters (e.g., search within `status=NEW`).

## What NOT to Do

- Do NOT search on un-indexed columns.
- Do NOT implement search in application code over full result sets.
- Do NOT skip the debounce on search inputs (floods the API).
- Do NOT start searching on < 2 characters (produces noisy, low-quality results).
- Do NOT ignore the user's access control when constructing search queries.
