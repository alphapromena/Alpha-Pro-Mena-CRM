# CRM Domain Business Rules & Workflow Engine

## 1. Lead Lifecycle State Machine

A contact transitions through validated states:

```
NEW ──► CONTACTED ──► IN_PROGRESS ──► DEMO_SCHEDULED ──► DEMO_DONE ──► PROPOSAL_SENT ──► NEGOTIATION ──► WON
 │          │              │                                                                          ▲
 │          ▼              ▼                                                                          │
 └──► NO_ANSWER ──► RECALL_SCHEDULED ──────────────────────────────────────────────────────────────────┘
            │              │
            ▼              ▼
     DO_NOT_CONTACT (Terminal)
```

### Inviolable Rules
1. **Do Not Contact (DNC) Guarantee**: Marking a contact as DNC immediately blocks all outbound call logging, email dispatch, and scheduled task creation.
2. **History Preservation**: A lead status change never deletes previous interaction history. All calls, notes, and task records remain permanently attached to the contact timeline.
3. **No Answer Retry Cadence**:
   * Attempt 1: Retry after 7 days
   * Attempt 2: Retry after 7 days
   * Attempt 3: Retry after 14 days or escalate to manager review.
4. **Email Requested Automation**: When a call outcome is recorded as `EMAIL_REQUESTED`, the system automatically generates an outreach task and schedules a 24-hour follow-up upon completion.
5. **Customer Recall Booking**: When `CALL_LATER` is selected with a specific timestamp, the system registers a dedicated `Recall` task that alerts the agent 15 minutes before the appointment.
