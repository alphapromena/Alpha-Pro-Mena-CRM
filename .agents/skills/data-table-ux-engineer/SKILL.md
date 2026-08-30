---
name: data-table-ux-engineer
description: >-
  Use this skill when designing, building, or refining CRM data tables.
  Enforces sticky headers, sticky identity columns (Name & Company), smooth
  horizontal scrolling, dynamic attempt columns, inline editing controls, bulk
  selection, sort/filter workflows, and robust skeleton/empty states.
---

# Data Table UX Engineering Standard

## Table Architectural Rules

1. **Sticky Identity Columns & Sticky Header**:
   - Always freeze primary identification columns (`Name` at `left: 0`, `Company` at `left: 200px`) with elevated z-index and subtle drop shadow separator.
   - Table `<thead>` must have `position: sticky; top: 0; z-index: 10`.

2. **Dynamic Columns & Unbounded Attempts**:
   - Compute `maxAttempts = Math.max(3, ...data.map(r => r.attempts.length))`.
   - Never hardcode fixed attempt bounds. Render columns `1st Attempt`, `2nd Attempt`, ..., `Nth Attempt`.

3. **Inline Micro-Interactions**:
   - Provide compact 1-click status dropdowns on the active next attempt slot.
   - Visual copy feedback on phone numbers and email addresses.

4. **Bidirectional (RTL/LTR) Precision**:
   - In RTL, sticky columns must anchor to `right: 0` and `right: 200px` with reversed borders and shadows.
