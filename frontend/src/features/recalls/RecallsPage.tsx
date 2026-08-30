import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../../lib/apiClient';
import { useAuthStore } from '../../store/authStore';
import { LoadingSpinner } from '../../components/feedback/LoadingSpinner';
import { EmptyState } from '../../components/feedback/EmptyState';
import { PhoneCall, CheckCircle2, Clock, Calendar, Copy, Check, Filter } from 'lucide-react';
import { useTranslation } from '../../i18n';

export const RecallsPage: React.FC = () => {
  const navigate = useNavigate();
  const { user } = useAuthStore();
  const { isRTL } = useTranslation();

  const [recalls, setRecalls] = useState<any[]>([]);
  const [usersList, setUsersList] = useState<any[]>([]);
  const [assignedUserFilter, setAssignedUserFilter] = useState('');
  const [timeFilter, setTimeFilter] = useState<'ALL' | 'TODAY' | 'UPCOMING' | 'OVERDUE'>('ALL');
  const [isLoading, setIsLoading] = useState(true);
  const [copiedId, setCopiedId] = useState<string | null>(null);

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

  const fetchRecalls = async () => {
    setIsLoading(true);
    try {
      const params: Record<string, any> = { status: 'PENDING' };
      if (assignedUserFilter) params.user_id = assignedUserFilter;
      if (timeFilter === 'TODAY') params.today_only = true;
      if (timeFilter === 'UPCOMING') params.upcoming_only = true;
      if (timeFilter === 'OVERDUE') params.overdue_only = true;

      const res = await api.get<any>('/recalls', params);
      setRecalls(res.data || []);
    } catch (e) {
      console.error('Failed to load recalls', e);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchRecalls();
  }, [assignedUserFilter, timeFilter]);

  const handleCopy = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 1500);
  };

  // Direct Call Result from Scheduled Recalls (Synchronizes next attempt in Contacts)
  const handleRecordRecallOutcome = async (contactId: string, recallId: string, outcome: string) => {
    try {
      await api.post(`/contacts/${contactId}/quick-call`, { outcome });
      // Remove from pending list or reload
      setRecalls((prev) => prev.filter((r) => r.id !== recallId));
    } catch (err: any) {
      alert(err.message || 'Failed to record call outcome');
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-5)' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 'var(--space-4)' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
            <h1 className="font-display font-bold text-2xl" style={{ color: 'var(--neutral-900)' }}>
              {isRTL ? "إعادة الاتصال المجدولة" : "Scheduled Recalls"}
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
              {recalls.length} {isRTL ? "مكالمة معلقة" : "Pending"}
            </span>
          </div>
          <p className="text-sm text-muted" style={{ marginTop: '2px' }}>
            {isRTL
              ? "مواعيد إعادة الاتصال المجدولة مع العملاء. يمكنك الاتصال وتسجيل النتيجة مباشرة لتحديث المحاولة القادمة في جهات الاتصال تلقائياً."
              : "Customer-scheduled callbacks. Call and record outcomes directly to automatically synchronize the next attempt in Contacts."}
          </p>
        </div>

        {/* User Filter Dropdown for Managers */}
        {user?.role === 'MANAGER' && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
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
          </div>
        )}
      </div>

      {/* Filter Tabs */}
      <div style={{ display: 'flex', gap: 'var(--space-2)', borderBottom: '1px solid var(--border-color)', paddingBottom: '6px' }}>
        <button
          onClick={() => setTimeFilter('ALL')}
          className={`btn ${timeFilter === 'ALL' ? 'btn-accent' : 'btn-secondary'} btn-sm`}
        >
          {isRTL ? "الكل" : "All Recalls"} ({recalls.length})
        </button>
        <button
          onClick={() => setTimeFilter('TODAY')}
          className={`btn ${timeFilter === 'TODAY' ? 'btn-accent' : 'btn-secondary'} btn-sm`}
        >
          {isRTL ? "اليوم فقط" : "Today"}
        </button>
        <button
          onClick={() => setTimeFilter('UPCOMING')}
          className={`btn ${timeFilter === 'UPCOMING' ? 'btn-accent' : 'btn-secondary'} btn-sm`}
        >
          {isRTL ? "القادمة" : "Upcoming"}
        </button>
        <button
          onClick={() => setTimeFilter('OVERDUE')}
          className={`btn ${timeFilter === 'OVERDUE' ? 'btn-danger' : 'btn-secondary'} btn-sm`}
        >
          {isRTL ? "المتأخرة" : "Overdue"}
        </button>
      </div>

      {isLoading ? (
        <LoadingSpinner message={isRTL ? "جاري تحميل قائمة إعادة الاتصال..." : "Loading scheduled recalls..."} />
      ) : recalls.length === 0 ? (
        <EmptyState
          title={isRTL ? "لا توجد مكالمات مجدولة معلقة" : "No pending scheduled recalls"}
          description={isRTL ? "لا توجد مواعيد إعادة اتصال مستحقة حالياً." : "There are no pending customer callbacks at this time."}
        />
      ) : (
        <div className="table-container custom-scrollbar" style={{ overflowX: 'auto' }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>{isRTL ? "جهة الاتصال" : "Contact Name"}</th>
                <th>{isRTL ? "الشركة" : "Company"}</th>
                <th>{isRTL ? "الهاتف" : "Phone"}</th>
                <th>{isRTL ? "تاريخ الموعد" : "Scheduled Date"}</th>
                <th>{isRTL ? "وقت الموعد" : "Scheduled Time"}</th>
                <th>{isRTL ? "رقم المحاولة" : "Attempt Number"}</th>
                <th>{isRTL ? "النتيجة السابقة" : "Previous Result"}</th>
                <th>{isRTL ? "الملاحظات" : "Notes"}</th>
                <th style={{ minWidth: '180px' }}>{isRTL ? "تسجيل النتيجة مباشرة" : "Action / Result"}</th>
              </tr>
            </thead>
            <tbody>
              {recalls.map((r: any) => {
                const dt = new Date(r.scheduled_at);
                const dateStr = dt.toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' });
                const timeStr = dt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

                return (
                  <tr key={r.id}>
                    <td>
                      <button
                        onClick={() => navigate(`/contacts/${r.contact_id}`)}
                        style={{
                          background: 'none',
                          border: 'none',
                          padding: 0,
                          cursor: 'pointer',
                          fontWeight: 600,
                          fontSize: '13px',
                          color: 'var(--neutral-900)',
                          textDecoration: 'underline',
                        }}
                      >
                        {r.contact_name || '—'}
                      </button>
                    </td>
                    <td>
                      <span className="text-xs font-medium text-muted">{r.company_name || '—'}</span>
                    </td>
                    <td>
                      {r.phone ? (
                        <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                          <span className="text-xs font-mono text-dark">{r.phone}</span>
                          <button
                            onClick={() => handleCopy(r.phone, r.id)}
                            style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '1px' }}
                          >
                            {copiedId === r.id ? <Check size={12} color="var(--color-success)" /> : <Copy size={12} color="var(--neutral-400)" />}
                          </button>
                        </div>
                      ) : (
                        '—'
                      )}
                    </td>
                    <td>
                      <span className="text-xs font-semibold" style={{ color: 'var(--neutral-800)' }}>
                        📅 {dateStr}
                      </span>
                    </td>
                    <td>
                      <span className="text-xs font-bold" style={{ color: 'var(--color-primary)' }}>
                        ⏰ {timeStr}
                      </span>
                    </td>
                    <td>
                      <span
                        style={{
                          fontSize: '11px',
                          fontWeight: 700,
                          padding: '2px 8px',
                          borderRadius: 'var(--radius-sm)',
                          backgroundColor: 'var(--color-primary-subtle)',
                          color: 'var(--color-primary)',
                        }}
                      >
                        Attempt #{r.attempt_number || 1}
                      </span>
                    </td>
                    <td>
                      <span className="text-xs text-muted font-normal">{r.previous_result || 'Re Call'}</span>
                    </td>
                    <td>
                      <span className="text-xs text-dark" style={{ maxWidth: '200px', display: 'inline-block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {r.notes || '—'}
                      </span>
                    </td>
                    <td>
                      {/* Direct Outcome Dropdown that synchronizes with Contacts */}
                      <select
                        onChange={(e) => {
                          if (e.target.value) {
                            handleRecordRecallOutcome(r.contact_id, r.id, e.target.value);
                            e.target.value = '';
                          }
                        }}
                        className="form-select text-xs"
                        style={{ height: '30px', padding: '2px 6px', fontSize: '11px', minWidth: '160px', borderColor: 'var(--color-primary)' }}
                        defaultValue=""
                      >
                        <option value="" disabled>+ Record Result...</option>
                        <option value="No Answer">📞 No Answer</option>
                        <option value="Interested">✨ Interested</option>
                        <option value="Asked for email">📧 Asked for email</option>
                        <option value="Asked for whatapp">💬 Asked for whatsapp</option>
                        <option value="Demo">🎯 Demo</option>
                        <option value="Re Call">⏰ Re Call Again</option>
                        <option value="Not interested">🚫 Not interested</option>
                        <option value="wrong number">❌ Wrong number</option>
                      </select>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
