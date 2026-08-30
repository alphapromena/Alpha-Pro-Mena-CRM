import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../../lib/apiClient';
import { useAuthStore } from '../../store/authStore';
import { LoadingSpinner } from '../../components/feedback/LoadingSpinner';
import { EmptyState } from '../../components/feedback/EmptyState';
import { Modal } from '../../components/ui/Modal';
import { PhoneMissed, Copy, Check, AlertCircle, Clock, Archive } from 'lucide-react';
import { useTranslation } from '../../i18n';

export const NoAnswerPage: React.FC = () => {
  const navigate = useNavigate();
  const { user } = useAuthStore();
  const { isRTL } = useTranslation();

  const [items, setItems] = useState<any[]>([]);
  const [usersList, setUsersList] = useState<any[]>([]);
  const [assignedUserFilter, setAssignedUserFilter] = useState('');
  const [overdueOnly, setOverdueOnly] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  // Final Outcome Modal for 5th Attempt
  const [finalModalContact, setFinalModalContact] = useState<any | null>(null);
  const [finalChoice, setFinalChoice] = useState('No Answer');
  const [finalNotes, setFinalNotes] = useState('');
  const [isArchiving, setIsArchiving] = useState(false);

  // Fetch Users for Filter
  useEffect(() => {
    const fetchUsers = async () => {
      try {
        const res = await api.get<any>('/users');
        setUsersList(res.data || []);
      } catch (e) {
        console.error('Failed to load users', e);
      }
    };
    fetchUsers();
  }, []);

  const fetchQueue = async () => {
    setIsLoading(true);
    try {
      const params: Record<string, any> = { status: 'PENDING' };
      if (assignedUserFilter) params.user_id = assignedUserFilter;
      if (overdueOnly) params.overdue_only = true;

      const res = await api.get<any>('/no-answer', params);
      setItems(res.data || []);
    } catch (e) {
      console.error('Failed to load no-answer queue', e);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchQueue();
  }, [assignedUserFilter, overdueOnly]);

  const handleCopy = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 1500);
  };

  // Direct Call Result from No Answer Queue
  const handleQuickOutcome = async (item: any, outcome: string) => {
    if (outcome === '__FINAL_OUTCOME__' || (item.attempt_number >= 5 && outcome === 'No Answer')) {
      setFinalModalContact(item);
      setFinalChoice('No Answer');
      setFinalNotes('');
      return;
    }

    try {
      await api.post(`/contacts/${item.contact_id}/quick-call`, { outcome });
      await fetchQueue();
    } catch (err: any) {
      alert(err.message || 'Failed to record outcome');
    }
  };

  const handleFinalOutcomeSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!finalModalContact) return;
    setIsArchiving(true);

    try {
      await api.post(`/contacts/${finalModalContact.contact_id}/final-outcome`, {
        final_outcome: finalChoice,
        notes: finalNotes || undefined,
      });
      setFinalModalContact(null);
      await fetchQueue();
    } catch (err: any) {
      alert(err.message || 'Failed to set final outcome');
    } finally {
      setIsArchiving(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-5)' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 'var(--space-4)' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
            <h1 className="font-display font-bold text-2xl" style={{ color: 'var(--neutral-900)' }}>
              {isRTL ? "طابور إعادة المحاولة (عدم الرد)" : "No Answer Retry Queue"}
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
              {items.length} {isRTL ? "عميل بانتظار المحاولة" : "In Cadence"}
            </span>
          </div>
          <p className="text-sm text-muted" style={{ marginTop: '2px' }}>
            {isRTL
              ? "إعادة الاتصال التلقائي كل 48 ساعة للعملاء الذين لم يردوا (حتى 5 محاولات كحد أقصى). يمكنك تسجيل النتيجة مباشرة."
              : "Automated 48-hour retry cadence for unanswered calls (up to 5 attempts max). Record outcomes directly."}
          </p>
        </div>

        {/* User Filter & Overdue Toggle */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
          {user?.role === 'MANAGER' && (
            <select
              className="form-select text-xs"
              style={{ width: '180px' }}
              value={assignedUserFilter}
              onChange={(e) => setAssignedUserFilter(e.target.value)}
            >
              <option value="">{isRTL ? "جميع الموظفين" : "All Sales Reps"}</option>
              {usersList.map((u) => (
                <option key={u.id} value={u.id}>
                  👤 {u.full_name} ({u.role})
                </option>
              ))}
            </select>
          )}

          <button
            type="button"
            onClick={() => setOverdueOnly(!overdueOnly)}
            className={`btn btn-sm ${overdueOnly ? 'btn-danger' : 'btn-secondary'}`}
            style={{ fontSize: '12px' }}
          >
            <AlertCircle size={14} />
            <span>{isRTL ? "المستحقة الآن فقط" : "Due Retries Only"}</span>
          </button>
        </div>
      </div>

      {isLoading ? (
        <LoadingSpinner message={isRTL ? "جاري فحص طابور إعادة المحاولة..." : "Scanning no-answer retry queue..."} />
      ) : items.length === 0 ? (
        <EmptyState
          title={isRTL ? "لا يوجد عملاء في طابور عدم الرد" : "No leads in retry queue"}
          description={isRTL ? "جميع العملاء إما تمت إجابتهم أو مجدولين لمواعيد أخرى." : "All leads have either answered or are scheduled for callbacks."}
        />
      ) : (
        <div className="table-container custom-scrollbar" style={{ overflowX: 'auto' }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>{isRTL ? "جهة الاتصال" : "Lead Name"}</th>
                <th>{isRTL ? "الشركة" : "Company"}</th>
                <th>{isRTL ? "الهاتف" : "Phone"}</th>
                <th>{isRTL ? "المحاولة الحالية" : "Current Attempt"}</th>
                <th>{isRTL ? "النتيجة السابقة" : "Previous Result"}</th>
                <th>{isRTL ? "موعد المحاولة القادمة (48 ساعة)" : "Next Retry (48h Cadence)"}</th>
                <th>{isRTL ? "الملاحظات" : "Notes"}</th>
                <th style={{ minWidth: '180px' }}>{isRTL ? "تسجيل النتيجة مباشرة" : "Action / New Result"}</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => {
                const isMax = item.attempt_number >= 5;
                const nextDate = item.next_attempt_at ? new Date(item.next_attempt_at) : null;

                return (
                  <tr key={item.id}>
                    <td>
                      <button
                        onClick={() => navigate(`/contacts/${item.contact_id}`)}
                        style={{
                          background: 'none',
                          border: 'none',
                          padding: 0,
                          cursor: 'pointer',
                          fontWeight: '600',
                          fontSize: '13px',
                          color: 'var(--neutral-900)',
                          textDecoration: 'underline',
                        }}
                      >
                        {item.contact_name || '—'}
                      </button>
                    </td>
                    <td>
                      <span className="text-xs font-medium text-muted">{item.company_name || '—'}</span>
                    </td>
                    <td>
                      {item.phone ? (
                        <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                          <span className="text-xs font-mono text-dark">{item.phone}</span>
                          <button
                            onClick={() => handleCopy(item.phone, item.id)}
                            style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '1px' }}
                          >
                            {copiedId === item.id ? <Check size={12} color="var(--color-success)" /> : <Copy size={12} color="var(--neutral-400)" />}
                          </button>
                        </div>
                      ) : (
                        '—'
                      )}
                    </td>
                    <td>
                      <span
                        style={{
                          fontSize: '11px',
                          fontWeight: '700',
                          padding: '2px 8px',
                          borderRadius: 'var(--radius-sm)',
                          backgroundColor: isMax ? '#fee2e2' : 'var(--status-noanswer-bg)',
                          color: isMax ? '#b91c1c' : 'var(--status-noanswer-text)',
                          border: isMax ? '1px solid #fca5a5' : '1px solid rgba(245, 158, 11, 0.3)',
                        }}
                      >
                        {isMax ? 'Attempt 5/5 (Max)' : `Attempt #${item.attempt_number}`}
                      </span>
                    </td>
                    <td>
                      <span className="text-xs text-muted">{item.previous_result || 'No Answer'}</span>
                    </td>
                    <td>
                      <span
                        className="text-xs font-semibold"
                        style={{
                          color: item.is_overdue ? 'var(--color-danger)' : 'var(--color-primary)',
                        }}
                      >
                        {nextDate ? `📅 ${nextDate.toLocaleDateString([], { month: 'short', day: 'numeric' })} · ${nextDate.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}` : 'Due Now'}
                      </span>
                    </td>
                    <td>
                      <span className="text-xs text-dark" style={{ maxWidth: '180px', display: 'inline-block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {item.notes || '—'}
                      </span>
                    </td>
                    <td>
                      {isMax ? (
                        <button
                          onClick={() => {
                            setFinalModalContact(item);
                            setFinalChoice('No Answer');
                            setFinalNotes('');
                          }}
                          className="btn btn-accent btn-xs"
                          style={{ fontWeight: 700 }}
                        >
                          + Set Final Outcome
                        </button>
                      ) : (
                        <select
                          onChange={(e) => {
                            if (e.target.value) {
                              handleQuickOutcome(item, e.target.value);
                              e.target.value = '';
                            }
                          }}
                          className="form-select text-xs"
                          style={{ height: '30px', padding: '2px 6px', fontSize: '11px', minWidth: '160px', borderColor: 'var(--color-primary)' }}
                          defaultValue=""
                        >
                          <option value="" disabled>+ Log Outcome...</option>
                          <option value="No Answer">📞 Still No Answer (+48h)</option>
                          <option value="Interested">✨ Answered: Interested</option>
                          <option value="Asked for email">📧 Asked for email</option>
                          <option value="Asked for whatapp">💬 Asked for whatsapp</option>
                          <option value="Demo">🎯 Demo</option>
                          <option value="Re Call">⏰ Re Call (Schedule)</option>
                          <option value="Not interested">🚫 Not Interested</option>
                          <option value="wrong number">❌ Wrong Number</option>
                          <option value="__FINAL_OUTCOME__">🏁 Set Final Outcome...</option>
                        </select>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* ── Final Outcome Modal ─────────────────────────────────────────── */}
      {finalModalContact && (
        <Modal
          isOpen={!!finalModalContact}
          onClose={() => setFinalModalContact(null)}
          title={isRTL ? `إنهاء التواصل والأرشفة — ${finalModalContact.contact_name}` : `Set Final Outcome & Archive — ${finalModalContact.contact_name}`}
        >
          <form onSubmit={handleFinalOutcomeSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
            <p className="text-xs text-muted" style={{ margin: 0 }}>
              {isRTL
                ? "وصلت جهة الاتصال إلى الحد الأقصى للمحاولات (أو تم اختيار إنهاء التواصل). سيتم نقلها مباشرة إلى الأرشيف."
                : "The contact has reached the 5-attempt limit (or you selected to close the workflow). This moves the contact to Archive."}
            </p>

            <div>
              <label className="form-label text-xs">{isRTL ? "النتيجة النهائية" : "Final Outcome"}</label>
              <select
                className="form-select text-xs"
                value={finalChoice}
                onChange={(e) => setFinalChoice(e.target.value)}
              >
                <option value="No Answer">📞 No Answer (Max Attempts Completed)</option>
                <option value="Not Interested">🚫 Not Interested</option>
                <option value="Wrong Number">❌ Wrong Number</option>
                <option value="Voice Mail / Don't Call Again">⛔ Voice Mail / Don't Call Again</option>
                <option value="HQ">🏢 HQ</option>
              </select>
            </div>

            <div>
              <label className="form-label text-xs">{isRTL ? "ملاحظة ختامية" : "Closing Note"}</label>
              <textarea
                className="form-input text-xs"
                rows={2}
                placeholder={isRTL ? "ملاحظات إغلاق جهة الاتصال..." : "Closing notes..."}
                value={finalNotes}
                onChange={(e) => setFinalNotes(e.target.value)}
              />
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 'var(--space-2)' }}>
              <button type="button" onClick={() => setFinalModalContact(null)} className="btn btn-secondary btn-sm">
                {isRTL ? "إلغاء" : "Cancel"}
              </button>
              <button type="submit" disabled={isArchiving} className="btn btn-danger btn-sm">
                <Archive size={14} />
                <span>{isArchiving ? (isRTL ? "جاري الأرشفة..." : "Archiving...") : (isRTL ? "تأكيد والأرشفة" : "Confirm & Archive")}</span>
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
};
