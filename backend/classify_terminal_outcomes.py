"""
GULF LEADS TERMINAL OUTCOME CLASSIFIER
========================================
For each archived contact imported from Gulf Leads,
classify their last recorded attempt result into one of the 5 terminal outcomes:

  1. No Answer (Max Attempts)  -> attempt_1/2/3 all say "No Answer" or similar  
  2. Not Interested            -> "Not interested", "not int", etc.
  3. Wrong Number              -> "wrong number", "not the right", "skip"
  4. Voice Mail / Don't Call   -> "voice mail", "voicemail", "do not call"
  5. HQ / Switchboard          -> "HQ", "switchboard", "reception"

Active (non-terminal) results that stay in active status (but since these are
Gulf Leads which are all ARCHIVED, we just set final_outcome correctly):
  - "No Answer" with fewer than 3 matching attempts -> No Answer (Max Attempts) anyway
  - "Asked for email", "email requested"  -> final_outcome = EMAIL_REQUESTED
  - "Asked for whatsapp", "WhatsApp"      -> final_outcome = WHATSAPP_REQUESTED
  - "Re Call", "Recall", "Call Later"     -> final_outcome = RECALL_SCHEDULED
  - "Demo", "Demo scheduled"              -> final_outcome = DEMO_DONE
  - "Interested"                          -> final_outcome = INTERESTED
  - Empty / None                          -> final_outcome = NULL (no outcome recorded)

This does NOT move contacts between ACTIVE and ARCHIVED — all Gulf Leads are
already ARCHIVED. It only stamps the correct final_outcome field so the archive
view correctly shows WHY each lead was closed.
"""
import sqlite3
import re
from datetime import datetime, timezone

DB_PATH = 'f:\\New folder\\backend\\crm.db'

# ── Terminal outcome mappings ────────────────────────────────────────────────
# Each tuple: (regex pattern, final_outcome value)
TERMINAL_PATTERNS = [
    # Wrong Number
    (r'wrong.?number|not.?the.?right|wrong.?per|skip', 'Wrong Number'),
    # Voice Mail / Don't Call
    (r'voice.?m(ai|a)l|voicemail|don.?t.?call|do.?not.?call', "Voice Mail / Don't Call Again"),
    # HQ / Switchboard
    (r'\bhq\b|switchboard|reception|head.?quarter', 'HQ / Switchboard'),
    # Not Interested
    (r'not.?int|not interested|no.?interest|غير مهتم', 'Not Interested'),
]

# Active outcome mappings (will set final_outcome only, keep ARCHIVED status)
ACTIVE_PATTERNS = [
    (r'ask(ed)?.?(for)?.?email|email.?req|send.?email|send.*email', 'EMAIL_REQUESTED'),
    (r'ask(ed)?.?(for)?.?whatsapp|whatsapp.?req|send.?what', 'WHATSAPP_REQUESTED'),
    (r're.?call|recall|call.?later|call.?back', 'RECALL_SCHEDULED'),
    (r'\bdemo\b', 'DEMO_DONE'),
    (r'\binterested\b', 'INTERESTED'),
]

def classify_attempt(text: str) -> str | None:
    """Classify a single attempt text. Returns terminal outcome, active category, or None."""
    if not text:
        return None
    t = text.strip().lower()
    for pat, outcome in TERMINAL_PATTERNS:
        if re.search(pat, t, re.IGNORECASE):
            return outcome
    for pat, outcome in ACTIVE_PATTERNS:
        if re.search(pat, t, re.IGNORECASE):
            return outcome
    if re.search(r'no.?answer|no answer|لا يرد|بدون رد', t, re.IGNORECASE):
        return 'NO_ANSWER'
    return None

def classify_contact(a1, a2, a3) -> tuple[str | None, bool]:
    """
    Given 3 attempt fields, return (final_outcome, is_terminal).
    - If last non-None attempt is terminal -> return that terminal outcome
    - If all 3 attempts are NO_ANSWER -> return 'No Answer (Max Attempts)' as terminal
    - Otherwise -> return active outcome or None
    """
    attempts = [a for a in [a1, a2, a3] if a and str(a).strip()]
    if not attempts:
        return None, False

    outcomes = [classify_attempt(a) for a in attempts]
    
    # Check last recorded outcome
    last_outcome = outcomes[-1] if outcomes else None

    # Terminal check on last outcome
    terminal_outcomes = {'Wrong Number', "Voice Mail / Don't Call Again", 'HQ / Switchboard', 'Not Interested'}
    
    if last_outcome in terminal_outcomes:
        return last_outcome, True
    
    # Special: if ALL three attempts are NO_ANSWER -> terminal "No Answer (Max Attempts)"
    no_answer_count = sum(1 for o in outcomes if o == 'NO_ANSWER')
    if no_answer_count >= 3 or (len(attempts) >= 3 and all(o in ('NO_ANSWER', None) for o in outcomes)):
        return 'No Answer (Max Attempts)', True
    
    # Non-terminal outcomes for Gulf archived leads
    if last_outcome in ('EMAIL_REQUESTED', 'WHATSAPP_REQUESTED', 'RECALL_SCHEDULED', 'DEMO_DONE', 'INTERESTED'):
        return last_outcome, False
    
    return None, False

def run():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    now = datetime.now(timezone.utc).isoformat()

    print("=" * 70)
    print("GULF LEADS TERMINAL OUTCOME CLASSIFIER")
    print("=" * 70)

    # Get all archived contacts
    c.execute("""
        SELECT id, first_name, last_name, attempt_1, attempt_2, attempt_3, final_outcome
        FROM contacts
        WHERE status = 'ARCHIVED'
        AND deleted_at IS NULL
    """)
    archived = c.fetchall()
    print(f"\nTotal archived contacts: {len(archived)}")

    # Classify each
    counts = {
        'Wrong Number': 0,
        "Voice Mail / Don't Call Again": 0,
        'HQ / Switchboard': 0,
        'Not Interested': 0,
        'No Answer (Max Attempts)': 0,
        'EMAIL_REQUESTED': 0,
        'WHATSAPP_REQUESTED': 0,
        'RECALL_SCHEDULED': 0,
        'DEMO_DONE': 0,
        'INTERESTED': 0,
        'NO_OUTCOME': 0,
        'ALREADY_SET': 0,
    }

    updated = 0
    for row in archived:
        # Skip if already has a final_outcome set
        if row['final_outcome']:
            counts['ALREADY_SET'] += 1
            continue

        a1 = row['attempt_1']
        a2 = row['attempt_2']
        a3 = row['attempt_3']
        final_outcome, is_terminal = classify_contact(a1, a2, a3)

        if final_outcome:
            c.execute(
                "UPDATE contacts SET final_outcome=?, updated_at=? WHERE id=?",
                (final_outcome, now, row['id'])
            )
            updated += 1
            counts[final_outcome] = counts.get(final_outcome, 0) + 1
        else:
            counts['NO_OUTCOME'] += 1

    conn.commit()

    print(f"\nUpdated {updated} contacts with final_outcome")
    print("\nOutcome distribution:")
    for outcome, count in sorted(counts.items(), key=lambda x: -x[1]):
        if count > 0:
            print(f"  {outcome}: {count}")

    # Per-rep breakdown
    print("\n--- PER-REP BREAKDOWN ---")
    c.execute("""
        SELECT u.first_name,
               COUNT(*) as total,
               SUM(CASE WHEN ct.final_outcome IN ('Wrong Number', 'Voice Mail / Don''t Call Again',
                   'HQ / Switchboard', 'Not Interested', 'No Answer (Max Attempts)') THEN 1 ELSE 0 END) as terminal_count,
               SUM(CASE WHEN ct.final_outcome IS NULL THEN 1 ELSE 0 END) as no_outcome_count
        FROM contacts ct
        LEFT JOIN users u ON ct.owner_id = u.id
        WHERE ct.status = 'ARCHIVED' AND ct.deleted_at IS NULL
        GROUP BY ct.owner_id, u.first_name
        ORDER BY u.first_name
    """)
    for row in c.fetchall():
        rep = row['first_name'] or 'Unknown'
        total = row['total']
        terminal = row['terminal_count']
        no_outcome = row['no_outcome_count']
        print(f"  {rep}: {total} archived | {terminal} terminal | {no_outcome} no-outcome")

    # Final data integrity check
    print("\n--- FINAL COUNTS ---")
    c.execute("SELECT COUNT(*) FROM contacts WHERE status='NEW' AND deleted_at IS NULL")
    active_new = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM contacts WHERE status='UNASSIGNED' AND deleted_at IS NULL")
    active_unassigned = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM contacts WHERE status='ARCHIVED' AND deleted_at IS NULL")
    archived_count = c.fetchone()[0]
    
    print(f"  Active (NEW):        {active_new}")
    print(f"  Active (UNASSIGNED): {active_unassigned}")
    print(f"  Total Active:        {active_new + active_unassigned}")
    print(f"  Archived:            {archived_count}")
    print(f"  Grand Total:         {active_new + active_unassigned + archived_count}")

    print("\n[OK] DONE")
    conn.close()

if __name__ == '__main__':
    run()
