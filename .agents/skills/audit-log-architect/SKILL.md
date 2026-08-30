---
name: audit-log-architect
description: >-
  Use this skill when designing or implementing audit logging for any entity,
  action, or administrative operation. Activate when the task involves tracking
  user actions, contact modifications, lead ownership changes, status changes,
  task operations, authentication events, or any operation that must be
  permanently recorded for compliance, security, or business accountability.
  Audit logs are immutable — this skill enforces that guarantee.
---

# Audit Log Architect

You are acting as a Senior Compliance and Audit Architect. Your responsibility
is to ensure all significant system actions are permanently, immutably recorded
with enough context to reconstruct exactly what happened, when, by whom, and why.

## Core Guarantee: Immutability

Audit logs are **append-only**. Once written, they cannot be modified or deleted.
This is enforced at multiple levels:
1. Database: no `UPDATE` or `DELETE` granted on the `audit_logs` table.
2. Application: no `update()` or `delete()` method exists on the audit log repository.
3. ORM: the audit log model has no mutation methods.

## Database Schema

```sql
CREATE TABLE audit_logs (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  
  -- Who performed the action
  actor_id      UUID REFERENCES users(id) ON DELETE SET NULL,
  actor_role    TEXT NOT NULL,          -- snapshot of role at time of action
  actor_email   TEXT NOT NULL,          -- snapshot of email (in case user is deleted)
  
  -- What was done
  action        TEXT NOT NULL,          -- event name, e.g., 'contact.status_changed'
  
  -- What was affected
  entity_type   TEXT NOT NULL,          -- e.g., 'contact', 'lead', 'user', 'task'
  entity_id     UUID NOT NULL,
  
  -- The change
  old_value     JSONB,                  -- state before change (null for create actions)
  new_value     JSONB,                  -- state after change (null for delete actions)
  
  -- Context
  ip_address    INET,
  user_agent    TEXT,
  request_id    TEXT,                   -- links to application log trace
  
  -- Notes
  description   TEXT,                  -- human-readable description of what happened
  
  -- Timestamp (immutable)
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
  
  -- No updated_at — audit logs are never updated
);

-- Indexes for efficient querying
CREATE INDEX idx_audit_entity ON audit_logs (entity_type, entity_id, created_at DESC);
CREATE INDEX idx_audit_actor ON audit_logs (actor_id, created_at DESC);
CREATE INDEX idx_audit_action ON audit_logs (action, created_at DESC);
CREATE INDEX idx_audit_created ON audit_logs (created_at DESC);

-- Revoke modification permissions
REVOKE UPDATE, DELETE ON audit_logs FROM app_user;
-- Only INSERT and SELECT allowed
GRANT INSERT, SELECT ON audit_logs TO app_user;
```

## Audit Event Catalogue

### Authentication Events
| Action | Trigger |
|--------|---------|
| `auth.login.success` | Successful login |
| `auth.login.failed` | Failed login attempt |
| `auth.logout` | User logout |
| `auth.password.changed` | Password changed by user |
| `auth.password.reset.requested` | Reset link requested |
| `auth.password.reset.completed` | Password reset via link |
| `auth.account.locked` | Account locked after failures |
| `auth.account.unlocked` | Account manually unlocked |
| `auth.session.expired` | Session timeout |

### Contact Events
| Action | Trigger |
|--------|---------|
| `contact.created` | New contact created |
| `contact.updated` | Contact fields modified |
| `contact.status_changed` | Status transition |
| `contact.deleted` | Soft delete |
| `contact.restored` | Soft delete reversed |
| `contact.dnc_set` | Marked Do Not Contact |
| `contact.dnc_removed` | DNC status removed |
| `contact.merged` | Two contacts merged |
| `contact.duplicate_flagged` | Flagged as duplicate |

### Lead Events
| Action | Trigger |
|--------|---------|
| `lead.assigned` | Lead assigned to user |
| `lead.reassigned` | Lead ownership changed |
| `lead.imported` | Lead imported from Google Sheets |
| `lead.status_changed` | Pipeline status change |
| `lead.unassigned` | Lead returned to pool |

### Activity Events
| Action | Trigger |
|--------|---------|
| `call.logged` | Call activity recorded |
| `email.logged` | Email activity recorded |
| `whatsapp.logged` | WhatsApp activity recorded |
| `note.created` | Note added |
| `note.deleted` | Note removed |

### Task Events
| Action | Trigger |
|--------|---------|
| `task.created` | Task created (manual or automated) |
| `task.completed` | Task marked complete |
| `task.deleted` | Task removed |
| `task.reassigned` | Task assigned to different user |

### Admin Events
| Action | Trigger |
|--------|---------|
| `user.created` | New user account |
| `user.role_changed` | User role modified |
| `user.deactivated` | User account disabled |
| `user.activated` | User account re-enabled |
| `campaign.created` | New campaign |
| `campaign.updated` | Campaign modified |
| `automation_rule.created` | New automation rule |
| `automation_rule.updated` | Rule modified |
| `automation_rule.disabled` | Rule deactivated |
| `import.started` | Google Sheets sync began |
| `import.completed` | Sync completed |
| `import.failed` | Sync failed |
| `config.updated` | System configuration change |

## Application Layer Implementation

```typescript
// repositories/auditLog.repo.ts
export class AuditLogRepository {
  async log(entry: CreateAuditLogInput): Promise<void> {
    await db.query(`
      INSERT INTO audit_logs (
        actor_id, actor_role, actor_email, action, entity_type, entity_id,
        old_value, new_value, ip_address, user_agent, request_id, description
      ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
    `, [
      entry.actorId, entry.actorRole, entry.actorEmail,
      entry.action, entry.entityType, entry.entityId,
      entry.oldValue ? JSON.stringify(entry.oldValue) : null,
      entry.newValue ? JSON.stringify(entry.newValue) : null,
      entry.ipAddress, entry.userAgent, entry.requestId, entry.description
    ]);
    // No update() or delete() methods exist on this repository
  }

  async getForEntity(entityType: string, entityId: string, options: PaginationOptions) {
    // Read-only queries only
  }
}
```

## Integration Pattern (In Service Layer)

```typescript
// In services, audit log AFTER the operation succeeds
async updateLeadStatus(
  leadId: string,
  newStatus: LeadStatus,
  actor: AuthenticatedUser,
  context: RequestContext
): Promise<Lead> {
  const lead = await this.leadRepo.findById(leadId);
  if (!lead) throw new NotFoundError('Lead not found');

  const oldStatus = lead.status;

  // 1. Perform the actual operation
  const updated = await this.leadRepo.updateStatus(leadId, newStatus);

  // 2. Audit log the change
  await this.auditLogRepo.log({
    actorId: actor.id,
    actorRole: actor.role,
    actorEmail: actor.email,
    action: 'lead.status_changed',
    entityType: 'lead',
    entityId: leadId,
    oldValue: { status: oldStatus },
    newValue: { status: newStatus },
    ipAddress: context.ipAddress,
    requestId: context.requestId,
    description: `Status changed from ${oldStatus} to ${newStatus}`,
  });

  return updated;
}
```

## Sensitive Data in Audit Logs

- **DO include**: old status, new status, field names changed, IDs, roles.
- **DO NOT include**: passwords, full credit card numbers, authentication tokens.
- **For PII fields** (email, phone): include them in audit logs for accountability but ensure audit logs are access-controlled (Manager/Admin only).

## Audit Log API (Admin/Manager)

```
GET /api/v1/audit-logs?entity_type=contact&entity_id={id}&page=1&per_page=25
```

Response: paginated list, most recent first.

Access control:
- Sales User: ❌ No access.
- Team Leader: Team entities only.
- Manager: All entities.
- Admin: All entities including auth events.

## Retention & Archival

- Audit logs are NEVER deleted from the primary table.
- After 1 year: archive to cold storage (S3, separate DB, or compressed files).
- Archived logs remain queryable (via an admin tool, not the main UI).
- Compliance requirement: retain for minimum 3 years (adjust per jurisdiction).

## What NOT to Do

- Do NOT add UPDATE or DELETE methods to the audit log repository.
- Do NOT skip audit logging for "minor" operations (every significant action counts).
- Do NOT log audit events BEFORE the operation — they might succeed in logging but fail in operation.
- Do NOT log passwords or tokens in audit log values.
- Do NOT allow sales users to read audit logs.
- Do NOT delete or modify audit log rows, ever.
