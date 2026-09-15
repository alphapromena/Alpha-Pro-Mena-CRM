import React, { useState, useEffect } from 'react';
import { api } from '../../lib/apiClient';
import { useAuthStore } from '../../store/authStore';
import { isManagerOrAbove } from '../../lib/permissions';
import { FollowUpItem } from '../../types';
import { LoadingSpinner } from '../../components/feedback/LoadingSpinner';
import { EmptyState } from '../../components/feedback/EmptyState';
import { Modal } from '../../components/ui/Modal';
import { AsyncCompanySelector, CompanySelectorItem } from '../../components/selectors/AsyncCompanySelector';
import { AsyncContactSelector, ContactSelectorItem } from '../../components/selectors/AsyncContactSelector';
import {
  Building2,
  ArrowDown,
  Plus,
  Calendar,
  User,
  CheckCircle2,
  Clock,
  Trash2,
  Edit2,
  FileText,
  Sparkles,
  PhoneCall,
  Mail,
  Presentation,
  Award,
  Search,
  Check,
  MessageSquare,
  Filter,
  ArrowRight,
  Building,
} from 'lucide-react';
import { useTranslation } from '../../i18n';
import { HistoricalImportDropZone } from '../../components/imports/HistoricalImportDropZone';

interface RoadmapStep {
  id: string;
  company_id: string;
  contact_id?: string | null;
  contact_name?: string | null;
  user_id?: string | null;
  user_name?: string;
  step_type: string;
  step_date: string;
  notes?: string | null;
  status: string;
  step_order: number;
  created_at: string;
}

const STEP_TYPE_PRESETS = [
  'First Call',
  'Email Sent',
  'Demo Scheduled',
  'Demo Completed',
  'Commercial Proposal Sent',
  'Security & Procurement Review',
  'Contract Negotiation',
  'Closed Won 🏆',
  'Latest Update',
];

export const FollowUpsPage: React.FC = () => {
  const { user } = useAuthStore();
  const { isRTL } = useTranslation();

  // Active View Tab
  const [activeTab, setActiveTab] = useState<'all' | 'journey'>('all');

  // ── Tab 1: All Follow-ups State ──────────────────────────────────────────
  const [followUps, setFollowUps] = useState<FollowUpItem[]>([]);
  const [isLoadingFollowUps, setIsLoadingFollowUps] = useState(false);
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [typeFilter, setTypeFilter] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [userFilter, setUserFilter] = useState<string>('');
  const [usersList, setUsersList] = useState<any[]>([]);

  // Create Follow-up Modal State
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [createForm, setCreateForm] = useState({
    company_name_snapshot: '',
    meeting_with: '',
    contact_id: '',
    user_id: user?.id || '',
    type: 'CALL',
    due_at: '',
    notes: '',
    next_step: '',
  });
  const [createContactItem, setCreateContactItem] = useState<ContactSelectorItem | null>(null);
  const [isSubmittingCreate, setIsSubmittingCreate] = useState(false);

  // Edit Follow-up Modal State
  const [editingFollowUp, setEditingFollowUp] = useState<FollowUpItem | null>(null);
  const [editForm, setEditForm] = useState({
    company_name_snapshot: '',
    meeting_with: '',
    status: 'PENDING',
    type: 'CALL',
    due_at: '',
    notes: '',
    next_step: '',
  });
  const [isSubmittingEdit, setIsSubmittingEdit] = useState(false);

  // ── Tab 2: Account Journey State ─────────────────────────────────────────
  const [selectedCompanyId, setSelectedCompanyId] = useState<string>('');
  const [selectedCompany, setSelectedCompany] = useState<CompanySelectorItem | null>(null);
  const [companyContacts, setCompanyContacts] = useState<any[]>([]);
  const [steps, setSteps] = useState<RoadmapStep[]>([]);
  const [isLoadingSteps, setIsLoadingSteps] = useState(false);

  // Add Step Modal State
  const [isAddStepModalOpen, setIsAddStepModalOpen] = useState(false);
  const [editingStep, setEditingStep] = useState<RoadmapStep | null>(null);
  const [stepTitle, setStepTitle] = useState('First Call');
  const [stepDate, setStepDate] = useState(() => new Date().toISOString().split('T')[0]);
  const [stepContactItem, setStepContactItem] = useState<ContactSelectorItem | null>(null);
  const [stepContactId, setStepContactId] = useState('');
  const [stepStatus, setStepStatus] = useState('COMPLETED');
  const [stepNotes, setStepNotes] = useState('');
  const [isSubmittingStep, setIsSubmittingStep] = useState(false);

  const hasManagerPrivileges = isManagerOrAbove(user?.role);

  // Load Users List for filtering and assignments
  useEffect(() => {
    const loadUsers = async () => {
      try {
        const res = await api.get<any>('/users/eligible-demo-owners');
        setUsersList(res.data || []);
      } catch {
        // fallback (only if authorized)
        if (hasManagerPrivileges) {
          try {
            const res = await api.get<any>('/users');
            setUsersList(res.data || []);
          } catch (e) {
            console.error('Failed to load users list', e);
          }
        }
      }
    };
    loadUsers();
  }, [hasManagerPrivileges]);

  // Fetch Follow-ups list
  const fetchFollowUps = async () => {
    setIsLoadingFollowUps(true);
    try {
      const params: Record<string, any> = { per_page: 100 };
      if (statusFilter !== 'ALL') params.status = statusFilter;
      if (typeFilter !== 'ALL') params.type = typeFilter;
      if (userFilter) params.user_id = userFilter;
      const res = await api.get<any>('/follow-ups', params);
      setFollowUps(res.data || []);
    } catch (e) {
      console.error('Failed to load follow-ups', e);
    } finally {
      setIsLoadingFollowUps(false);
    }
  };

  useEffect(() => {
    if (activeTab === 'all') {
      fetchFollowUps();
    }
  }, [activeTab, statusFilter, typeFilter, userFilter]);

  // Fetch Steps and Contacts when selected company changes (Journey tab)
  useEffect(() => {
    if (!selectedCompanyId || activeTab !== 'journey') return;

    const fetchJourney = async () => {
      setIsLoadingSteps(true);
      try {
        const [stepsRes, contactsRes] = await Promise.all([
          api.get<any>(`/opportunities/roadmap/${selectedCompanyId}`),
          api.get<any>('/contacts', { company_id: selectedCompanyId, per_page: 50 }),
        ]);
        setSteps(stepsRes.data || []);
        setCompanyContacts(contactsRes.data || []);
      } catch (e) {
        console.error('Failed to load journey steps', e);
      } finally {
        setIsLoadingSteps(false);
      }
    };

    fetchJourney();
  }, [selectedCompanyId, activeTab]);

  // Handle Create Follow-up
  const handleOpenCreateModal = () => {
    setCreateContactItem(null);
    setCreateForm({
      company_name_snapshot: '',
      meeting_with: '',
      contact_id: '',
      user_id: user?.id || '',
      type: 'CALL',
      due_at: '',
      notes: '',
      next_step: '',
    });
    setIsCreateModalOpen(true);
  };

  const handleSaveFollowUp = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmittingCreate(true);
    try {
      await api.post('/follow-ups', {
        company_name_snapshot: createForm.company_name_snapshot.trim() || undefined,
        meeting_with: createForm.meeting_with.trim() || undefined,
        contact_id: createForm.contact_id || undefined,
        user_id: createForm.user_id || undefined,
        type: createForm.type,
        due_at: createForm.due_at ? new Date(createForm.due_at).toISOString() : undefined,
        notes: createForm.notes.trim() || undefined,
        next_step: createForm.next_step.trim() || undefined,
        status: 'PENDING',
      });
      setIsCreateModalOpen(false);
      await fetchFollowUps();
    } catch (err: any) {
      alert(err.message || 'Failed to create follow-up');
    } finally {
      setIsSubmittingCreate(false);
    }
  };

  // Handle Edit Follow-up
  const handleOpenEditModal = (fu: FollowUpItem) => {
    setEditingFollowUp(fu);
    setEditForm({
      company_name_snapshot: fu.company_name_snapshot || fu.company_name || '',
      meeting_with: fu.meeting_with || fu.contact_name || '',
      status: fu.status || 'PENDING',
      type: fu.type || 'CALL',
      due_at: fu.due_at ? fu.due_at.slice(0, 16) : '',
      notes: fu.notes || '',
      next_step: fu.next_step || '',
    });
  };

  const handleUpdateFollowUp = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingFollowUp) return;
    setIsSubmittingEdit(true);
    try {
      await api.patch(`/follow-ups/${editingFollowUp.id}`, {
        company_name_snapshot: editForm.company_name_snapshot.trim() || undefined,
        meeting_with: editForm.meeting_with.trim() || undefined,
        status: editForm.status,
        type: editForm.type,
        due_at: editForm.due_at ? new Date(editForm.due_at).toISOString() : undefined,
        notes: editForm.notes.trim() || undefined,
        next_step: editForm.next_step.trim() || undefined,
      });
      setEditingFollowUp(null);
      await fetchFollowUps();
    } catch (err: any) {
      alert(err.message || 'Failed to update follow-up');
    } finally {
      setIsSubmittingEdit(false);
    }
  };

  const handleQuickMarkComplete = async (fu: FollowUpItem) => {
    try {
      await api.patch(`/follow-ups/${fu.id}`, { status: 'COMPLETED' });
      await fetchFollowUps();
    } catch (err: any) {
      alert(err.message || 'Failed to mark follow-up complete');
    }
  };

  // Roadmap Step Handlers
  const handleOpenAddStep = () => {
    setEditingStep(null);
    setStepTitle('First Call');
    setStepDate(new Date().toISOString().split('T')[0]);
    setStepContactId('');
    setStepContactItem(null);
    setStepStatus('COMPLETED');
    setStepNotes('');
    setIsAddStepModalOpen(true);
  };

  const handleOpenEditStep = (step: RoadmapStep) => {
    setEditingStep(step);
    setStepTitle(step.step_type);
    setStepDate(step.step_date.split('T')[0]);
    setStepContactId(step.contact_id || '');
    const existingContact = companyContacts.find((c: any) => c.id === step.contact_id);
    if (existingContact) {
      setStepContactItem({
        id: existingContact.id,
        full_name: existingContact.full_name || `${existingContact.first_name || ''} ${existingContact.last_name || ''}`.trim(),
        phone: existingContact.phone,
        email: existingContact.email,
        company_id: existingContact.company_id,
        company_name: existingContact.company_name,
        display: existingContact.full_name || '',
      });
    } else {
      setStepContactItem(null);
    }
    setStepStatus(step.status || 'COMPLETED');
    setStepNotes(step.notes || '');
    setIsAddStepModalOpen(true);
  };

  const handleSaveStep = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedCompanyId) return;
    setIsSubmittingStep(true);

    try {
      if (editingStep) {
        const res = await api.patch<any>(`/opportunities/roadmap/steps/${editingStep.id}`, {
          step_type: stepTitle,
          step_date: new Date(stepDate).toISOString(),
          contact_id: stepContactId || null,
          status: stepStatus,
          notes: stepNotes.trim() || null,
        });
        if (res.data) {
          setSteps((prev) => prev.map((s) => (s.id === editingStep.id ? res.data : s)));
        }
      } else {
        const res = await api.post<any>(`/opportunities/roadmap/${selectedCompanyId}`, {
          step_type: stepTitle,
          step_date: new Date(stepDate).toISOString(),
          contact_id: stepContactId || null,
          status: stepStatus,
          notes: stepNotes.trim() || null,
          step_order: steps.length + 1,
        });
        if (res.data) {
          setSteps((prev) => [...prev, res.data]);
        }
      }
      setIsAddStepModalOpen(false);
    } catch (err: any) {
      alert(err.message || 'Failed to save journey step');
    } finally {
      setIsSubmittingStep(false);
    }
  };

  const handleDeleteStep = async (stepId: string) => {
    if (!confirm(isRTL ? 'هل أنت متأكد من حذف هذه الخطوة من المسار؟' : 'Are you sure you want to delete this step?')) return;
    try {
      await api.delete(`/opportunities/roadmap/steps/${stepId}`);
      setSteps((prev) => prev.filter((s) => s.id !== stepId));
    } catch (e) {
      console.error('Failed to delete step', e);
    }
  };

  const getStepIcon = (title: string) => {
    const t = title.toLowerCase();
    if (t.includes('call') || t.includes('phone')) return <PhoneCall size={16} style={{ color: 'var(--color-primary)' }} />;
    if (t.includes('email') || t.includes('mail')) return <Mail size={16} style={{ color: '#0284c7' }} />;
    if (t.includes('demo') || t.includes('meeting')) return <Presentation size={16} style={{ color: '#7c3aed' }} />;
    if (t.includes('proposal') || t.includes('contract')) return <FileText size={16} style={{ color: '#d97706' }} />;
    if (t.includes('won') || t.includes('closed')) return <Award size={16} style={{ color: '#059669' }} />;
    return <Sparkles size={16} style={{ color: 'var(--color-accent)' }} />;
  };

  // Filtered follow-ups by search
  const filteredFollowUps = followUps.filter((f) => {
    if (!searchQuery.trim()) return true;
    const term = searchQuery.toLowerCase();
    return (
      (f.company_name_snapshot && f.company_name_snapshot.toLowerCase().includes(term)) ||
      (f.company_name && f.company_name.toLowerCase().includes(term)) ||
      (f.meeting_with && f.meeting_with.toLowerCase().includes(term)) ||
      (f.contact_name && f.contact_name.toLowerCase().includes(term)) ||
      (f.notes && f.notes.toLowerCase().includes(term)) ||
      (f.next_step && f.next_step.toLowerCase().includes(term))
    );
  });

  const pendingCount = followUps.filter((f) => f.status === 'PENDING').length;
  const completedCount = followUps.filter((f) => f.status === 'COMPLETED').length;

  const selectedCompanyInfo = selectedCompany as any;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-6)' }}>
      {/* Historical Dropzone */}
      <HistoricalImportDropZone kind="FOLLOW_UP" />

      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 'var(--space-4)' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
            <h1 className="font-display font-bold text-2xl" style={{ color: 'var(--neutral-900)' }}>
              {isRTL ? "إدارة المتابعات والمسار (Follow-ups & Journeys)" : "Follow-ups & Account Journeys"}
            </h1>
            <span className="badge badge-accent text-xs">
              {followUps.length} {isRTL ? "متابعة مسجلة" : "Follow-ups"}
            </span>
          </div>
          <p className="text-sm text-muted" style={{ marginTop: '2px' }}>
            {isRTL
              ? "متابعة المواعيد والمهام المرحّلة من العروض التجريبية والمكالمات، واستعراض مسار الشركات البيعي."
              : "Track scheduled follow-ups, converted demo actions, and account-level milestone progressions."}
          </p>
        </div>

        {/* Top Actions */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
          {activeTab === 'all' ? (
            <button onClick={handleOpenCreateModal} className="btn btn-accent btn-md" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Plus size={16} />
              <span>{isRTL ? "جدولة متابعة جديدة" : "+ Schedule Follow-up"}</span>
            </button>
          ) : (
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', minWidth: '300px' }}>
              <Building2 size={16} style={{ color: 'var(--color-primary)', flexShrink: 0 }} />
              <div style={{ flex: 1 }}>
                <AsyncCompanySelector
                  value={selectedCompanyId}
                  onChange={(item) => {
                    if (!item) return;
                    setSelectedCompany(item);
                    setSelectedCompanyId(item.id);
                    setStepContactId('');
                    setStepContactItem(null);
                  }}
                  placeholder="Search company journey..."
                  label="Select Company"
                />
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ── Main Dual-View Navigation Tabs ─────────────────────────────────── */}
      <div style={{ display: 'flex', borderBottom: '1px solid var(--border-color)', gap: 'var(--space-6)' }}>
        <button
          onClick={() => setActiveTab('all')}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: 'var(--space-3) var(--space-2)',
            borderBottom: activeTab === 'all' ? '3px solid var(--color-accent)' : '3px solid transparent',
            color: activeTab === 'all' ? 'var(--color-accent)' : 'var(--neutral-600)',
            fontWeight: activeTab === 'all' ? 700 : 500,
            fontSize: '14px',
            background: 'none',
            borderTop: 'none',
            borderLeft: 'none',
            borderRight: 'none',
            cursor: 'pointer',
          }}
        >
          <Clock size={17} />
          {isRTL ? `جميع المتابعات (${followUps.length})` : `All Follow-ups (${followUps.length})`}
        </button>

        <button
          onClick={() => setActiveTab('journey')}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: 'var(--space-3) var(--space-2)',
            borderBottom: activeTab === 'journey' ? '3px solid var(--color-accent)' : '3px solid transparent',
            color: activeTab === 'journey' ? 'var(--color-accent)' : 'var(--neutral-600)',
            fontWeight: activeTab === 'journey' ? 700 : 500,
            fontSize: '14px',
            background: 'none',
            borderTop: 'none',
            borderLeft: 'none',
            borderRight: 'none',
            cursor: 'pointer',
          }}
        >
          <Building2 size={17} />
          {isRTL ? "مسار متابعة الشركات (Journey Builder)" : "Account Journey Roadmap"}
        </button>
      </div>

      {/* ── TAB 1: ALL FOLLOW-UPS TABLE ───────────────────────────────────── */}
      {activeTab === 'all' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
          {/* Summary Badges Bar */}
          <div style={{ display: 'flex', gap: 'var(--space-3)', flexWrap: 'wrap' }}>
            <div style={{ padding: '8px 14px', borderRadius: 'var(--radius-md)', backgroundColor: 'var(--bg-surface)', border: '1px solid var(--border-color)', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span className="text-xs text-muted font-semibold">{isRTL ? "قيد المتابعة" : "Pending"}</span>
              <span className="font-bold text-sm" style={{ color: '#D97706' }}>{pendingCount}</span>
            </div>
            <div style={{ padding: '8px 14px', borderRadius: 'var(--radius-md)', backgroundColor: 'var(--bg-surface)', border: '1px solid var(--border-color)', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span className="text-xs text-muted font-semibold">{isRTL ? "مكتملة" : "Completed"}</span>
              <span className="font-bold text-sm" style={{ color: '#059669' }}>{completedCount}</span>
            </div>
          </div>

          {/* Filters Bar */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 'var(--space-3)' }}>
            <div style={{ display: 'flex', gap: 'var(--space-2)', flexWrap: 'wrap', alignItems: 'center' }}>
              {/* Status Tabs */}
              {['ALL', 'PENDING', 'COMPLETED', 'CANCELLED'].map((st) => (
                <button
                  key={st}
                  onClick={() => setStatusFilter(st)}
                  className={`btn btn-sm ${statusFilter === st ? 'btn-accent' : 'btn-secondary'}`}
                  style={{ fontSize: '11px', fontWeight: 700, padding: '4px 10px' }}
                >
                  {st}
                </button>
              ))}

              {/* Type Filter */}
              <select
                className="form-select text-xs"
                style={{ width: '130px' }}
                value={typeFilter}
                onChange={(e) => setTypeFilter(e.target.value)}
              >
                <option value="ALL">All Types</option>
                <option value="CALL">Call</option>
                <option value="EMAIL">Email</option>
                <option value="MEETING">Meeting</option>
                <option value="DEMO">Demo</option>
                <option value="WHATSAPP">WhatsApp</option>
                <option value="GENERAL">General</option>
              </select>

              {/* User filter */}
              {(user?.role === 'ADMIN' || user?.role === 'MANAGER' || user?.role === 'TEAM_LEAD') && (
                <select
                  className="form-select text-xs"
                  style={{ width: '160px' }}
                  value={userFilter}
                  onChange={(e) => setUserFilter(e.target.value)}
                >
                  <option value="">All Sales Reps</option>
                  {usersList.map((u) => (
                    <option key={u.id} value={u.id}>
                      👤 {u.full_name}
                    </option>
                  ))}
                </select>
              )}
            </div>

            {/* Search Input */}
            <div style={{ position: 'relative', width: '100%', maxWidth: '280px' }}>
              <Search
                size={14}
                style={{
                  position: 'absolute',
                  left: isRTL ? 'auto' : '10px',
                  right: isRTL ? '10px' : 'auto',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  color: 'var(--neutral-400)',
                }}
              />
              <input
                type="text"
                placeholder={isRTL ? "بحث بالشركة، الشخص، أو الملاحظة..." : "Search company, person, notes..."}
                className="form-input text-xs"
                style={{
                  paddingLeft: isRTL ? '10px' : '30px',
                  paddingRight: isRTL ? '30px' : '10px',
                  width: '100%',
                }}
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </div>
          </div>

          {/* Follow-ups Table */}
          {isLoadingFollowUps ? (
            <LoadingSpinner message={isRTL ? "جاري تحميل سجل المتابعات..." : "Loading follow-up records..."} />
          ) : filteredFollowUps.length === 0 ? (
            <EmptyState
              title={isRTL ? "لا توجد متابعات مسجلة" : "No follow-up records found"}
              description={isRTL ? "استخدم زر جدولة متابعة جديدة أو تغيير شروط التصفية." : "Schedule a new follow-up or adjust filters to view records."}
            />
          ) : (
            <div className="table-container custom-scrollbar" style={{ overflowX: 'auto' }}>
              <table className="data-table">
                <thead>
                  <tr>
                    <th style={{ minWidth: '120px' }}>{isRTL ? "الحالة والنوع" : "Status & Type"}</th>
                    <th style={{ minWidth: '180px' }}>{isRTL ? "الشركة" : "Company"}</th>
                    <th style={{ minWidth: '160px' }}>{isRTL ? "المسؤول والمقابلة" : "Meeting With / Contact"}</th>
                    <th style={{ minWidth: '130px' }}>{isRTL ? "مندوب المبيعات" : "Sales Owner"}</th>
                    <th style={{ minWidth: '140px' }}>{isRTL ? "تاريخ الاستحقاق" : "Due Date"}</th>
                    <th style={{ minWidth: '220px' }}>{isRTL ? "الملاحظات والخطوة التالية" : "Notes & Next Step"}</th>
                    <th style={{ minWidth: '130px', textAlign: 'center' }}>{isRTL ? "الإجراء" : "Actions"}</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredFollowUps.map((fu) => {
                    const isPending = fu.status === 'PENDING';
                    const isOverdue = isPending && fu.due_at && new Date(fu.due_at) < new Date();
                    return (
                      <tr key={fu.id} style={{ backgroundColor: isOverdue ? 'rgba(239, 68, 68, 0.04)' : undefined }}>
                        {/* Status & Type */}
                        <td>
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '3px', alignItems: 'flex-start' }}>
                            <span
                              style={{
                                fontSize: '11px',
                                fontWeight: 700,
                                padding: '2px 7px',
                                borderRadius: 'var(--radius-sm)',
                                backgroundColor:
                                  fu.status === 'COMPLETED'
                                    ? '#ecfdf5'
                                    : fu.status === 'CANCELLED'
                                    ? '#fee2e2'
                                    : '#fef3c7',
                                color:
                                  fu.status === 'COMPLETED'
                                    ? '#065f46'
                                    : fu.status === 'CANCELLED'
                                    ? '#991b1b'
                                    : '#b45309',
                              }}
                            >
                              {fu.status}
                            </span>
                            <span className="badge badge-secondary text-xs" style={{ fontSize: '10px' }}>
                              {fu.type}
                            </span>
                            {fu.demo_id && (
                              <span
                                style={{
                                  fontSize: '9px',
                                  fontWeight: 800,
                                  color: '#7c3aed',
                                  backgroundColor: 'rgba(124, 58, 237, 0.1)',
                                  padding: '1px 4px',
                                  borderRadius: '3px',
                                }}
                              >
                                FROM DEMO
                              </span>
                            )}
                          </div>
                        </td>

                        {/* Company Name */}
                        <td>
                          <div className="font-semibold text-xs" style={{ color: 'var(--neutral-900)' }}>
                            {fu.company_name_snapshot || fu.company_name || '—'}
                          </div>
                        </td>

                        {/* Meeting With / Contact */}
                        <td>
                          <div className="text-xs font-medium" style={{ color: 'var(--neutral-800)' }}>
                            {fu.meeting_with || fu.contact_name || '—'}
                          </div>
                          {fu.phone && <div className="text-xs font-mono text-muted">{fu.phone}</div>}
                        </td>

                        {/* Owner */}
                        <td>
                          <span className="badge badge-secondary text-xs font-semibold">
                            {fu.owner_name || 'Sales Rep'}
                          </span>
                        </td>

                        {/* Due Date */}
                        <td>
                          {fu.due_at ? (
                            <div>
                              <div
                                className="text-xs font-semibold"
                                style={{ color: isOverdue ? 'var(--color-danger)' : 'var(--color-primary)' }}
                              >
                                {new Date(fu.due_at).toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' })}
                              </div>
                              <div className="text-xs text-muted" style={{ fontSize: '10px' }}>
                                {new Date(fu.due_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                              </div>
                            </div>
                          ) : (
                            <span className="text-xs text-muted italic">Undated</span>
                          )}
                        </td>

                        {/* Notes & Next Step */}
                        <td>
                          {fu.notes && (
                            <div className="text-xs" style={{ color: 'var(--neutral-900)', maxWidth: '260px' }}>
                              {fu.notes}
                            </div>
                          )}
                          {fu.next_step && (
                            <div className="text-xs font-semibold" style={{ color: 'var(--color-accent)', marginTop: '2px' }}>
                              Next: {fu.next_step}
                            </div>
                          )}
                          {!fu.notes && !fu.next_step && <span className="text-xs text-muted">—</span>}
                        </td>

                        {/* Actions */}
                        <td>
                          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px' }}>
                            {fu.status === 'PENDING' && (
                              <button
                                onClick={() => handleQuickMarkComplete(fu)}
                                className="btn btn-secondary btn-sm"
                                style={{ fontSize: '11px', padding: '3px 6px', color: '#059669' }}
                                title="Mark as Completed"
                              >
                                <Check size={13} />
                              </button>
                            )}
                            <button
                              onClick={() => handleOpenEditModal(fu)}
                              className="btn btn-secondary btn-sm"
                              style={{ fontSize: '11px', padding: '3px 8px', display: 'flex', alignItems: 'center', gap: '3px' }}
                            >
                              <Edit2 size={12} />
                              <span>Edit</span>
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* ── TAB 2: ACCOUNT JOURNEY ROADMAP ─────────────────────────────────── */}
      {activeTab === 'journey' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-6)' }}>
          {selectedCompanyInfo && (
            <div
              style={{
                padding: 'var(--space-5) var(--space-6)',
                backgroundColor: 'var(--bg-surface)',
                borderRadius: 'var(--radius-xl)',
                border: '1px solid var(--border-color)',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                flexWrap: 'wrap',
                gap: 'var(--space-4)',
              }}
            >
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <h2 style={{ margin: 0, fontSize: '20px', fontWeight: 800, color: 'var(--neutral-900)' }}>
                    {selectedCompanyInfo.name}
                  </h2>
                  <span className="badge badge-accent text-xs">
                    {companyContacts.length} {isRTL ? 'جهات اتصال' : 'Contacts'}
                  </span>
                </div>
                <div style={{ display: 'flex', gap: 'var(--space-4)', marginTop: '4px', fontSize: '12px', color: 'var(--neutral-500)' }}>
                  <span>📍 {selectedCompanyInfo.country || 'Saudi Arabia'}</span>
                  <span>🏢 {selectedCompanyInfo.industry || 'Enterprise'}</span>
                  {(selectedCompanyInfo as any).account_owner_name && (
                    <span>👤 Owner: {(selectedCompanyInfo as any).account_owner_name}</span>
                  )}
                </div>
              </div>

              <button onClick={handleOpenAddStep} className="btn btn-accent btn-sm">
                <Plus size={15} />
                <span>{isRTL ? 'إضافة خطوة للمسار' : '+ Add Next Step'}</span>
              </button>
            </div>
          )}

          {/* Journey Steps Pipeline Flow */}
          {isLoadingSteps ? (
            <LoadingSpinner message={isRTL ? "جاري تحميل مسار الشركة..." : "Loading company sales journey..."} />
          ) : !selectedCompanyId ? (
            <EmptyState
              title={isRTL ? "اختر شركة لعرض مسارها" : "Select an Enterprise Account"}
              description={isRTL ? "استخدم محدد الشركات في الأعلى لاستعراض أو بناء المسار البيعي." : "Select an account from the company selector above to build or review their journey."}
            />
          ) : steps.length === 0 ? (
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                padding: 'var(--space-12) var(--space-6)',
                backgroundColor: 'var(--bg-surface)',
                borderRadius: 'var(--radius-xl)',
                border: '2px dashed var(--border-color)',
                textAlign: 'center',
                gap: 'var(--space-3)',
              }}
            >
              <div
                style={{
                  width: '56px',
                  height: '56px',
                  borderRadius: '50%',
                  backgroundColor: 'var(--color-primary-subtle)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: 'var(--color-primary)',
                }}
              >
                <Sparkles size={28} />
              </div>
              <h3 className="font-bold text-lg" style={{ margin: 0, color: 'var(--neutral-900)' }}>
                {isRTL ? `ابدأ مسار المتابعة لشركة ${selectedCompany?.name || ''}` : `Start Sales Journey for ${selectedCompany?.name || 'Company'}`}
              </h3>
              <p className="text-xs text-muted" style={{ maxWidth: '420px', margin: 0 }}>
                {isRTL
                  ? "لم يتم تسجيل أي خطوات متابعة لهذه الشركة بعد. ابدأ بإضافة المكالمة الأولى أو المتابعة المبدئية."
                  : "No journey steps have been recorded yet for this company. Click below to add the First Call or initial outreach."}
              </p>
              <button onClick={handleOpenAddStep} className="btn btn-accent btn-sm" style={{ marginTop: 'var(--space-2)' }}>
                <Plus size={15} />
                <span>{isRTL ? "إضافة أول خطوة (First Call)" : "+ Add First Step"}</span>
              </button>
            </div>
          ) : (
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                gap: '0',
                maxWidth: '680px',
                margin: '0 auto',
                width: '100%',
              }}
            >
              {steps.map((step, idx) => {
                const isLast = idx === steps.length - 1;
                const dateObj = new Date(step.step_date);
                const dateStr = dateObj.toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' });

                return (
                  <React.Fragment key={step.id}>
                    <div
                      className="card"
                      style={{
                        width: '100%',
                        padding: 'var(--space-5)',
                        backgroundColor: 'var(--bg-surface)',
                        borderRadius: 'var(--radius-xl)',
                        border: '1px solid var(--border-color)',
                        boxShadow: 'var(--shadow-sm)',
                        position: 'relative',
                        transition: 'all 0.2s ease',
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 'var(--space-2)' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                          <div
                            style={{
                              width: '36px',
                              height: '36px',
                              borderRadius: 'var(--radius-lg)',
                              backgroundColor: 'var(--bg-app)',
                              border: '1px solid var(--border-light)',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                            }}
                          >
                            {getStepIcon(step.step_type)}
                          </div>
                          <div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                              <span
                                style={{
                                  fontSize: '10px',
                                  fontWeight: 800,
                                  color: 'var(--neutral-400)',
                                  letterSpacing: '0.5px',
                                }}
                              >
                                STEP {idx + 1}
                              </span>
                              <h3 style={{ margin: 0, fontSize: '15px', fontWeight: 700, color: 'var(--neutral-900)' }}>
                                {step.step_type}
                              </h3>
                            </div>
                            <div style={{ fontSize: '11px', color: 'var(--neutral-500)', display: 'flex', alignItems: 'center', gap: '8px', marginTop: '2px' }}>
                              <span>📅 {dateStr}</span>
                              {step.contact_name && <span>👤 {step.contact_name}</span>}
                              {step.user_name && <span>💼 {step.user_name}</span>}
                            </div>
                          </div>
                        </div>

                        <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                          <span
                            className="badge text-xs"
                            style={{
                              backgroundColor: step.status === 'WON' ? '#ecfdf5' : '#f1f5f9',
                              color: step.status === 'WON' ? '#047857' : '#475569',
                              border: '1px solid var(--border-light)',
                              fontWeight: 700,
                            }}
                          >
                            {step.status}
                          </span>
                          <button onClick={() => handleOpenEditStep(step)} className="btn btn-ghost btn-xs" title="Edit Step">
                            <Edit2 size={13} style={{ color: 'var(--neutral-400)' }} />
                          </button>
                          <button onClick={() => handleDeleteStep(step.id)} className="btn btn-ghost btn-xs text-danger" title="Delete Step">
                            <Trash2 size={13} />
                          </button>
                        </div>
                      </div>

                      {step.notes && (
                        <div
                          style={{
                            marginTop: 'var(--space-3)',
                            padding: '8px 12px',
                            backgroundColor: 'var(--bg-app)',
                            borderRadius: 'var(--radius-md)',
                            fontSize: '12px',
                            color: 'var(--neutral-800)',
                            lineHeight: 1.5,
                            borderInlineStart: '3px solid var(--color-accent)',
                          }}
                        >
                          {step.notes}
                        </div>
                      )}
                    </div>

                    {!isLast && (
                      <div
                        style={{
                          display: 'flex',
                          flexDirection: 'column',
                          alignItems: 'center',
                          padding: '8px 0',
                          color: 'var(--color-accent)',
                        }}
                      >
                        <div style={{ width: '2px', height: '14px', backgroundColor: 'var(--color-accent)', opacity: 0.5 }} />
                        <ArrowDown size={18} style={{ margin: '-2px 0' }} />
                      </div>
                    )}
                  </React.Fragment>
                );
              })}

              <div style={{ marginTop: 'var(--space-5)' }}>
                <button onClick={handleOpenAddStep} className="btn btn-accent btn-md">
                  <Plus size={16} />
                  <span>{isRTL ? "+ إضافة الخطوة التالية" : "+ Add Next Step"}</span>
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── Create Follow-up Modal ────────────────────────────────────────── */}
      <Modal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        title={isRTL ? "جدولة متابعة جديدة" : "Schedule New Follow-up"}
      >
        <form onSubmit={handleSaveFollowUp} style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
          <div className="form-group">
            <label className="form-label font-semibold text-xs">
              Company Name <span className="text-muted font-normal">(Free text or known company)</span>
            </label>
            <input
              type="text"
              required
              className="form-input"
              placeholder="e.g. Saudi Aramco, Al-Fanar..."
              value={createForm.company_name_snapshot}
              onChange={(e) => setCreateForm({ ...createForm, company_name_snapshot: e.target.value })}
            />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-3)' }}>
            <div className="form-group">
              <label className="form-label font-semibold text-xs">Meeting With / Client Contact</label>
              <input
                type="text"
                className="form-input"
                placeholder="e.g. Eng. Abdullah, IT Manager..."
                value={createForm.meeting_with}
                onChange={(e) => setCreateForm({ ...createForm, meeting_with: e.target.value })}
              />
            </div>
            <div className="form-group">
              <label className="form-label font-semibold text-xs">Follow-up Type</label>
              <select
                className="form-select"
                value={createForm.type}
                onChange={(e) => setCreateForm({ ...createForm, type: e.target.value })}
              >
                <option value="CALL">Phone Call</option>
                <option value="EMAIL">Email</option>
                <option value="MEETING">Meeting</option>
                <option value="DEMO">Demo</option>
                <option value="WHATSAPP">WhatsApp</option>
                <option value="GENERAL">General</option>
              </select>
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-3)' }}>
            <div className="form-group">
              <label className="form-label font-semibold text-xs">Due Date & Time (Optional)</label>
              <input
                type="datetime-local"
                className="form-input"
                value={createForm.due_at}
                onChange={(e) => setCreateForm({ ...createForm, due_at: e.target.value })}
              />
            </div>
            <div className="form-group">
              <label className="form-label font-semibold text-xs">Assigned Sales Rep</label>
              <select
                className="form-select"
                value={createForm.user_id}
                onChange={(e) => setCreateForm({ ...createForm, user_id: e.target.value })}
              >
                <option value="">Current User</option>
                {usersList.map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.full_name} ({u.role})
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="form-group">
            <label className="form-label font-semibold text-xs">Link CRM Contact (Optional)</label>
            <AsyncContactSelector
              value={createForm.contact_id}
              onChange={(item) => {
                setCreateContactItem(item);
                setCreateForm({
                  ...createForm,
                  contact_id: item?.id || '',
                  company_name_snapshot: createForm.company_name_snapshot || item?.company_name || '',
                  meeting_with: createForm.meeting_with || item?.full_name || '',
                });
              }}
              placeholder="Search contact..."
              label="Associated Contact"
              initialItem={createContactItem}
            />
          </div>

          <div className="form-group">
            <label className="form-label font-semibold text-xs">Notes</label>
            <textarea
              rows={2}
              className="form-textarea"
              placeholder="Context or talking points..."
              value={createForm.notes}
              onChange={(e) => setCreateForm({ ...createForm, notes: e.target.value })}
            />
          </div>

          <div className="form-group">
            <label className="form-label font-semibold text-xs">Agreed Next Step</label>
            <input
              type="text"
              className="form-input"
              placeholder="e.g. Share quotation and follow up in 3 days..."
              value={createForm.next_step}
              onChange={(e) => setCreateForm({ ...createForm, next_step: e.target.value })}
            />
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 'var(--space-2)', marginTop: 'var(--space-2)' }}>
            <button type="button" onClick={() => setIsCreateModalOpen(false)} className="btn btn-secondary">
              Cancel
            </button>
            <button type="submit" disabled={isSubmittingCreate} className="btn btn-accent">
              {isSubmittingCreate ? 'Saving...' : 'Create Follow-up'}
            </button>
          </div>
        </form>
      </Modal>

      {/* ── Edit Follow-up Modal ──────────────────────────────────────────── */}
      {editingFollowUp && (
        <Modal
          isOpen={!!editingFollowUp}
          onClose={() => setEditingFollowUp(null)}
          title={isRTL ? "تعديل المتابعة" : "Edit Follow-up"}
        >
          <form onSubmit={handleUpdateFollowUp} style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
            <div className="form-group">
              <label className="form-label font-semibold text-xs">Company Name (Snapshot / Free text)</label>
              <input
                type="text"
                className="form-input"
                value={editForm.company_name_snapshot}
                onChange={(e) => setEditForm({ ...editForm, company_name_snapshot: e.target.value })}
              />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-3)' }}>
              <div className="form-group">
                <label className="form-label font-semibold text-xs">Meeting With</label>
                <input
                  type="text"
                  className="form-input"
                  value={editForm.meeting_with}
                  onChange={(e) => setEditForm({ ...editForm, meeting_with: e.target.value })}
                />
              </div>
              <div className="form-group">
                <label className="form-label font-semibold text-xs">Status</label>
                <select
                  className="form-select"
                  value={editForm.status}
                  onChange={(e) => setEditForm({ ...editForm, status: e.target.value })}
                >
                  <option value="PENDING">PENDING</option>
                  <option value="COMPLETED">COMPLETED</option>
                  <option value="CANCELLED">CANCELLED</option>
                </select>
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-3)' }}>
              <div className="form-group">
                <label className="form-label font-semibold text-xs">Type</label>
                <select
                  className="form-select"
                  value={editForm.type}
                  onChange={(e) => setEditForm({ ...editForm, type: e.target.value })}
                >
                  <option value="CALL">Call</option>
                  <option value="EMAIL">Email</option>
                  <option value="MEETING">Meeting</option>
                  <option value="DEMO">Demo</option>
                  <option value="WHATSAPP">WhatsApp</option>
                  <option value="GENERAL">General</option>
                </select>
              </div>
              <div className="form-group">
                <label className="form-label font-semibold text-xs">Due Date & Time</label>
                <input
                  type="datetime-local"
                  className="form-input"
                  value={editForm.due_at}
                  onChange={(e) => setEditForm({ ...editForm, due_at: e.target.value })}
                />
              </div>
            </div>

            <div className="form-group">
              <label className="form-label font-semibold text-xs">Notes</label>
              <textarea
                rows={2}
                className="form-textarea"
                value={editForm.notes}
                onChange={(e) => setEditForm({ ...editForm, notes: e.target.value })}
              />
            </div>

            <div className="form-group">
              <label className="form-label font-semibold text-xs">Next Step</label>
              <input
                type="text"
                className="form-input"
                value={editForm.next_step}
                onChange={(e) => setEditForm({ ...editForm, next_step: e.target.value })}
              />
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 'var(--space-2)', marginTop: 'var(--space-2)' }}>
              <button type="button" onClick={() => setEditingFollowUp(null)} className="btn btn-secondary">
                Cancel
              </button>
              <button type="submit" disabled={isSubmittingEdit} className="btn btn-accent">
                {isSubmittingEdit ? 'Saving...' : 'Save Changes'}
              </button>
            </div>
          </form>
        </Modal>
      )}

      {/* ── Add / Edit Roadmap Step Modal ─────────────────────────────────── */}
      {isAddStepModalOpen && (
        <Modal
          isOpen={isAddStepModalOpen}
          onClose={() => setIsAddStepModalOpen(false)}
          title={editingStep ? (isRTL ? "تعديل خطوة المسار" : "Edit Journey Step") : (isRTL ? "إضافة خطوة جديدة للمسار" : "Add Journey Step")}
        >
          <form onSubmit={handleSaveStep} style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
            <div>
              <label className="form-label text-xs">{isRTL ? "عنوان أو نوع الخطوة" : "Step Title / Type"}</label>
              <input
                type="text"
                required
                className="form-input text-xs"
                placeholder="e.g. First Call, Demo Scheduled, Proposal Sent..."
                value={stepTitle}
                onChange={(e) => setStepTitle(e.target.value)}
                list="step-presets"
              />
              <datalist id="step-presets">
                {STEP_TYPE_PRESETS.map((p) => (
                  <option key={p} value={p} />
                ))}
              </datalist>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-3)' }}>
              <div>
                <label className="form-label text-xs">{isRTL ? "تاريخ الخطوة" : "Date"}</label>
                <input
                  type="date"
                  required
                  className="form-input text-xs"
                  value={stepDate}
                  onChange={(e) => setStepDate(e.target.value)}
                />
              </div>

              <div>
                <label className="form-label text-xs">{isRTL ? "الحالة" : "Status"}</label>
                <select
                  className="form-select text-xs"
                  value={stepStatus}
                  onChange={(e) => setStepStatus(e.target.value)}
                >
                  <option value="COMPLETED">Completed</option>
                  <option value="IN_PROGRESS">In Progress</option>
                  <option value="SCHEDULED">Scheduled</option>
                  <option value="WON">Closed Won 🏆</option>
                </select>
              </div>
            </div>

            <div>
              <label className="form-label text-xs">{isRTL ? 'جهة الاتصال المعنية (اختياري)' : 'Associated Contact (Optional)'}</label>
              <AsyncContactSelector
                value={stepContactId}
                onChange={(item) => {
                  setStepContactItem(item);
                  setStepContactId(item?.id || '');
                }}
                companyId={selectedCompanyId || undefined}
                placeholder={isRTL ? 'ابحث عن جهة اتصال...' : 'Search contacts in this company...'}
                label="Associated Contact"
                initialItem={stepContactItem}
              />
            </div>

            <div>
              <label className="form-label text-xs">{isRTL ? "الملاحظات والتفاصيل" : "Step Notes & Outcome"}</label>
              <textarea
                className="form-input text-xs"
                rows={3}
                placeholder={isRTL ? "تفاصيل ما تم في هذه الخطوة والنتيجة المحققة..." : "Details of what happened in this step, customer reaction, next actions..."}
                value={stepNotes}
                onChange={(e) => setStepNotes(e.target.value)}
              />
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 'var(--space-2)' }}>
              <button type="button" onClick={() => setIsAddStepModalOpen(false)} className="btn btn-secondary btn-sm">
                {isRTL ? "إلغاء" : "Cancel"}
              </button>
              <button type="submit" disabled={isSubmittingStep} className="btn btn-accent btn-sm">
                <Check size={14} />
                <span>{isSubmittingStep ? (isRTL ? "جاري الحفظ..." : "Saving...") : (isRTL ? "حفظ الخطوة" : "Save Step")}</span>
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
};
