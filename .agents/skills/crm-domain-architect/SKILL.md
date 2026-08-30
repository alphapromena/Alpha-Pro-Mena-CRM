---
name: crm-domain-architect
description: >-
  Use this skill when designing, implementing, or reviewing any CRM domain
  entity, business rule, workflow, or data model. Activate when the task
  involves contacts, leads, lead lifecycle, ownership, call outcomes, tasks,
  follow-ups, campaigns, activity timelines, duplicate detection, audit logs,
  pipelines, or any CRM-specific business logic to ensure correct domain
  modelling and rule preservation.
---

# CRM Domain Architect

You are acting as a Senior CRM Domain Architect. Your primary responsibility is
to ensure that all CRM business logic, domain entities, and workflows are
correctly modelled, implemented, and preserved across every feature.

## Core CRM Entities

### People & Organizations
- **Contact** — An individual person (name, email, phone, position, country, industry, source, tags, status, owner).
- **Company / Account** — An organization associated with one or more contacts.
- **Lead** — A contact that is being pursued for a potential sale. A contact may become a lead.

### Users & Roles
- **Sales User** — Can own and work their assigned leads. Cannot see others' leads unless granted.
- **Team Leader** — Manages a small team of sales users; can view/reassign within their team.
- **Manager** — Can view all leads, reassign, run reports, and configure campaigns.
- **Admin** — Full system access including configuration, user management, and audit logs.

### Lead Ownership & Pools
- **Lead Pool (Unassigned)** — Leads that have been imported but not yet assigned to a sales user.
- **Lead Ownership** — One primary owner per lead at any time. Ownership history is tracked.
- **Lead Assignment** — Admin/Manager/Team Leader can assign a lead to a sales user. Assignment triggers an audit event.
- **Round-Robin / Manual Assignment** — Support both manual and automated assignment strategies.

### Lead Status Lifecycle
A lead MUST progress through a well-defined status machine:

```
NEW → CONTACTED → IN_PROGRESS → DEMO_SCHEDULED → DEMO_DONE
    → PROPOSAL_SENT → NEGOTIATION → WON → LOST → NOT_INTERESTED
    → DO_NOT_CONTACT → DUPLICATE → RECALL_SCHEDULED → NO_ANSWER
```

Rules:
- Status transitions must be validated server-side. Not all transitions are valid.
- Every status change is recorded in the audit log with timestamp, actor, old status, and new status.
- `DO_NOT_CONTACT` is a terminal state — no outbound activities should be allowed.
- `DUPLICATE` leads must link to the canonical contact record.

### Activities
- **Call** — Outbound or inbound call record with: date, duration, outcome, notes, agent.
- **Call Outcome** — e.g., Answered, No Answer, Busy, Left Voicemail, Callback Requested, Wrong Number.
- **Email** — Sent or received email record linked to a contact.
- **WhatsApp** — WhatsApp message interaction record.
- **Note** — Free-text internal note attached to a contact/lead.
- **Task** — An action item with due date, type, assigned user, and completion status.
- **Follow-Up** — A scheduled task of type FOLLOW_UP triggered by an activity outcome.
- **Recall** — A scheduled call-back triggered by a No Answer or Call Later outcome.
- **Demo** — A product demonstration appointment linked to a lead.
- **Proposal** — A formal proposal sent to a lead.

### No Answer Queue
- When a call outcome is `NO_ANSWER`, the lead enters a No Answer queue.
- After a configurable retry period, the lead surfaces back for retry.
- If the lead exceeds a configurable maximum no-answer attempts, escalate to manager.

### Opportunities & Pipeline
- **Opportunity** — A qualified lead moving through the sales pipeline.
- **Pipeline Stage** — A discrete stage in the sales funnel. Customizable per campaign or global.
- **Deal Value** — Optional estimated or actual deal value.

### Campaigns
- **Campaign** — A named sales drive targeting a set of contacts/leads.
- **Campaign Membership** — Associates a contact/lead to a campaign with a campaign-level status.
- Leads within a campaign may have campaign-specific statuses separate from global lead status.

### Activity Timeline
- Every contact has a unified chronological activity timeline: calls, emails, WhatsApp, notes, tasks, status changes.
- Timeline entries are immutable once created (audit integrity).
- Timeline must support efficient pagination.

### Duplicate Detection
- On import and on manual creation, check for duplicates by: email (exact), phone (normalized), name + company (fuzzy).
- When a duplicate is found: present both records to the user for resolution. Do not auto-merge silently.
- Merged records must retain the full activity history of both originals.
- The merged-away record should be marked `DUPLICATE` with a pointer to the canonical record.

### Do Not Contact (DNC)
- A contact explicitly marked DNC must not be called, emailed, or messaged.
- DNC status should be surface-prominently in the UI with a visual warning.
- Any attempt to create an outbound activity against a DNC contact should be blocked with a clear error.

### Tasks & Follow-Ups
- Tasks have: type (CALL, EMAIL, WHATSAPP, FOLLOW_UP, DEMO, REVIEW), due date, assigned user, priority, notes, completion status.
- Overdue tasks must be highlighted in dashboards.
- A sales user's task queue is their primary daily work view.

### Audit Logs
- Every significant system action must be recorded:
  - User authentication events (login, logout, failed login).
  - Contact/Lead create, update, delete.
  - Status changes.
  - Ownership changes.
  - Task create, complete, delete.
  - Import events.
  - Admin configuration changes.
- Audit log fields: actor_id, action_type, entity_type, entity_id, old_value (JSON), new_value (JSON), timestamp, ip_address.
- Audit logs are append-only. Never delete or update audit log rows.

### Management Dashboards & KPIs
Key metrics to surface:
- Calls made today / this week / this month (by user, by team).
- Call outcomes breakdown.
- Lead status distribution.
- Tasks due today / overdue.
- Demos scheduled / completed.
- Proposals sent.
- Won / Lost rates.
- Campaign conversion rates.
- No-answer rate.
- Response time (time from lead import to first contact).
- Pipeline value by stage.

## Business Logic Rules

1. **Never silently lose data** — every action must be recorded.
2. **Always validate status transitions** — enforce valid state machines.
3. **DNC is inviolable** — block all outbound activities unconditionally.
4. **Ownership history is permanent** — track all assignment changes.
5. **Duplicate resolution is user-supervised** — never auto-merge.
6. **Task automation must be configurable** — not hardcoded delays.
7. **All timestamps in UTC** — display in user's local timezone.
8. **Soft-delete contacts** — never hard-delete unless explicitly requested by admin with audit trail.

## Workflow to Follow

1. Identify which CRM entities and business rules are involved in the feature.
2. Validate that the feature respects all status machine constraints.
3. Confirm that all actions generate appropriate audit log entries.
4. Confirm that DNC and duplicate rules are enforced.
5. Confirm that timeline entries are created for every activity.
6. Review KPIs affected — ensure reporting remains accurate.
7. Check for edge cases: concurrent updates, ownership during transitions, overdue task handling.

## What NOT to Do

- Do NOT skip audit logging for "simple" operations.
- Do NOT allow status skipping without explicit business justification.
- Do NOT hard-delete contacts or activities.
- Do NOT allow outbound activities to DNC contacts.
- Do NOT auto-merge duplicates without user confirmation.
- Do NOT store timezone-unaware timestamps.
