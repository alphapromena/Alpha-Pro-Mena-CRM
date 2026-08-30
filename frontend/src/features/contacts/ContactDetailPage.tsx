import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { api } from '../../lib/apiClient';
import { Contact, TimelineItem, ContactStatus } from '../../types';
import { Badge } from '../../components/ui/Badge';
import { Modal } from '../../components/ui/Modal';
import { LoadingSpinner } from '../../components/feedback/LoadingSpinner';
import {
  PhoneCall,
  Mail,
  MessageSquare,
  FileText,
  Clock,
  CheckCircle2,
  Calendar,
  AlertTriangle,
  Building,
  ShieldAlert,
  ArrowLeft,
  User,
  Plus,
  Archive,
  ArchiveRestore,
  Tag,
} from 'lucide-react';

export const ContactDetailPage: React.FC = () => {
  const { contactId } = useParams<{ contactId: string }>();
  const navigate = useNavigate();

  const [contact, setContact] = useState<Contact | null>(null);
  const [timeline, setTimeline] = useState<TimelineItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  // Call Modal
  const [showCallModal, setShowCallModal] = useState(false);
  const [callOutcome, setCallOutcome] = useState('ANSWERED');
  const [callNotes, setCallNotes] = useState('');
  const [callDuration, setCallDuration] = useState('60');
  const [callbackTime, setCallbackTime] = useState('');
  const [isLoggingCall, setIsLoggingCall] = useState(false);

  // Status Change
  const [newStatus, setNewStatus] = useState<string>('');

  // Note Modal
  const [showNoteModal, setShowNoteModal] = useState(false);
  const [noteContent, setNoteContent] = useState('');
  const [isAddingNote, setIsAddingNote] = useState(false);

  // Final Outcome Modal
  const [showFinalOutcomeModal, setShowFinalOutcomeModal] = useState(false);
  const [finalOutcomeChoice, setFinalOutcomeChoice] = useState('Not Interested');
  const [finalOutcomeNotes, setFinalOutcomeNotes] = useState('');
  const [isSubmittingFinalOutcome, setIsSubmittingFinalOutcome] = useState(false);

  // Helper for attempt ordinal (1st, 2nd, 3rd, 4th, 5th, ...)
  const formatAttemptOrdinal = (n: number) => {
    const s = ['th', 'st', 'nd', 'rd'];
    const v = n % 100;
    return n + (s[(v - 20) % 10] || s[v] || s[0]) + ' Attempt';
  };

  const loadContact = async () => {
    if (!contactId) return;
    setIsLoading(true);
    try {
      const [cRes, tRes] = await Promise.all([
        api.get<any>(`/contacts/${contactId}`),
        api.get<any>(`/contacts/${contactId}/timeline`),
      ]);
      setContact(cRes.data);
      setNewStatus(cRes.data.status);
      setTimeline(tRes.data || []);
    } catch (e) {
      console.error('Failed to load contact', e);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadContact();
  }, [contactId]);

  const handleLogCall = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!contact) return;
    setIsLoggingCall(true);
    try {
      await api.post('/calls', {
        contact_id: contact.id,
        outcome: callOutcome,
        notes: callNotes,
        duration_seconds: parseInt(callDuration) || 0,
        callback_requested_at: callbackTime ? new Date(callbackTime).toISOString() : undefined,
      });
      setShowCallModal(false);
      setCallNotes('');
      setCallbackTime('');
      await loadContact();
    } catch (err: any) {
      alert(err.message || 'Failed to log call');
    } finally {
      setIsLoggingCall(false);
    }
  };

  const handleSetFinalOutcome = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!contact) return;
    const confirmed = window.confirm(
      'This will mark the contact as complete and move it to Archive. Continue?'
    );
    if (!confirmed) return;

    setIsSubmittingFinalOutcome(true);
    try {
      await api.post(`/contacts/${contact.id}/final-outcome`, {
        final_outcome: finalOutcomeChoice,
        notes: finalOutcomeNotes.trim() || undefined,
      });
      setShowFinalOutcomeModal(false);
      setFinalOutcomeNotes('');
      await loadContact();
    } catch (err: any) {
      alert(err.message || 'Failed to set final outcome');
    } finally {
      setIsSubmittingFinalOutcome(false);
    }
  };

  const handleStatusChange = async (status: string) => {
    if (!contact) return;
    try {
      await api.patch(`/contacts/${contact.id}/status`, { status });
      await loadContact();
    } catch (err: any) {
      alert(err.message || 'Status transition not allowed');
    }
  };

  const handleSetDnc = async () => {
    if (!contact) return;
    const confirm = window.confirm(
      'Are you sure you want to mark this contact as DO NOT CONTACT? All future automated sales outreach will be permanently blocked.'
    );
    if (!confirm) return;

    try {
      await api.post(`/contacts/${contact.id}/dnc`);
      await loadContact();
    } catch (err: any) {
      alert(err.message || 'Failed to set DNC');
    }
  };

  const handleAddNote = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!contact || !noteContent.trim()) return;
    setIsAddingNote(true);
    try {
      await api.post(`/contacts/${contact.id}/notes`, {
        note_text: noteContent.trim(),
      });
      setShowNoteModal(false);
      setNoteContent('');
      await loadContact();
    } catch (err: any) {
      alert(err.message || 'Failed to add note');
    } finally {
      setIsAddingNote(false);
    }
  };

  const handleArchive = async () => {
    if (!contact) return;
    setShowFinalOutcomeModal(true);
  };

  const handleUnarchive = async () => {
    if (!contact) return;
    const confirmed = window.confirm(
      `Restore "${contact.full_name}" to Active Contacts?`
    );
    if (!confirmed) return;
    try {
      await api.post(`/contacts/${contact.id}/unarchive`);
      await loadContact();
    } catch (err: any) {
      alert(err.message || 'Failed to restore contact');
    }
  };

  if (isLoading) return <LoadingSpinner message="Loading contact profile & activity timeline..." />;
  if (!contact) return <div>Contact not found.</div>;

  const totalCalls = timeline.filter((t) => t.type === 'call').length;
  const answeredCalls = timeline.filter((t) => t.type === 'call' && t.outcome !== 'NO_ANSWER' && t.outcome !== 'BUSY').length;
  const noAnswers = timeline.filter((t) => t.type === 'call' && t.outcome === 'NO_ANSWER').length;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-6)' }}>
      {/* Archived State Banner with Final Outcome & Restore */}
      {(contact.status === 'ARCHIVED' || contact.archived_at) && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: 'var(--space-3) var(--space-5)',
            backgroundColor: '#fef3c7',
            border: '1px solid #f59e0b',
            borderRadius: 'var(--radius-md)',
            gap: 'var(--space-3)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
            <Archive size={18} style={{ color: '#d97706' }} />
            <div>
              <div style={{ fontSize: '13px', fontWeight: 700, color: '#92400e' }}>
                Contact is in Archive • Final Outcome: <span style={{ textDecoration: 'underline' }}>{contact.final_outcome || 'Completed'}</span>
              </div>
              <div style={{ fontSize: '11px', color: '#b45309' }}>
                {contact.archived_at ? `Archived on ${new Date(contact.archived_at).toLocaleDateString()}` : ''}
                {contact.archived_by_name ? ` by ${contact.archived_by_name}` : ''} • All history and attempt records are permanently preserved.
              </div>
            </div>
          </div>
          <button
            onClick={handleUnarchive}
            className="btn btn-secondary btn-sm"
            style={{ display: 'flex', alignItems: 'center', gap: '4px', backgroundColor: '#fff', borderColor: '#f59e0b', color: '#92400e', fontWeight: 700 }}
          >
            <ArchiveRestore size={14} />
            Restore to Active Contacts
          </button>
        </div>
      )}

      {/* Top Breadcrumb & Action Bar */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <button
          onClick={() => navigate('/contacts')}
          className="btn btn-secondary btn-sm"
          style={{ display: 'flex', alignItems: 'center', gap: '4px' }}
        >
          <ArrowLeft size={16} />
          <span>Back to Contacts</span>
        </button>

        <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
          {!contact.is_dnc && contact.status !== 'ARCHIVED' && !contact.archived_at && (
            <>
              <button
                onClick={() => setShowCallModal(true)}
                className="btn btn-accent btn-md"
              >
                <PhoneCall size={16} />
                <span>Log Call Attempt</span>
              </button>
              <button
                onClick={() => setShowNoteModal(true)}
                className="btn btn-secondary btn-md"
              >
                <Plus size={16} />
                <span>Add Note</span>
              </button>
              <button
                onClick={() => setShowFinalOutcomeModal(true)}
                className="btn btn-secondary btn-md"
                style={{ borderColor: 'var(--color-primary)', color: 'var(--color-primary)', fontWeight: 700 }}
              >
                <CheckCircle2 size={16} />
                <span>Set Final Outcome</span>
              </button>
            </>
          )}
          {!contact.is_dnc ? (
            <button onClick={handleSetDnc} className="btn btn-danger btn-sm">
              <ShieldAlert size={15} />
              <span>Mark DNC</span>
            </button>
          ) : (
            <span className="badge badge-dnc" style={{ padding: '6px 12px', fontSize: '12px' }}>
              ⚠️ DO NOT CONTACT ACTIVE
            </span>
          )}
          {/* Archive / Restore Button */}
          {contact.status !== 'ARCHIVED' && !contact.archived_at ? (
            <button onClick={handleArchive} className="btn btn-secondary btn-sm" style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
              <Archive size={14} />
              Archive
            </button>
          ) : (
            <button onClick={handleUnarchive} className="btn btn-secondary btn-sm" style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
              <ArchiveRestore size={14} />
              Restore
            </button>
          )}
        </div>
      </div>

      {/* Main Grid: Left Profile Card, Right Chronological Timeline */}
      <div style={{ display: 'grid', gridTemplateColumns: '360px 1fr', gap: 'var(--space-6)' }}>
        {/* Left: Contact Profile & Stats */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
          <div className="card">
            {/* Header / Avatar */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)', marginBottom: 'var(--space-4)' }}>
              <div
                style={{
                  width: '48px',
                  height: '48px',
                  borderRadius: 'var(--radius-full)',
                  backgroundColor: 'var(--color-primary-subtle)',
                  color: 'var(--color-primary)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: 'var(--text-lg)',
                  fontWeight: 700,
                }}
              >
                {contact.first_name?.[0]}
                {contact.last_name?.[0]}
              </div>
              <div>
                <h2 className="font-display font-bold text-xl" style={{ color: 'var(--neutral-900)' }}>
                  {contact.full_name}
                </h2>
                <div className="text-xs text-muted">{contact.position || 'No Title'}</div>
              </div>
            </div>

            {/* PROMINENT OUTCOME BADGE — clearly distinct from attempt history below */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: 'var(--space-3) var(--space-4)',
                marginBottom: 'var(--space-3)',
                backgroundColor: contact.last_outcome
                  ? 'var(--color-accent-light)'
                  : 'var(--bg-subtle)',
                border: `1px solid ${contact.last_outcome ? 'var(--color-accent)' : 'var(--border-light)'}`,
                borderRadius: 'var(--radius-lg)',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                <Tag size={13} style={{ color: contact.last_outcome ? 'var(--color-accent)' : 'var(--neutral-400)' }} />
                <span
                  style={{
                    fontSize: '10px',
                    fontWeight: 800,
                    textTransform: 'uppercase',
                    letterSpacing: '0.08em',
                    color: 'var(--neutral-500)',
                  }}
                >
                  Last Outcome
                </span>
              </div>
              <span
                style={{
                  fontSize: '12px',
                  fontWeight: 700,
                  color: contact.last_outcome ? 'var(--color-accent)' : 'var(--neutral-400)',
                  fontStyle: contact.last_outcome ? 'normal' : 'italic',
                }}
              >
                {contact.last_outcome
                  ? contact.last_outcome.replace(/_/g, ' ')
                  : 'No outcome logged yet'}
              </span>
            </div>

            {/* Status Selector */}
            <div style={{ marginBottom: 'var(--space-4)' }}>
              <label className="form-label" style={{ fontSize: '11px', textTransform: 'uppercase', color: 'var(--neutral-500)' }}>
                Current Lead Lifecycle Stage
              </label>
              <select
                className="form-select"
                disabled={contact.is_dnc}
                value={newStatus}
                onChange={(e) => {
                  setNewStatus(e.target.value);
                  handleStatusChange(e.target.value);
                }}
              >
                <option value="NEW">New</option>
                <option value="CONTACTED">Contacted</option>
                <option value="IN_PROGRESS">In Progress</option>
                <option value="INTERESTED">Interested</option>
                <option value="EMAIL_REQUESTED">Email Requested</option>
                <option value="WHATSAPP_REQUESTED">WhatsApp Requested</option>
                <option value="DEMO_SCHEDULED">Demo Scheduled</option>
                <option value="PROPOSAL_SENT">Proposal Sent</option>
                <option value="WON">Won</option>
                <option value="LOST">Lost</option>
                <option value="NO_ANSWER">No Answer</option>
                <option value="RECALL_SCHEDULED">Recall Scheduled</option>
              </select>
            </div>

            {/* Info Fields */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)', fontSize: 'var(--text-sm)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span className="text-muted">Company</span>
                <span className="font-medium">{contact.company_name || '—'}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span className="text-muted">Phone</span>
                <span className="font-medium" style={{ color: 'var(--color-accent)' }}>
                  {contact.phone || '—'}
                </span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span className="text-muted">Email</span>
                <span className="font-medium">{contact.email || '—'}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span className="text-muted">Country</span>
                <span className="font-medium">{contact.country || '—'}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span className="text-muted">Industry</span>
                <span className="font-medium">{contact.industry || '—'}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span className="text-muted">Lead Owner</span>
                <span className="font-medium" style={{ color: 'var(--neutral-800)' }}>
                  {contact.owner_name || 'Unassigned'}
                </span>
              </div>
            </div>
          </div>

          {/* Interaction Statistics Card */}
          <div className="card">
            <h4 className="card-title text-sm font-semibold" style={{ marginBottom: 'var(--space-3)' }}>
              Outreach Statistics
            </h4>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 'var(--space-2)', textAlign: 'center' }}>
              <div style={{ padding: 'var(--space-2)', backgroundColor: 'var(--neutral-50)', borderRadius: 'var(--radius-md)' }}>
                <div className="font-bold text-lg text-dark">{contact.attempt_count || totalCalls}</div>
                <div className="text-xs text-muted">Attempts</div>
              </div>
              <div style={{ padding: 'var(--space-2)', backgroundColor: 'var(--status-interested-bg)', borderRadius: 'var(--radius-md)' }}>
                <div className="font-bold text-lg" style={{ color: 'var(--status-interested-text)' }}>
                  {answeredCalls}
                </div>
                <div className="text-xs text-muted">Answered</div>
              </div>
              <div style={{ padding: 'var(--space-2)', backgroundColor: 'var(--status-noanswer-bg)', borderRadius: 'var(--radius-md)' }}>
                <div className="font-bold text-lg" style={{ color: 'var(--status-noanswer-text)' }}>
                  {noAnswers}
                </div>
                <div className="text-xs text-muted">No Answer</div>
              </div>
            </div>
          </div>

          {/* Attempt History Grid — unlimited attempts tracked in timeline */}
          <div className="card" style={{ borderLeft: '3px solid var(--color-accent)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-3)' }}>
              <h4 className="card-title text-sm font-semibold" style={{ margin: 0 }}>
                Attempt History
              </h4>
              <span className="badge badge-accent text-xs">
                {totalCalls} Call{totalCalls !== 1 ? 's' : ''} Logged
              </span>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
              {/* Dynamic Call Attempts List — Unlimited Attempts */}
              {timeline.filter((t) => t.type === 'call').length > 0 ? (
                timeline
                  .filter((t) => t.type === 'call')
                  .map((c, i) => (
                    <div
                      key={c.id || i}
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        padding: 'var(--space-2) var(--space-3)',
                        backgroundColor: 'var(--bg-subtle)',
                        borderRadius: 'var(--radius-md)',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span
                          style={{
                            width: '20px',
                            height: '20px',
                            borderRadius: '50%',
                            backgroundColor: 'var(--color-primary-subtle)',
                            color: 'var(--color-primary)',
                            display: 'inline-flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            fontSize: '11px',
                            fontWeight: 700,
                          }}
                        >
                          {i + 1}
                        </span>
                        <span className="text-xs font-semibold">{formatAttemptOrdinal(i + 1)}</span>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <span className="badge text-xs" style={{ backgroundColor: 'var(--neutral-200)', color: 'var(--neutral-900)', fontWeight: 600 }}>
                          {c.outcome ? c.outcome.replace(/_/g, ' ') : 'Called'}
                        </span>
                        <span className="text-xs text-muted">
                          {c.timestamp ? new Date(c.timestamp).toLocaleDateString() : ''}
                        </span>
                      </div>
                    </div>
                  ))
              ) : (
                <>
                  {/* Fallback to imported attempt 1, 2, 3 if no calls logged yet */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: 'var(--space-2) var(--space-3)', backgroundColor: 'var(--bg-subtle)', borderRadius: 'var(--radius-md)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span style={{ width: '20px', height: '20px', borderRadius: '50%', backgroundColor: 'var(--color-primary-subtle)', color: 'var(--color-primary)', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', fontSize: '11px', fontWeight: 700 }}>1</span>
                      <span className="text-xs font-semibold">1st Attempt</span>
                    </div>
                    <span className="badge text-xs" style={{ backgroundColor: contact.attempt_1 ? 'var(--neutral-200)' : 'transparent', color: contact.attempt_1 ? 'var(--neutral-900)' : 'var(--neutral-400)' }}>
                      {contact.attempt_1 || 'Not contacted'}
                    </span>
                  </div>

                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: 'var(--space-2) var(--space-3)', backgroundColor: 'var(--bg-subtle)', borderRadius: 'var(--radius-md)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span style={{ width: '20px', height: '20px', borderRadius: '50%', backgroundColor: 'var(--color-primary-subtle)', color: 'var(--color-primary)', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', fontSize: '11px', fontWeight: 700 }}>2</span>
                      <span className="text-xs font-semibold">2nd Attempt</span>
                    </div>
                    <span className="badge text-xs" style={{ backgroundColor: contact.attempt_2 ? 'var(--neutral-200)' : 'transparent', color: contact.attempt_2 ? 'var(--neutral-900)' : 'var(--neutral-400)' }}>
                      {contact.attempt_2 || 'Pending'}
                    </span>
                  </div>

                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: 'var(--space-2) var(--space-3)', backgroundColor: 'var(--bg-subtle)', borderRadius: 'var(--radius-md)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span style={{ width: '20px', height: '20px', borderRadius: '50%', backgroundColor: 'var(--color-primary-subtle)', color: 'var(--color-primary)', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', fontSize: '11px', fontWeight: 700 }}>3</span>
                      <span className="text-xs font-semibold">3rd Attempt</span>
                    </div>
                    <span className="badge text-xs" style={{ backgroundColor: contact.attempt_3 ? 'var(--neutral-200)' : 'transparent', color: contact.attempt_3 ? 'var(--neutral-900)' : 'var(--neutral-400)' }}>
                      {contact.attempt_3 || 'Pending'}
                    </span>
                  </div>
                </>
              )}
            </div>

            {/* Quick Next Attempt Action */}
            <div style={{ marginTop: 'var(--space-4)', paddingTop: 'var(--space-3)', borderTop: '1px solid var(--border-light)' }}>
              <button
                type="button"
                onClick={() => setShowCallModal(true)}
                className="btn btn-accent btn-sm"
                style={{ width: '100%', justifyContent: 'center' }}
              >
                <PhoneCall size={14} />
                <span>Log Next Contact Attempt</span>
              </button>
            </div>
          </div>
        </div>

        {/* Right: Unified Chronological Activity Timeline */}
        <div className="card">
          <div className="card-header">
            <h3 className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
              <Clock size={18} style={{ color: 'var(--color-accent)' }} />
              <span>Unified Activity Timeline ({timeline.length})</span>
            </h3>
          </div>

          {timeline.length === 0 ? (
            <div style={{ padding: 'var(--space-10) 0', textAlign: 'center', color: 'var(--neutral-400)' }}>
              No recorded interactions yet. Use the "Log Call Attempt" button to start the conversation history.
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)', position: 'relative' }}>
              {timeline.map((item, idx) => (
                <div
                  key={idx}
                  style={{
                    display: 'flex',
                    gap: 'var(--space-4)',
                    paddingBottom: 'var(--space-4)',
                    borderBottom: idx < timeline.length - 1 ? '1px solid var(--border-light)' : 'none',
                  }}
                >
                  {/* Icon Indicator */}
                  <div
                    style={{
                      width: '36px',
                      height: '36px',
                      borderRadius: 'var(--radius-full)',
                      backgroundColor:
                        item.type === 'call'
                          ? 'var(--color-primary-subtle)'
                          : item.type === 'status_change'
                          ? 'var(--neutral-100)'
                          : 'var(--color-success-bg)',
                      color:
                        item.type === 'call'
                          ? 'var(--color-accent)'
                          : item.type === 'status_change'
                          ? 'var(--neutral-700)'
                          : 'var(--color-success)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      flexShrink: 0,
                    }}
                  >
                    {item.type === 'call' && <PhoneCall size={16} />}
                    {item.type === 'note' && <FileText size={16} />}
                    {item.type === 'task' && <CheckCircle2 size={16} />}
                    {item.type === 'status_change' && <Clock size={16} />}
                  </div>

                  {/* Content */}
                  <div style={{ flex: 1 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span className="font-semibold text-sm" style={{ color: 'var(--neutral-900)' }}>
                        {item.type === 'call' && `Call Attempt: ${item.outcome}`}
                        {item.type === 'note' && 'Internal Note Added'}
                        {item.type === 'task' && `Task: ${item.title}`}
                        {item.type === 'status_change' && `Status updated to ${item.new_status}`}
                      </span>
                      <span className="text-xs text-muted">
                        {new Date(item.timestamp).toLocaleString([], {
                          month: 'short',
                          day: 'numeric',
                          hour: '2-digit',
                          minute: '2-digit',
                        })}
                      </span>
                    </div>

                    <div className="text-xs text-muted" style={{ marginTop: '2px' }}>
                      By <strong>{item.user}</strong>
                    </div>

                    {item.notes && (
                      <div
                        style={{
                          marginTop: 'var(--space-2)',
                          padding: 'var(--space-2) var(--space-3)',
                          backgroundColor: 'var(--neutral-50)',
                          borderRadius: 'var(--radius-md)',
                          fontSize: 'var(--text-xs)',
                          color: 'var(--neutral-800)',
                        }}
                      >
                        "{item.notes}"
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Fast Call Logging Modal */}
      <Modal
        isOpen={showCallModal}
        onClose={() => setShowCallModal(false)}
        title={`Log Call with ${contact.full_name}`}
        footer={
          <>
            <button
              type="button"
              onClick={() => setShowCallModal(false)}
              className="btn btn-secondary"
            >
              Cancel
            </button>
            <button
              type="button"
              disabled={isLoggingCall}
              onClick={handleLogCall}
              className="btn btn-accent"
            >
              {isLoggingCall ? 'Saving...' : 'Record Call Result'}
            </button>
          </>
        }
      >
        <form onSubmit={handleLogCall}>
          <div className="form-group">
            <label className="form-label">Call Outcome</label>
            <select
              className="form-select"
              value={callOutcome}
              onChange={(e) => setCallOutcome(e.target.value)}
            >
              <option value="ANSWERED">Answered (General)</option>
              <option value="INTERESTED">Interested (High Intent)</option>
              <option value="EMAIL_REQUESTED">Email Requested</option>
              <option value="WHATSAPP_REQUESTED">WhatsApp Requested</option>
              <option value="DEMO_REQUESTED">Demo Requested</option>
              <option value="CALL_LATER">Call Later (Callback)</option>
              <option value="NO_ANSWER">No Answer (Auto Retry)</option>
              <option value="BUSY">Busy</option>
              <option value="NOT_INTERESTED">Not Interested</option>
              <option value="DO_NOT_CONTACT">Do Not Contact</option>
            </select>
          </div>

          {callOutcome === 'CALL_LATER' && (
            <div className="form-group">
              <label className="form-label">Requested Recall Date & Time</label>
              <input
                type="datetime-local"
                required
                className="form-input"
                value={callbackTime}
                onChange={(e) => setCallbackTime(e.target.value)}
              />
            </div>
          )}

          <div className="form-group">
            <label className="form-label">Call Duration (Seconds)</label>
            <input
              type="number"
              className="form-input"
              value={callDuration}
              onChange={(e) => setCallDuration(e.target.value)}
            />
          </div>

          <div className="form-group">
            <label className="form-label">Notes & Summary</label>
            <textarea
              className="form-textarea"
              placeholder="What was discussed? Customer objections, timeline, pricing..."
              value={callNotes}
              onChange={(e) => setCallNotes(e.target.value)}
            />
          </div>
        </form>
      </Modal>

      {/* Explicit Final Outcome Modal */}
      <Modal
        isOpen={showFinalOutcomeModal}
        onClose={() => setShowFinalOutcomeModal(false)}
        title={`Set Final Outcome for ${contact.full_name}`}
        footer={
          <>
            <button
              type="button"
              onClick={() => setShowFinalOutcomeModal(false)}
              className="btn btn-secondary"
            >
              Cancel
            </button>
            <button
              type="button"
              disabled={isSubmittingFinalOutcome}
              onClick={handleSetFinalOutcome}
              className="btn btn-primary"
              style={{ fontWeight: 700 }}
            >
              {isSubmittingFinalOutcome ? 'Archiving...' : 'Confirm & Move to Archive'}
            </button>
          </>
        }
      >
        <form onSubmit={handleSetFinalOutcome}>
          <div style={{ marginBottom: 'var(--space-4)', padding: 'var(--space-3)', backgroundColor: 'var(--bg-subtle)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-light)' }}>
            <div style={{ fontSize: '13px', color: 'var(--neutral-700)', lineHeight: 1.5 }}>
              Setting a <strong>Final Outcome</strong> indicates outreach with this contact is complete.
              The contact will move from <strong>Active Contacts</strong> to <strong>Archive</strong>, but all call history, notes, attempts, and activity timeline will be permanently preserved.
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">Final Outcome</label>
            <select
              className="form-select"
              value={finalOutcomeChoice}
              onChange={(e) => setFinalOutcomeChoice(e.target.value)}
            >
              <option value="Not Interested">Not Interested</option>
              <option value="Converted">Converted</option>
              <option value="Do Not Contact">Do Not Contact</option>
              <option value="Wrong Number">Wrong Number</option>
              <option value="Left Company">Left Company</option>
              <option value="Closed">Closed</option>
              <option value="Other Final Outcome">Other Final Outcome</option>
            </select>
          </div>

          <div className="form-group">
            <label className="form-label">Final Outcome Notes & Closing Details</label>
            <textarea
              className="form-textarea"
              style={{ minHeight: '90px' }}
              placeholder="Provide context on why this contact is finished (reason, competitor chosen, no budget, etc.)..."
              value={finalOutcomeNotes}
              onChange={(e) => setFinalOutcomeNotes(e.target.value)}
            />
          </div>
        </form>
      </Modal>

      {/* Note Modal */}
      <Modal
        isOpen={showNoteModal}
        onClose={() => setShowNoteModal(false)}
        title="Add Internal Note"
        footer={
          <>
            <button
              type="button"
              onClick={() => setShowNoteModal(false)}
              className="btn btn-secondary"
            >
              Cancel
            </button>
            <button
              type="button"
              disabled={isAddingNote}
              onClick={handleAddNote}
              className="btn btn-accent"
            >
              {isAddingNote ? 'Saving...' : 'Add Note'}
            </button>
          </>
        }
      >
        <form onSubmit={handleAddNote}>
          <div className="form-group">
            <label className="form-label">Note Content</label>
            <textarea
              className="form-textarea"
              style={{ minHeight: '120px' }}
              placeholder="Record important internal intelligence or instructions..."
              value={noteContent}
              onChange={(e) => setNoteContent(e.target.value)}
            />
          </div>
        </form>
      </Modal>
    </div>
  );
};
