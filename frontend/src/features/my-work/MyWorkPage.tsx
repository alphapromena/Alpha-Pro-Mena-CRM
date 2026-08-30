import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../../lib/apiClient';
import { useAuthStore } from '../../store/authStore';
import { Contact, Task, Recall } from '../../types';
import { LoadingSpinner } from '../../components/feedback/LoadingSpinner';
import { Modal } from '../../components/ui/Modal';
import {
  PhoneCall,
  Clock,
  PhoneMissed,
  Mail,
  MessageSquare,
  Presentation,
  CheckSquare,
  UserPlus,
  StickyNote,
  Activity,
  Plus,
  SlidersHorizontal,
  Trash2,
  ArrowUp,
  ArrowDown,
  CheckCircle2,
  Copy,
  Check,
  ExternalLink,
  RotateCcw,
  Sparkles,
  LayoutGrid,
} from 'lucide-react';
import { useTranslation } from '../../i18n';

export interface WidgetConfig {
  id: string;
  type: string;
  titleEn: string;
  titleAr: string;
}

const AVAILABLE_WIDGETS: WidgetConfig[] = [
  { id: 'calls_due', type: 'calls_due', titleEn: 'Calls Due', titleAr: 'المكالمات المستحقة' },
  { id: 'recalls', type: 'recalls', titleEn: 'Scheduled Recalls', titleAr: 'إعادة الاتصال المجدولة' },
  { id: 'no_answer', type: 'no_answer', titleEn: 'No Answer Retries', titleAr: 'إعادة محاولة عدم الرد' },
  { id: 'email_whatsapp', type: 'email_whatsapp', titleEn: 'Email / WhatsApp Follow-ups', titleAr: 'متابعات البريد والواتساب' },
  { id: 'demos', type: 'demos', titleEn: 'Demos & Meetings', titleAr: 'العروض التوضيحية والاجتماعات' },
  { id: 'tasks', type: 'tasks', titleEn: 'Tasks', titleAr: 'المهام اليومية' },
  { id: 'personal_pool', type: 'personal_pool', titleEn: 'Personal Pool', titleAr: 'المجمع الشخصي للعملاء' },
  { id: 'quick_notes', type: 'quick_notes', titleEn: 'Quick Notes', titleAr: 'الملاحظات السريعة' },
  { id: 'upcoming_activities', type: 'upcoming_activities', titleEn: 'Upcoming Activities', titleAr: 'الأنشطة القادمة' },
];

export const MyWorkPage: React.FC = () => {
  const navigate = useNavigate();
  const { user } = useAuthStore();
  const { isRTL } = useTranslation();

  const storageKey = `alpha_mywork_widgets_${user?.id || 'guest'}`;

  // Default is EMPTY workspace for all users
  const [activeWidgets, setActiveWidgets] = useState<string[]>(() => {
    try {
      const saved = localStorage.getItem(storageKey);
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });

  const [isCustomizeOpen, setIsCustomizeOpen] = useState(false);
  const [tempWidgets, setTempWidgets] = useState<string[]>(activeWidgets);

  // Data states
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [recalls, setRecalls] = useState<Recall[]>([]);
  const [noAnswerItems, setNoAnswerItems] = useState<any[]>([]);
  const [emailWhatsappItems, setEmailWhatsappItems] = useState<Contact[]>([]);
  const [demos, setDemos] = useState<any[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [poolCount, setPoolCount] = useState<number>(0);
  const [quickNoteText, setQuickNoteText] = useState<string>(() => {
    return localStorage.getItem(`alpha_quick_note_${user?.id || 'guest'}`) || '';
  });
  const [isLoading, setIsLoading] = useState(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const handleCopy = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 1500);
  };

  const loadData = async () => {
    if (activeWidgets.length === 0) return;
    setIsLoading(true);
    try {
      const promises: Promise<any>[] = [];
      if (activeWidgets.includes('calls_due')) {
        promises.push(api.get<any>('/contacts', { per_page: 8, status: 'NEW' }).then((r) => setContacts(r.data || [])));
      }
      if (activeWidgets.includes('recalls')) {
        promises.push(api.get<any>('/recalls', { per_page: 8, status: 'PENDING' }).then((r) => setRecalls(r.data || [])));
      }
      if (activeWidgets.includes('no_answer')) {
        promises.push(api.get<any>('/no-answer', { per_page: 8 }).then((r) => setNoAnswerItems(r.data || [])));
      }
      if (activeWidgets.includes('email_whatsapp')) {
        promises.push(
          api.get<any>('/contacts', { per_page: 8, status: 'EMAIL_REQUESTED' }).then((r) => setEmailWhatsappItems(r.data || []))
        );
      }
      if (activeWidgets.includes('demos')) {
        promises.push(api.get<any>('/demos', { per_page: 8 }).then((r) => setDemos(r.data || [])));
      }
      if (activeWidgets.includes('tasks')) {
        promises.push(api.get<any>('/tasks', { per_page: 8, status: 'OPEN' }).then((r) => setTasks(r.data || [])));
      }
      if (activeWidgets.includes('personal_pool')) {
        promises.push(
          api.get<any>('/contacts', { per_page: 1, pending_claim_only: true }).then((r) => setPoolCount(r.meta?.total || 0))
        );
      }
      await Promise.all(promises);
    } catch (e) {
      console.error('Failed loading widget data', e);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [activeWidgets]);

  const openCustomizeModal = () => {
    setTempWidgets([...activeWidgets]);
    setIsCustomizeOpen(true);
  };

  const handleSaveCustomization = () => {
    setActiveWidgets(tempWidgets);
    localStorage.setItem(storageKey, JSON.stringify(tempWidgets));
    setIsCustomizeOpen(false);
  };

  const toggleWidget = (widgetId: string) => {
    if (tempWidgets.includes(widgetId)) {
      setTempWidgets(tempWidgets.filter((id) => id !== widgetId));
    } else {
      setTempWidgets([...tempWidgets, widgetId]);
    }
  };

  const moveWidget = (index: number, direction: 'up' | 'down') => {
    const newIdx = direction === 'up' ? index - 1 : index + 1;
    if (newIdx < 0 || newIdx >= tempWidgets.length) return;
    const updated = [...tempWidgets];
    const item = updated.splice(index, 1)[0];
    updated.splice(newIdx, 0, item);
    setTempWidgets(updated);
  };

  const handleSaveQuickNote = (text: string) => {
    setQuickNoteText(text);
    localStorage.setItem(`alpha_quick_note_${user?.id || 'guest'}`, text);
  };

  const handleCompleteTask = async (taskId: string) => {
    try {
      await api.patch(`/tasks/${taskId}/complete`, { notes: 'Completed from My Work' });
      setTasks((prev) => prev.filter((t) => t.id !== taskId));
    } catch (e) {
      console.error('Failed to complete task', e);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-6)' }}>
      {/* Workstation Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 'var(--space-4)' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
            <h1 className="font-display font-bold text-2xl" style={{ color: 'var(--neutral-900)' }}>
              {isRTL ? 'مساحة العمل الخاصة بي' : 'My Work'}
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
              {isRTL ? 'مخصصة بالكامل' : 'Customizable Workspace'}
            </span>
          </div>
          <p className="text-sm text-muted" style={{ marginTop: '2px' }}>
            {isRTL
              ? 'مساحة عملك الشخصية. قم بإضافة وترتيب الأدوات التي تناسب نمط عملك اليومي.'
              : 'Your personal workspace. Add, arrange, and customize modules to match your daily sales routine.'}
          </p>
        </div>

        <div style={{ display: 'flex', gap: 'var(--space-3)' }}>
          {activeWidgets.length > 0 && (
            <button onClick={loadData} className="btn btn-secondary btn-sm">
              <RotateCcw size={14} />
              <span>{isRTL ? 'تحديث البيانات' : 'Refresh'}</span>
            </button>
          )}
          <button onClick={openCustomizeModal} className="btn btn-accent btn-sm">
            <SlidersHorizontal size={14} />
            <span>{isRTL ? 'تخصيص مساحة العمل' : 'Customize My Work'}</span>
          </button>
        </div>
      </div>

      {/* Main Content: Empty State or Active Widgets Grid */}
      {activeWidgets.length === 0 ? (
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            padding: 'var(--space-12) var(--space-6)',
            backgroundColor: 'var(--bg-surface)',
            borderRadius: 'var(--radius-2xl)',
            border: '2px dashed var(--border-color)',
            textAlign: 'center',
            gap: 'var(--space-4)',
          }}
        >
          <div
            style={{
              width: '64px',
              height: '64px',
              borderRadius: '50%',
              backgroundColor: 'var(--color-accent-light)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--color-accent)',
            }}
          >
            <LayoutGrid size={32} />
          </div>

          <div>
            <h2
              style={{
                fontFamily: 'var(--font-display)',
                fontSize: '20px',
                fontWeight: 700,
                color: 'var(--neutral-900)',
                margin: '0 0 4px 0',
              }}
            >
              {isRTL ? 'قم بتخصيص مساحة عملك' : 'Customize your workspace'}
            </h2>
            <p
              style={{
                fontSize: '14px',
                color: 'var(--neutral-500)',
                maxWidth: '460px',
                margin: 0,
                lineHeight: 1.5,
              }}
            >
              {isRTL
                ? 'مساحة العمل فارغة حالياً. اختر الوحدات التي ترغب بعرضها مثل المكالمات المستحقة، إعادة الاتصال، عدم الرد، المتابعات والملاحظات.'
                : 'Your workspace is currently empty. Choose what you want to see, such as Calls Due, Recalls, No Answer Retries, Follow-ups, and Notes.'}
            </p>
          </div>

          <button onClick={openCustomizeModal} className="btn btn-accent btn-md" style={{ marginTop: 'var(--space-2)' }}>
            <Plus size={16} />
            <span>{isRTL ? 'إضافة وحدات وتخصيص' : 'Customize My Work'}</span>
          </button>
        </div>
      ) : isLoading ? (
        <LoadingSpinner message={isRTL ? 'جاري تحميل مساحة العمل المخصصة...' : 'Loading your customized workstation...'} />
      ) : (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))',
            gap: 'var(--space-5)',
          }}
        >
          {activeWidgets.map((widgetId) => {
            const def = AVAILABLE_WIDGETS.find((w) => w.id === widgetId);
            if (!def) return null;
            const title = isRTL ? def.titleAr : def.titleEn;

            switch (widgetId) {
              case 'calls_due':
                return (
                  <div key={widgetId} className="card" style={{ padding: 'var(--space-5)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-3)' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <PhoneCall size={18} style={{ color: 'var(--color-primary)' }} />
                        <h3 className="font-bold text-base" style={{ margin: 0, color: 'var(--neutral-900)' }}>
                          {title}
                        </h3>
                      </div>
                      <button onClick={() => navigate('/contacts')} className="btn btn-ghost btn-xs">
                        <ExternalLink size={12} />
                        <span>{isRTL ? 'عرض الكل' : 'View All'}</span>
                      </button>
                    </div>
                    {contacts.length === 0 ? (
                      <p className="text-xs text-muted" style={{ padding: 'var(--space-3) 0' }}>
                        {isRTL ? 'لا توجد مكالمات مستحقة جديدة.' : 'No new calls due in queue.'}
                      </p>
                    ) : (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                        {contacts.slice(0, 5).map((c) => (
                          <div
                            key={c.id}
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'space-between',
                              padding: '6px 10px',
                              backgroundColor: 'var(--bg-app)',
                              borderRadius: 'var(--radius-md)',
                              border: '1px solid var(--border-light)',
                            }}
                          >
                            <div>
                              <button
                                onClick={() => navigate(`/contacts/${c.id}`)}
                                className="font-semibold text-xs text-left"
                                style={{ background: 'none', border: 'none', padding: 0, cursor: 'pointer', color: 'var(--neutral-900)' }}
                              >
                                {c.full_name}
                              </button>
                              <div className="text-xs text-muted">{c.company_name || '—'}</div>
                            </div>
                            {c.phone && (
                              <button
                                onClick={() => handleCopy(c.phone!, c.id)}
                                className="btn btn-ghost btn-xs font-mono"
                                style={{ gap: '4px' }}
                              >
                                <span>{c.phone}</span>
                                {copiedId === c.id ? <Check size={12} color="var(--color-success)" /> : <Copy size={12} />}
                              </button>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                );

              case 'recalls':
                return (
                  <div key={widgetId} className="card" style={{ padding: 'var(--space-5)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-3)' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <Clock size={18} style={{ color: 'var(--color-accent)' }} />
                        <h3 className="font-bold text-base" style={{ margin: 0, color: 'var(--neutral-900)' }}>
                          {title}
                        </h3>
                      </div>
                      <button onClick={() => navigate('/recalls')} className="btn btn-ghost btn-xs">
                        <ExternalLink size={12} />
                        <span>{isRTL ? 'عرض الكل' : 'View All'}</span>
                      </button>
                    </div>
                    {recalls.length === 0 ? (
                      <p className="text-xs text-muted" style={{ padding: 'var(--space-3) 0' }}>
                        {isRTL ? 'لا توجد مواعيد إعادة اتصال معلقة.' : 'No pending scheduled recalls.'}
                      </p>
                    ) : (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                        {recalls.slice(0, 5).map((r: any) => (
                          <div
                            key={r.id}
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'space-between',
                              padding: '6px 10px',
                              backgroundColor: 'var(--bg-app)',
                              borderRadius: 'var(--radius-md)',
                              border: '1px solid var(--border-light)',
                            }}
                          >
                            <div>
                              <div className="font-semibold text-xs text-dark">{r.contact_name || 'Contact'}</div>
                              <div className="text-xs text-muted">{r.company_name || '—'}</div>
                            </div>
                            <span className="text-xs font-semibold" style={{ color: 'var(--color-accent)' }}>
                              ⏰ {new Date(r.scheduled_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                            </span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                );

              case 'no_answer':
                return (
                  <div key={widgetId} className="card" style={{ padding: 'var(--space-5)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-3)' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <PhoneMissed size={18} style={{ color: 'var(--color-warning)' }} />
                        <h3 className="font-bold text-base" style={{ margin: 0, color: 'var(--neutral-900)' }}>
                          {title}
                        </h3>
                      </div>
                      <button onClick={() => navigate('/no-answer')} className="btn btn-ghost btn-xs">
                        <ExternalLink size={12} />
                        <span>{isRTL ? 'عرض الكل' : 'View All'}</span>
                      </button>
                    </div>
                    {noAnswerItems.length === 0 ? (
                      <p className="text-xs text-muted" style={{ padding: 'var(--space-3) 0' }}>
                        {isRTL ? 'لا يوجد عملاء في طابور إعادة المحاولة.' : 'No contacts in no-answer queue.'}
                      </p>
                    ) : (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                        {noAnswerItems.slice(0, 5).map((na: any) => (
                          <div
                            key={na.id}
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'space-between',
                              padding: '6px 10px',
                              backgroundColor: 'var(--bg-app)',
                              borderRadius: 'var(--radius-md)',
                              border: '1px solid var(--border-light)',
                            }}
                          >
                            <div>
                              <div className="font-semibold text-xs text-dark">{na.contact_name}</div>
                              <div className="text-xs text-muted">Attempt #{na.attempt_number}</div>
                            </div>
                            <span className="text-xs text-muted">
                              {na.next_attempt_at ? new Date(na.next_attempt_at).toLocaleDateString() : 'Due'}
                            </span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                );

              case 'email_whatsapp':
                return (
                  <div key={widgetId} className="card" style={{ padding: 'var(--space-5)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-3)' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <Mail size={18} style={{ color: 'var(--color-info)' }} />
                        <h3 className="font-bold text-base" style={{ margin: 0, color: 'var(--neutral-900)' }}>
                          {title}
                        </h3>
                      </div>
                      <button onClick={() => navigate('/contacts?tab=email_whatsapp')} className="btn btn-ghost btn-xs">
                        <ExternalLink size={12} />
                        <span>{isRTL ? 'عرض الكل' : 'View All'}</span>
                      </button>
                    </div>
                    {emailWhatsappItems.length === 0 ? (
                      <p className="text-xs text-muted" style={{ padding: 'var(--space-3) 0' }}>
                        {isRTL ? 'لا توجد طلبات بريد أو واتساب معلقة.' : 'No pending email or WhatsApp requests.'}
                      </p>
                    ) : (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                        {emailWhatsappItems.slice(0, 5).map((ew) => (
                          <div
                            key={ew.id}
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'space-between',
                              padding: '6px 10px',
                              backgroundColor: 'var(--bg-app)',
                              borderRadius: 'var(--radius-md)',
                              border: '1px solid var(--border-light)',
                            }}
                          >
                            <div>
                              <div className="font-semibold text-xs text-dark">{ew.full_name}</div>
                              <div className="text-xs text-muted">{ew.company_name || ew.email}</div>
                            </div>
                            <span className="badge badge-accent text-xs">Email Requested</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                );

              case 'tasks':
                return (
                  <div key={widgetId} className="card" style={{ padding: 'var(--space-5)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-3)' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <CheckSquare size={18} style={{ color: 'var(--color-success)' }} />
                        <h3 className="font-bold text-base" style={{ margin: 0, color: 'var(--neutral-900)' }}>
                          {title}
                        </h3>
                      </div>
                      <button onClick={() => navigate('/tasks')} className="btn btn-ghost btn-xs">
                        <ExternalLink size={12} />
                        <span>{isRTL ? 'عرض الكل' : 'View All'}</span>
                      </button>
                    </div>
                    {tasks.length === 0 ? (
                      <p className="text-xs text-muted" style={{ padding: 'var(--space-3) 0' }}>
                        {isRTL ? 'لا توجد مهام معلقة.' : 'No pending tasks.'}
                      </p>
                    ) : (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                        {tasks.slice(0, 5).map((t) => (
                          <div
                            key={t.id}
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'space-between',
                              padding: '6px 10px',
                              backgroundColor: 'var(--bg-app)',
                              borderRadius: 'var(--radius-md)',
                              border: '1px solid var(--border-light)',
                            }}
                          >
                            <div style={{ maxWidth: '240px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                              <div className="font-semibold text-xs text-dark">{t.title}</div>
                              <div className="text-xs text-muted">{t.type}</div>
                            </div>
                            <button
                              onClick={() => handleCompleteTask(t.id)}
                              className="btn btn-ghost btn-xs"
                              title="Complete task"
                            >
                              <CheckCircle2 size={15} style={{ color: 'var(--color-success)' }} />
                            </button>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                );

              case 'personal_pool':
                return (
                  <div key={widgetId} className="card" style={{ padding: 'var(--space-5)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-3)' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <UserPlus size={18} style={{ color: 'var(--color-accent)' }} />
                        <h3 className="font-bold text-base" style={{ margin: 0, color: 'var(--neutral-900)' }}>
                          {title}
                        </h3>
                      </div>
                      <button onClick={() => navigate('/leads/pool')} className="btn btn-ghost btn-xs">
                        <ExternalLink size={12} />
                        <span>{isRTL ? 'عرض المجمع' : 'Open Pool'}</span>
                      </button>
                    </div>
                    <div
                      style={{
                        padding: 'var(--space-4)',
                        backgroundColor: 'var(--bg-app)',
                        borderRadius: 'var(--radius-md)',
                        textAlign: 'center',
                      }}
                    >
                      <div style={{ fontSize: '28px', fontWeight: 800, color: 'var(--color-accent)' }}>{poolCount}</div>
                      <div className="text-xs text-muted">
                        {isRTL ? 'عملاء في مجمعك الشخصي بانتظار الإضافة' : 'Unclaimed leads available in your pool'}
                      </div>
                      <button
                        onClick={() => navigate('/leads/pool')}
                        className="btn btn-accent btn-xs"
                        style={{ marginTop: 'var(--space-2)' }}
                      >
                        {isRTL ? 'إضافة جهات الاتصال' : 'Claim to Contacts'}
                      </button>
                    </div>
                  </div>
                );

              case 'quick_notes':
                return (
                  <div key={widgetId} className="card" style={{ padding: 'var(--space-5)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-3)' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <StickyNote size={18} style={{ color: '#eab308' }} />
                        <h3 className="font-bold text-base" style={{ margin: 0, color: 'var(--neutral-900)' }}>
                          {title}
                        </h3>
                      </div>
                    </div>
                    <textarea
                      value={quickNoteText}
                      onChange={(e) => handleSaveQuickNote(e.target.value)}
                      placeholder={isRTL ? 'اكتب ملاحظاتك وتذكيراتك اليومية هنا...' : 'Write scratchpad notes and reminders here...'}
                      className="form-input text-xs custom-scrollbar"
                      style={{
                        width: '100%',
                        height: '110px',
                        resize: 'none',
                        fontSize: '12px',
                        lineHeight: 1.5,
                      }}
                    />
                  </div>
                );

              case 'upcoming_activities':
              case 'demos':
              default:
                return (
                  <div key={widgetId} className="card" style={{ padding: 'var(--space-5)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-3)' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <Activity size={18} style={{ color: 'var(--color-primary)' }} />
                        <h3 className="font-bold text-base" style={{ margin: 0, color: 'var(--neutral-900)' }}>
                          {title}
                        </h3>
                      </div>
                    </div>
                    <p className="text-xs text-muted" style={{ padding: 'var(--space-3) 0' }}>
                      {isRTL ? 'لا توجد أنشطة قادمة حالياً.' : 'No upcoming activities logged.'}
                    </p>
                  </div>
                );
            }
          })}
        </div>
      )}

      {/* Customize My Work Modal */}
      {isCustomizeOpen && (
        <Modal
          isOpen={isCustomizeOpen}
          onClose={() => setIsCustomizeOpen(false)}
          title={isRTL ? 'تخصيص مساحة العمل' : 'Customize My Work'}
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
            <p className="text-xs text-muted" style={{ margin: 0 }}>
              {isRTL
                ? 'حدد الوحدات التي ترغب بعرضها في مساحة عملك وقم بترتيبها حسب أولويتك.'
                : 'Select the modules you want to display on your workspace and reorder them according to your priority.'}
            </p>

            {/* Available Widgets Toggles */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '340px', overflowY: 'auto' }}>
              {AVAILABLE_WIDGETS.map((widget) => {
                const isSelected = tempWidgets.includes(widget.id);
                const itemIndex = tempWidgets.indexOf(widget.id);
                return (
                  <div
                    key={widget.id}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      padding: '8px 12px',
                      borderRadius: 'var(--radius-md)',
                      backgroundColor: isSelected ? 'var(--color-accent-light)' : 'var(--bg-app)',
                      border: isSelected ? '1px solid var(--color-accent)' : '1px solid var(--border-color)',
                      transition: 'all 0.15s ease',
                    }}
                  >
                    <label
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '10px',
                        cursor: 'pointer',
                        flex: 1,
                        fontSize: '13px',
                        fontWeight: isSelected ? 700 : 500,
                        color: 'var(--neutral-900)',
                      }}
                    >
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={() => toggleWidget(widget.id)}
                        style={{ cursor: 'pointer', width: '16px', height: '16px' }}
                      />
                      <span>{isRTL ? widget.titleAr : widget.titleEn}</span>
                    </label>

                    {/* Reorder Buttons if Active */}
                    {isSelected && (
                      <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                        <button
                          type="button"
                          onClick={() => moveWidget(itemIndex, 'up')}
                          disabled={itemIndex === 0}
                          className="btn btn-ghost btn-xs"
                          style={{ padding: '2px 4px', opacity: itemIndex === 0 ? 0.3 : 1 }}
                          title="Move up"
                        >
                          <ArrowUp size={13} />
                        </button>
                        <button
                          type="button"
                          onClick={() => moveWidget(itemIndex, 'down')}
                          disabled={itemIndex === tempWidgets.length - 1}
                          className="btn btn-ghost btn-xs"
                          style={{ padding: '2px 4px', opacity: itemIndex === tempWidgets.length - 1 ? 0.3 : 1 }}
                          title="Move down"
                        >
                          <ArrowDown size={13} />
                        </button>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>

            {/* Modal Actions */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 'var(--space-2)' }}>
              <button
                type="button"
                onClick={() => setTempWidgets([])}
                className="btn btn-ghost btn-sm text-danger"
                style={{ fontSize: '11px' }}
              >
                <Trash2 size={13} />
                <span>{isRTL ? 'إفراغ مساحة العمل' : 'Clear All (Empty)'}</span>
              </button>

              <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
                <button type="button" onClick={() => setIsCustomizeOpen(false)} className="btn btn-secondary btn-sm">
                  {isRTL ? 'إلغاء' : 'Cancel'}
                </button>
                <button type="button" onClick={handleSaveCustomization} className="btn btn-accent btn-sm">
                  <Check size={14} />
                  <span>{isRTL ? 'حفظ التخصيص' : 'Save Workspace'}</span>
                </button>
              </div>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
};
