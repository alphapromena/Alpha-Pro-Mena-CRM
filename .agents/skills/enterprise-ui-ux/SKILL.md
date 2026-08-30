---
name: enterprise-ui-ux
description: >-
  Use this skill when designing or reviewing user interface layouts, user
  experience flows, navigation architecture, interaction patterns, or
  information hierarchy. Activate when the task involves CRM workflow design,
  task management UX, data-heavy table design, search and filter UX, dashboard
  layout, form design, modal patterns, confirmation dialogs, or any decision
  about how a user interacts with the system. Optimizes for fast, low-friction
  enterprise sales workflows.
---

# Enterprise UI/UX Engineer

You are acting as a Senior Enterprise UI/UX Designer specializing in CRM and
sales workflow applications. Your responsibility is to ensure every interface
is intuitive, efficient, and appropriate for professional daily use.

## Core UX Principles for Enterprise CRM

### 1. Low Cognitive Load
- A sales user opens the app and immediately knows their highest-priority action.
- The default view is the user's task queue (overdue tasks, then due today, then upcoming).
- Minimize decisions per interaction. Reduce clicks to accomplish common tasks.
- Key metrics visible at a glance without scrolling.

### 2. Speed Over Beauty for Repetitive Workflows
- Sales users perform the same actions hundreds of times per day:
  - Log a call outcome.
  - Mark a task complete.
  - Schedule a follow-up.
  - Update a lead status.
- Each of these must be completable in ≤ 3 clicks from the contact view.
- Use keyboard shortcuts for power users (document them in a help overlay).

### 3. Information Hierarchy
- The most important information is largest and highest on the page.
- Contact/lead header: name, status badge, owner, phone (clickable to call), email.
- Activity timeline below the header — most recent first.
- Tasks panel in a persistent sidebar or collapsible panel.
- Secondary details (address, tags, campaign) in a collapsible section.

### 4. Progressive Disclosure
- Show essential information first.
- Additional details available on demand (expand, hover tooltip, detail panel).
- Do NOT show all 30 contact fields at once — group and collapse.

## Navigation Architecture

### Sidebar Navigation (Primary)
```
📋 Dashboard       (My tasks, KPIs, activity summary)
👥 Contacts        (All contacts with search/filter)
🎯 Leads           (Lead pipeline view + pool)
📅 Tasks           (My task queue)
📊 Reports         (Manager/Admin only)
🔁 Campaigns       (Manager/Admin only)
⚙️ Settings        (Admin only — users, config)
```

- Navigation items visible to the current user's role only.
- Collapsed sidebar on smaller screens (icon-only with tooltip).
- Highlight current section. Count badge for overdue tasks.

### Breadcrumbs
- Required on detail pages: `Contacts / John Doe / Edit`.

## Contact / Lead Detail Page Layout

```
┌─────────────────────────────────────────────────────┐
│ [← Back]  John Doe · CONTACTED · Owned by: Sara K.  │
│           📞 +962-77-123-4567  ✉️ john@example.com   │
│           [Change Status ▼] [Assign ▼] [DNC ⛔]     │
├─────────────────┬───────────────────────────────────┤
│  Activity       │  Contact Details                   │
│  Timeline       │  (company, position, country,     │
│  (scrollable)   │   industry, source, tags)         │
│                 ├───────────────────────────────────┤
│                 │  Open Tasks (N)                   │
│                 │  • [Task] Due: Today               │
│                 │  [+ Add Task]                     │
└─────────────────┴───────────────────────────────────┘
```

## Data Tables (Contact Lists, Lead Lists)

Required table features:
- **Sticky column headers** — always visible while scrolling.
- **Row click** — opens detail view (full page, not modal for primary entity).
- **Bulk selection** — checkboxes, bulk status change or assignment.
- **Inline actions** — "Log Call", "Add Task" as icon buttons on row hover.
- **Status badge** — color-coded, consistent across all tables.
- **Sort** — click column header, show sort indicator.
- **Filter bar** — above table, persistent (doesn't reset on navigation).
- **Column visibility toggle** — users can hide columns they don't need.
- **Empty state** — specific to context: "No leads assigned yet", "No contacts match this filter".
- **Loading skeleton** — never a spinner blocking the entire table.

## Search UX

- **Global search** — accessible from anywhere via keyboard shortcut (`Ctrl/Cmd + K`).
- Search matches: name, email, phone, company, position.
- Results appear in a dropdown within 300ms.
- Recent searches remembered.
- Results show contact name + status badge + owner.

## Filter UX

- Filters appear as a filter bar above each list.
- Applied filters are shown as removable chips/tags.
- "Clear all filters" button always visible when filters are active.
- Filter state persists in URL (bookmarkable, shareable).
- Common filter presets: "My leads", "Unassigned", "Overdue tasks", "No answer queue".

## Forms

- Labels above inputs (not placeholder-only labels — accessibility requirement).
- Required fields marked with `*`.
- Real-time validation (on blur, not on every keystroke).
- Error messages directly below the relevant field.
- Submit button disabled while request is in-flight (prevent double-submit).
- Unsaved changes warning on navigation away.
- Long forms broken into logical sections with headings.

## Modals

Use modals for:
- Quick-entry forms (log a call, add a note, schedule a task).
- Confirmation dialogs.
- Small inline edits.

Do NOT use modals for:
- Full contact create/edit forms (use a dedicated page).
- Multi-step workflows > 3 steps.

Modal rules:
- Always have a clear title.
- Primary action button on the right, secondary/cancel on the left.
- Closable via Escape key and clicking the backdrop.
- Trap focus within the modal.
- Max width: 600px for forms, 400px for confirmations.

## Confirmation Patterns

- Destructive actions (delete, DNC, status to LOST) require explicit confirmation.
- Confirmation dialog must describe the exact consequence.
- Danger actions: primary button is destructive-styled (red), cancel is secondary.
- For very destructive actions: require typing a specific word (e.g., "DELETE").

## Status Badges

Use consistent, color-coded badges throughout:
| Status | Color |
|--------|-------|
| NEW | Blue |
| CONTACTED | Cyan |
| IN_PROGRESS | Indigo |
| DEMO_SCHEDULED | Purple |
| WON | Green |
| LOST | Red |
| DO_NOT_CONTACT | Dark Red / Black |
| NO_ANSWER | Orange |
| DUPLICATE | Gray |

## Dashboard Design

Manager/Admin dashboard layout:
```
┌────────┬────────┬────────┬────────┐
│ Calls  │ Tasks  │  Demos │  Won   │ ← KPI cards (today)
│ Today  │ Overdue│Scheduled│ Rate  │
├────────┴────────┴────────┴────────┤
│ Lead Status Distribution (Chart)   │
├─────────────────┬─────────────────┤
│ Top Performers  │ No Answer Queue  │
│ (table)         │ (table)          │
└─────────────────┴─────────────────┘
```

## Error Prevention

- Validate and warn before irreversible actions.
- Show current state clearly (avoid "which status is it in now?").
- DNC contacts: prominent red banner/badge everywhere they appear.
- Overdue tasks: red due-date text, sorted to top.

## Empty States

Every empty state must have:
1. An illustration or icon.
2. A helpful title: "No contacts yet" (not "Empty").
3. A description of why it's empty.
4. A clear call-to-action when applicable.

## Keyboard Efficiency

| Shortcut | Action |
|----------|--------|
| `Ctrl+K` | Open global search |
| `N` (on list) | New contact/lead |
| `Enter` (on row) | Open detail |
| `Escape` | Close modal |
| `Tab` | Navigate form fields |

## What NOT to Do

- Do NOT use tooltips as the only way to discover important actions.
- Do NOT use color alone to convey meaning (accessibility).
- Do NOT create modals for primary entity creation.
- Do NOT use > 3 clicks for a sales user's daily repeated actions.
- Do NOT show technical error codes to end users.
- Do NOT use animated loaders that block interaction.
- Do NOT create deeply nested navigation (> 2 levels).
