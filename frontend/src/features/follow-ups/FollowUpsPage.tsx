import React, { useState, useEffect } from 'react';
import { api } from '../../lib/apiClient';
import { useAuthStore } from '../../store/authStore';
import { LoadingSpinner } from '../../components/feedback/LoadingSpinner';
import { Modal } from '../../components/ui/Modal';
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
} from 'lucide-react';
import { useTranslation } from '../../i18n';

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

  const [companies, setCompanies] = useState<any[]>([]);
  const [selectedCompanyId, setSelectedCompanyId] = useState<string>('');
  const [selectedCompany, setSelectedCompany] = useState<any | null>(null);
  const [companyContacts, setCompanyContacts] = useState<any[]>([]);
  const [steps, setSteps] = useState<RoadmapStep[]>([]);
  const [isLoadingCompanies, setIsLoadingCompanies] = useState(true);
  const [isLoadingSteps, setIsLoadingSteps] = useState(false);
  const [companySearch, setCompanySearch] = useState('');

  // Add Step Modal State
  const [isAddStepModalOpen, setIsAddStepModalOpen] = useState(false);
  const [editingStep, setEditingStep] = useState<RoadmapStep | null>(null);
  const [stepTitle, setStepTitle] = useState('First Call');
  const [stepDate, setStepDate] = useState(() => new Date().toISOString().split('T')[0]);
  const [stepContactId, setStepContactId] = useState('');
  const [stepStatus, setStepStatus] = useState('COMPLETED');
  const [stepNotes, setStepNotes] = useState('');
  const [isSubmittingStep, setIsSubmittingStep] = useState(false);

  // Fetch Companies List
  useEffect(() => {
    const fetchCompanies = async () => {
      setIsLoadingCompanies(true);
      try {
        const res = await api.get<any>('/companies', { per_page: 100 });
        const list = res.data || [];
        setCompanies(list);
        if (list.length > 0) {
          // Default to ELM or first company
          const elmCompany = list.find((c: any) => c.name.toUpperCase().includes('ELM')) || list[0];
          setSelectedCompanyId(elmCompany.id);
          setSelectedCompany(elmCompany);
        }
      } catch (e) {
        console.error('Failed to load companies', e);
      } finally {
        setIsLoadingCompanies(false);
      }
    };
    fetchCompanies();
  }, []);

  // Fetch Steps and Contacts when selected company changes
  useEffect(() => {
    if (!selectedCompanyId) return;

    const comp = companies.find((c) => c.id === selectedCompanyId);
    setSelectedCompany(comp || null);

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
  }, [selectedCompanyId, companies]);

  const handleOpenAddStep = () => {
    setEditingStep(null);
    setStepTitle('First Call');
    setStepDate(new Date().toISOString().split('T')[0]);
    setStepContactId(companyContacts[0]?.id || '');
    setStepStatus('COMPLETED');
    setStepNotes('');
    setIsAddStepModalOpen(true);
  };

  const handleOpenEditStep = (step: RoadmapStep) => {
    setEditingStep(step);
    setStepTitle(step.step_type);
    setStepDate(step.step_date.split('T')[0]);
    setStepContactId(step.contact_id || '');
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
        // Update Step
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
        // Create Next Step
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

  const filteredCompanies = companies.filter((c) =>
    c.name.toLowerCase().includes(companySearch.toLowerCase())
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-6)' }}>
      {/* ── Header ──────────────────────────────────────────────────────── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 'var(--space-4)' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
            <h1 className="font-display font-bold text-2xl" style={{ color: 'var(--neutral-900)' }}>
              {isRTL ? "مسار متابعة الشركات (Journey Builder)" : "Company Follow-up Journey"}
            </h1>
            <span
              style={{
                fontSize: '11px',
                fontWeight: 700,
                padding: '2px 8px',
                borderRadius: 'var(--radius-full)',
                backgroundColor: 'var(--color-accent-light)',
                color: 'var(--color-accent)',
                border: '1px solid var(--color-accent)',
              }}
            >
              {isRTL ? "مستوى الشركة" : "Company Level"}
            </span>
          </div>
          <p className="text-sm text-muted" style={{ marginTop: '2px' }}>
            {isRTL
              ? "مسار بيعي موحد لكل شركة يوضح مراحل التواصل والتقدم: مكالمة أولى ← بريد إلكتروني ← عرض تجريبي ← مقترح مالي ← إغلاق."
              : "Unified account-level sales journey: First Call → Email Sent → Demo Scheduled → Proposal Sent → Closed."}
          </p>
        </div>

        {/* Company Quick Selector */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
          <Building2 size={16} style={{ color: 'var(--color-primary)' }} />
          <select
            className="form-select text-xs"
            style={{ width: '220px', fontWeight: 600 }}
            value={selectedCompanyId}
            onChange={(e) => setSelectedCompanyId(e.target.value)}
          >
            {companies.map((c) => (
              <option key={c.id} value={c.id}>
                🏢 {c.name} ({c.country || 'Gulf'})
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* ── Company Banner Card ─────────────────────────────────────────── */}
      {selectedCompany && (
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
                {selectedCompany.name}
              </h2>
              <span className="badge badge-accent text-xs">
                {companyContacts.length} {isRTL ? "جهات اتصال" : "Contacts"}
              </span>
            </div>
            <div style={{ display: 'flex', gap: 'var(--space-4)', marginTop: '4px', fontSize: '12px', color: 'var(--neutral-500)' }}>
              <span>📍 {selectedCompany.country || 'Saudi Arabia'}</span>
              <span>🏢 {selectedCompany.industry || 'Enterprise'}</span>
              <span>👤 {selectedCompany.account_owner_name ? `Owner: ${selectedCompany.account_owner_name}` : 'Unassigned'}</span>
            </div>
          </div>

          <button onClick={handleOpenAddStep} className="btn btn-accent btn-sm">
            <Plus size={15} />
            <span>{isRTL ? "إضافة خطوة للمسار" : "+ Add Next Step"}</span>
          </button>
        </div>
      )}

      {/* ── Journey Steps Pipeline Flow ─────────────────────────────────── */}
      {isLoadingSteps ? (
        <LoadingSpinner message={isRTL ? "جاري تحميل مسار الشركة..." : "Loading company sales journey..."} />
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
                {/* Step Card Box */}
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

                    {/* Step Actions */}
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
                      <button
                        onClick={() => handleOpenEditStep(step)}
                        className="btn btn-ghost btn-xs"
                        title="Edit Step"
                      >
                        <Edit2 size={13} style={{ color: 'var(--neutral-400)' }} />
                      </button>
                      <button
                        onClick={() => handleDeleteStep(step.id)}
                        className="btn btn-ghost btn-xs text-danger"
                        title="Delete Step"
                      >
                        <Trash2 size={13} />
                      </button>
                    </div>
                  </div>

                  {/* Notes Block */}
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

                {/* Downward Arrow Connector */}
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

          {/* Add Next Step Button at the bottom of the journey */}
          <div style={{ marginTop: 'var(--space-5)' }}>
            <button onClick={handleOpenAddStep} className="btn btn-accent btn-md">
              <Plus size={16} />
              <span>{isRTL ? "+ إضافة الخطوة التالية" : "+ Add Next Step"}</span>
            </button>
          </div>
        </div>
      )}

      {/* ── Add / Edit Step Modal ────────────────────────────────────────── */}
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
              <label className="form-label text-xs">{isRTL ? "جهة الاتصال المعنية (اختياري)" : "Associated Contact (Optional)"}</label>
              <select
                className="form-select text-xs"
                value={stepContactId}
                onChange={(e) => setStepContactId(e.target.value)}
              >
                <option value="">{isRTL ? "— عام للشركة (بدون تحديد جهة اتصال) —" : "— General Company Level (No Contact) —"}</option>
                {companyContacts.map((cc) => (
                  <option key={cc.id} value={cc.id}>
                    👤 {cc.full_name} ({cc.position || 'Employee'})
                  </option>
                ))}
              </select>
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
