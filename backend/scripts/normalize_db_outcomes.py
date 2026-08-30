"""
normalize_db_outcomes.py

Normalizes all raw outcome strings across the database (calls.outcome and contacts.last_outcome)
to official CallOutcome enum values (e.g., 'Asked for email' -> 'EMAIL_REQUESTED',
'No Answer' -> 'NO_ANSWER', 'Demo' -> 'DEMO_REQUESTED', etc.).
"""
import asyncio
from sqlalchemy import text
from app.database import engine

# Exact mapping table for existing database strings
OUTCOME_MAP = {
    # No Answer / Skipped
    "No Answer": "NO_ANSWER",
    "NO_ANSWER": "NO_ANSWER",
    "skip": "NO_ANSWER",
    "Skip": "NO_ANSWER",
    
    # Positive / High intent
    "Demo": "DEMO_REQUESTED",
    "DEMO_REQUESTED": "DEMO_REQUESTED",
    "Asked for email": "EMAIL_REQUESTED",
    "EMAIL_REQUESTED": "EMAIL_REQUESTED",
    "Asked for whatapp": "WHATSAPP_REQUESTED",
    "WHATSAPP_REQUESTED": "WHATSAPP_REQUESTED",
    "INTERESTED": "INTERESTED",
    "Interested": "INTERESTED",
    
    # Callback / Call later
    "Re Call": "CALL_LATER",
    "CALL_LATER": "CALL_LATER",
    "حولني لرقم ثاني": "CALL_LATER",
    
    # Not interested / Do not contact
    "Not interested": "NOT_INTERESTED",
    "NOT_INTERESTED": "NOT_INTERESTED",
    "Marketing": "NOT_INTERESTED",
    "don't call again": "DO_NOT_CONTACT",
    "DO_NOT_CONTACT": "DO_NOT_CONTACT",
    
    # Wrong number / Invalid person
    "wrong number": "WRONG_NUMBER",
    "WRONG_NUMBER": "WRONG_NUMBER",
    "NOT THE RIGHT PER": "WRONG_NUMBER",
    
    # Voicemail
    "voice male": "VOICEMAIL",
    "VOICEMAIL": "VOICEMAIL",
    
    # Other
    "HQ": "OTHER",
    "SOB": "OTHER",
    "OTHER": "OTHER",
}

def normalize_string(raw: str) -> str:
    if not raw:
        return "NO_ANSWER"
    raw_s = raw.strip()
    if raw_s in OUTCOME_MAP:
        return OUTCOME_MAP[raw_s]
    upper = raw_s.upper()
    if "DEMO" in upper:
        return "DEMO_REQUESTED"
    elif "EMAIL" in upper or "إيميل" in raw_s or "ايميل" in raw_s:
        return "EMAIL_REQUESTED"
    elif "WHATSAPP" in upper or "WHATAPP" in upper or "واتساب" in raw_s:
        return "WHATSAPP_REQUESTED"
    elif "NOT INTERESTED" in upper or "غير مهتم" in raw_s or "MARKETING" in upper:
        return "NOT_INTERESTED"
    elif "INTERESTED" in upper or "مهتم" in raw_s:
        return "INTERESTED"
    elif "CALL LATER" in upper or "RE CALL" in upper or "CALLBACK" in upper or "حولني" in raw_s:
        return "CALL_LATER"
    elif "WRONG" in upper or "رقم خاطئ" in raw_s or "NOT THE RIGHT" in upper:
        return "WRONG_NUMBER"
    elif "VOICE" in upper:
        return "VOICEMAIL"
    elif "DON'T CALL" in upper or "DONT CALL" in upper:
        return "DO_NOT_CONTACT"
    elif "NO ANSWER" in upper or upper in ("NA", "N/A", "NO ANS", "SKIP") or "لم يرد" in raw_s:
        return "NO_ANSWER"
    elif "BUSY" in upper or "مشغول" in raw_s:
        return "BUSY"
    elif "ANSWERED" in upper or "تم الرد" in raw_s:
        return "ANSWERED"
    return "OTHER"

async def run():
    async with engine.begin() as conn:
        print("1. Normalizing calls.outcome...")
        res = await conn.execute(text("SELECT id, outcome FROM calls"))
        calls = res.fetchall()
        updated_calls = 0
        for cid, out in calls:
            norm = normalize_string(out)
            if norm != out:
                await conn.execute(
                    text("UPDATE calls SET outcome = :norm WHERE id = :id"),
                    {"norm": norm, "id": cid}
                )
                updated_calls += 1
        print(f"[OK] Updated {updated_calls} of {len(calls)} calls.")

        print("2. Normalizing contacts.last_outcome...")
        res = await conn.execute(text("SELECT id, last_outcome FROM contacts WHERE last_outcome IS NOT NULL"))
        contacts = res.fetchall()
        updated_contacts = 0
        for cid, out in contacts:
            norm = normalize_string(out)
            if norm != out:
                await conn.execute(
                    text("UPDATE contacts SET last_outcome = :norm WHERE id = :id"),
                    {"norm": norm, "id": cid}
                )
                updated_contacts += 1
        print(f"[OK] Updated {updated_contacts} of {len(contacts)} contacts.")

    print("\nOutcome normalization complete successfully.")

if __name__ == "__main__":
    asyncio.run(run())
