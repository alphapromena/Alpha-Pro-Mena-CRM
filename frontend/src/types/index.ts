/**
 * Alpha Pro MENA CRM Shared TypeScript Types
 */

export type UserRole = 'TEAM_LEAD' | 'MANAGER' | 'USER' | 'ADMIN' | 'TEAM_LEADER' | 'SALES_USER' | 'DATA_OPS';

export interface User {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  full_name: string;
  role: UserRole;
  team_id: string | null;
  team_name: string | null;
  is_active: boolean;
  must_change_password?: boolean;
  email_verified?: boolean;
  lead_capacity: number;
  theme_preference?: string;
}

export type ContactStatus =
  | 'NEW'
  | 'CONTACTED'
  | 'IN_PROGRESS'
  | 'INTERESTED'
  | 'EMAIL_REQUESTED'
  | 'WHATSAPP_REQUESTED'
  | 'DEMO_SCHEDULED'
  | 'DEMO_DONE'
  | 'PROPOSAL_SENT'
  | 'NEGOTIATION'
  | 'WON'
  | 'LOST'
  | 'NOT_INTERESTED'
  | 'DO_NOT_CONTACT'
  | 'DUPLICATE'
  | 'RECALL_SCHEDULED'
  | 'NO_ANSWER'
  | 'UNASSIGNED'
  | 'ARCHIVED'
  | 'PENDING_CLAIM';

export interface Contact {
  id: string;
  first_name: string;
  last_name: string | null;
  full_name: string;
  email: string | null;
  phone: string | null;
  secondary_email?: string | null;
  secondary_phone?: string | null;
  company_id: string | null;
  company_name: string | null;
  position: string | null;
  department: string | null;
  country: string | null;
  industry: string | null;
  source: string | null;
  tags: string | null;
  notes: string | null;
  status: ContactStatus;
  priority: 'LOW' | 'MEDIUM' | 'HIGH' | 'URGENT';
  is_dnc: boolean;
  attempt_count?: number;
  attempts?: Array<{ id?: string; outcome: string; attempt_number: number; notes?: string | null; called_at?: string | null }>;
  attempt_1?: string | null;
  attempt_2?: string | null;
  attempt_3?: string | null;
  source_sheet?: string | null;
  sheet_order?: number | null;
  last_outcome?: string | null;
  final_outcome?: string | null;
  archived_at?: string | null;
  archived_by_id?: string | null;
  archived_by_name?: string | null;
  owner_id: string | null;
  owner_name: string | null;
  campaign_id: string | null;
  last_contact_at: string | null;
  next_contact_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface OpportunityRoadmapStep {
  id: string;
  company_id: string;
  opportunity_id?: string | null;
  contact_id?: string | null;
  contact_name?: string | null;
  user_id?: string | null;
  user_name?: string | null;
  step_type: string;
  step_date: string;
  notes?: string | null;
  status: string;
  step_order: number;
  created_at: string;
}

export interface Company {
  id: string;
  name: string;
  domain: string | null;
  industry: string | null;
  country: string | null;
  website: string | null;
  address: string | null;
  account_owner_id: string | null;
  account_owner_name: string | null;
  status: string;
  notes: string | null;
  tags: string | null;
  created_at: string;
  contacts?: Array<{
    id: string;
    full_name: string;
    position: string | null;
    email: string | null;
    phone: string | null;
    status: ContactStatus;
  }>;
  opportunities?: Array<{
    id: string;
    title: string;
    value: number | null;
    stage: string;
  }>;
}

export type TaskType = 'CALL' | 'EMAIL' | 'WHATSAPP' | 'RECALL' | 'FOLLOW_UP' | 'DEMO' | 'MEETING' | 'PROPOSAL' | 'OTHER';
export type TaskStatus = 'OPEN' | 'IN_PROGRESS' | 'COMPLETED' | 'OVERDUE' | 'CANCELLED';

export interface Task {
  id: string;
  title: string;
  description: string | null;
  contact_id: string | null;
  contact_name: string | null;
  company_id: string | null;
  assigned_to: string | null;
  assignee_name: string | null;
  type: TaskType;
  priority: 'LOW' | 'MEDIUM' | 'HIGH' | 'URGENT';
  status: TaskStatus;
  due_at: string | null;
  completed_at: string | null;
  completion_notes: string | null;
  created_at: string;
}

export interface Recall {
  id: string;
  contact_id: string;
  contact_name: string | null;
  company_name: string | null;
  user_id: string | null;
  scheduled_at: string;
  status: string;
  notes: string | null;
  created_at: string;
}

export interface NoAnswerItem {
  id: string;
  contact_id: string;
  contact_name: string | null;
  company_name: string | null;
  attempt_number: number;
  last_attempt_at: string | null;
  next_attempt_at: string | null;
  status: string;
}

export type DemoStatus =
  | 'INTERESTED_NEXT_STEP'
  | 'NOT_INTERESTED'
  | 'CANCELLED'
  | 'POSTPONED'
  | 'PENDING';

export type DemoReportStatus =
  | 'REPORT_COMPLETE'
  | 'NEEDS_REPORT';

export interface DemoItem {
  id: string;
  contact_id: string;
  contact_name: string | null;
  contact_phone?: string | null;
  contact_email?: string | null;
  company_id: string | null;
  company_name: string | null;
  owner_id: string | null;
  owner_name?: string | null;
  stage: string;
  status: DemoStatus | string;
  scheduled_at: string | null;
  completed_at: string | null;
  cancelled_at?: string | null;
  presenter?: string | null;
  attendees?: string | null;
  topics_covered?: string | null;
  summary?: string | null;
  result: string | null;
  reason?: string | null;
  next_step?: string | null;
  next_step_due_date?: string | null;
  notes: string | null;
  report_status: DemoReportStatus | string;
  is_historical: boolean;
  historical_source?: string | null;
  historical_date?: string | null;
  created_by_id?: string | null;
  updated_by_id?: string | null;
  created_at: string;
  updated_at?: string;
}

export interface Opportunity {
  id: string;
  title: string;
  contact_id: string | null;
  contact_name: string | null;
  company_id: string | null;
  company_name: string | null;
  owner_id: string | null;
  value: number | null;
  stage: 'NEW' | 'QUALIFIED' | 'DEMO' | 'PROPOSAL' | 'NEGOTIATION' | 'WON' | 'LOST';
  probability: number | null;
  expected_close_at: string | null;
  lost_reason: string | null;
  created_at: string;
}

export interface Campaign {
  id: string;
  name: string;
  description: string | null;
  status: string;
  target_country: string | null;
  target_industry: string | null;
  owner_id: string | null;
  start_at: string | null;
  end_at: string | null;
  created_at: string;
}

export interface NotificationItem {
  id: string;
  type: string;
  title: string;
  message: string;
  is_read: boolean;
  entity_type: string | null;
  entity_id: string | null;
  created_at: string;
}

export interface TimelineItem {
  type: 'call' | 'note' | 'task' | 'email' | 'whatsapp' | 'status_change' | 'audit' | 'demo';
  id: string;
  timestamp: string;
  user: string;
  outcome?: string;
  notes?: string;
  content?: string;
  duration_seconds?: number;
  is_pinned?: boolean;
  task_type?: string;
  status?: string;
  title?: string;
  subject?: string;
  direction?: string;
  message_preview?: string;
  old_status?: string;
  new_status?: string;
  action?: string;
  stage?: string;
  old_value?: any;
  new_value?: any;
}

export interface ApiResponse<T> {
  data: T;
  meta?: {
    total?: number;
    page?: number;
    per_page?: number;
    total_pages?: number;
    unread_count?: number;
    request_id?: string;
  };
  error?: {
    code: string;
    message: string;
    details?: Array<{ field?: string; message: string }>;
  };
}
