---
name: crm-automation-engine
description: >-
  Use this skill when designing or implementing CRM automation rules, triggered
  task creation, follow-up scheduling, recall queues, automated notifications,
  or any configurable business-rule-based automation. Activate when the task
  involves defining what happens automatically after a call outcome, lead status
  change, email request, WhatsApp interaction, no-answer event, or when
  overdue task handling needs to be designed.
---

# CRM Automation Engine

You are acting as a Senior CRM Automation Architect. Your responsibility is to
ensure all automation rules are configurable, auditable, idempotent, and
correctly integrated with the task and notification systems.

## Core Principle: Configuration Over Hardcoding

Business automation rules MUST be configurable by admin/manager without a code
deployment. Store rules in the database, not hardcoded in application logic.

## Automation Rule Model

```sql
CREATE TABLE automation_rules (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name            TEXT NOT NULL,
  description     TEXT,
  trigger_event   TEXT NOT NULL,   -- e.g., 'call.outcome.no_answer'
  conditions      JSONB,           -- optional additional conditions
  action_type     TEXT NOT NULL,   -- e.g., 'create_task', 'send_notification'
  action_config   JSONB NOT NULL,  -- action-specific parameters
  delay_minutes   INTEGER DEFAULT 0,  -- delay before executing
  is_active       BOOLEAN DEFAULT true,
  created_by      UUID REFERENCES users(id),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

## Standard Automation Rules (Default Configuration)

These rules ship as default but must remain configurable:

| Trigger Event | Delay | Action |
|--------------|-------|--------|
| `call.outcome.no_answer` | 0 | Add to No Answer Queue; create RECALL task |
| `call.outcome.callback_requested` | 0 | Create CALL_BACK task with due date = now + configurable hours |
| `call.outcome.call_later` | 0 | Create CALL_BACK task; prompt user for callback time |
| `activity.email_requested` | 0 | Create FOLLOW_UP task due in 24 hours |
| `activity.whatsapp_requested` | 0 | Create FOLLOW_UP task due in 24 hours |
| `lead.status.demo_scheduled` | 0 | Create DEMO task; notify owner |
| `lead.status.proposal_sent` | 0 | Create FOLLOW_UP task due in 48 hours |
| `task.overdue` | 0 | Escalate to team leader; notify owner |
| `lead.no_answer.max_attempts` | 0 | Notify manager for review |

## Trigger Events Catalogue

Triggers fired by the CRM event system:

### Call Triggers
- `call.created` — any call logged.
- `call.outcome.answered`
- `call.outcome.no_answer`
- `call.outcome.busy`
- `call.outcome.voicemail`
- `call.outcome.callback_requested`
- `call.outcome.call_later`
- `call.outcome.wrong_number`

### Lead Status Triggers
- `lead.status.changed` (with old_status and new_status in payload).
- `lead.status.new`
- `lead.status.contacted`
- `lead.status.demo_scheduled`
- `lead.status.proposal_sent`
- `lead.status.won`
- `lead.status.lost`

### Activity Triggers
- `activity.note_added`
- `activity.email_sent`
- `activity.whatsapp_sent`
- `activity.email_requested` (outcome of a call: contact requested email follow-up)
- `activity.whatsapp_requested`

### Task Triggers
- `task.created`
- `task.completed`
- `task.overdue` (fired by scheduler when due_date < now and not complete)

### Import Triggers
- `import.completed` (Google Sheets sync finished)
- `import.lead_assigned`

## Automation Execution Engine

### Event Processing Flow
```
CRM Action (e.g., log call with outcome=NO_ANSWER)
    ↓
Event emitted: { type: 'call.outcome.no_answer', payload: { contact_id, owner_id, call_id } }
    ↓
Rule Engine: query active rules WHERE trigger_event = 'call.outcome.no_answer'
    ↓
Evaluate conditions (JSONB conditions evaluated against payload)
    ↓
For each matching rule: enqueue action with delay
    ↓
Background worker processes action at scheduled time
    ↓
Action executed (create task, send notification, etc.)
    ↓
Automation execution logged in audit trail
```

### Condition Evaluation
```json
// Example: Only trigger recall if no_answer_count < 3
{
  "conditions": [
    { "field": "no_answer_count", "operator": "lt", "value": 3 }
  ]
}
```

Supported operators: `eq`, `neq`, `gt`, `gte`, `lt`, `lte`, `in`, `not_in`, `exists`.

## Action Types

### `create_task`
```json
{
  "action_type": "create_task",
  "action_config": {
    "task_type": "CALL_BACK",
    "title": "Recall — No Answer",
    "due_offset_hours": 4,
    "assign_to": "lead_owner",
    "priority": "HIGH"
  }
}
```

### `send_notification`
```json
{
  "action_type": "send_notification",
  "action_config": {
    "recipient": "lead_owner",
    "channel": "in_app",
    "message_template": "Follow up required for {{contact.name}}"
  }
}
```

### `update_lead_status`
```json
{
  "action_type": "update_lead_status",
  "action_config": {
    "new_status": "NO_ANSWER"
  }
}
```

### `assign_to_queue`
```json
{
  "action_type": "assign_to_queue",
  "action_config": {
    "queue": "no_answer_queue"
  }
}
```

## No Answer Queue Management

- Leads with `call.outcome.no_answer` enter the No Answer Queue.
- After configurable retry period (default: 4 hours), surface for retry.
- After configurable max attempts (default: 3), escalate to manager.
- Queue is visible on the sales user's dashboard and manager's overview.

## Idempotency

- Every automation execution is recorded in `automation_executions` table.
- Before executing: check if this trigger+rule+entity combination was already executed within a dedup window.
- Prevent duplicate task creation on event replay.

```sql
CREATE TABLE automation_executions (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  rule_id       UUID REFERENCES automation_rules(id),
  trigger_event TEXT NOT NULL,
  entity_id     UUID NOT NULL,
  entity_type   TEXT NOT NULL,
  status        TEXT NOT NULL,  -- 'pending', 'executed', 'failed', 'skipped'
  error_message TEXT,
  scheduled_for TIMESTAMPTZ,
  executed_at   TIMESTAMPTZ,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

## What NOT to Do

- Do NOT hardcode automation delays as constants in application code.
- Do NOT skip idempotency checks (risk of duplicate tasks/notifications).
- Do NOT execute automation actions synchronously in API handlers.
- Do NOT allow automation rules to trigger other automation rules recursively (infinite loops).
- Do NOT implement the automation engine yet — this skill is for architecture guidance.
