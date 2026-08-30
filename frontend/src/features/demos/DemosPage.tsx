import React, { useState, useEffect } from 'react';
import { api } from '../../lib/apiClient';
import { useAuthStore } from '../../store/authStore';
import { DemoItem } from '../../types';
import { Badge } from '../../components/ui/Badge';
import { Modal } from '../../components/ui/Modal';
import { LoadingSpinner } from '../../components/feedback/LoadingSpinner';
import { EmptyState } from '../../components/feedback/EmptyState';
import { Presentation, CheckCircle2, AlertCircle, Edit3, Plus, Calendar, Clock } from 'lucide-react';
import { useTranslation } from '../../i18n';

export const DemosPage: React.FC = () => {
  const { user } = useAuthStore();
  const { t, isRTL } = useTranslation();

  const [demos, setDemos] = useState<any[]>([]);
  const [stageFilter, setStageFilter] = useState<string>('ALL');
  const [assignedUserFilter, setAssignedUserFilter] = useState<string>('');
  const [usersList, setUsersList] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  // Edit / Update Stage Modal State
  const [editingDemo, setEditingDemo] = useState<any | null>(null);
  const [newStage, setNewStage] = useState('REQUESTED');
  const [newScheduledAt, setNewScheduledAt] = useState('');
  const [newNotes, setNewNotes] = useState('');
  const [newResult, setNewResult] = useState('');
  const [isUpdating, setIsUpdating] = useState(false);

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

  const fetchDemos = async () => {
    setIsLoading(true);
    try {
      const params: Record<string, any> = {};
      if (stageFilter !== 'ALL') params.stage = stageFilter;
      if (assignedUserFilter) params.user_id = assignedUserFilter;

      const res = await api.get<any>('/demos', params);
      setDemos(res.data || []);
    } catch (e) {
      console.error('Failed to load demos', e);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchDemos();
  }, [stageFilter, assignedUserFilter]);

  const handleQuickUpdateStage = async (id: string, stage: string) => {
    try {
      await api.patch(`/demos/${id}`, { stage });
      await fetchDemos();
    } catch (e) {
      console.error('Failed to update demo stage', e);
    }
  };

  const handleEditSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingDemo) return;
    setIsUpdating(true);
    try {
      await api.patch(`/demos/${editingDemo.id}`, {
        stage: newStage,
        scheduled_at: newScheduledAt ? new Date(newScheduledAt).toISOString() : undefined,
        notes: newNotes,
        result: newResult,
      });
      setEditingDemo(null);
      await fetchDemos();
    } catch (err: any) {
      alert(err.message || 'Failed to update demo');
    } finally {
      setIsUpdating(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-6)' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 'var(--space-4)' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
            <h1 className="font-display font-bold text-2xl" style={{ color: 'var(--neutral-900)' }}>
              {isRTL ? "العروض التوضيحية للمنتج (Demos)" : "Product Demonstrations"}
            </h1>
            <span className="badge badge-accent text-xs">
              {demos.length} {isRTL ? "عرض تجريبي" : "Demos"}
            </span>
          </div>
          <p className="text-sm text-muted" style={{ marginTop: '2px' }}>
            {isRTL
              ? "متابعة العروض المتفق عليها، المجدولة، المنجزة، والملغية لكافة أعضاء فريق المبيعات."
              : "Track demo lifecycle from initial request to scheduled presentation and final deal outcome."}
          </p>
        </div>

        {/* User Filter Dropdown for Managers */}
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
      </div>

      {/* Stage Navigation Tabs */}
      <div
        style={{
          display: 'flex',
          gap: 'var(--space-2)',
          borderBottom: '1px solid var(--border-color)',
          paddingBottom: 'var(--space-2)',
          overflowX: 'auto',
        }}
      >
        <button
          onClick={() => setStageFilter('ALL')}
          className={`btn ${stageFilter === 'ALL' ? 'btn-accent' : 'btn-secondary'} btn-sm`}
        >
          {isRTL ? "جميع العروض" : "All Demos"} ({demos.length})
        </button>
        <button
          onClick={() => setStageFilter('AGREED')}
          className={`btn ${stageFilter === 'AGREED' ? 'btn-accent' : 'btn-secondary'} btn-sm`}
        >
          {isRTL ? "تم الاتفاق / مطلوب" : "Agreed / Requested"}
        </button>
        <button
          onClick={() => setStageFilter('SCHEDULED')}
          className={`btn ${stageFilter === 'SCHEDULED' ? 'btn-accent' : 'btn-secondary'} btn-sm`}
        >
          {isRTL ? "مجدول ومؤكد" : "Scheduled"}
        </button>
        <button
          onClick={() => setStageFilter('COMPLETED')}
          className={`btn ${stageFilter === 'COMPLETED' ? 'btn-accent' : 'btn-secondary'} btn-sm`}
        >
          {isRTL ? "مكتمل بنجاح" : "Completed"}
        </button>
        <button
          onClick={() => setStageFilter('CANCELLED')}
          className={`btn ${stageFilter === 'CANCELLED' ? 'btn-danger' : 'btn-secondary'} btn-sm`}
        >
          {isRTL ? "ملغي / لم يحضر" : "Cancelled / No Show"}
        </button>
      </div>

      {/* Table */}
      {isLoading ? (
        <LoadingSpinner message={isRTL ? "جاري تحميل جدول العروض..." : "Loading scheduled demos..."} />
      ) : demos.length === 0 ? (
        <EmptyState
          title={isRTL ? "لا توجد عروض توضيحية مطابقة" : "No demos found"}
          description={isRTL ? "لا توجد عروض تجريبية في هذه المرحلة حالياً." : "Use call outcomes to request and schedule demonstrations."}
        />
      ) : (
        <div className="table-container custom-scrollbar" style={{ overflowX: 'auto' }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>{isRTL ? "المرحلة" : "Stage"}</th>
                <th>{isRTL ? "جهة الاتصال" : "Target Contact"}</th>
                <th>{isRTL ? "الشركة" : "Company"}</th>
                <th>{isRTL ? "المسؤول" : "Sales Rep"}</th>
                <th>{isRTL ? "موعد العرض" : "Scheduled Date & Time"}</th>
                <th>{isRTL ? "الملاحظات والنتائج" : "Demo Notes & Result"}</th>
                <th>{isRTL ? "الإجراء" : "Actions"}</th>
              </tr>
            </thead>
            <tbody>
              {demos.map((d: any) => (
                <tr key={d.id}>
                  <td>
                    <Badge status={d.stage} />
                  </td>
                  <td>
                    <span className="font-semibold text-sm text-dark">{d.contact_name || '—'}</span>
                    {d.contact_phone && <div className="text-xs font-mono text-muted">{d.contact_phone}</div>}
                  </td>
                  <td>
                    <span className="text-sm font-medium" style={{ color: 'var(--neutral-800)' }}>
                      {d.company_name || '—'}
                    </span>
                  </td>
                  <td>
                    <span className="badge badge-secondary text-xs font-semibold">
                      {d.owner_name || 'Sales Rep'}
                    </span>
                  </td>
                  <td>
                    <span className="text-xs font-semibold text-primary">
                      {d.scheduled_at ? new Date(d.scheduled_at).toLocaleString([], { dateStyle: 'short', timeStyle: 'short' }) : 'Pending scheduling'}
                    </span>
                  </td>
                  <td>
                    <div className="text-xs text-dark">{d.notes || '—'}</div>
                    {d.result && <div className="text-xs text-muted" style={{ marginTop: '2px' }}>Outcome: {d.result}</div>}
                  </td>
                  <td>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                      <button
                        onClick={() => {
                          setEditingDemo(d);
                          setNewStage(d.stage);
                          setNewScheduledAt(d.scheduled_at ? d.scheduled_at.slice(0, 16) : '');
                          setNewNotes(d.notes || '');
                          setNewResult(d.result || '');
                        }}
                        className="btn btn-secondary btn-sm"
                        style={{ display: 'flex', alignItems: 'center', gap: '4px' }}
                      >
                        <Edit3 size={13} />
                        <span>{isRTL ? "تعديل" : "Edit"}</span>
                      </button>

                      {d.stage !== 'COMPLETED' && (
                        <button
                          onClick={() => handleQuickUpdateStage(d.id, 'COMPLETED')}
                          className="btn btn-ghost btn-sm"
                          title="Mark Completed"
                        >
                          <CheckCircle2 size={15} style={{ color: 'var(--color-success)' }} />
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* ── Edit Demo Modal ────────────────────────────────────────────── */}
      <Modal
        isOpen={!!editingDemo}
        onClose={() => setEditingDemo(null)}
        title={isRTL ? "تعديل بيانات العرض التجريبي" : "Update Demo Details & Outcome"}
        footer={
          <>
            <button
              type="button"
              onClick={() => setEditingDemo(null)}
              className="btn btn-secondary"
            >
              {isRTL ? "إلغاء" : "Cancel"}
            </button>
            <button
              type="button"
              disabled={isUpdating}
              onClick={handleEditSubmit}
              className="btn btn-accent"
            >
              {isUpdating ? (isRTL ? 'جاري الحفظ...' : 'Saving...') : (isRTL ? 'حفظ التعديل' : 'Save Changes')}
            </button>
          </>
        }
      >
        <form onSubmit={handleEditSubmit}>
          <div style={{ marginBottom: 'var(--space-4)', padding: 'var(--space-3)', backgroundColor: 'var(--bg-subtle)', borderRadius: 'var(--radius-md)' }}>
            <div className="text-xs text-muted">TARGET CONTACT</div>
            <div className="font-bold text-sm" style={{ color: 'var(--neutral-900)', marginTop: '2px' }}>
              {editingDemo?.contact_name} ({editingDemo?.company_name || 'No Company'})
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">{isRTL ? "المرحلة / الحالة *" : "Demo Stage *"}</label>
            <select
              className="form-select"
              value={newStage}
              onChange={(e) => setNewStage(e.target.value)}
            >
              <option value="REQUESTED">REQUESTED (طلب جديد)</option>
              <option value="SCHEDULED">SCHEDULED (مجدول ومؤكد)</option>
              <option value="COMPLETED">COMPLETED (مكتمل بنجاح)</option>
              <option value="CANCELLED">CANCELLED (ملغي)</option>
              <option value="NO_SHOW">NO_SHOW (لم يحضر)</option>
              <option value="RESCHEDULED">RESCHEDULED (إعادة جدولة)</option>
            </select>
          </div>

          <div className="form-group">
            <label className="form-label">{isRTL ? "تاريخ ووقت العرض" : "Scheduled Date & Time"}</label>
            <input
              type="datetime-local"
              className="form-input"
              value={newScheduledAt}
              onChange={(e) => setNewScheduledAt(e.target.value)}
            />
          </div>

          <div className="form-group">
            <label className="form-label">{isRTL ? "ملاحظات وتفاصيل العرض" : "Demo Preparation Notes"}</label>
            <textarea
              className="form-textarea"
              rows={2}
              value={newNotes}
              onChange={(e) => setNewNotes(e.target.value)}
              placeholder="e.g. Focus on enterprise compliance module..."
            />
          </div>

          <div className="form-group">
            <label className="form-label">{isRTL ? "النتيجة والخطوة التالية" : "Demo Result & Next Step"}</label>
            <input
              type="text"
              className="form-input"
              value={newResult}
              onChange={(e) => setNewResult(e.target.value)}
              placeholder="e.g. Client requested commercial proposal by Thursday"
            />
          </div>
        </form>
      </Modal>
    </div>
  );
};
