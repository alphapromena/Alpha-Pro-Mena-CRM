import React, { useState, useEffect, useRef } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { api } from '../../lib/apiClient';
import { useAuthStore } from '../../store/authStore';
import { Contact, ContactStatus } from '../../types';
import { Badge } from '../../components/ui/Badge';
import { Modal } from '../../components/ui/Modal';
import { LoadingSpinner } from '../../components/feedback/LoadingSpinner';
import { EmptyState } from '../../components/feedback/EmptyState';
import {
  Plus,
  Search,
  Phone,
  Mail,
  Copy,
  Check,
  Edit2,
  Clock,
  UserCheck,
  Archive,
  ArchiveRestore,
  Layers,
  MessageSquare,
  Sparkles,
  PhoneCall,
  Calendar,
  AlertCircle,
  SlidersHorizontal,
} from 'lucide-react';
import { useTranslation } from '../../i18n';

const CopyBtn: React.FC<{ text: string; label: string }> = ({ text, label }) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = (e: React.MouseEvent) => {
    e.stopPropagation();
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <button
      onClick={handleCopy}
      type="button"
      title={copied ? `Copied ${label}!` : `Copy ${label}`}
      style={{
        background: 'none',
        border: 'none',
        padding: '2px 4px',
        cursor: 'pointer',
        color: copied ? 'var(--color-success)' : 'var(--neutral-400)',
        display: 'inline-flex',
        alignItems: 'center',
        transition: 'color 0.15s ease',
      }}
    >
      {copied ? <Check size={13} /> : <Copy size={13} />}
    </button>
  );
};

// Inline Quick Note Editor Cell
const InlineNoteCell: React.FC<{
  contact: Contact;
  onNoteUpdated: (contactId: string, noteText: string) => void;
}> = ({ contact, onNoteUpdated }) => {
  const [isEditing, setIsEditing] = useState(false);
  const [noteText, setNoteText] = useState(contact.notes || '');
  const [isSaving, setIsSaving] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isEditing && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isEditing]);

  const handleSave = async () => {
    if (!noteText.trim() || noteText === contact.notes) {
      setIsEditing(false);
      return;
    }
    setIsSaving(true);
    try {
      await api.post(`/contacts/${contact.id}/notes`, {
        note_text: noteText.trim(),
      });
      onNoteUpdated(contact.id, noteText.trim());
      setIsEditing(false);
    } catch (e: any) {
      alert(e.message || 'Failed to save note');
    } finally {
      setIsSaving(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleSave();
    } else if (e.key === 'Escape') {
      setNoteText(contact.notes || '');
      setIsEditing(false);
    }
  };

  if (isEditing) {
    return (
      <div
        style={{ display: 'flex', alignItems: 'center', gap: '4px', minWidth: '180px' }}
        onClick={(e) => e.stopPropagation()}
      >
        <input
          ref={inputRef}
          type="text"
          value={noteText}
          disabled={isSaving}
          onChange={(e) => setNoteText(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Type note and hit Enter..."
          className="form-input text-xs"
          style={{ height: '28px', padding: '2px 6px', fontSize: '11px' }}
        />
        <button
          onClick={handleSave}
          disabled={isSaving}
          className="btn btn-accent btn-sm"
          style={{ padding: '2px 6px', height: '28px' }}
          title="Save note (Enter)"
        >
          <Check size={12} />
        </button>
        <button
          onClick={() => {
            setNoteText(contact.notes || '');
            setIsEditing(false);
          }}
          className="btn btn-secondary btn-sm"
          style={{ padding: '2px 6px', height: '28px' }}
          title="Cancel (Esc)"
        >
          &times;
        </button>
      </div>
    );
  }

  return (
    <div
      onClick={() => setIsEditing(true)}
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        cursor: 'pointer',
        padding: '2px 4px',
        borderRadius: '4px',
        minHeight: '26px',
        minWidth: '140px',
      }}
      className="hover-bg-subtle"
      title="Click to edit note inline"
    >
      <span
        style={{
          fontSize: '11px',
          color: contact.notes ? 'var(--neutral-800)' : 'var(--neutral-400)',
          fontStyle: contact.notes ? 'normal' : 'italic',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
          maxWidth: '220px',
        }}
      >
        {contact.notes || 'Click to add note...'}
      </span>
      <Edit2 size={11} style={{ color: 'var(--neutral-400)', opacity: 0.6, flexShrink: 0, marginLeft: '4px' }} />
    </div>
  );
};

// Outcome Badge Helper
const getOutcomeStyle = (outcome?: string) => {
  if (!outcome) return { bg: '#f8fafc', color: '#64748b', border: '#e2e8f0' };
  const norm = outcome.toUpperCase().replace(/\s+/g, '_');
  if (norm.includes('NO_ANSWER') || norm === 'NA') {
    return { bg: '#f1f5f9', color: '#475569', border: '#cbd5e1' };
  }
  if (norm.includes('INTERESTED') && !norm.includes('NOT')) {
    return { bg: '#ecfdf5', color: '#047857', border: '#a7f3d0' };
  }
  if (norm.includes('EMAIL')) {
    return { bg: '#f0f9ff', color: '#0369a1', border: '#bae6fd' };
  }
  if (norm.includes('WHATSAPP') || norm.includes('WHATA')) {
    return { bg: '#f0fdf4', color: '#15803d', border: '#bbf7d0' };
  }
  if (norm.includes('RE_CALL') || norm.includes('RECALL') || norm.includes('CALL_LATER') || norm.includes('CALLBACK')) {
    return { bg: '#fffbeb', color: '#b45309', border: '#fde68a' };
  }
  if (norm.includes('DEMO')) {
    return { bg: '#faf5ff', color: '#6d28d9', border: '#ddd6fe' };
  }
  if (norm.includes('NOT_INTERESTED')) {
    return { bg: '#fef2f2', color: '#b91c1c', border: '#fecaca' };
  }
  if (norm.includes('WRONG_NUMBER')) {
    return { bg: '#f8fafc', color: '#64748b', border: '#cbd5e1' };
  }
  if (norm.includes('CONVERTED') || norm.includes('WON')) {
    return { bg: '#ecfdf5', color: '#047857', border: '#6ee7b7' };
  }
  if (norm.includes('DNC') || norm.includes('DON')) {
    return { bg: '#fef2f2', color: '#991b1b', border: '#fca5a5' };
  }
  return { bg: '#f8fafc', color: '#334155', border: '#e2e8f0' };
};

const AttemptOutcomeBadge: React.FC<{ outcome: string; notes?: string | null; calledAt?: string | null }> = ({
  outcome,
  notes,
  calledAt,
}) => {
  const style = getOutcomeStyle(outcome);
  return (
    <div
      title={`${outcome}${calledAt ? ` • ${new Date(calledAt).toLocaleDateString()}` : ''}${notes ? ` • ${notes}` : ''}`}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '3px 8px',
        borderRadius: '6px',
        fontSize: '11px',
        fontWeight: 600,
        backgroundColor: style.bg,
        color: style.color,
        border: `1px solid ${style.border}`,
        whiteSpace: 'nowrap',
        maxWidth: '135px',
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        boxShadow: '0 1px 2px rgba(0,0,0,0.03)',
      }}
    >
      {outcome.replace(/_/g, ' ')}
    </div>
  );
};

// Helper for Ordinal format (1st, 2nd, 3rd, 4th, 5th)
const formatAttemptOrdinalShort = (n: number) => {
  const s = ['th', 'st', 'nd', 'rd'];
  const v = n % 100;
  return n + (s[(v - 20) % 10] || s[v] || s[0]);
};

// Inline Next Attempt Selector Cell (compact dropdown matching Google Sheet style)
const InlineNextAttemptSelector: React.FC<{
  contact: Contact;
  attemptNumber: number;
  onAttemptLogged: (updatedContact: Contact) => void;
  onRequestRecallModal: (contact: Contact) => void;
}> = ({ contact, attemptNumber, onAttemptLogged, onRequestRecallModal }) => {
  const [isSaving, setIsSaving] = useState(false);
  const [selected, setSelected] = useState('');

  const handleChange = async (e: React.ChangeEvent<HTMLSelectElement>) => {
    const outcome = e.target.value;
    if (!outcome) return;

    if (outcome === 'Re Call' || outcome === 'RECALL' || outcome === 'CALL_LATER') {
      onRequestRecallModal(contact);
      return;
    }

    setSelected(outcome);
    setIsSaving(true);
    try {
      const res = await api.post<any>(`/contacts/${contact.id}/quick-call`, { outcome });
      if (res.data) {
        onAttemptLogged(res.data);
      }
    } catch (err: any) {
      alert(err.message || 'Failed to log attempt');
    } finally {
      setIsSaving(false);
      setSelected('');
    }
  };

  return (
    <div style={{ display: 'inline-flex', alignItems: 'center' }} onClick={(e) => e.stopPropagation()}>
      <select
        value={selected}
        disabled={isSaving}
        onChange={handleChange}
        className="form-select text-xs"
        style={{
          height: '28px',
          padding: '1px 6px',
          fontSize: '11px',
          fontWeight: 500,
          backgroundColor: 'var(--bg-surface)',
          color: isSaving ? 'var(--neutral-400)' : 'var(--neutral-700)',
          borderColor: isSaving ? 'var(--color-primary)' : 'var(--border-color)',
          borderRadius: '6px',
          minWidth: '120px',
          maxWidth: '140px',
          cursor: 'pointer',
        }}
      >
        <option value="">+ {formatAttemptOrdinalShort(attemptNumber)} Attempt...</option>
        <option value="No Answer">📞 No Answer</option>
        <option value="Asked for email">📧 Asked for email</option>
        <option value="Asked for whatapp">💬 Asked for whatsapp</option>
        <option value="Re Call">⏰ Re Call (Schedule)</option>
        <option value="Demo">🎯 Demo</option>
        <option value="Interested">✨ Interested</option>
        <option value="Not interested">🚫 Not interested</option>
        <option value="wrong number">❌ Wrong number</option>
        <option value="voice male">🎙️ Voice mail</option>
        <option value="don't call again">⛔ Don't call again</option>
        <option value="HQ">🏢 HQ</option>
      </select>
    </div>
  );
};

export const ContactsPage: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { user } = useAuthStore();
  const { t, isRTL } = useTranslation();

  // Active Workflow View: LEADS | EMAIL_WHATSAPP | ARCHIVE
  const tabParam = searchParams.get('tab');
  const [activeView, setActiveView] = useState<'LEADS' | 'EMAIL_WHATSAPP' | 'ARCHIVE'>(() => {
    if (tabParam === 'email_whatsapp') return 'EMAIL_WHATSAPP';
    if (tabParam === 'archive') return 'ARCHIVE';
    return 'LEADS';
  });

  const [contacts, setContacts] = useState<Contact[]>([]);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [isLoading, setIsLoading] = useState(true);

  // Users List for Owner Filter
  const [usersList, setUsersList] = useState<any[]>([]);

  // Filters State
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState(searchParams.get('search') || '');
  const [ownerFilter, setOwnerFilter] = useState(searchParams.get('owner_id') || '');
  const [outcomeFilter, setOutcomeFilter] = useState(searchParams.get('outcome') || '');
  const [countryFilter, setCountryFilter] = useState('');
  const [industryFilter, setIndustryFilter] = useState('');
  const [positionFilter, setPositionFilter] = useState('');
  const [sortBy, setSortBy] = useState<string>('sheet_order');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc');

  // Column Visibility Customization
  const defaultColumns = {
    position: true,
    phone: true,
    email: true,
    owner: true,
    attempts: true,
    final_outcome: true,
    notes: true,
  };

  const [visibleColumns, setVisibleColumns] = useState(() => {
    try {
      const saved = localStorage.getItem('alpha_contacts_cols_v5');
      return saved ? JSON.parse(saved) : defaultColumns;
    } catch {
      return defaultColumns;
    }
  });

  const [showColumnMenu, setShowColumnMenu] = useState(false);

  const toggleColumn = (col: keyof typeof defaultColumns) => {
    const updated = { ...visibleColumns, [col]: !visibleColumns[col] };
    setVisibleColumns(updated);
    localStorage.setItem('alpha_contacts_cols_v5', JSON.stringify(updated));
  };

  // Scheduled Recall Modal State
  const [recallModalContact, setRecallModalContact] = useState<Contact | null>(null);
  const [recallDate, setRecallDate] = useState<string>(() => {
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    return tomorrow.toISOString().split('T')[0];
  });
  const [recallTime, setRecallTime] = useState<string>('11:30');
  const [recallNotes, setRecallNotes] = useState<string>('');
  const [isSavingRecall, setIsSavingRecall] = useState(false);

  // Final Outcome Modal State
  const [finalOutcomeContact, setFinalOutcomeContact] = useState<Contact | null>(null);
  const [finalOutcomeChoice, setFinalOutcomeChoice] = useState('Not Interested');
  const [finalOutcomeNotes, setFinalOutcomeNotes] = useState('');
  const [isSubmittingFinalOutcome, setIsSubmittingFinalOutcome] = useState(false);

  // Reassign Modal State
  const [reassignContact, setReassignContact] = useState<Contact | null>(null);
  const [reassignTargetUserId, setReassignTargetUserId] = useState('');
  const [reassignReason, setReassignReason] = useState('Manager portfolio redistribution');
  const [isReassigning, setIsReassigning] = useState(false);

  // Create Contact Modal
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newContact, setNewContact] = useState({
    first_name: '',
    last_name: '',
    email: '',
    phone: '',
    company_id: '',
    position: '',
    country: 'Saudi Arabia',
    industry: 'Financial Services',
    notes: '',
  });

  // Fetch Users for Filter and Reassignment
  useEffect(() => {
    const fetchUsers = async () => {
      try {
        const res = await api.get<any>('/users');
        setUsersList(res.data || []);
      } catch (e) {
        console.error('Failed to load users for filter', e);
      }
    };
    fetchUsers();
  }, []);

  const PER_PAGE = 100;
  const [isFetchingMore, setIsFetchingMore] = useState(false);
  const sentinelRef = useRef<HTMLDivElement>(null);
  const observerRef = useRef<IntersectionObserver | null>(null);
  // Track whether there are more pages to fetch
  const hasMoreRef = useRef(false);
  const currentPageRef = useRef(1);

  const buildParams = (targetPage: number): Record<string, any> => {
    const params: Record<string, any> = {
      page: targetPage,
      per_page: PER_PAGE,
      sort_by: sortBy,
      sort_dir: sortDir,
    };
    if (search) params.search = search;
    if (ownerFilter) params.owner_id = ownerFilter;
    if (outcomeFilter) params.last_outcome = outcomeFilter;
    if (countryFilter) params.country = countryFilter;
    if (industryFilter) params.industry = industryFilter;
    if (positionFilter) params.position = positionFilter;
    if (activeView === 'ARCHIVE') {
      params.include_archived = true;
      params.status = 'ARCHIVED';
    } else if (activeView === 'EMAIL_WHATSAPP') {
      params.status = 'EMAIL_AND_WHATSAPP';
    }
    return params;
  };

  // Initial / filter-change load — resets list
  const loadContacts = async (targetPage: number = 1) => {
    setIsLoading(true);
    currentPageRef.current = 1;
    hasMoreRef.current = false;
    try {
      const res = await api.get<any>('/contacts', buildParams(targetPage));
      const items = res.data || [];
      const metaTotal = res.meta?.total || 0;
      const metaPages = res.meta?.total_pages || 1;
      setContacts(items);
      setTotal(metaTotal);
      setTotalPages(metaPages);
      setPage(1);
      currentPageRef.current = 1;
      hasMoreRef.current = metaPages > 1;
    } catch (err) {
      console.error('Error fetching contacts', err);
    } finally {
      setIsLoading(false);
    }
  };

  // Append-load for subsequent pages (infinite scroll)
  const loadMoreContacts = async () => {
    if (isFetchingMore || !hasMoreRef.current) return;
    setIsFetchingMore(true);
    const nextPage = currentPageRef.current + 1;
    try {
      const res = await api.get<any>('/contacts', buildParams(nextPage));
      const items = res.data || [];
      const metaPages = res.meta?.total_pages || 1;
      setContacts((prev) => [...prev, ...items]);
      currentPageRef.current = nextPage;
      hasMoreRef.current = nextPage < metaPages;
    } catch (err) {
      console.error('Error fetching more contacts', err);
    } finally {
      setIsFetchingMore(false);
    }
  };

  // Reset and reload when filters / view change
  useEffect(() => {
    loadContacts(1);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeView, ownerFilter, outcomeFilter, countryFilter, industryFilter, positionFilter, sortBy, sortDir]);

  // Set up IntersectionObserver on the sentinel div
  useEffect(() => {
    if (observerRef.current) observerRef.current.disconnect();
    observerRef.current = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && hasMoreRef.current && !isFetchingMore) {
          loadMoreContacts();
        }
      },
      { rootMargin: '200px' }
    );
    if (sentinelRef.current) observerRef.current.observe(sentinelRef.current);
    return () => observerRef.current?.disconnect();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isFetchingMore, contacts.length]);

  const handleTabChange = (view: 'LEADS' | 'EMAIL_WHATSAPP' | 'ARCHIVE') => {
    setActiveView(view);
    const tabName = view === 'EMAIL_WHATSAPP' ? 'email_whatsapp' : view === 'ARCHIVE' ? 'archive' : 'leads';
    setSearchParams({ tab: tabName });
    setPage(1);
  };

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    loadContacts(1);
  };

  const updateContactInList = (updated: Contact) => {
    setContacts((prev) => prev.map((c) => (c.id === updated.id ? updated : c)));
  };

  // Open Recall Modal from Inline Selector
  const handleOpenRecallModal = (c: Contact) => {
    setRecallModalContact(c);
    setRecallNotes(c.notes || '');
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    setRecallDate(tomorrow.toISOString().split('T')[0]);
    setRecallTime('11:30');
  };

  // Submit Scheduled Recall
  const handleSaveRecallSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!recallModalContact) return;
    setIsSavingRecall(true);

    try {
      const scheduledDateTime = new Date(`${recallDate}T${recallTime}:00Z`).toISOString();
      const res = await api.post<any>(`/contacts/${recallModalContact.id}/quick-call`, {
        outcome: 'CALL_LATER',
        callback_requested_at: scheduledDateTime,
        notes: recallNotes.trim() || undefined,
      });

      if (res.data) {
        updateContactInList(res.data);
      }
      setRecallModalContact(null);
    } catch (err: any) {
      alert(err.message || 'Failed to schedule recall');
    } finally {
      setIsSavingRecall(false);
    }
  };

  // Submit Final Outcome (Moves lead to Archive)
  const handleSetFinalOutcomeSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!finalOutcomeContact) return;
    setIsSubmittingFinalOutcome(true);

    try {
      await api.post<any>(`/contacts/${finalOutcomeContact.id}/final-outcome`, {
        final_outcome: finalOutcomeChoice,
        notes: finalOutcomeNotes || undefined,
      });

      // Remove from active LEADS or EMAIL_WHATSAPP view
      if (activeView !== 'ARCHIVE') {
        setContacts((prev) => prev.filter((c) => c.id !== finalOutcomeContact.id));
        setTotal((prev) => Math.max(0, prev - 1));
      }
      setFinalOutcomeContact(null);
    } catch (err: any) {
      alert(err.message || 'Failed to record final outcome');
    } finally {
      setIsSubmittingFinalOutcome(false);
    }
  };

  // Restore Lead from Archive
  const handleUnarchiveRow = async (contact: Contact) => {
    try {
      await api.post(`/contacts/${contact.id}/unarchive`);
      setContacts((prev) => prev.filter((c) => c.id !== contact.id));
      setTotal((prev) => Math.max(0, prev - 1));
    } catch (err: any) {
      alert(err.message || 'Failed to restore contact');
    }
  };

  // Create Contact
  const handleCreateContact = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.post('/contacts', newContact);
      setShowCreateModal(false);
      setNewContact({
        first_name: '',
        last_name: '',
        email: '',
        phone: '',
        company_id: '',
        position: '',
        country: 'Saudi Arabia',
        industry: 'Financial Services',
        notes: '',
      });
      loadContacts(1);
    } catch (err: any) {
      alert(err.message || 'Failed to create contact');
    }
  };

  const resetAllFilters = () => {
    setSearch('');
    setOwnerFilter('');
    setOutcomeFilter('');
    setCountryFilter('');
    setIndustryFilter('');
    setPositionFilter('');
    setSortBy('sheet_order');
    setSortDir('asc');
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-5)' }}>
      {/* ── Page Header ─────────────────────────────────────────────────── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 'var(--space-4)' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
            <h1 className="font-display font-bold text-2xl" style={{ color: 'var(--neutral-900)' }}>
              {isRTL ? "جهات الاتصال وسير العمليات" : "Contacts & Calling Queue"}
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
              {total} {activeView === 'ARCHIVE' ? (isRTL ? 'في الأرشيف' : 'Archived') : (isRTL ? 'عميل نشط' : 'Leads')}
            </span>
          </div>
          <p className="text-sm text-muted" style={{ marginTop: '2px' }}>
            {isRTL
              ? "سير عمل المكالمات المباشر: نسخ الهاتف بنقرة واحدة، تسجيل المحاولات الخمس، وجدولة المتابعات."
              : "Live calling workstation: 1-click phone copy, fixed 5-attempt logging, and synchronized recall scheduling."}
          </p>
        </div>

        {/* Action Buttons */}
        <div style={{ display: 'flex', gap: 'var(--space-3)', alignItems: 'center', position: 'relative' }}>
          <button
            onClick={() => setShowColumnMenu(!showColumnMenu)}
            className="btn btn-secondary btn-sm"
            style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
          >
            <SlidersHorizontal size={14} />
            <span>{isRTL ? "تخصيص الأعمدة" : "Columns"}</span>
          </button>

          {showColumnMenu && (
            <div
              style={{
                position: 'absolute',
                top: '100%',
                right: isRTL ? 'auto' : 0,
                left: isRTL ? 0 : 'auto',
                marginTop: '6px',
                backgroundColor: 'var(--bg-surface)',
                border: '1px solid var(--border-color)',
                borderRadius: 'var(--radius-lg)',
                boxShadow: 'var(--shadow-lg)',
                padding: 'var(--space-3)',
                zIndex: 50,
                minWidth: '180px',
                display: 'flex',
                flexDirection: 'column',
                gap: '6px',
              }}
            >
              {Object.entries(visibleColumns).map(([key, isChecked]) => (
                <label key={key} style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '12px', cursor: 'pointer', color: 'var(--neutral-800)' }}>
                  <input
                    type="checkbox"
                    checked={isChecked as boolean}
                    onChange={() => toggleColumn(key as any)}
                  />
                  <span style={{ textTransform: 'capitalize' }}>{key.replace('_', ' ')}</span>
                </label>
              ))}
            </div>
          )}

          <button onClick={() => setShowCreateModal(true)} className="btn btn-accent btn-sm">
            <Plus size={16} />
            <span>{isRTL ? "إضافة جهة اتصال" : "Add Contact"}</span>
          </button>
        </div>
      </div>

      {/* ── 3 Main Workflow Views Tabs (NO SHEET CLUTTER) ─────────────────── */}
      <div
        style={{
          display: 'flex',
          gap: 'var(--space-2)',
          borderBottom: '1px solid var(--border-color)',
          paddingBottom: '6px',
        }}
      >
        <button
          onClick={() => handleTabChange('LEADS')}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '8px',
            padding: '8px 18px',
            borderRadius: 'var(--radius-md)',
            fontSize: '13px',
            fontWeight: activeView === 'LEADS' ? 700 : 500,
            color: activeView === 'LEADS' ? 'var(--color-primary)' : 'var(--neutral-600)',
            backgroundColor: activeView === 'LEADS' ? 'var(--color-primary-subtle)' : 'transparent',
            border: activeView === 'LEADS' ? '1px solid var(--color-primary)' : '1px solid transparent',
            cursor: 'pointer',
            transition: 'all 0.15s ease',
          }}
        >
          <PhoneCall size={15} style={{ opacity: activeView === 'LEADS' ? 1 : 0.6 }} />
          <span>{isRTL ? "العملاء المحتملين (LEADS)" : "LEADS"}</span>
        </button>

        <button
          onClick={() => handleTabChange('EMAIL_WHATSAPP')}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '8px',
            padding: '8px 18px',
            borderRadius: 'var(--radius-md)',
            fontSize: '13px',
            fontWeight: activeView === 'EMAIL_WHATSAPP' ? 700 : 500,
            color: activeView === 'EMAIL_WHATSAPP' ? '#0284c7' : 'var(--neutral-600)',
            backgroundColor: activeView === 'EMAIL_WHATSAPP' ? '#f0f9ff' : 'transparent',
            border: activeView === 'EMAIL_WHATSAPP' ? '1px solid #bae6fd' : '1px solid transparent',
            cursor: 'pointer',
            transition: 'all 0.15s ease',
          }}
        >
          <Mail size={15} style={{ opacity: activeView === 'EMAIL_WHATSAPP' ? 1 : 0.6 }} />
          <span>{isRTL ? "البريد والواتساب" : "EMAIL & WHATSAPP"}</span>
        </button>

        <button
          onClick={() => handleTabChange('ARCHIVE')}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '8px',
            padding: '8px 18px',
            borderRadius: 'var(--radius-md)',
            fontSize: '13px',
            fontWeight: activeView === 'ARCHIVE' ? 700 : 500,
            color: activeView === 'ARCHIVE' ? 'var(--color-warning)' : 'var(--neutral-600)',
            backgroundColor: activeView === 'ARCHIVE' ? 'var(--color-warning-bg)' : 'transparent',
            border: activeView === 'ARCHIVE' ? '1px solid var(--color-warning-border)' : '1px solid transparent',
            cursor: 'pointer',
            transition: 'all 0.15s ease',
          }}
        >
          <Archive size={15} style={{ opacity: activeView === 'ARCHIVE' ? 1 : 0.6 }} />
          <span>{isRTL ? "الأرشيف" : "ARCHIVE"}</span>
        </button>
      </div>

      {/* ── Search & Filter Bar ─────────────────────────────────────────── */}
      <div
        className="card"
        style={{
          padding: 'var(--space-3) var(--space-4)',
          display: 'flex',
          gap: 'var(--space-3)',
          flexWrap: 'wrap',
          alignItems: 'center',
        }}
      >
        {/* Search Box */}
        <form onSubmit={handleSearchSubmit} style={{ flex: '1 1 240px', minWidth: '220px' }}>
          <div style={{ position: 'relative' }}>
            <Search
              size={15}
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
              className="form-input text-xs"
              placeholder={isRTL ? "بحث بالاسم، البريد، الهاتف، الشركة..." : "Search name, company, phone, email..."}
              style={{ paddingLeft: isRTL ? '10px' : '32px', paddingRight: isRTL ? '32px' : '10px', height: '32px' }}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
        </form>

        {/* Sales Owner Filter */}
        <select
          className="form-select text-xs"
          style={{ width: '160px', height: '32px' }}
          value={ownerFilter}
          onChange={(e) => {
            setOwnerFilter(e.target.value);
            setPage(1);
          }}
        >
          <option value="">{isRTL ? "جميع الموظفين" : "All Sales Reps"}</option>
          <option value="unassigned">{isRTL ? "غير مخصص" : "Unassigned"}</option>
          {usersList.map((u) => (
            <option key={u.id} value={u.id}>
              👤 {u.first_name || u.full_name}
            </option>
          ))}
        </select>

        {/* Outcome Filter */}
        <select
          className="form-select text-xs"
          style={{ width: '150px', height: '32px' }}
          value={outcomeFilter}
          onChange={(e) => {
            setOutcomeFilter(e.target.value);
            setPage(1);
          }}
        >
          <option value="">{isRTL ? "جميع النتائج" : "All Call Outcomes"}</option>
          <option value="NO_ANSWER">📞 No Answer</option>
          <option value="INTERESTED">✨ Interested</option>
          <option value="EMAIL_REQUESTED">📧 Email Requested</option>
          <option value="WHATSAPP_REQUESTED">💬 WhatsApp Requested</option>
          <option value="DEMO_REQUESTED">🎯 Demo</option>
          <option value="CALL_LATER">⏰ Re Call</option>
          <option value="NOT_INTERESTED">🚫 Not Interested</option>
          <option value="WRONG_NUMBER">❌ Wrong Number</option>
        </select>

        {/* Clear Filters */}
        {(search || ownerFilter || outcomeFilter || countryFilter || industryFilter || positionFilter) && (
          <button
            onClick={resetAllFilters}
            className="btn btn-ghost btn-xs"
            style={{ color: 'var(--color-danger)', fontWeight: 600 }}
          >
            {isRTL ? "مسح التصفية" : "Clear Filters"}
          </button>
        )}
      </div>

      {/* ── Fixed 5-Attempt Contacts Table with Horizontal Scroll ─────────── */}
      {isLoading ? (
        <LoadingSpinner message={isRTL ? "جاري تحميل جهات الاتصال..." : "Loading contacts workstation..."} />
      ) : contacts.length === 0 ? (
        <EmptyState
          title={isRTL ? "لا توجد جهات اتصال مطابقة" : "No contacts found"}
          description={isRTL ? "جرب تعديل خيارات البحث أو التصفية." : "Try adjusting your search filters or add a new contact."}
          action={
            <button onClick={() => setShowCreateModal(true)} className="btn btn-accent btn-sm">
              {isRTL ? "إضافة جهة اتصال" : "Add Contact"}
            </button>
          }
        />
      ) : (
        <div
          className="table-container custom-scrollbar"
          style={{
            overflowX: 'auto',
            border: '1px solid var(--border-color)',
            borderRadius: 'var(--radius-lg)',
            backgroundColor: 'var(--bg-surface)',
            boxShadow: 'var(--shadow-sm)',
            maxWidth: '100%',
          }}
        >
          <table
            className="data-table"
            style={{
              width: '100%',
              minWidth: '1450px',
              borderCollapse: 'separate',
              borderSpacing: 0,
            }}
          >
            <thead>
              <tr>
                {/* 1. Sticky Contact Name */}
                <th
                  className="sticky-left"
                  style={{
                    position: 'sticky',
                    left: isRTL ? 'auto' : 0,
                    right: isRTL ? 0 : 'auto',
                    minWidth: '190px',
                    backgroundColor: 'var(--bg-surface-elevated)',
                    zIndex: 20,
                    boxShadow: isRTL ? '-2px 0 5px rgba(0,0,0,0.08)' : '2px 0 5px rgba(0,0,0,0.08)',
                  }}
                >
                  {isRTL ? "الاسم" : "Contact Name"}
                </th>

                {/* 2. Sticky Company */}
                <th
                  className="sticky-left-2"
                  style={{
                    position: 'sticky',
                    left: isRTL ? 'auto' : '190px',
                    right: isRTL ? '190px' : 'auto',
                    minWidth: '180px',
                    backgroundColor: 'var(--bg-surface-elevated)',
                    zIndex: 20,
                    boxShadow: isRTL ? '-2px 0 5px rgba(0,0,0,0.08)' : '2px 0 5px rgba(0,0,0,0.08)',
                  }}
                >
                  {isRTL ? "الشركة" : "Company"}
                </th>

                {/* 3. Position */}
                {visibleColumns.position && <th style={{ minWidth: '130px' }}>{isRTL ? "المنصب" : "Position"}</th>}

                {/* 4. Phone */}
                {visibleColumns.phone && <th style={{ minWidth: '150px' }}>{isRTL ? "الهاتف" : "Phone"}</th>}

                {/* 5. Email */}
                {visibleColumns.email && <th style={{ minWidth: '180px' }}>{isRTL ? "البريد" : "Email"}</th>}

                {/* 6. Sales Person */}
                {visibleColumns.owner && <th style={{ minWidth: '140px' }}>{isRTL ? "الموظف" : "Sales Rep"}</th>}

                {/* 7. FIXED FIVE ATTEMPT COLUMNS */}
                {visibleColumns.attempts && (
                  <>
                    <th style={{ minWidth: '140px', textAlign: 'center', borderLeft: '1px solid var(--border-color)', backgroundColor: 'var(--bg-surface-elevated)' }}>
                      1st Attempt
                    </th>
                    <th style={{ minWidth: '140px', textAlign: 'center', borderLeft: '1px solid var(--border-color)', backgroundColor: 'var(--bg-surface-elevated)' }}>
                      2nd Attempt
                    </th>
                    <th style={{ minWidth: '140px', textAlign: 'center', borderLeft: '1px solid var(--border-color)', backgroundColor: 'var(--bg-surface-elevated)' }}>
                      3rd Attempt
                    </th>
                    <th style={{ minWidth: '140px', textAlign: 'center', borderLeft: '1px solid var(--border-color)', backgroundColor: 'var(--bg-surface-elevated)' }}>
                      4th Attempt
                    </th>
                    <th style={{ minWidth: '140px', textAlign: 'center', borderLeft: '1px solid var(--border-color)', backgroundColor: 'var(--bg-surface-elevated)' }}>
                      5th Attempt
                    </th>
                  </>
                )}

                {/* 8. Dedicated Final Outcome */}
                {visibleColumns.final_outcome && (
                  <th
                    style={{
                      minWidth: '160px',
                      backgroundColor: 'var(--bg-surface-elevated)',
                      color: 'var(--neutral-900)',
                      fontWeight: 800,
                      borderLeft: '2px solid var(--border-color)',
                    }}
                  >
                    {isRTL ? "النتيجة النهائية" : "Final Outcome"}
                  </th>
                )}

                {/* 9. Notes */}
                {visibleColumns.notes && <th style={{ minWidth: '200px' }}>{isRTL ? "الملاحظات" : "Notes"}</th>}

                {/* 10. Actions / Restore */}
                <th style={{ minWidth: '110px', textAlign: 'center' }}>
                  {isRTL ? "الإجراءات" : "Actions"}
                </th>
              </tr>
            </thead>
            <tbody>
              {contacts.map((c) => {
                const contactAttempts = c.attempts || [];
                return (
                  <tr key={c.id}>
                    {/* 1. Sticky Name */}
                    <td
                      className="sticky-left"
                      style={{
                        position: 'sticky',
                        left: isRTL ? 'auto' : 0,
                        right: isRTL ? 0 : 'auto',
                        backgroundColor: 'var(--bg-surface)',
                        zIndex: 10,
                        boxShadow: isRTL ? '-2px 0 5px rgba(0,0,0,0.05)' : '2px 0 5px rgba(0,0,0,0.05)',
                      }}
                    >
                      <button
                        onClick={() => navigate(`/contacts/${c.id}`)}
                        className="font-semibold text-xs text-left"
                        style={{
                          color: 'var(--neutral-900)',
                          background: 'none',
                          border: 'none',
                          padding: 0,
                          cursor: 'pointer',
                          textDecoration: 'underline',
                          textUnderlineOffset: '2px',
                        }}
                      >
                        {c.full_name}
                      </button>
                      <div className="text-xs text-muted">{c.country || '—'}</div>
                    </td>

                    {/* 2. Sticky Company */}
                    <td
                      className="sticky-left-2"
                      style={{
                        position: 'sticky',
                        left: isRTL ? 'auto' : '190px',
                        right: isRTL ? '190px' : 'auto',
                        backgroundColor: 'var(--bg-surface)',
                        zIndex: 10,
                        boxShadow: isRTL ? '-2px 0 5px rgba(0,0,0,0.05)' : '2px 0 5px rgba(0,0,0,0.05)',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                        <span className="text-xs font-medium" style={{ color: 'var(--neutral-800)' }}>
                          {c.company_name || '—'}
                        </span>
                        {c.company_name && <CopyBtn text={c.company_name} label="Company" />}
                      </div>
                    </td>

                    {/* 3. Position */}
                    {visibleColumns.position && (
                      <td>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                          <span className="text-xs text-muted">{c.position || '—'}</span>
                          {c.position && <CopyBtn text={c.position} label="Position" />}
                        </div>
                      </td>
                    )}

                    {/* 4. Phone */}
                    {visibleColumns.phone && (
                      <td>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                          <span className="text-xs font-mono bidi-override" style={{ color: 'var(--neutral-800)' }}>
                            {c.phone || '—'}
                          </span>
                          {c.phone && <CopyBtn text={c.phone} label="Phone" />}
                        </div>
                      </td>
                    )}

                    {/* 5. Email */}
                    {visibleColumns.email && (
                      <td>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                          <span className="text-xs text-muted" style={{ maxWidth: '160px', overflow: 'hidden', textOverflow: 'ellipsis', display: 'inline-block' }}>
                            {c.email || '—'}
                          </span>
                          {c.email && <CopyBtn text={c.email} label="Email" />}
                        </div>
                      </td>
                    )}

                    {/* 6. Sales Rep */}
                    {visibleColumns.owner && (
                      <td>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                          <span className="badge badge-secondary text-xs font-semibold">
                            {c.owner_name || (isRTL ? "غير مخصص" : "Unassigned")}
                          </span>
                          {user?.role === 'MANAGER' && (
                            <button
                              onClick={() => {
                                setReassignContact(c);
                                setReassignTargetUserId(c.owner_id || '');
                              }}
                              className="btn btn-ghost btn-xs"
                              title="Reassign lead"
                            >
                              <UserCheck size={12} style={{ color: 'var(--neutral-400)' }} />
                            </button>
                          )}
                        </div>
                      </td>
                    )}

                    {/* 7. FIXED 5 ATTEMPT CELLS */}
                    {visibleColumns.attempts &&
                      [0, 1, 2, 3, 4].map((attIdx) => {
                        const att = contactAttempts[attIdx];
                        const isNextSlot = attIdx === contactAttempts.length && activeView !== 'ARCHIVE';

                        return (
                          <td
                            key={`td-attempt-${c.id}-${attIdx}`}
                            style={{
                              textAlign: 'center',
                              borderLeft: '1px solid var(--border-light)',
                              padding: '5px 6px',
                            }}
                          >
                            {att ? (
                              <AttemptOutcomeBadge
                                outcome={att.outcome}
                                notes={att.notes}
                                calledAt={att.called_at}
                              />
                            ) : isNextSlot ? (
                              <InlineNextAttemptSelector
                                contact={c}
                                attemptNumber={attIdx + 1}
                                onAttemptLogged={updateContactInList}
                                onRequestRecallModal={handleOpenRecallModal}
                              />
                            ) : (
                              <span style={{ color: 'var(--neutral-300)', fontSize: '13px' }}>—</span>
                            )}
                          </td>
                        );
                      })}

                    {/* 8. Dedicated Final Outcome Column */}
                    {visibleColumns.final_outcome && (
                      <td style={{ borderLeft: '2px solid var(--border-color)', padding: '5px 8px' }}>
                        {c.final_outcome ? (
                          <span
                            className="badge text-xs"
                            style={{
                              backgroundColor: '#fef3c7',
                              color: '#92400e',
                              border: '1px solid #f59e0b',
                              fontWeight: 700,
                              padding: '2px 6px',
                              borderRadius: '4px',
                            }}
                          >
                            {c.final_outcome}
                          </span>
                        ) : activeView !== 'ARCHIVE' ? (
                          <button
                            onClick={() => {
                              setFinalOutcomeContact(c);
                              setFinalOutcomeChoice('Not Interested');
                              setFinalOutcomeNotes('');
                            }}
                            className="btn btn-ghost btn-xs"
                            style={{
                              fontSize: '11px',
                              color: 'var(--color-primary)',
                              fontWeight: 600,
                              padding: '2px 6px',
                              border: '1px dashed var(--color-primary-light, #cbd5e1)',
                              borderRadius: '4px',
                            }}
                            title="Set terminal outcome and move to archive"
                          >
                            + Set Final
                          </button>
                        ) : (
                          <span style={{ color: 'var(--neutral-400)', fontSize: '12px' }}>—</span>
                        )}
                      </td>
                    )}

                    {/* 9. Inline Notes Cell */}
                    {visibleColumns.notes && (
                      <td>
                        <InlineNoteCell
                          contact={c}
                          onNoteUpdated={(contactId, noteText) => {
                            setContacts((prev) =>
                              prev.map((item) => (item.id === contactId ? { ...item, notes: noteText } : item))
                            );
                          }}
                        />
                      </td>
                    )}

                    {/* 10. Actions / Restore */}
                    <td style={{ textAlign: 'center' }}>
                      {activeView === 'ARCHIVE' ? (
                        <button
                          onClick={() => handleUnarchiveRow(c)}
                          className="btn btn-secondary btn-xs"
                          style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '4px',
                            fontSize: '11px',
                            borderColor: '#f59e0b',
                            color: '#92400e',
                            fontWeight: 700,
                          }}
                          title="Restore to Active Leads"
                        >
                          <ArchiveRestore size={12} />
                          <span>{isRTL ? "استعادة" : "Restore"}</span>
                        </button>
                      ) : (
                        <button
                          onClick={() => navigate(`/contacts/${c.id}`)}
                          className="btn btn-ghost btn-xs text-muted"
                        >
                          {isRTL ? "التفاصيل" : "Details"}
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {/* Infinite scroll sentinel — triggers next page when visible */}
          <div ref={sentinelRef} style={{ height: '1px' }} />
          {isFetchingMore && (
            <div style={{ textAlign: 'center', padding: '12px', color: 'var(--neutral-400)', fontSize: '12px' }}>
              Loading more contacts…
            </div>
          )}
          {!hasMoreRef.current && contacts.length > 0 && total > PER_PAGE && (
            <div style={{ textAlign: 'center', padding: '8px 0', color: 'var(--neutral-500)', fontSize: '11px', opacity: 0.7 }}>
              All {total} contacts loaded
            </div>
          )}
        </div>
      )}

      {/* ── Scheduled Recall Modal ───────────────────────────────────────── */}
      {recallModalContact && (
        <Modal
          isOpen={!!recallModalContact}
          onClose={() => setRecallModalContact(null)}
          title={isRTL ? `جدولة إعادة الاتصال — ${recallModalContact.full_name}` : `Schedule Callback — ${recallModalContact.full_name}`}
        >
          <form onSubmit={handleSaveRecallSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
            <div
              style={{
                padding: 'var(--space-3)',
                backgroundColor: 'var(--bg-app)',
                borderRadius: 'var(--radius-md)',
                fontSize: '12px',
              }}
            >
              <div><strong>Company:</strong> {recallModalContact.company_name || '—'}</div>
              <div><strong>Phone:</strong> <span className="font-mono">{recallModalContact.phone || '—'}</span></div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-3)' }}>
              <div>
                <label className="form-label text-xs">{isRTL ? "تاريخ الاتصال" : "Callback Date"}</label>
                <input
                  type="date"
                  required
                  className="form-input text-xs"
                  value={recallDate}
                  onChange={(e) => setRecallDate(e.target.value)}
                />
              </div>

              <div>
                <label className="form-label text-xs">{isRTL ? "وقت الاتصال" : "Callback Time"}</label>
                <input
                  type="time"
                  required
                  className="form-input text-xs"
                  value={recallTime}
                  onChange={(e) => setRecallTime(e.target.value)}
                />
              </div>
            </div>

            <div>
              <label className="form-label text-xs">{isRTL ? "ملاحظات طلب العميل" : "Customer Request Notes"}</label>
              <textarea
                className="form-input text-xs"
                rows={3}
                placeholder={isRTL ? "مثال: طلب العميل الاتصال بعد اجتماع الإدارة..." : "e.g., Customer requested call after management meeting..."}
                value={recallNotes}
                onChange={(e) => setRecallNotes(e.target.value)}
              />
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 'var(--space-2)' }}>
              <button type="button" onClick={() => setRecallModalContact(null)} className="btn btn-secondary btn-sm">
                {isRTL ? "إلغاء" : "Cancel"}
              </button>
              <button type="submit" disabled={isSavingRecall} className="btn btn-accent btn-sm">
                <Clock size={14} />
                <span>{isSavingRecall ? (isRTL ? "جاري الحفظ..." : "Saving...") : (isRTL ? "حفظ وجدولة" : "Save Recall")}</span>
              </button>
            </div>
          </form>
        </Modal>
      )}

      {/* ── Final Outcome Modal ──────────────────────────────────────────── */}
      {finalOutcomeContact && (
        <Modal
          isOpen={!!finalOutcomeContact}
          onClose={() => setFinalOutcomeContact(null)}
          title={isRTL ? `تسجيل النتيجة النهائية والأرشفة — ${finalOutcomeContact.full_name}` : `Set Final Outcome & Archive — ${finalOutcomeContact.full_name}`}
        >
          <form onSubmit={handleSetFinalOutcomeSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
            <p className="text-xs text-muted" style={{ margin: 0 }}>
              {isRTL
                ? "اختيار النتيجة النهائية ينقل جهة الاتصال مباشرة من قائمة العملاء النشطين إلى الأرشيف، مع الاحتفاظ بجميع المحاولات والملاحظات وسجل النشاط."
                : "Setting a Final Outcome permanently completes this workflow and moves the contact to Archive while preserving all 5 attempts, notes, and timeline."}
            </p>

            <div>
              <label className="form-label text-xs">{isRTL ? "النتيجة النهائية" : "Terminal Final Outcome"}</label>
              <select
                className="form-select text-xs"
                value={finalOutcomeChoice}
                onChange={(e) => setFinalOutcomeChoice(e.target.value)}
              >
                <option value="No Answer">📞 No Answer (Max Attempts)</option>
                <option value="Not Interested">🚫 Not Interested</option>
                <option value="Wrong Number">❌ Wrong Number</option>
                <option value="Voice Mail / Don't Call Again">⛔ Voice Mail / Don't Call Again</option>
                <option value="HQ">🏢 HQ / Switchboard</option>
              </select>
            </div>

            <div>
              <label className="form-label text-xs">{isRTL ? "ملاحظة نهائية (اختياري)" : "Final Closing Notes"}</label>
              <textarea
                className="form-input text-xs"
                rows={2}
                placeholder={isRTL ? "سبب إنهاء التواصل..." : "Closing reason / final notes..."}
                value={finalOutcomeNotes}
                onChange={(e) => setFinalOutcomeNotes(e.target.value)}
              />
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 'var(--space-2)' }}>
              <button type="button" onClick={() => setFinalOutcomeContact(null)} className="btn btn-secondary btn-sm">
                {isRTL ? "إلغاء" : "Cancel"}
              </button>
              <button type="submit" disabled={isSubmittingFinalOutcome} className="btn btn-danger btn-sm">
                <Archive size={14} />
                <span>{isSubmittingFinalOutcome ? (isRTL ? "جاري الأرشفة..." : "Archiving...") : (isRTL ? "تأكيد والأرشفة" : "Confirm & Archive")}</span>
              </button>
            </div>
          </form>
        </Modal>
      )}

      {/* ── Create Contact Modal ─────────────────────────────────────────── */}
      {showCreateModal && (
        <Modal
          isOpen={showCreateModal}
          onClose={() => setShowCreateModal(false)}
          title={isRTL ? "إضافة جهة اتصال جديدة" : "Add New Contact"}
        >
          <form onSubmit={handleCreateContact} style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-3)' }}>
              <div>
                <label className="form-label text-xs">{isRTL ? "الاسم الأول" : "First Name"}</label>
                <input
                  type="text"
                  required
                  className="form-input text-xs"
                  value={newContact.first_name}
                  onChange={(e) => setNewContact({ ...newContact, first_name: e.target.value })}
                />
              </div>
              <div>
                <label className="form-label text-xs">{isRTL ? "اسم العائلة" : "Last Name"}</label>
                <input
                  type="text"
                  className="form-input text-xs"
                  value={newContact.last_name}
                  onChange={(e) => setNewContact({ ...newContact, last_name: e.target.value })}
                />
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-3)' }}>
              <div>
                <label className="form-label text-xs">{isRTL ? "رقم الهاتف" : "Phone"}</label>
                <input
                  type="text"
                  required
                  className="form-input text-xs font-mono"
                  placeholder="+966..."
                  value={newContact.phone}
                  onChange={(e) => setNewContact({ ...newContact, phone: e.target.value })}
                />
              </div>
              <div>
                <label className="form-label text-xs">{isRTL ? "البريد الإلكتروني" : "Email"}</label>
                <input
                  type="email"
                  className="form-input text-xs"
                  placeholder="contact@company.com"
                  value={newContact.email}
                  onChange={(e) => setNewContact({ ...newContact, email: e.target.value })}
                />
              </div>
            </div>

            <div>
              <label className="form-label text-xs">{isRTL ? "المنصب" : "Position"}</label>
              <input
                type="text"
                className="form-input text-xs"
                placeholder="e.g. IT Manager, CFO"
                value={newContact.position}
                onChange={(e) => setNewContact({ ...newContact, position: e.target.value })}
              />
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 'var(--space-2)', marginTop: 'var(--space-2)' }}>
              <button type="button" onClick={() => setShowCreateModal(false)} className="btn btn-secondary btn-sm">
                {isRTL ? "إلغاء" : "Cancel"}
              </button>
              <button type="submit" className="btn btn-accent btn-sm">
                {isRTL ? "إضافة" : "Create Contact"}
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
};
