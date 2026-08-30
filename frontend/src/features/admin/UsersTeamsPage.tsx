import React, { useState, useEffect } from 'react';
import { api } from '../../lib/apiClient';
import { User } from '../../types';
import { Modal } from '../../components/ui/Modal';
import { LoadingSpinner } from '../../components/feedback/LoadingSpinner';
import { useTranslation } from '../../i18n';
import { UserCog, Plus, Shield, Users, Edit3, UserCheck, UserX, CheckCircle2, AlertCircle } from 'lucide-react';

export const UsersTeamsPage: React.FC = () => {
  const { t, isRTL } = useTranslation();
  const [users, setUsers] = useState<User[]>([]);
  const [teams, setTeams] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [feedback, setFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  // New User Modal
  const [showAddUserModal, setShowAddUserModal] = useState(false);
  const [newEmail, setNewEmail] = useState('');
  const [newFirstName, setNewFirstName] = useState('');
  const [newLastName, setNewLastName] = useState('');
  const [newPassword, setNewPassword] = useState('Welcome123!');
  const [newRole, setNewRole] = useState('USER');
  const [newTeamId, setNewTeamId] = useState('');
  const [newCapacity, setNewCapacity] = useState('500');
  const [isCreating, setIsCreating] = useState(false);

  // Edit User Modal
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [editFirstName, setEditFirstName] = useState('');
  const [editLastName, setEditLastName] = useState('');
  const [editRole, setEditRole] = useState('USER');
  const [editTeamId, setEditTeamId] = useState('');
  const [editCapacity, setEditCapacity] = useState('500');
  const [editIsActive, setEditIsActive] = useState(true);
  const [isUpdating, setIsUpdating] = useState(false);

  const fetchUsersAndTeams = async () => {
    setIsLoading(true);
    try {
      const [uRes, tRes] = await Promise.all([
        api.get<any>('/users'),
        api.get<any>('/teams'),
      ]);
      setUsers(uRes.data || []);
      setTeams(tRes.data || []);
    } catch (e) {
      console.error('Failed to load users & teams', e);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchUsersAndTeams();
  }, []);

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsCreating(true);
    setFeedback(null);
    try {
      await api.post('/users', {
        email: newEmail,
        first_name: newFirstName,
        last_name: newLastName,
        password: newPassword,
        role: newRole,
        team_id: newTeamId || null,
        lead_capacity: parseInt(newCapacity) || 500,
      });
      setShowAddUserModal(false);
      setNewEmail('');
      setNewFirstName('');
      setNewLastName('');
      setNewTeamId('');
      await fetchUsersAndTeams();
      setFeedback({
        type: 'success',
        message: isRTL ? 'تم إنشاء الحساب بنجاح وتعيين الصلاحيات' : 'User account created successfully.',
      });
    } catch (err: any) {
      setFeedback({
        type: 'error',
        message: err.message || 'Failed to create user',
      });
    } finally {
      setIsCreating(false);
    }
  };

  const openEditModal = (user: User) => {
    setEditingUser(user);
    setEditFirstName(user.first_name);
    setEditLastName(user.last_name);
    setEditRole(user.role === 'ADMIN' || user.role === 'TEAM_LEADER' ? 'TEAM_LEAD' : user.role === 'SALES_USER' ? 'USER' : user.role);
    setEditTeamId(user.team_id || '');
    setEditCapacity(String(user.lead_capacity || 500));
    setEditIsActive(user.is_active);
  };

  const handleUpdateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingUser) return;
    setIsUpdating(true);
    setFeedback(null);
    try {
      await api.patch(`/users/${editingUser.id}`, {
        first_name: editFirstName,
        last_name: editLastName,
        role: editRole,
        team_id: editTeamId || null,
        lead_capacity: parseInt(editCapacity) || 500,
        is_active: editIsActive,
      });
      setEditingUser(null);
      await fetchUsersAndTeams();
      setFeedback({
        type: 'success',
        message: isRTL ? 'تم تحديث بيانات وصلاحيات المستخدم بنجاح' : 'User profile and permissions updated successfully.',
      });
    } catch (err: any) {
      setFeedback({
        type: 'error',
        message: err.message || 'Failed to update user',
      });
    } finally {
      setIsUpdating(false);
    }
  };

  const handleToggleStatus = async (user: User) => {
    setFeedback(null);
    try {
      if (user.is_active) {
        await api.post(`/users/${user.id}/disable`, {});
      } else {
        await api.post(`/users/${user.id}/reactivate`, {});
      }
      await fetchUsersAndTeams();
      setFeedback({
        type: 'success',
        message: isRTL ? 'تم تغيير حالة الحساب بنجاح' : 'Account status updated successfully.',
      });
    } catch (err: any) {
      setFeedback({
        type: 'error',
        message: err.message || 'Failed to toggle status',
      });
    }
  };

  const getRoleBadge = (role: string) => {
    if (role === 'TEAM_LEAD' || role === 'ADMIN' || role === 'TEAM_LEADER') {
      return (
        <span className="badge badge-demo" style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', fontWeight: 700 }}>
          {isRTL ? 'قائد الفريق' : 'Team Lead'}
        </span>
      );
    }
    if (role === 'MANAGER') {
      return (
        <span className="badge badge-interested" style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', fontWeight: 700 }}>
          {isRTL ? 'مدير عمليات' : 'Manager'}
        </span>
      );
    }
    return (
      <span className="badge badge-new" style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
        {isRTL ? 'مندوب مبيعات' : 'Sales User'}
      </span>
    );
  };

  if (isLoading) return <LoadingSpinner message={isRTL ? 'جاري تحميل المستخدمين والفرق...' : 'Loading user & team configurations...'} />;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-6)' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 'var(--space-4)' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
            <span style={{ padding: '6px', backgroundColor: 'rgba(14, 135, 235, 0.1)', borderRadius: 'var(--radius-md)', color: 'var(--color-accent)' }}>
              <UserCog size={22} />
            </span>
            <h1 className="font-display font-bold text-2xl" style={{ color: 'var(--neutral-900)' }}>
              {isRTL ? 'إدارة المستخدمين والفرق (Users & Teams)' : 'User Accounts & Team Management'}
            </h1>
          </div>
          <p className="text-sm text-muted" style={{ marginTop: '4px' }}>
            {isRTL
              ? 'إدارة حسابات النظام وفق النموذج الثلاثي (قائد الفريق، مدير العمليات، ومندوبي المبيعات)'
              : 'Manage system accounts under the 3-role operational hierarchy: Team Lead, Manager, and Sales User.'}
          </p>
        </div>
        <button onClick={() => setShowAddUserModal(true)} className="btn btn-accent btn-md">
          <Plus size={18} />
          <span>{isRTL ? 'إضافة مستخدم جديد' : 'Add System User'}</span>
        </button>
      </div>

      {/* Feedback Banner */}
      {feedback && (
        <div
          style={{
            padding: 'var(--space-3) var(--space-4)',
            backgroundColor: feedback.type === 'success' ? 'var(--color-success-bg)' : 'var(--color-danger-bg)',
            border: `1px solid ${feedback.type === 'success' ? 'var(--color-success-border)' : 'var(--color-danger-border)'}`,
            borderRadius: 'var(--radius-md)',
            color: feedback.type === 'success' ? 'var(--color-success-text)' : 'var(--color-danger-text)',
            fontSize: 'var(--text-sm)',
            display: 'flex',
            alignItems: 'center',
            gap: 'var(--space-2)',
          }}
        >
          {feedback.type === 'success' ? <CheckCircle2 size={18} /> : <AlertCircle size={18} />}
          <span>{feedback.message}</span>
        </div>
      )}

      {/* Teams Grid */}
      <div>
        <h3 className="card-title text-base" style={{ marginBottom: 'var(--space-3)' }}>
          {isRTL ? 'فرق العمل والمجموعات البيعية' : 'Active Sales & Regional Teams'}
        </h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 'var(--space-4)' }}>
          {teams.map((t) => (
            <div key={t.id} className="card" style={{ padding: 'var(--space-4)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-2)' }}>
                <span className="font-bold text-sm text-dark">{t.name}</span>
                <span className="badge badge-new">{t.member_count} {isRTL ? 'أعضاء' : 'members'}</span>
              </div>
              <p className="text-xs text-muted" style={{ minHeight: '32px' }}>
                {t.description || (isRTL ? 'لا يوجد وصف' : 'No description')}
              </p>
              <div style={{ fontSize: '11px', color: 'var(--neutral-600)', marginTop: 'var(--space-2)' }}>
                {isRTL ? 'مدير الفريق:' : 'Manager:'} <strong>{t.manager_name || (isRTL ? 'غير معين' : 'Unassigned')}</strong>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Users Table */}
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-3)' }}>
          <h3 className="card-title text-base">
            {isRTL ? `حسابات النظام النشطة (${users.length})` : `System Accounts (${users.length})`}
          </h3>
        </div>
        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>{isRTL ? 'اسم المستخدم' : 'User Full Name'}</th>
                <th>{isRTL ? 'البريد الإلكتروني' : 'Email Address'}</th>
                <th>{isRTL ? 'الدور والصلاحية' : 'System Role'}</th>
                <th>{isRTL ? 'الفريق المعين' : 'Assigned Team'}</th>
                <th>{isRTL ? 'الطاقة الاستيعابية' : 'Lead Capacity'}</th>
                <th>{isRTL ? 'الحالة' : 'Status'}</th>
                <th style={{ textAlign: 'right' }}>{isRTL ? 'الإجراءات' : 'Actions'}</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id}>
                  <td>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <div
                        style={{
                          width: '28px',
                          height: '28px',
                          borderRadius: '50%',
                          backgroundColor: 'var(--color-primary-subtle)',
                          color: 'var(--color-primary)',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          fontSize: '11px',
                          fontWeight: 700,
                        }}
                      >
                        {u.first_name?.[0]}
                      </div>
                      <span className="font-semibold text-sm text-dark">{u.full_name}</span>
                    </div>
                  </td>
                  <td>
                    <span className="text-sm text-muted">{u.email}</span>
                  </td>
                  <td>{getRoleBadge(u.role)}</td>
                  <td>
                    <span className="text-xs font-medium">{u.team_name || (isRTL ? 'عام / غير مخصص' : 'Global')}</span>
                  </td>
                  <td>
                    <span className="text-xs font-bold text-primary">{u.lead_capacity} {isRTL ? 'عميل' : 'leads'}</span>
                  </td>
                  <td>
                    <span className={`badge ${u.is_active ? 'badge-won' : 'badge-lost'}`}>
                      {u.is_active ? (isRTL ? 'نشط' : 'Active') : (isRTL ? 'معطل' : 'Disabled')}
                    </span>
                  </td>
                  <td style={{ textAlign: 'right' }}>
                    <div style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
                      <button
                        onClick={() => openEditModal(u)}
                        className="btn btn-secondary btn-sm"
                        style={{ padding: '4px 8px', fontSize: '11px', gap: '4px' }}
                      >
                        <Edit3 size={13} />
                        <span>{isRTL ? 'تعديل' : 'Edit'}</span>
                      </button>
                      <button
                        onClick={() => handleToggleStatus(u)}
                        className={`btn ${u.is_active ? 'btn-danger' : 'btn-accent'} btn-sm`}
                        style={{ padding: '4px 8px', fontSize: '11px', gap: '4px' }}
                      >
                        {u.is_active ? <UserX size={13} /> : <UserCheck size={13} />}
                        <span>{u.is_active ? (isRTL ? 'تعطيل' : 'Disable') : (isRTL ? 'تفعيل' : 'Activate')}</span>
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Add User Modal */}
      <Modal
        isOpen={showAddUserModal}
        onClose={() => setShowAddUserModal(false)}
        title={isRTL ? 'إضافة مستخدم جديد للنظام' : 'Add New System User'}
        footer={
          <>
            <button
              type="button"
              onClick={() => setShowAddUserModal(false)}
              className="btn btn-secondary"
            >
              {isRTL ? 'إلغاء' : 'Cancel'}
            </button>
            <button
              type="button"
              disabled={isCreating}
              onClick={handleCreateUser}
              className="btn btn-accent"
            >
              {isCreating ? (isRTL ? 'جاري الإنشاء...' : 'Creating...') : (isRTL ? 'إنشاء الحساب' : 'Create Account')}
            </button>
          </>
        }
      >
        <form onSubmit={handleCreateUser}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-3)' }}>
            <div className="form-group">
              <label className="form-label">{isRTL ? 'الاسم الأول *' : 'First Name *'}</label>
              <input
                type="text"
                required
                className="form-input"
                value={newFirstName}
                onChange={(e) => setNewFirstName(e.target.value)}
              />
            </div>
            <div className="form-group">
              <label className="form-label">{isRTL ? 'اسم العائلة *' : 'Last Name *'}</label>
              <input
                type="text"
                required
                className="form-input"
                value={newLastName}
                onChange={(e) => setNewLastName(e.target.value)}
              />
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">{isRTL ? 'البريد الإلكتروني *' : 'Email Address *'}</label>
            <input
              type="email"
              required
              className="form-input"
              value={newEmail}
              onChange={(e) => setNewEmail(e.target.value)}
            />
          </div>

          <div className="form-group">
            <label className="form-label">{isRTL ? 'كلمة المرور الأولية *' : 'Initial Password *'}</label>
            <input
              type="password"
              required
              className="form-input"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
            />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-3)' }}>
            <div className="form-group">
              <label className="form-label">{isRTL ? 'الدور التشغيلي' : 'Operational Role'}</label>
              <select
                className="form-select"
                value={newRole}
                onChange={(e) => setNewRole(e.target.value)}
              >
                <option value="USER">{isRTL ? 'مندوب مبيعات (User)' : 'Sales User'}</option>
                <option value="MANAGER">{isRTL ? 'مدير عمليات (Manager)' : 'Operational Manager'}</option>
                <option value="TEAM_LEAD">{isRTL ? 'قائد الفريق (Team Lead)' : 'Team Lead (Highest)'}</option>
              </select>
            </div>

            <div className="form-group">
              <label className="form-label">{isRTL ? 'الفريق المعين' : 'Assigned Team'}</label>
              <select
                className="form-select"
                value={newTeamId}
                onChange={(e) => setNewTeamId(e.target.value)}
              >
                <option value="">{isRTL ? 'بدون فريق (عام)' : 'No Team (Global)'}</option>
                {teams.map((t) => (
                  <option key={t.id} value={t.id}>{t.name}</option>
                ))}
              </select>
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">{isRTL ? 'سعة استيعاب العملاء' : 'Max Lead Capacity'}</label>
            <input
              type="number"
              className="form-input"
              value={newCapacity}
              onChange={(e) => setNewCapacity(e.target.value)}
            />
          </div>
        </form>
      </Modal>

      {/* Edit User Modal */}
      {editingUser && (
        <Modal
          isOpen={true}
          onClose={() => setEditingUser(null)}
          title={isRTL ? `تعديل بيانات المستخدم: ${editingUser.full_name}` : `Edit User Profile: ${editingUser.full_name}`}
          footer={
            <>
              <button
                type="button"
                onClick={() => setEditingUser(null)}
                className="btn btn-secondary"
              >
                {isRTL ? 'إلغاء' : 'Cancel'}
              </button>
              <button
                type="button"
                disabled={isUpdating}
                onClick={handleUpdateUser}
                className="btn btn-accent"
              >
                {isUpdating ? (isRTL ? 'جاري الحفظ...' : 'Saving...') : (isRTL ? 'حفظ التعديلات' : 'Save Changes')}
              </button>
            </>
          }
        >
          <form onSubmit={handleUpdateUser}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-3)' }}>
              <div className="form-group">
                <label className="form-label">{isRTL ? 'الاسم الأول' : 'First Name'}</label>
                <input
                  type="text"
                  required
                  className="form-input"
                  value={editFirstName}
                  onChange={(e) => setEditFirstName(e.target.value)}
                />
              </div>
              <div className="form-group">
                <label className="form-label">{isRTL ? 'اسم العائلة' : 'Last Name'}</label>
                <input
                  type="text"
                  required
                  className="form-input"
                  value={editLastName}
                  onChange={(e) => setEditLastName(e.target.value)}
                />
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-3)' }}>
              <div className="form-group">
                <label className="form-label">{isRTL ? 'الدور التشغيلي' : 'Operational Role'}</label>
                <select
                  className="form-select"
                  value={editRole}
                  onChange={(e) => setEditRole(e.target.value)}
                >
                  <option value="USER">{isRTL ? 'مندوب مبيعات (User)' : 'Sales User'}</option>
                  <option value="MANAGER">{isRTL ? 'مدير عمليات (Manager)' : 'Operational Manager'}</option>
                  <option value="TEAM_LEAD">{isRTL ? 'قائد الفريق (Team Lead)' : 'Team Lead'}</option>
                </select>
              </div>

              <div className="form-group">
                <label className="form-label">{isRTL ? 'الفريق المعين' : 'Assigned Team'}</label>
                <select
                  className="form-select"
                  value={editTeamId}
                  onChange={(e) => setEditTeamId(e.target.value)}
                >
                  <option value="">{isRTL ? 'بدون فريق (عام)' : 'No Team (Global)'}</option>
                  {teams.map((t) => (
                    <option key={t.id} value={t.id}>{t.name}</option>
                  ))}
                </select>
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-3)' }}>
              <div className="form-group">
                <label className="form-label">{isRTL ? 'سعة استيعاب العملاء' : 'Max Lead Capacity'}</label>
                <input
                  type="number"
                  className="form-input"
                  value={editCapacity}
                  onChange={(e) => setEditCapacity(e.target.value)}
                />
              </div>

              <div className="form-group" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', fontWeight: 600 }}>
                  <input
                    type="checkbox"
                    checked={editIsActive}
                    onChange={(e) => setEditIsActive(e.target.checked)}
                    style={{ width: '16px', height: '16px', accentColor: 'var(--color-accent)' }}
                  />
                  <span>{isRTL ? 'الحساب نشط (Active)' : 'Account Active'}</span>
                </label>
              </div>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
};
