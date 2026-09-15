import React, { useState, useEffect } from 'react';
import { api } from '../../lib/apiClient';
import { useAuthStore } from '../../store/authStore';
import { isManagerOrAbove } from '../../lib/permissions';
import { Company, OpportunityRoadmapStep, Opportunity } from '../../types';
import { Badge } from '../../components/ui/Badge';
import { Modal } from '../../components/ui/Modal';
import { LoadingSpinner } from '../../components/feedback/LoadingSpinner';
import { EmptyState } from '../../components/feedback/EmptyState';
import {
  TrendingUp,
  Plus,
  ArrowRight,
  CheckCircle2,
  Clock,
  Building,
  Calendar,
  User,
  Check,
  ChevronRight,
  ListOrdered,
  DollarSign,
  Briefcase,
  Edit3,
  Trash2,
} from 'lucide-react';
import { useTranslation } from '../../i18n';

const STEP_TYPES = [
  'First Call',
  'Email Sent',
  'WhatsApp Follow-up',
  'Demo Agreed / Scheduled',
  'Demo Completed',
  'Proposal Sent',
  'Contract & Legal Review',
  'Deal Won 🎉',
  'Deal Lost / Postponed',
  'Other Custom Step',
];

export const OpportunitiesPage: React.FC = () => {
  const { user } = useAuthStore();
  const { t, isRTL } = useTranslation();

  // Active View Tab
  const [viewTab, setViewTab] = useState<'pipeline' | 'roadmap'>('pipeline');

  // Opportunities List State
  const [opps, setOpps] = useState<any[]>([]);
  const [totalOpps, setTotalOpps] = useState<number>(0);
  const [stageFilter, setStageFilter] = useState<string>('ALL');
  const [userFilter, setUserFilter] = useState<string>('');
  const [usersList, setUsersList] = useState<any[]>([]);

  // Roadmap State
  const [companies, setCompanies] = useState<Company[]>([]);
  const [selectedCompanyId, setSelectedCompanyId] = useState<string>('');
  const [roadmapSteps, setRoadmapSteps] = useState<OpportunityRoadmapStep[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isStepsLoading, setIsStepsLoading] = useState(false);

  // Add Step Modal
  const [showAddModal, setShowAddModal] = useState(false);
  const [stepType, setStepType] = useState('First Call');
  const [stepDate, setStepDate] = useState(new Date().toISOString().split('T')[0]);
  const [stepNotes, setStepNotes] = useState('');
  const [stepStatus, setStepStatus] = useState('COMPLETED');
  const [isSaving, setIsSaving] = useState(false);

  // Create Opportunity Modal
  const [showCreateOppModal, setShowCreateOppModal] = useState(false);
  const [createOppForm, setCreateOppForm] = useState({
    title: '',
    company_name_snapshot: '',
    contact_person: '',
    company_id: '',
    owner_id: user?.id || '',
    stage: 'NEW',
    value: 0,
    probability: 50,
    expected_close_at: '',
    notes: '',
    next_step: '',
  });
  const [isCreatingOpp, setIsCreatingOpp] = useState(false);

  // Edit Opportunity Modal
  const [editingOpp, setEditingOpp] = useState<any | null>(null);
  const [editTitle, setEditTitle] = useState('');
  const [editStage, setEditStage] = useState('NEW');
  const [editValue, setEditValue] = useState<number>(0);
  const [editProbability, setEditProbability] = useState<number>(50);
  const [editCompanySnapshot, setEditCompanySnapshot] = useState('');
  const [editContactPerson, setEditContactPerson] = useState('');
  const [editExpectedClose, setEditExpectedClose] = useState('');
  const [editNotes, setEditNotes] = useState('');
  const [editNextStep, setEditNextStep] = useState('');
  const [isUpdatingOpp, setIsUpdatingOpp] = useState(false);

  const hasManagerPrivileges = isManagerOrAbove(user?.role);

  // Fetch Users & Companies
  useEffect(() => {
    const initData = async () => {
      setIsLoading(true);
      try {
        const cRes = await api.get<any>('/companies', { per_page: 100 });
        const list = cRes.data || [];
        setCompanies(list);
        if (list.length > 0) {
          setSelectedCompanyId(list[0].id);
        }

        if (hasManagerPrivileges) {
          try {
            const uRes = await api.get<any>('/users');
            setUsersList(uRes.data || []);
          } catch (ue) {
            console.error('Failed to load users list', ue);
          }
        }
      } catch (e) {
        console.error('Failed to load initial data', e);
      } finally {
        setIsLoading(false);
      }
    };
    initData();
  }, [hasManagerPrivileges]);

  // Fetch Opportunities Pipeline
  const fetchOpportunities = async () => {
    try {
      const params: Record<string, any> = { per_page: 100 };
      if (stageFilter !== 'ALL') params.stage = stageFilter;
      if (userFilter) params.user_id = userFilter;

      const res = await api.get<any>('/opportunities', params);
      setOpps(res.data || []);
      setTotalOpps(res.meta?.total || 0);
    } catch (e) {
      console.error('Failed to load opportunities', e);
    }
  };

  useEffect(() => {
    fetchOpportunities();
  }, [stageFilter, userFilter]);

  // Fetch roadmap steps for selected company
  const fetchRoadmap = async (companyId: string) => {
    if (!companyId) return;
    setIsStepsLoading(true);
    try {
      const res = await api.get<any>(`/opportunities/roadmap/${companyId}`);
      setRoadmapSteps(res.data || []);
    } catch (e) {
      console.error('Failed to load roadmap steps', e);
    } finally {
      setIsStepsLoading(false);
    }
  };

  useEffect(() => {
    if (selectedCompanyId) {
      fetchRoadmap(selectedCompanyId);
    }
  }, [selectedCompanyId]);

  const handleAddStep = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedCompanyId) return;
    setIsSaving(true);
    try {
      await api.post(`/opportunities/roadmap/${selectedCompanyId}`, {
        step_type: stepType,
        step_date: new Date(stepDate).toISOString(),
        notes: stepNotes || undefined,
        status: stepStatus,
      });
      setShowAddModal(false);
      setStepNotes('');
      await fetchRoadmap(selectedCompanyId);
    } catch (err: any) {
      alert(err.message || 'Failed to save roadmap step');
    } finally {
      setIsSaving(false);
    }
  };

  const handleCreateOpp = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!createOppForm.title.trim()) {
      alert('Opportunity title is required');
      return;
    }
    setIsCreatingOpp(true);
    try {
      await api.post('/opportunities', {
        title: createOppForm.title.trim(),
        company_name_snapshot: createOppForm.company_name_snapshot.trim() || undefined,
        contact_person: createOppForm.contact_person.trim() || undefined,
        company_id: createOppForm.company_id || undefined,
        owner_id: createOppForm.owner_id || undefined,
        stage: createOppForm.stage,
        value: Number(createOppForm.value) || 0,
        probability: Number(createOppForm.probability) || 50,
        expected_close_at: createOppForm.expected_close_at ? new Date(createOppForm.expected_close_at).toISOString() : undefined,
        notes: createOppForm.notes.trim() || undefined,
        next_step: createOppForm.next_step.trim() || undefined,
      });
      setShowCreateOppModal(false);
      await fetchOpportunities();
    } catch (err: any) {
      alert(err.message || 'Failed to create opportunity');
    } finally {
      setIsCreatingOpp(false);
    }
  };

  const handleUpdateOpp = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingOpp) return;
    setIsUpdatingOpp(true);
    try {
      await api.patch(`/opportunities/${editingOpp.id}`, {
        title: editTitle.trim() || undefined,
        stage: editStage,
        value: editValue,
        probability: editProbability,
        company_name_snapshot: editCompanySnapshot.trim() || undefined,
        contact_person: editContactPerson.trim() || undefined,
        expected_close_at: editExpectedClose ? new Date(editExpectedClose).toISOString() : undefined,
        notes: editNotes.trim() || undefined,
        next_step: editNextStep.trim() || undefined,
      });
      setEditingOpp(null);
      await fetchOpportunities();
    } catch (err: any) {
      alert(err.message || 'Failed to update opportunity');
    } finally {
      setIsUpdatingOpp(false);
    }
  };

  const handleDeleteOpp = async (oppId: string, oppTitle: string) => {
    if (!confirm(isRTL ? `هل أنت متأكد من حذف الصفقة "${oppTitle}"؟` : `Are you sure you want to delete opportunity "${oppTitle}"?`)) {
      return;
    }
    try {
      await api.delete(`/opportunities/${oppId}`);
      await fetchOpportunities();
    } catch (err: any) {
      alert(err.message || 'Failed to delete opportunity');
    }
  };

  const selectedCompany = companies.find((c) => c.id === selectedCompanyId);
  const totalPipelineValue = opps.reduce((sum, o) => sum + (o.value || 0), 0);
  const wonValue = opps.filter((o) => o.stage === 'WON').reduce((sum, o) => sum + (o.value || 0), 0);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-6)' }}>
      {/* Header */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: 'var(--space-4)',
        }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
            <h1 className="font-display font-bold text-2xl" style={{ color: 'var(--neutral-900)' }}>
              {isRTL ? "إدارة الفرص والمسار البيعي (Opportunities)" : "Sales Opportunities & Pipeline"}
            </h1>
            <span className="badge badge-accent text-xs">
              {totalOpps} {isRTL ? "صفقة نشطة" : "Deals"}
            </span>
          </div>
          <p className="text-sm text-muted" style={{ marginTop: '2px' }}>
            {isRTL
              ? "متابعة مسار الصفقات الإجمالي وخارطة الطريق المتسلسلة لعملاء الشركات والمؤسسات."
              : "Track team-wide revenue pipeline and sequential milestones from First Call to Proposal and Deal Won."}
          </p>
        </div>

        {/* Actions & Filters */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
          {viewTab === 'pipeline' && (
            <button
              onClick={() => {
                setCreateOppForm({
                  title: '',
                  company_name_snapshot: '',
                  contact_person: '',
                  company_id: '',
                  owner_id: user?.id || '',
                  stage: 'NEW',
                  value: 0,
                  probability: 50,
                  expected_close_at: '',
                  notes: '',
                  next_step: '',
                });
                setShowCreateOppModal(true);
              }}
              className="btn btn-accent btn-md"
              style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
            >
              <Plus size={16} />
              <span>{isRTL ? "إضافة فرصة جديدة" : "+ New Opportunity"}</span>
            </button>
          )}

          {/* User Filter Dropdown for Managers */}
          {hasManagerPrivileges && (
            <select
              className="form-select text-xs"
              style={{ width: '180px' }}
              value={userFilter}
              onChange={(e) => setUserFilter(e.target.value)}
            >
              <option value="">{isRTL ? "جميع الموظفين" : "All Sales Reps"}</option>
              {usersList.map((u) => (
                <option key={u.id} value={u.id}>
                  👤 {u.full_name} ({u.role})
                </option>
              ))}
            </select>
          )}
        </div>
      </div>

      {/* Main Tabs */}
      <div style={{ display: 'flex', borderBottom: '1px solid var(--border-color)', gap: 'var(--space-6)' }}>
        <button
          onClick={() => setViewTab('pipeline')}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: 'var(--space-3) var(--space-2)',
            borderBottom: viewTab === 'pipeline' ? '3px solid var(--color-accent)' : '3px solid transparent',
            color: viewTab === 'pipeline' ? 'var(--color-accent)' : 'var(--neutral-600)',
            fontWeight: viewTab === 'pipeline' ? 700 : 500,
            fontSize: '14px',
            background: 'none',
            borderTop: 'none',
            borderLeft: 'none',
            borderRight: 'none',
            cursor: 'pointer',
          }}
        >
          <Briefcase size={17} />
          {isRTL ? `قائمة الصفقات والفرص ($${totalPipelineValue.toLocaleString()})` : `Deals Pipeline ($${totalPipelineValue.toLocaleString()})`}
        </button>

        <button
          onClick={() => setViewTab('roadmap')}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: 'var(--space-3) var(--space-2)',
            borderBottom: viewTab === 'roadmap' ? '3px solid var(--color-accent)' : '3px solid transparent',
            color: viewTab === 'roadmap' ? 'var(--color-accent)' : 'var(--neutral-600)',
            fontWeight: viewTab === 'roadmap' ? 700 : 500,
            fontSize: '14px',
            background: 'none',
            borderTop: 'none',
            borderLeft: 'none',
            borderRight: 'none',
            cursor: 'pointer',
          }}
        >
          <ListOrdered size={17} />
          {isRTL ? "خارطة طريق رحلة العميل (Roadmap)" : "Company Journey Roadmap"}
        </button>
      </div>

      {/* ── TAB 1: DEALS PIPELINE ──────────────────────────────────────── */}
      {viewTab === 'pipeline' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
          {/* Stage Filter Tabs */}
          <div style={{ display: 'flex', gap: 'var(--space-2)', overflowX: 'auto', paddingBottom: 'var(--space-1)' }}>
            {['ALL', 'NEW', 'QUALIFIED', 'PROPOSAL', 'NEGOTIATION', 'WON', 'LOST'].map((st) => (
              <button
                key={st}
                onClick={() => setStageFilter(st)}
                className={`btn ${stageFilter === st ? 'btn-accent' : 'btn-secondary'} btn-sm text-xs`}
              >
                {st}
              </button>
            ))}
          </div>

          {opps.length === 0 ? (
            <EmptyState
              title={isRTL ? "لا توجد فرص بيعية" : "No opportunities found"}
              description={isRTL ? "لا توجد صفقات مسجلة تطابق هذه التصفية." : "No deals match your selected filters."}
            />
          ) : (
            <div className="table-container custom-scrollbar" style={{ overflowX: 'auto' }}>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>{isRTL ? "المرحلة" : "Stage"}</th>
                    <th>{isRTL ? "عنوان الفرصة" : "Opportunity Title"}</th>
                    <th>{isRTL ? "الشركة" : "Company"}</th>
                    <th>{isRTL ? "المسؤول" : "Sales Owner"}</th>
                    <th>{isRTL ? "القيمة المتوقعة" : "Estimated Value"}</th>
                    <th>{isRTL ? "الاحتمالية" : "Probability"}</th>
                    <th>{isRTL ? "الموعد المتوقع للإغلاق" : "Expected Close"}</th>
                    <th>{isRTL ? "الإجراء" : "Action"}</th>
                  </tr>
                </thead>
                <tbody>
                  {opps.map((o) => (
                    <tr key={o.id}>
                      <td>
                        <Badge status={o.stage} />
                      </td>
                      <td>
                        <span className="font-semibold text-sm text-dark">{o.title}</span>
                        {(o.contact_person || o.contact_name) && (
                          <div className="text-xs text-muted" style={{ marginTop: '2px' }}>
                            👤 {o.contact_person || o.contact_name}
                          </div>
                        )}
                        {o.next_step && (
                          <div className="text-xs font-semibold" style={{ color: 'var(--color-accent)', marginTop: '2px' }}>
                            Next: {o.next_step}
                          </div>
                        )}
                      </td>
                      <td>
                        <span className="text-sm font-medium" style={{ color: 'var(--neutral-800)' }}>
                          {o.company_name_snapshot || o.company_name || '—'}
                        </span>
                      </td>
                      <td>
                        <span className="badge badge-secondary text-xs font-semibold">
                          {o.owner_name || 'Sales Rep'}
                        </span>
                      </td>
                      <td>
                        <span className="font-bold text-sm" style={{ color: 'var(--color-primary)' }}>
                          ${(o.value || 0).toLocaleString()}
                        </span>
                      </td>
                      <td>
                        <span className="text-xs font-semibold">{o.probability || 50}%</span>
                      </td>
                      <td>
                        <span className="text-xs text-muted">
                          {o.expected_close_at ? new Date(o.expected_close_at).toLocaleDateString() : '—'}
                        </span>
                      </td>
                      <td>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                          <button
                            onClick={() => {
                              setEditingOpp(o);
                              setEditTitle(o.title || '');
                              setEditStage(o.stage || 'NEW');
                              setEditValue(o.value || 0);
                              setEditProbability(o.probability || 50);
                              setEditCompanySnapshot(o.company_name_snapshot || o.company_name || '');
                              setEditContactPerson(o.contact_person || o.contact_name || '');
                              setEditExpectedClose(o.expected_close_at ? o.expected_close_at.slice(0, 10) : '');
                              setEditNotes(o.notes || '');
                              setEditNextStep(o.next_step || '');
                            }}
                            className="btn btn-secondary btn-sm"
                            style={{ display: 'flex', alignItems: 'center', gap: '4px' }}
                          >
                            <Edit3 size={13} />
                            <span>{isRTL ? "تعديل" : "Edit"}</span>
                          </button>
                          <button
                            onClick={() => handleDeleteOpp(o.id, o.title)}
                            className="btn btn-ghost btn-sm text-danger"
                            title={isRTL ? "حذف الصفقة" : "Delete Opportunity"}
                          >
                            <Trash2 size={13} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* ── TAB 2: COMPANY JOURNEY ROADMAP ─────────────────────────────── */}
      {viewTab === 'roadmap' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-6)' }}>
          {/* Company Selector Header */}
          <div
            style={{
              padding: 'var(--space-4) var(--space-5)',
              borderRadius: 'var(--radius-lg)',
              backgroundColor: 'var(--bg-surface)',
              border: '1px solid var(--border-color)',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              flexWrap: 'wrap',
              gap: 'var(--space-3)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
              <Building size={18} style={{ color: 'var(--color-accent)' }} />
              <div>
                <label className="text-xs font-semibold text-muted block mb-1">
                  {isRTL ? "اختر الشركة لعرض رحلتها البيعية" : "Select Enterprise Account"}
                </label>
                <select
                  className="form-select font-semibold text-sm"
                  style={{ minWidth: '260px' }}
                  value={selectedCompanyId}
                  onChange={(e) => setSelectedCompanyId(e.target.value)}
                >
                  {companies.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name} {c.industry ? `(${c.industry})` : ''}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <button
              onClick={() => setShowAddModal(true)}
              disabled={!selectedCompanyId}
              className="btn btn-accent btn-md"
              style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
            >
              <Plus size={16} />
              <span>{isRTL ? "إضافة خطوة جديدة للمسار" : "Add Next Journey Step"}</span>
            </button>
          </div>

          {/* Stepper Flow */}
          {isStepsLoading ? (
            <LoadingSpinner message={isRTL ? "جاري تحميل خارطة المسار..." : "Rendering roadmap..."} />
          ) : !selectedCompany ? (
            <EmptyState title={isRTL ? "اختر شركة" : "Select a company"} description="Choose an account to inspect roadmap." />
          ) : roadmapSteps.length === 0 ? (
            <EmptyState
              title={isRTL ? `لا توجد خطوات مسجلة لشركة ${selectedCompany.name}` : `No roadmap steps for ${selectedCompany.name}`}
              description={isRTL ? "ابدأ ببناء مسار الرحلة خطوة بخطوة." : "Start building the sales journey for this account."}
              action={
                <button onClick={() => setShowAddModal(true)} className="btn btn-accent btn-sm">
                  {isRTL ? "إنشاء الخطوة الأولى (مثال: First Call)" : "Create First Step"}
                </button>
              }
            />
          ) : (
            <div className="card" style={{ padding: 'var(--space-6)', display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
              {roadmapSteps.map((step, idx) => {
                const isLast = idx === roadmapSteps.length - 1;
                return (
                  <div key={step.id} style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'flex-start',
                        gap: 'var(--space-4)',
                        padding: 'var(--space-4) var(--space-5)',
                        borderRadius: 'var(--radius-lg)',
                        backgroundColor: isLast ? 'var(--bg-subtle)' : 'var(--bg-surface)',
                        border: `1px solid ${isLast ? 'var(--color-primary)' : 'var(--border-color)'}`,
                      }}
                    >
                      <div
                        style={{
                          width: '32px',
                          height: '32px',
                          borderRadius: '50%',
                          backgroundColor: isLast ? 'var(--color-primary)' : 'var(--bg-subtle)',
                          color: isLast ? '#fff' : 'var(--neutral-800)',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          fontWeight: '700',
                          fontSize: '13px',
                          flexShrink: 0,
                        }}
                      >
                        {idx + 1}
                      </div>

                      <div style={{ flex: 1 }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 'var(--space-2)' }}>
                          <div className="font-semibold text-base" style={{ color: 'var(--neutral-900)' }}>
                            {step.step_type}
                          </div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                            <Badge variant={step.status === 'COMPLETED' ? 'success' : 'accent'}>{step.status}</Badge>
                            <span className="text-xs text-muted" style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                              <Calendar size={13} />
                              {new Date(step.step_date).toLocaleDateString()}
                            </span>
                          </div>
                        </div>

                        {step.notes && (
                          <p className="text-sm text-muted" style={{ marginTop: 'var(--space-2)', lineHeight: 1.5 }}>
                            {step.notes}
                          </p>
                        )}

                        <div style={{ marginTop: 'var(--space-2)', display: 'flex', gap: 'var(--space-3)', fontSize: '11px', color: 'var(--neutral-500)' }}>
                          {step.user_name && <span>Logged by: <strong>{step.user_name}</strong></span>}
                          {step.contact_name && <span>Related: <strong>{step.contact_name}</strong></span>}
                        </div>
                      </div>
                    </div>

                    {!isLast && (
                      <div style={{ display: 'flex', justifyContent: 'center', padding: '2px 0', color: 'var(--color-accent)' }}>
                        <span style={{ fontSize: '18px', fontWeight: 'bold' }}>↓</span>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* ── Edit Opportunity Modal ─────────────────────────────────────── */}
      <Modal
        isOpen={!!editingOpp}
        onClose={() => setEditingOpp(null)}
        title={isRTL ? "تعديل تفاصيل الفرصة البيعية" : "Update Opportunity Deal"}
        footer={
          <>
            <button
              type="button"
              onClick={() => setEditingOpp(null)}
              className="btn btn-secondary"
            >
              {isRTL ? "إلغاء" : "Cancel"}
            </button>
            <button
              type="button"
              disabled={isUpdatingOpp}
              onClick={handleUpdateOpp}
              className="btn btn-accent"
            >
              {isUpdatingOpp ? (isRTL ? 'جاري الحفظ...' : 'Saving...') : (isRTL ? 'حفظ التعديل' : 'Save Changes')}
            </button>
          </>
        }
      >
        <form onSubmit={handleUpdateOpp} style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
          <div className="form-group">
            <label className="form-label">{isRTL ? "عنوان الفرصة *" : "Opportunity Title *"}</label>
            <input
              type="text"
              required
              className="form-input"
              value={editTitle}
              onChange={(e) => setEditTitle(e.target.value)}
            />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-3)' }}>
            <div className="form-group">
              <label className="form-label">{isRTL ? "الشركة (اسم حر)" : "Company (Snapshot)"}</label>
              <input
                type="text"
                className="form-input"
                value={editCompanySnapshot}
                onChange={(e) => setEditCompanySnapshot(e.target.value)}
              />
            </div>

            <div className="form-group">
              <label className="form-label">{isRTL ? "الشخص المسؤول لدى العميل" : "Contact Person"}</label>
              <input
                type="text"
                className="form-input"
                value={editContactPerson}
                onChange={(e) => setEditContactPerson(e.target.value)}
              />
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">{isRTL ? "المرحلة البيعية *" : "Pipeline Stage *"}</label>
            <select
              className="form-select"
              value={editStage}
              onChange={(e) => setEditStage(e.target.value)}
            >
              <option value="NEW">NEW (جديدة)</option>
              <option value="QUALIFIED">QUALIFIED (مؤهلة)</option>
              <option value="PROPOSAL">PROPOSAL (عرض سعر مرسل)</option>
              <option value="NEGOTIATION">NEGOTIATION (مفاوضات)</option>
              <option value="WON">WON (تم الفوز بالصفقة 🏆)</option>
              <option value="LOST">LOST (خسارة الصفقة)</option>
            </select>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-3)' }}>
            <div className="form-group">
              <label className="form-label">{isRTL ? "القيمة المتوقعة ($)" : "Estimated Value ($)"}</label>
              <input
                type="number"
                className="form-input"
                value={editValue}
                onChange={(e) => setEditValue(parseFloat(e.target.value) || 0)}
              />
            </div>

            <div className="form-group">
              <label className="form-label">{isRTL ? "احتمالية النجاح (%)" : "Probability (%)"}</label>
              <input
                type="number"
                min={0}
                max={100}
                className="form-input"
                value={editProbability}
                onChange={(e) => setEditProbability(parseInt(e.target.value) || 0)}
              />
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">{isRTL ? "التاريخ المتوقع للإغلاق" : "Expected Close Date"}</label>
            <input
              type="date"
              className="form-input"
              value={editExpectedClose}
              onChange={(e) => setEditExpectedClose(e.target.value)}
            />
          </div>

          <div className="form-group">
            <label className="form-label">{isRTL ? "الملاحظات" : "Notes"}</label>
            <textarea
              rows={2}
              className="form-textarea"
              value={editNotes}
              onChange={(e) => setEditNotes(e.target.value)}
            />
          </div>

          <div className="form-group">
            <label className="form-label">{isRTL ? "الخطوة التالية" : "Next Step"}</label>
            <input
              type="text"
              className="form-input"
              value={editNextStep}
              onChange={(e) => setEditNextStep(e.target.value)}
            />
          </div>
        </form>
      </Modal>

      {/* ── Create Opportunity Modal ─────────────────────────────────────── */}
      <Modal
        isOpen={showCreateOppModal}
        onClose={() => setShowCreateOppModal(false)}
        title={isRTL ? "إضافة فرصة بيعية جديدة" : "Create New Opportunity"}
        footer={
          <>
            <button
              type="button"
              onClick={() => setShowCreateOppModal(false)}
              className="btn btn-secondary"
            >
              {isRTL ? "إلغاء" : "Cancel"}
            </button>
            <button
              type="button"
              disabled={isCreatingOpp}
              onClick={handleCreateOpp}
              className="btn btn-accent"
            >
              {isCreatingOpp ? (isRTL ? 'جاري الإنشاء...' : 'Creating...') : (isRTL ? 'إنشاء الفرصة' : 'Create Opportunity')}
            </button>
          </>
        }
      >
        <form onSubmit={handleCreateOpp} style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
          <div className="form-group">
            <label className="form-label">{isRTL ? "عنوان الفرصة *" : "Opportunity Title *"}</label>
            <input
              type="text"
              required
              className="form-input"
              placeholder="e.g. Enterprise License Expansion 2026"
              value={createOppForm.title}
              onChange={(e) => setCreateOppForm({ ...createOppForm, title: e.target.value })}
            />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-3)' }}>
            <div className="form-group">
              <label className="form-label">{isRTL ? "الشركة (اسم حر أو معروف)" : "Company Name (Snapshot)"}</label>
              <input
                type="text"
                className="form-input"
                placeholder="e.g. Saudi Aramco"
                value={createOppForm.company_name_snapshot}
                onChange={(e) => setCreateOppForm({ ...createOppForm, company_name_snapshot: e.target.value })}
              />
            </div>

            <div className="form-group">
              <label className="form-label">{isRTL ? "الشخص المسؤول لدى العميل" : "Contact Person"}</label>
              <input
                type="text"
                className="form-input"
                placeholder="e.g. Eng. Khalid Al-Otaibi"
                value={createOppForm.contact_person}
                onChange={(e) => setCreateOppForm({ ...createOppForm, contact_person: e.target.value })}
              />
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-3)' }}>
            <div className="form-group">
              <label className="form-label">{isRTL ? "المرحلة البيعية *" : "Pipeline Stage *"}</label>
              <select
                className="form-select"
                value={createOppForm.stage}
                onChange={(e) => setCreateOppForm({ ...createOppForm, stage: e.target.value })}
              >
                <option value="NEW">NEW (جديدة)</option>
                <option value="QUALIFIED">QUALIFIED (مؤهلة)</option>
                <option value="PROPOSAL">PROPOSAL (عرض سعر مرسل)</option>
                <option value="NEGOTIATION">NEGOTIATION (مفاوضات)</option>
                <option value="WON">WON (تم الفوز بالصفقة 🏆)</option>
                <option value="LOST">LOST (خسارة الصفقة)</option>
              </select>
            </div>

            <div className="form-group">
              <label className="form-label">{isRTL ? "المسؤول عن الفرصة" : "Sales Owner"}</label>
              <select
                className="form-select"
                value={createOppForm.owner_id}
                onChange={(e) => setCreateOppForm({ ...createOppForm, owner_id: e.target.value })}
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

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-3)' }}>
            <div className="form-group">
              <label className="form-label">{isRTL ? "القيمة المتوقعة ($)" : "Estimated Value ($)"}</label>
              <input
                type="number"
                className="form-input"
                value={createOppForm.value}
                onChange={(e) => setCreateOppForm({ ...createOppForm, value: parseFloat(e.target.value) || 0 })}
              />
            </div>

            <div className="form-group">
              <label className="form-label">{isRTL ? "احتمالية النجاح (%)" : "Probability (%)"}</label>
              <input
                type="number"
                min={0}
                max={100}
                className="form-input"
                value={createOppForm.probability}
                onChange={(e) => setCreateOppForm({ ...createOppForm, probability: parseInt(e.target.value) || 0 })}
              />
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">{isRTL ? "التاريخ المتوقع للإغلاق" : "Expected Close Date"}</label>
            <input
              type="date"
              className="form-input"
              value={createOppForm.expected_close_at}
              onChange={(e) => setCreateOppForm({ ...createOppForm, expected_close_at: e.target.value })}
            />
          </div>

          <div className="form-group">
            <label className="form-label">{isRTL ? "الملاحظات" : "Notes"}</label>
            <textarea
              rows={2}
              className="form-textarea"
              placeholder="Key requirements, budget timeline, decision process..."
              value={createOppForm.notes}
              onChange={(e) => setCreateOppForm({ ...createOppForm, notes: e.target.value })}
            />
          </div>

          <div className="form-group">
            <label className="form-label">{isRTL ? "الخطوة التالية" : "Next Step"}</label>
            <input
              type="text"
              className="form-input"
              placeholder="e.g. Schedule commercial pricing review call..."
              value={createOppForm.next_step}
              onChange={(e) => setCreateOppForm({ ...createOppForm, next_step: e.target.value })}
            />
          </div>
        </form>
      </Modal>

      {/* ── Add Step Modal ─────────────────────────────────────────────── */}
      <Modal
        isOpen={showAddModal}
        onClose={() => setShowAddModal(false)}
        title={`Add Step to ${selectedCompany?.name || 'Roadmap'}`}
        footer={
          <>
            <button
              type="button"
              onClick={() => setShowAddModal(false)}
              className="btn btn-secondary"
            >
              {isRTL ? "إلغاء" : "Cancel"}
            </button>
            <button
              type="button"
              disabled={isSaving || !stepType}
              onClick={handleAddStep}
              className="btn btn-accent"
            >
              {isSaving ? (isRTL ? 'جاري الحفظ...' : 'Saving...') : (isRTL ? 'حفظ الخطوة' : 'Save Step')}
            </button>
          </>
        }
      >
        <form onSubmit={handleAddStep}>
          <div className="form-group">
            <label className="form-label">Roadmap Milestone / Stage *</label>
            <select
              className="form-select"
              value={stepType}
              onChange={(e) => setStepType(e.target.value)}
            >
              {STEP_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-3)' }}>
            <div className="form-group">
              <label className="form-label">Step Date *</label>
              <input
                type="date"
                required
                className="form-input"
                value={stepDate}
                onChange={(e) => setStepDate(e.target.value)}
              />
            </div>

            <div className="form-group">
              <label className="form-label">Status</label>
              <select
                className="form-select"
                value={stepStatus}
                onChange={(e) => setStepStatus(e.target.value)}
              >
                <option value="COMPLETED">Completed</option>
                <option value="IN_PROGRESS">In Progress</option>
                <option value="PENDING">Scheduled / Pending</option>
              </select>
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">Notes & Outcome Details</label>
            <textarea
              className="form-textarea"
              rows={3}
              placeholder="e.g. Discussed cloud migration SLA with CTO..."
              value={stepNotes}
              onChange={(e) => setStepNotes(e.target.value)}
            />
          </div>
        </form>
      </Modal>
    </div>
  );
};
