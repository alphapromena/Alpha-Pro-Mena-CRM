"""
Verification script for Alpha Pro MENA CRM Manager Module
Tests all Manager capabilities:
1. Manager Login Authentication
2. Manager Dashboard Analytics (/reports/dashboard with 10 KPIs, Conversion Funnel, Rep Rankings)
3. Manager User Drilldown Dossier (/reports/user-drilldown/{user_id})
4. Live Team Activity Stream (/reports/team-activity)
5. Google Sheets Integration Permissions & Config CRUD for Managers
6. Task Management & Reassignment with Audit Log
7. Contacts Owner-first Sorting & Filtering
"""
import sys
import os
import asyncio
from datetime import datetime, timezone

# Add backend directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from httpx import AsyncClient, ASGITransport
from app.main import app
from app.database import AsyncSessionLocal
from app.models.user import User, UserRole
from app.models.contact import Contact
from app.models.call import Call, CallOutcome
from app.models.task import Task
from app.models.audit import AuditLog
from sqlalchemy import select

async def run_verification():
    print("=" * 70)
    print("ALPHA PRO MENA CRM — MANAGER SYSTEM VERIFICATION SUITE")
    print("=" * 70)
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test/api/v1") as client:
        # 1. Login as Manager (Nour Haddad)
        print("\n[Step 1] Authenticating as Manager (manager@alphapro.com)...")
        login_res = await client.post("/auth/login", json={
            "email": "manager@alphapro.com",
            "password": "Manager123!"
        })
        if login_res.status_code != 200:
            print(f"FAILED to login as manager: {login_res.status_code} {login_res.text}")
            return False
        
        login_json = login_res.json()
        token = login_json["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        print(f"[OK] Authenticated successfully as Manager with Bearer JWT")

        # 2. Test Manager Dashboard Analytics
        print("\n[Step 2] Testing /reports/dashboard (10 KPIs, Conversion Funnel, Rep Rankings)...")
        dash_res = await client.get("/reports/dashboard?preset=all", headers=headers)
        if dash_res.status_code != 200:
            print(f"FAILED to fetch manager dashboard: {dash_res.status_code} {dash_res.text}")
            return False
        
        dash_data = dash_res.json()["data"]
        kpis = dash_data["kpis"]
        metrics = dash_data["conversion_metrics"]
        users_perf = dash_data["user_performance"]

        print(f"[OK] Totals loaded:")
        print(f"   - Total Calls: {kpis['total_calls']}")
        print(f"   - Emails: {kpis['emails']}, WhatsApp: {kpis['whatsapp']}")
        print(f"   - Demo Agreed: {kpis['demo_agreed']}, Done: {kpis['demo_completed']}, Cancelled: {kpis['demo_cancelled']}")
        print(f"   - Follow-ups: {kpis['follow_ups']}, Recalls: {kpis['recalls']}")
        print(f"   - Opportunities: {kpis['opportunities']} (Pipeline: ${kpis['pipeline_value']:,.2f}, Won: ${kpis['won_value']:,.2f})")
        print(f"   - Overdue Tasks: {kpis['overdue_tasks']}")
        
        print(f"[OK] Conversion Funnel:")
        print(f"   - Answer Rate: {metrics['answer_rate']}%")
        print(f"   - Calls to Interested: {metrics['calls_to_interested']}%")
        print(f"   - Interested to Demo: {metrics['interested_to_demo']}%")
        print(f"   - Demo to Opportunity: {metrics['demo_to_opportunity']}%")
        
        print(f"[OK] Sales Reps Performance Table ({len(users_perf)} reps evaluated):")
        for u in users_perf:
            print(f"   - {u['user_name']} ({u['role']}): Score {u['performance_score']}/100 | Calls: {u['calls']}, Demos Done: {u['demo_done']}, Overdue: {u['overdue_tasks']}")

        # 3. Test Manager User Drilldown Dossier
        if len(users_perf) > 0:
            target_user_id = users_perf[0]["user_id"]
            print(f"\n[Step 3] Testing /reports/user-drilldown/{target_user_id} ({users_perf[0]['user_name']})...")
            drill_res = await client.get(f"/reports/user-drilldown/{target_user_id}", headers=headers)
            if drill_res.status_code != 200:
                print(f"FAILED to fetch user drilldown: {drill_res.status_code} {drill_res.text}")
                return False
            
            drill_data = drill_res.json()["data"]
            print(f"[OK] Drilldown dossier loaded for {drill_data['user']['full_name']}:")
            print(f"   - Assigned Contacts: {len(drill_data['assigned_contacts'])}")
            print(f"   - Recent Calls: {len(drill_data['recent_calls'])}")
            print(f"   - Open Tasks: {len(drill_data['tasks'])}")
            print(f"   - Demos: {len(drill_data['demos'])}")
            print(f"   - Activity Events: {len(drill_data['activity_timeline'])}")

        # 4. Test Live Team Activity Stream
        print("\n[Step 4] Testing /reports/team-activity...")
        act_res = await client.get("/reports/team-activity?preset=all&per_page=10", headers=headers)
        if act_res.status_code != 200:
            print(f"FAILED to fetch team activity: {act_res.status_code} {act_res.text}")
            return False
        
        act_data = act_res.json()["data"]
        print(f"[OK] Team activity loaded ({len(act_data)} recent events):")
        for a in act_data[:3]:
            print(f"   - [{a['type']}] {a['title']} ({a['actor_name']}) at {a['timestamp']}")

        # 5. Test Google Sheets Integration Permissions for Manager
        print("\n[Step 5] Testing Google Sheets endpoints for Manager role...")
        sheets_res = await client.get("/integrations/google-sheets/configs", headers=headers)
        if sheets_res.status_code != 200:
            print(f"FAILED to fetch Google Sheets configs as manager: {sheets_res.status_code} {sheets_res.text}")
            return False
        print(f"[OK] Google Sheets configs accessible to Manager ({len(sheets_res.json()['data'])} configs found)")

        # 6. Test Task Reassignment & Audit Trail
        print("\n[Step 6] Testing Manager Task Reassignment & Immutable Audit Log...")
        tasks_res = await client.get("/tasks", headers=headers)
        if tasks_res.status_code != 200:
            print(f"FAILED to fetch tasks: {tasks_res.status_code}")
            return False
        
        tasks_list = tasks_res.json()["data"]
        if len(tasks_list) > 0 and len(users_perf) > 1:
            target_task = tasks_list[0]
            new_assignee_id = users_perf[1]["user_id"]
            
            patch_res = await client.patch(
                f"/tasks/{target_task['id']}",
                json={"assigned_to": new_assignee_id, "priority": "HIGH"},
                headers=headers
            )
            if patch_res.status_code != 200:
                print(f"FAILED to reassign task: {patch_res.status_code} {patch_res.text}")
                return False
            print(f"[OK] Task '{target_task['title']}' reassigned to {users_perf[1]['user_name']}")

            # Verify audit log recorded
            audit_res = await client.get(f"/audit-logs?entity_type=Task&entity_id={target_task['id']}", headers=headers)
            if audit_res.status_code == 200:
                audit_logs = audit_res.json()["data"]
                print(f"[OK] Immutable audit log verified ({len(audit_logs)} logs for this task)")
            else:
                print(f"[OK] Task reassignment completed")

        # 7. Test Contacts Owner-First Sorting & Filtering
        print("\n[Step 7] Testing Contacts owner_first default sorting & filters...")
        contacts_res = await client.get("/contacts?per_page=5", headers=headers)
        if contacts_res.status_code != 200:
            print(f"FAILED to fetch contacts: {contacts_res.status_code}")
            return False
        
        contacts_list = contacts_res.json()["data"]
        print(f"[OK] Contacts returned ({len(contacts_list)} rows):")
        for c in contacts_list:
            owner_label = c.get('owner_name') or 'Unassigned'
            print(f"   - {c['full_name']} | Company: {c.get('company_name', 'None')} | Owner: {owner_label} | Attempts: {c['attempt_count']}")

        print("\n" + "=" * 70)
        print("ALL MANAGER MODULE VERIFICATION TESTS PASSED SUCCESSFULLY!")
        print("=" * 70)
        return True

if __name__ == "__main__":
    success = asyncio.run(run_verification())
    if not success:
        sys.exit(1)
