import React, { useState, useEffect } from 'react';
import { api } from '../../lib/apiClient';
import { useAuthStore } from '../../store/authStore';
import { Task } from '../../types';
import { Badge } from '../../components/ui/Badge';
import { Modal } from '../../components/ui/Modal';
import { LoadingSpinner } from '../../components/feedback/LoadingSpinner';
import { EmptyState } from '../../components/feedback/EmptyState';
import {
  CheckCircle2,
  Clock,
  Mail,
  MessageSquare,
  PhoneCall,
  Plus,
  Filter,
  UserCheck,
  AlertCircle,
  Calendar,
  Layers,
  Edit3,
  User,
  ArrowRight,
} from 'lucide-react';
import { useTranslation } from '../../i18n';

export const TasksPage: React.FC = () => {
  const { user } = useAuthStore();
  const { t, isRTL } = useTranslation();

  const [tasks, setTasks] = useState<Task[]>([]);
  const [total, setTotal] = useState(0);
  const [usersList, setUsersList] = useState<any[]>([]);

  // Filters State
  const [category, setCategory] = useState<'ALL' | 'COMMUNICATION' | 'CUSTOMER_ACTION' | 'INTERNAL_ASSIGNED'>('ALL');
  const [assignedUserFilter, setAssignedUserFilter] = useState('');
  const [priorityFilter, setPriorityFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [overdueOnly, setOverdueOnly] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  // Create Task Modal
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newTitle, setNewTitle] = useState('');
  const [newDescription, setNewDescription] = useState('');
  const [newPriority, setNewPriority] = useState<'HIGH' | 'MEDIUM' | 'LOW'>('MEDIUM');
  const [newAssignedTo, setNewAssignedTo] = useState('');
  const [newDueDate, setNewDueDate] = useState('');
  const [isCreating, setIsCreating] = useState(false);

  // Reassign Task Modal
  const [reassigningTask, setReassigningTask] = useState<any | null>(null);
  const [reassignTargetUserId, setReassignTargetUserId] = useState('');
  const [reassignPriority, setReassignPriority] = useState('');
  const [reassignDueDate, setReassignDueDate] = useState('');
  const [isReassigning, setIsReassigning] = useState(false);

  // No-Answer Recontact Panel
  const [showNoAnswerModal, setShowNoAnswerModal] = useState(false);
  const [noAnswerLeads, setNoAnswerLeads] = useState<any[]>([]);
  const [loadingNoAnswer, setLoadingNoAnswer] = useState(false);

  const fetchNoAnswerLeads = async () => {
    setLoadingNoAnswer(true);
    try {
      const res = await api.get<any>('/contacts', { last_outcome: 'No Answer', per_page: 50 });
      setNoAnswerLeads(res.data || []);
    } catch (e) {
      console.error('Failed to load no-answer leads', e);
    } finally {
      setLoadingNoAnswer(false);
    }
  };

  // Fetch Users for Filter & Assignment
  useEffect(() => {
    const fetchUsers = async () => {
      try {
        const res = await api.get<any>('/users');
        setUsersList(res.data || []);
      } catch (e) {
        console.error('Failed to load users list', e);
      }
    };
    fetchUsers();
  }, []);

  const fetchTasks = async () => {
    setIsLoading(true);
    try {
      const params: Record<string, any> = {
        per_page: 100,
      };
      if (category !== 'ALL') params.category = category;
      if (assignedUserFilter) params.assigned_to = assignedUserFilter;
      if (priorityFilter) params.priority = priorityFilter;
      if (statusFilter) params.status = statusFilter;
      if (overdueOnly) params.overdue_only = true;

      const res = await api.get<any>('/tasks', params);
      setTasks(res.data || []);
      setTotal(res.meta?.total || 0);
    } catch (e) {
      console.error('Failed to load tasks', e);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchTasks();
  }, [category, assignedUserFilter, priorityFilter, statusFilter, overdueOnly]);

  const handleComplete = async (taskId: string) => {
    try {
      await api.post(`/tasks/${taskId}/complete`, { completion_notes: 'Completed by team member' });
      await fetchTasks();
    } catch (e) {
      console.error('Failed to complete task', e);
    }
  };

  const handleCreateTask = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsCreating(true);
    try {
      await api.post('/tasks', {
        title: newTitle,
        description: newDescription || undefined,
        priority: newPriority,
        type: 'OTHER',
        assigned_to: newAssignedTo || undefined,
        due_at: newDueDate ? new Date(newDueDate).toISOString() : undefined,
      });
      setShowCreateModal(false);
      setNewTitle('');
      setNewDescription('');
      setNewDueDate('');
      setNewAssignedTo('');
      await fetchTasks();
    } catch (err: any) {
      alert(err.message || 'Failed to create task');
    } finally {
      setIsCreating(false);
    }
  };

  const handleReassignSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!reassigningTask) return;
    setIsReassigning(true);
    try {
      const payload: Record<string, any> = {};
      if (reassignTargetUserId) payload.assigned_to = reassignTargetUserId;
      if (reassignPriority) payload.priority = reassignPriority;
      if (reassignDueDate) payload.due_at = new Date(reassignDueDate).toISOString();

      await api.patch(`/tasks/${reassigningTask.id}`, payload);
      setReassigningTask(null);
      await fetchTasks();
    } catch (err: any) {
      alert(err.message || 'Failed to reassign task');
    } finally {
      setIsReassigning(false);
    }
  };

  const resetFilters = () => {
    setCategory('ALL');
    setAssignedUserFilter('');
    setPriorityFilter('');
    setStatusFilter('');
    setOverdueOnly(false);
  };

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
              {isRTL ? "إدارة المهام والإجراءات للفريق" : "Team Tasks & Action Center"}
            </h1>
            <span className="badge badge-accent text-xs">
              {total} {isRTL ? "مهمة مسجلة" : "Total Tasks"}
            </span>
          </div>
          <p className="text-sm text-muted" style={{ marginTop: '2px' }}>
            {isRTL
              ? "متابعة وتعيين مهام التواصل، الإجراءات المجدولة، والمهام الداخلية لجميع مندوبي المبيعات."
              : "Monitor, create, and reassign communication tasks, scheduled customer actions, and internal assignments."}
          </p>
        </div>
        <div style={{ display: 'flex', gap: 'var(--space-3)' }}>
          <button
            onClick={() => {
              setShowNoAnswerModal(true);
              fetchNoAnswerLeads();
            }}
            className="btn btn-secondary btn-md"
            style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}
          >
            <PhoneCall size={16} style={{ color: 'var(--color-primary)' }} />
            <span>{isRTL ? "إعادة الاتصال بالعملاء (لم يرد)" : "Recontact No-Answer Leads"}</span>
          </button>

          <button onClick={() => setShowCreateModal(true)} className="btn btn-accent btn-md">
            <Plus size={16} />
            <span>{isRTL ? "إسناد مهمة جديدة" : "Assign New Task"}</span>
          </button>
        </div>
      </div>

      {/* Category Navigation Tabs */}
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
          onClick={() => setCategory('ALL')}
          className={`btn ${category === 'ALL' ? 'btn-accent' : 'btn-secondary'} btn-sm`}
        >
          {isRTL ? "جميع المهام" : "All Tasks"} ({total})
        </button>
        <button
          onClick={() => setCategory('COMMUNICATION')}
          className={`btn ${category === 'COMMUNICATION' ? 'btn-accent' : 'btn-secondary'} btn-sm`}
          style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
        >
          <Mail size={15} />
          <span>{isRTL ? "1. مهام التواصل (إيميل / واتساب)" : "1. Communication Requests"}</span>
        </button>
        <button
          onClick={() => setCategory('CUSTOMER_ACTION')}
          className={`btn ${category === 'CUSTOMER_ACTION' ? 'btn-accent' : 'btn-secondary'} btn-sm`}
          style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
        >
          <Clock size={15} />
          <span>{isRTL ? "2. الإجراءات المجدولة للعملاء" : "2. Scheduled Customer Actions"}</span>
        </button>
        <button
          onClick={() => setCategory('INTERNAL_ASSIGNED')}
          className={`btn ${category === 'INTERNAL_ASSIGNED' ? 'btn-accent' : 'btn-secondary'} btn-sm`}
          style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
        >
          <UserCheck size={15} />
          <span>{isRTL ? "3. المهام الداخلية المسندة" : "3. Assigned Internal Tasks"}</span>
        </button>
      </div>

      {/* Filter Bar */}
      <div
        className="card"
        style={{
          padding: 'var(--space-4)',
          display: 'flex',
          gap: 'var(--space-3)',
          flexWrap: 'wrap',
          alignItems: 'center',
        }}
      >
        {/* User Filter */}
        <select
          className="form-select text-xs"
          style={{ width: '180px' }}
          value={assignedUserFilter}
          onChange={(e) => setAssignedUserFilter(e.target.value)}
        >
          <option value="">{isRTL ? "جميع الموظفين" : "All Assigned Reps"}</option>
          {usersList.map((u) => (
            <option key={u.id} value={u.id}>
              👤 {u.full_name} ({u.role})
            </option>
          ))}
        </select>

        {/* Priority Filter */}
        <select
          className="form-select text-xs"
          style={{ width: '150px' }}
          value={priorityFilter}
          onChange={(e) => setPriorityFilter(e.target.value)}
        >
          <option value="">{isRTL ? "جميع الأولويات" : "All Priorities"}</option>
          <option value="HIGH">{isRTL ? "عالية (High)" : "High Priority 🔴"}</option>
          <option value="MEDIUM">{isRTL ? "متوسطة (Medium)" : "Medium Priority 🟡"}</option>
          <option value="LOW">{isRTL ? "منخفضة (Low)" : "Low Priority 🟢"}</option>
        </select>

        {/* Status Filter */}
        <select
          className="form-select text-xs"
          style={{ width: '150px' }}
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
        >
          <option value="">{isRTL ? "جميع الحالات" : "All Statuses"}</option>
          <option value="OPEN">{isRTL ? "مفتوحة (Open)" : "Open"}</option>
          <option value="IN_PROGRESS">{isRTL ? "قيد التنفيذ" : "In Progress"}</option>
          <option value="COMPLETED">{isRTL ? "مكتملة" : "Completed"}</option>
          <option value="OVERDUE">{isRTL ? "متأخرة" : "Overdue"}</option>
        </select>

        {/* Overdue Toggle Chip */}
        <button
          type="button"
          onClick={() => setOverdueOnly(!overdueOnly)}
          className={`btn btn-sm ${overdueOnly ? 'btn-danger' : 'btn-secondary'}`}
          style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px' }}
        >
          <AlertCircle size={14} />
          <span>{isRTL ? "المتأخرة فقط" : "Overdue Only"}</span>
        </button>

        {(assignedUserFilter || priorityFilter || statusFilter || overdueOnly || category !== 'ALL') && (
          <button
            onClick={resetFilters}
            className="btn btn-secondary btn-sm text-xs"
          >
            {isRTL ? "إلغاء التصفية" : "Clear Filters"}
          </button>
        )}
      </div>

      {/* Tasks Table */}
      {isLoading ? (
        <LoadingSpinner message={isRTL ? "جاري تحميل جدول المهام..." : "Loading task queue..."} />
      ) : tasks.length === 0 ? (
        <EmptyState
          title={isRTL ? "لا توجد مهام مطابقة" : "No tasks found"}
          description={isRTL ? "لا توجد مهام تطابق خيارات التصفية الحالية." : "There are no tasks matching your selected category and filter."}
          action={
            <button onClick={() => setShowCreateModal(true)} className="btn btn-accent btn-sm">
              {isRTL ? "إنشاء مهمة جديدة" : "Create New Task"}
            </button>
          }
        />
      ) : (
        <div className="table-container custom-scrollbar" style={{ overflowX: 'auto' }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>{isRTL ? "الحالة" : "Status"}</th>
                <th>{isRTL ? "عنوان المهمة والتصنيف" : "Task Title & Category"}</th>
                <th>{isRTL ? "الأولوية" : "Priority"}</th>
                <th>{isRTL ? "الموظف المسند إليه" : "Assigned Rep"}</th>
                <th>{isRTL ? "العميل / الشركة" : "Related Contact"}</th>
                <th>{isRTL ? "الموعد النهائي" : "Due Date"}</th>
                <th>{isRTL ? "الإجراء" : "Actions"}</th>
              </tr>
            </thead>
            <tbody>
              {tasks.map((t: any) => {
                const isOverdue = t.due_at && new Date(t.due_at) < new Date() && t.status !== 'COMPLETED';
                return (
                  <tr key={t.id}>
                    <td>
                      <span
                        className={`badge ${
                          t.status === 'COMPLETED'
                            ? 'badge-won'
                            : isOverdue || t.status === 'OVERDUE'
                            ? 'badge-lost'
                            : 'badge-new'
                        }`}
                      >
                        {isOverdue && t.status !== 'COMPLETED' ? 'OVERDUE' : t.status}
                      </span>
                    </td>
                    <td>
                      <div className="font-semibold text-sm" style={{ color: 'var(--neutral-900)' }}>
                        {t.title}
                      </div>
                      <div className="text-xs text-muted" style={{ marginTop: '2px' }}>
                        {t.category === 'COMMUNICATION'
                          ? '✉️ Communication Request'
                          : t.category === 'CUSTOMER_ACTION'
                          ? '⏰ Scheduled Customer Action'
                          : '📋 Assigned Internal Task'}{' '}
                        • Type: {t.type}
                      </div>
                    </td>
                    <td>
                      <span
                        style={{
                          fontSize: '11px',
                          fontWeight: '700',
                          padding: '2px 8px',
                          borderRadius: 'var(--radius-sm)',
                          backgroundColor:
                            t.priority === 'HIGH' || t.priority === 'URGENT'
                              ? 'var(--color-danger-bg)'
                              : t.priority === 'MEDIUM'
                              ? 'var(--color-warning-bg)'
                              : 'var(--bg-subtle)',
                          color:
                            t.priority === 'HIGH' || t.priority === 'URGENT'
                              ? 'var(--color-danger-text)'
                              : t.priority === 'MEDIUM'
                              ? 'var(--color-warning-text)'
                              : 'var(--neutral-600)',
                          border: '1px solid var(--border-color)',
                        }}
                      >
                        {t.priority}
                      </span>
                    </td>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <span className="badge badge-secondary text-xs" style={{ fontWeight: 600 }}>
                          {t.assignee_name || 'Unassigned'}
                        </span>
                        {/* Reassign Button */}
                        <button
                          onClick={() => {
                            setReassigningTask(t);
                            setReassignTargetUserId(t.assigned_to || '');
                            setReassignPriority(t.priority || 'MEDIUM');
                            setReassignDueDate(t.due_at ? t.due_at.slice(0, 16) : '');
                          }}
                          className="btn btn-ghost btn-sm"
                          style={{ padding: '2px 4px', height: '22px' }}
                          title="Reassign Task"
                        >
                          <Edit3 size={13} style={{ color: 'var(--neutral-500)' }} />
                        </button>
                      </div>
                      {t.creator_name && (
                        <div className="text-xs text-muted" style={{ marginTop: '2px' }}>
                          By: {t.creator_name}
                        </div>
                      )}
                    </td>
                    <td>
                      <div className="font-medium text-sm" style={{ color: 'var(--neutral-900)' }}>
                        {t.contact_name || '—'}
                      </div>
                      {t.company_name && <div className="text-xs text-muted">{t.company_name}</div>}
                    </td>
                    <td>
                      <span
                        className="text-xs font-medium"
                        style={{
                          color: isOverdue ? 'var(--color-danger)' : 'var(--neutral-600)',
                        }}
                      >
                        {t.due_at ? new Date(t.due_at).toLocaleDateString() : 'No deadline'}
                      </span>
                    </td>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                        {t.status !== 'COMPLETED' && (
                          <button
                            onClick={() => handleComplete(t.id)}
                            className="btn btn-secondary btn-sm"
                            style={{ display: 'flex', alignItems: 'center', gap: '4px' }}
                          >
                            <CheckCircle2 size={14} style={{ color: 'var(--color-success)' }} />
                            <span>{isRTL ? "إكمال" : "Done"}</span>
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* ── Reassign Task Modal ────────────────────────────────────────── */}
      <Modal
        isOpen={!!reassigningTask}
        onClose={() => setReassigningTask(null)}
        title={isRTL ? "إعادة تعيين وتعديل المهمة" : "Reassign & Update Task"}
        footer={
          <>
            <button
              type="button"
              onClick={() => setReassigningTask(null)}
              className="btn btn-secondary"
            >
              {isRTL ? "إلغاء" : "Cancel"}
            </button>
            <button
              type="button"
              disabled={isReassigning}
              onClick={handleReassignSubmit}
              className="btn btn-accent"
            >
              {isReassigning ? (isRTL ? 'جاري الحفظ...' : 'Saving...') : (isRTL ? 'تأكيد التعديل' : 'Save Changes')}
            </button>
          </>
        }
      >
        <form onSubmit={handleReassignSubmit}>
          <div style={{ marginBottom: 'var(--space-4)', padding: 'var(--space-3)', backgroundColor: 'var(--bg-subtle)', borderRadius: 'var(--radius-md)' }}>
            <div className="text-xs text-muted">TASK DETAILS</div>
            <div className="font-bold text-sm" style={{ color: 'var(--neutral-900)', marginTop: '2px' }}>
              {reassigningTask?.title}
            </div>
            <div className="text-xs text-muted" style={{ marginTop: '2px' }}>
              Current Assignee: <strong>{reassigningTask?.assignee_name || 'Unassigned'}</strong>
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">{isRTL ? "الموظف المسؤول الجديد *" : "Assign To Rep *"}</label>
            <select
              className="form-select"
              value={reassignTargetUserId}
              onChange={(e) => setReassignTargetUserId(e.target.value)}
            >
              <option value="">{isRTL ? "-- اختر الموظف --" : "-- Select Sales Agent --"}</option>
              {usersList.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.full_name} ({u.role})
                </option>
              ))}
            </select>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-3)' }}>
            <div className="form-group">
              <label className="form-label">{isRTL ? "الأولوية" : "Priority"}</label>
              <select
                className="form-select"
                value={reassignPriority}
                onChange={(e) => setReassignPriority(e.target.value)}
              >
                <option value="HIGH">High Priority</option>
                <option value="MEDIUM">Medium Priority</option>
                <option value="LOW">Low Priority</option>
              </select>
            </div>

            <div className="form-group">
              <label className="form-label">{isRTL ? "الموعد النهائي" : "Due Date"}</label>
              <input
                type="datetime-local"
                className="form-input"
                value={reassignDueDate}
                onChange={(e) => setReassignDueDate(e.target.value)}
              />
            </div>
          </div>
        </form>
      </Modal>

      {/* ── Create Internal Task Modal ─────────────────────────────────── */}
      <Modal
        isOpen={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        title={isRTL ? "إسناد مهمة داخلية جديدة" : "Assign Internal Task"}
        footer={
          <>
            <button
              type="button"
              onClick={() => setShowCreateModal(false)}
              className="btn btn-secondary"
            >
              {isRTL ? "إلغاء" : "Cancel"}
            </button>
            <button
              type="button"
              disabled={isCreating || !newTitle}
              onClick={handleCreateTask}
              className="btn btn-accent"
            >
              {isCreating ? (isRTL ? 'جاري الحفظ...' : 'Saving...') : (isRTL ? 'إسناد المهمة' : 'Assign Task')}
            </button>
          </>
        }
      >
        <form onSubmit={handleCreateTask}>
          <div className="form-group">
            <label className="form-label">{isRTL ? "عنوان المهمة *" : "Task Title *"}</label>
            <input
              type="text"
              required
              className="form-input"
              placeholder="e.g. Review legal terms with Saudi procurement team"
              value={newTitle}
              onChange={(e) => setNewTitle(e.target.value)}
            />
          </div>

          <div className="form-group">
            <label className="form-label">{isRTL ? "الموظف المسند إليه" : "Assign To Sales Agent"}</label>
            <select
              className="form-select"
              value={newAssignedTo}
              onChange={(e) => setNewAssignedTo(e.target.value)}
            >
              <option value="">{isRTL ? "أنا (المستخدم الحالي)" : "Me (Current User)"}</option>
              {usersList.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.full_name} ({u.role})
                </option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label className="form-label">{isRTL ? "التفاصيل والتعليمات" : "Description / Instructions"}</label>
            <textarea
              className="form-textarea"
              rows={3}
              placeholder="Enter instructions, notes, or background context..."
              value={newDescription}
              onChange={(e) => setNewDescription(e.target.value)}
            />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-3)' }}>
            <div className="form-group">
              <label className="form-label">{isRTL ? "الأولوية *" : "Priority *"}</label>
              <select
                className="form-select"
                value={newPriority}
                onChange={(e) => setNewPriority(e.target.value as any)}
              >
                <option value="HIGH">High Priority</option>
                <option value="MEDIUM">Medium Priority</option>
                <option value="LOW">Low Priority</option>
              </select>
            </div>

            <div className="form-group">
              <label className="form-label">{isRTL ? "الموعد النهائي" : "Due Date"}</label>
              <input
                type="datetime-local"
                className="form-input"
                value={newDueDate}
                onChange={(e) => setNewDueDate(e.target.value)}
              />
            </div>
          </div>
        </form>
      </Modal>

      {/* ── Recontact No-Answer Leads Panel ───────────────────────────── */}
      <Modal
        isOpen={showNoAnswerModal}
        onClose={() => setShowNoAnswerModal(false)}
        title={isRTL ? "إعادة الاتصال بالعملاء (قائمة عدم الرد)" : "Recontact No-Answer Leads Pool"}
        footer={
          <button
            type="button"
            onClick={() => setShowNoAnswerModal(false)}
            className="btn btn-secondary"
          >
            {isRTL ? "إغلاق" : "Close"}
          </button>
        }
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
          <p className="text-xs text-muted" style={{ margin: 0 }}>
            {isRTL
              ? "جهات الاتصال التي تم تسجيل نتيجة اتصال سابقة لها كـ 'لم يرد' ومتاحة لإعادة الاتصال الفوري."
              : "Contacts whose previous call outcome was recorded as 'No Answer', queued for immediate retry."}
          </p>

          {loadingNoAnswer ? (
            <LoadingSpinner message={isRTL ? "جاري جلب القائمة..." : "Loading no-answer leads..."} />
          ) : noAnswerLeads.length === 0 ? (
            <div style={{ textAlign: 'center', padding: 'var(--space-6)', color: 'var(--neutral-500)' }}>
              {isRTL ? "لا توجد جهات اتصال بحالة عدم الرد حالياً" : "No contacts currently in No-Answer queue"}
            </div>
          ) : (
            <div style={{ maxHeight: '420px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
              {noAnswerLeads.map((contact) => (
                <div
                  key={contact.id}
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    padding: 'var(--space-3)',
                    backgroundColor: 'var(--bg-subtle)',
                    borderRadius: 'var(--radius-md)',
                    border: '1px solid var(--border-light)',
                    gap: 'var(--space-3)',
                  }}
                >
                  <div>
                    <div className="font-semibold text-sm" style={{ color: 'var(--neutral-900)' }}>
                      {contact.full_name}
                    </div>
                    <div className="text-xs text-muted">
                      {contact.company_name || 'No Company'} • {contact.phone || 'No Phone'}
                    </div>
                    <div className="text-xs text-muted" style={{ marginTop: '2px' }}>
                      {contact.attempt_count || 0} {isRTL ? 'محاولات سابقة' : 'attempts'} • Owner: <strong>{contact.owner_name || 'Unassigned'}</strong>
                    </div>
                  </div>

                  <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
                    <a
                      href={`tel:${contact.phone}`}
                      className="btn btn-accent btn-sm"
                      style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', textDecoration: 'none' }}
                    >
                      <PhoneCall size={13} />
                      <span>{isRTL ? "اتصال" : "Call"}</span>
                    </a>
                    <button
                      type="button"
                      onClick={() => (window.location.href = `/contacts/${contact.id}`)}
                      className="btn btn-secondary btn-sm"
                    >
                      {isRTL ? "الملف" : "Profile"}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </Modal>
    </div>
  );
};
