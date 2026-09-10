"""
app.imports.reconciler — Deduplication and record classification.

Responsibilities
----------------
- Merge duplicate LeadRows by import_key within a single batch.
- Classify rows as: new / matched / duplicate / invalid / awaiting_review.
- Build an ImportReport with per-sheet and per-category counters.
- No database access; pure in-memory logic.

Matching philosophy
-------------------
A contact is matched to an existing record when:
  1. import_keys are identical (primary), OR
  2. normalised emails are identical (non-blank), OR
  3. normalised phones are identical via phones_could_match() AND first names
     overlap (prevents merging a shared office phone as one person).

Condition 3 requires corroborating evidence — a phone alone is NOT sufficient
when the first names are clearly different people.  Ambiguous cases (same phone,
different name, no email) are flagged separately and NOT auto-merged.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Set, Tuple

from app.imports.normalizers import phones_could_match
from app.imports.workbook_reader import LeadRow


# ── Classification categories ─────────────────────────────────────────────────

CATEGORY_NEW             = "new"
CATEGORY_MATCHED         = "matched"
CATEGORY_DUPLICATE       = "duplicate"
CATEGORY_INVALID         = "invalid"
CATEGORY_AWAITING_REVIEW = "awaiting_review"

# Known legacy (unresolvable) salesperson values
LEGACY_SALESPERSON_NAMES: FrozenSet[str] = frozenset({"maria", "raneem"})
# Known valid CRM salesperson first-names (lower)
KNOWN_SALESPERSON_NAMES: FrozenSet[str] = frozenset(
    {"saleh", "hassan", "amin", "ghaida", "ghayda", "qusai", "abdallah", "aseel"}
)


# ── ImportReport ──────────────────────────────────────────────────────────────

@dataclass
class SheetStats:
    sheet_name: str
    rows_read: int = 0
    rows_invalid: int = 0
    rows_duplicate_intra: int = 0
    rows_matched_db: int = 0
    rows_new: int = 0
    rows_awaiting_review: int = 0
    rows_conflicts: int = 0


@dataclass
class ImportReport:
    """Aggregated statistics for one import run."""
    total_rows_read: int = 0
    total_invalid: int = 0
    total_intra_duplicates: int = 0
    total_db_matched: int = 0
    total_new: int = 0
    total_awaiting_review: int = 0
    total_inserted: int = 0
    total_updated: int = 0
    total_skipped: int = 0
    total_errors: int = 0
    total_conflicts: int = 0

    per_sheet: Dict[str, SheetStats] = field(default_factory=dict)
    awaiting_review_rows: List[Dict] = field(default_factory=list)
    invalid_rows: List[Dict] = field(default_factory=list)
    conflict_rows: List[Dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "summary": {
                "total_rows_read":       self.total_rows_read,
                "total_invalid":         self.total_invalid,
                "total_intra_duplicates": self.total_intra_duplicates,
                "total_db_matched":      self.total_db_matched,
                "total_new":             self.total_new,
                "total_awaiting_review": self.total_awaiting_review,
                "total_inserted":        self.total_inserted,
                "total_updated":         self.total_updated,
                "total_skipped":         self.total_skipped,
                "total_errors":          self.total_errors,
                "total_conflicts":       self.total_conflicts,
            },
            "per_sheet": {
                k: {
                    "rows_read":            v.rows_read,
                    "rows_invalid":         v.rows_invalid,
                    "rows_duplicate_intra": v.rows_duplicate_intra,
                    "rows_matched_db":      v.rows_matched_db,
                    "rows_new":             v.rows_new,
                    "rows_awaiting_review": v.rows_awaiting_review,
                    "rows_conflicts":       v.rows_conflicts,
                }
                for k, v in self.per_sheet.items()
            },
            "awaiting_review_rows": self.awaiting_review_rows[:200],
            "invalid_rows":         self.invalid_rows[:200],
            "conflict_rows":        self.conflict_rows[:100],
        }


# ── Merge scoring & conflict resolution ───────────────────────────────────────

def _completeness_score(lr: LeadRow) -> int:
    s = 0
    if lr.normalized_email:   s += 10
    if lr.normalized_phone:   s += 8
    if lr.company:            s += 4
    if lr.position:           s += 3
    if lr.notes:              s += 2
    if lr.last_contacted:     s += 1
    if lr.salesperson:        s += 2
    if lr.attempt_count > 0:  s += lr.attempt_count
    return s


def _qualification_weight(row: LeadRow) -> int:
    """Score the engagement / qualification progress of call attempt outcomes."""
    high_engagement = {
        "demo", "interested", "asked for email", "asked for whatapp",
        "asked for whatsapp", "re call", "recall",
    }
    score = 0
    for att in (row.attempt_1_text, row.attempt_2_text, row.attempt_3_text):
        if not att:
            continue
        low = att.strip().lower()
        if any(term in low for term in high_engagement):
            score += 5
        elif any(term in low for term in ("no answer", "wrong number", "not interested", "voice male", "voice mail")):
            score += 1
        else:
            score += 2
    return score


def _resolve_salesperson_conflict(
    row_a: LeadRow, row_b: LeadRow
) -> Tuple[str, str, str]:
    """Resolve ownership conflict between two rows with different salespeople.

    Returns (winner_salesperson, loser_salesperson, reason).

    Business rules:
    1. Empty vs non-empty: non-empty always wins.
    2. Operational / legacy exclusion: Aseel (DATA_OPS) and legacy employees
       (Maria, Raneem) are never preferred over active sales reps.
    3. Explicit Notes attribution: If one row's notes explicitly name the other
       salesperson (e.g. Amin's rows for QatarEnergy note 'Saleh'), that rep wins.
    4. Sales qualification progress: Rep with higher-engagement outcomes (Demo, Interested,
       Asked for email/whatsapp, Re Call) wins over passive No Answer.
    5. Attempt count: Rep with more recorded attempts wins.
    6. Canonical sheet priority: 'Leads' worksheet takes priority over sub-sheets.
    7. Deterministic tie-breaker: Alphabetical on normalized name (NEVER random row order).
    """
    sp_a = (row_a.salesperson or "").strip()
    sp_b = (row_b.salesperson or "").strip()

    if sp_a and not sp_b:
        return sp_a, sp_b, "Only one record has an assigned salesperson"
    if sp_b and not sp_a:
        return sp_b, sp_a, "Only one record has an assigned salesperson"

    sp_a_low = sp_a.lower()
    sp_b_low = sp_b.lower()

    if sp_a_low == sp_b_low:
        return sp_a, sp_b, "Identical salesperson"

    # Exclude operational/legacy
    excluded = {"aseel", "maria", "raneem"}
    if sp_a_low in excluded and sp_b_low not in excluded:
        return sp_b, sp_a, f"Sales rep '{sp_b}' preferred over operational/legacy '{sp_a}'"
    if sp_b_low in excluded and sp_a_low not in excluded:
        return sp_a, sp_b, f"Sales rep '{sp_a}' preferred over operational/legacy '{sp_b}'"

    # Explicit notes attribution / handoff
    notes_a = (row_a.notes or "").lower()
    notes_b = (row_b.notes or "").lower()
    if sp_b_low in notes_a and sp_a_low not in notes_b:
        return sp_b, sp_a, f"Explicit handoff to '{sp_b}' documented in row notes"
    if sp_a_low in notes_b and sp_b_low not in notes_a:
        return sp_a, sp_b, f"Explicit handoff to '{sp_a}' documented in row notes"

    # Qualification progress
    q_a = _qualification_weight(row_a)
    q_b = _qualification_weight(row_b)
    if q_a > q_b:
        return sp_a, sp_b, f"Salesperson '{sp_a}' has higher qualification progress ({q_a} vs {q_b})"
    if q_b > q_a:
        return sp_b, sp_a, f"Salesperson '{sp_b}' has higher qualification progress ({q_b} vs {q_a})"

    # Attempt count
    if row_a.attempt_count > row_b.attempt_count:
        return sp_a, sp_b, f"Salesperson '{sp_a}' has more call attempts ({row_a.attempt_count} vs {row_b.attempt_count})"
    if row_b.attempt_count > row_a.attempt_count:
        return sp_b, sp_a, f"Salesperson '{sp_b}' has more call attempts ({row_b.attempt_count} vs {row_a.attempt_count})"

    # Canonical sheet priority
    if row_a.source_sheet == "Leads" and row_b.source_sheet != "Leads":
        return sp_a, sp_b, "Canonical assignment from 'Leads' worksheet"
    if row_b.source_sheet == "Leads" and row_a.source_sheet != "Leads":
        return sp_b, sp_a, "Canonical assignment from 'Leads' worksheet"

    # Deterministic tie-breaker (alphabetical by name, NEVER random row order)
    if sp_a_low < sp_b_low:
        return sp_a, sp_b, f"Deterministic canonical selection ({sp_a} over {sp_b})"
    else:
        return sp_b, sp_a, f"Deterministic canonical selection ({sp_b} over {sp_a})"


def _merge_rows(
    existing: LeadRow,
    incoming: LeadRow,
    report: Optional[ImportReport] = None,
) -> LeadRow:
    """Merge two rows for the same identity, keeping the richest data.

    Rules:
    - Winner = row with higher completeness score.
    - Gaps filled from loser (never overwrite non-blank winner fields).
    - Attempt count takes the maximum.
    - DEMO_SCHEDULED status propagates from either row.
    - Salesperson conflict: resolved deterministically via _resolve_salesperson_conflict,
      never by file row order or uploading user.
    """
    if _completeness_score(existing) >= _completeness_score(incoming):
        winner, loser = existing, incoming
    else:
        winner, loser = incoming, existing

    for f in ("normalized_email", "email", "normalized_phone", "phone",
              "company", "position", "notes", "last_contacted"):
        if not getattr(winner, f) and getattr(loser, f):
            setattr(winner, f, getattr(loser, f))

    winner.attempt_count = max(winner.attempt_count, loser.attempt_count)
    for af in ("attempt_1_text", "attempt_2_text", "attempt_3_text"):
        if not getattr(winner, af) and getattr(loser, af):
            setattr(winner, af, getattr(loser, af))

    if (existing.status_hint == "DEMO_SCHEDULED" or
            incoming.status_hint == "DEMO_SCHEDULED"):
        winner.status_hint = "DEMO_SCHEDULED"

    # Deterministic salesperson conflict resolution
    sp_exist = (existing.salesperson or "").strip()
    sp_incom = (incoming.salesperson or "").strip()
    if sp_exist and sp_incom and sp_exist.lower() != sp_incom.lower():
        resolved_sp, loser_sp, reason = _resolve_salesperson_conflict(existing, incoming)
        winner.salesperson = resolved_sp
        if report is not None:
            report.total_conflicts += 1
            sheet = winner.source_sheet or incoming.source_sheet or "_batch_"
            if sheet in report.per_sheet:
                report.per_sheet[sheet].rows_conflicts += 1
            report.conflict_rows.append({
                "sheet": sheet,
                "row": winner.source_row,
                "name": f"{winner.first_name} {winner.last_name}".strip(),
                "phone": winner.phone,
                "chosen_salesperson": resolved_sp,
                "other_salesperson": loser_sp,
                "reason": reason,
            })
    elif not winner.salesperson and loser.salesperson:
        winner.salesperson = loser.salesperson

    return winner


# ── Deduplication within a batch ──────────────────────────────────────────────

def deduplicate(
    all_rows: List[LeadRow],
    report: Optional[ImportReport] = None,
) -> Tuple[List[LeadRow], int]:
    """Deduplicate rows by import_key within the batch.

    Returns (unique_rows, intra_duplicate_count).
    Invalid rows (no import_key) pass through without merging.
    """
    seen: Dict[str, LeadRow] = {}
    merged_count = 0
    invalid_passthrough: List[LeadRow] = []

    for row in all_rows:
        if row.is_invalid or not row.import_key:
            invalid_passthrough.append(row)
            continue
        if row.import_key in seen:
            seen[row.import_key] = _merge_rows(seen[row.import_key], row, report=report)
            merged_count += 1
        else:
            seen[row.import_key] = row

    return list(seen.values()) + invalid_passthrough, merged_count


# ── DB state snapshot ─────────────────────────────────────────────────────────

@dataclass
class DbSnapshot:
    """Read-only snapshot of existing contact identifiers from the database.

    Populated by db_writer.load_db_snapshot() before classification.
    Contains all active contacts, including those WITHOUT an import_key
    (legacy records entered manually or by older import scripts).
    """
    # import_key → contact_id
    key_to_id:   Dict[str, object] = field(default_factory=dict)
    # normalised_email → contact_id  (for legacy contacts without import_key)
    email_to_id: Dict[str, object] = field(default_factory=dict)
    # normalised_phone → (contact_id, first_name)  — for corroborated phone match
    phone_to_id: Dict[str, Tuple[object, str]] = field(default_factory=dict)
    # import_key → (owner_id, status)  — used to detect reassignment risk
    key_to_owner: Dict[str, Tuple[object, str]] = field(default_factory=dict)


def _names_overlap(name_a: str, name_b: str) -> bool:
    """True if the two first-names share at least one word token."""
    if not name_a or not name_b:
        return True   # can't disprove — give benefit of doubt
    tokens_a = set(name_a.strip().lower().split())
    tokens_b = set(name_b.strip().lower().split())
    return bool(tokens_a & tokens_b)


def match_to_db(row: LeadRow, snap: DbSnapshot) -> Tuple[Optional[object], str]:
    """Match one LeadRow to an existing DB contact.

    Returns (contact_id_or_None, match_reason).
    match_reason is one of: "key", "email", "phone+name", "phone_ambiguous", "none".
    """
    # 1. import_key
    if row.import_key and row.import_key in snap.key_to_id:
        return snap.key_to_id[row.import_key], "key"

    # 2. normalised email (requires non-blank email)
    if row.normalized_email and row.normalized_email in snap.email_to_id:
        return snap.email_to_id[row.normalized_email], "email"

    # 3. normalised phone + corroborating first name
    if row.normalized_phone and row.normalized_phone in snap.phone_to_id:
        db_id, db_first = snap.phone_to_id[row.normalized_phone]
        if _names_overlap(row.first_name, db_first):
            return db_id, "phone+name"
        else:
            # Same phone, clearly different person → flag as conflict, do not merge
            return None, "phone_ambiguous"

    return None, "none"


# ── Classification ────────────────────────────────────────────────────────────

def classify_rows(
    rows: List[LeadRow],
    snap: DbSnapshot,
    report: ImportReport,
) -> Tuple[List[Tuple[LeadRow, Optional[object]]], List[LeadRow]]:
    """Classify rows into actionable and skipped lists.

    Returns (to_upsert, to_skip).
    to_upsert entries are (row, existing_contact_id_or_None).
    Side-effects: populates report counters and detail lists.
    """
    to_upsert: List[Tuple[LeadRow, Optional[object]]] = []
    to_skip:   List[LeadRow] = []

    for row in rows:
        sheet = row.source_sheet or "_unknown_"
        if sheet not in report.per_sheet:
            report.per_sheet[sheet] = SheetStats(sheet_name=sheet)
        stats = report.per_sheet[sheet]
        stats.rows_read += 1
        report.total_rows_read += 1

        # Invalid rows
        if row.is_invalid:
            stats.rows_invalid += 1
            report.total_invalid += 1
            report.invalid_rows.append({
                "sheet": row.source_sheet, "row": row.source_row,
                "reason": row.invalid_reason,
            })
            to_skip.append(row)
            continue

        # Salesperson classification
        sp_lower = row.salesperson.strip().lower() if row.salesperson else ""
        if sp_lower in LEGACY_SALESPERSON_NAMES:
            row.status_hint = "UNASSIGNED"
            stats.rows_awaiting_review += 1
            report.total_awaiting_review += 1
            report.awaiting_review_rows.append({
                "sheet": row.source_sheet, "row": row.source_row,
                "name": f"{row.first_name} {row.last_name}".strip(),
                "salesperson": row.salesperson,
                "reason": f"Legacy salesperson '{row.salesperson}' has no CRM account",
            })

        # Match to DB
        existing_id, match_reason = match_to_db(row, snap)

        if match_reason == "phone_ambiguous":
            stats.rows_conflicts += 1
            report.total_conflicts += 1
            report.conflict_rows.append({
                "sheet": row.source_sheet, "row": row.source_row,
                "name": f"{row.first_name} {row.last_name}".strip(),
                "phone": row.phone,
                "reason": "Phone matches existing contact but first names differ — not auto-merged",
            })
            to_skip.append(row)
            continue

        if existing_id is not None:
            stats.rows_matched_db += 1
            report.total_db_matched += 1
        else:
            stats.rows_new += 1
            report.total_new += 1

        to_upsert.append((row, existing_id))

    return to_upsert, to_skip
