import React, { useState, useEffect } from 'react';
import { api } from '../../lib/apiClient';
import { useAuthStore } from '../../store/authStore';
import { LoadingSpinner } from '../../components/feedback/LoadingSpinner';
import { EmptyState } from '../../components/feedback/EmptyState';
import { Badge } from '../../components/ui/Badge';
import {
  Clock,
  PhoneCall,
  Mail,
  MessageSquare,
  Presentation,
  CheckCircle2,
  Filter,
  UserCheck,
  TrendingUp,
  RotateCcw,
  Calendar,
  Layers,
  ArrowRight,
  ShieldCheck,
  Zap,
} from 'lucide-react';
import { useTranslation } from '../../i18n';

interface ActivityItem {
  type: string;
  id: string;
  timestamp: string;
  actor_id?: string;
  actor_name: string;
  title: string;
  subtitle?: string;
  outcome?: string;
  notes?: string;
  details?: string;
  link?: string;
}

export const TeamActivityPage: React.FC = () => {
  const { user } = useAuthStore();
  const { t, isRTL } = useTranslation();

  const [activities, setActivities] = useState<ActivityItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [isLoading, setIsLoading] = useState(true);

  // Filters State
  const [preset, setPreset] = useState<string>('today');
  const [selectedUserId, setSelectedUserId] = useState<string>('');
  const [activityType, setActivityType] = useState<string>('ALL');
  const [usersList, setUsersList] = useState<any[]>([]);

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

  const fetchActivities = async () => {
    setIsLoading(true);
    try {
      const params: Record<string, any> = {
        page,
        per_page: 30,
        preset: preset || undefined,
      };
      if (selectedUserId) params.user_id = selectedUserId;
      if (activityType !== 'ALL') params.activity_type = activityType;

      const res = await api.get<any>('/reports/team-activity', params);
      setActivities(res.data || []);
      setTotal(res.meta?.total || 0);
      setTotalPages(res.meta?.total_pages || 1);
    } catch (e) {
      console.error('Failed to load team activity', e);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchActivities();
  }, [page, preset, selectedUserId, activityType]);

  const getActivityIcon = (type: string) => {
    switch (type) {
      case 'CALL':
        return <PhoneCall size={16} color="var(--color-accent)" />;
      case 'TASK_COMPLETED':
        return <CheckCircle2 size={16} color="var(--color-success)" />;
      case 'DEMO':
        return <Presentation size={16} color="#8b5cf6" />;
      case 'OPPORTUNITY_STEP':
        return <TrendingUp size={16} color="#0284c7" />;
      case 'MANAGEMENT_ACTION':
        return <ShieldCheck size={16} color="#d97706" />;
      default:
        return <Zap size={16} color="var(--neutral-600)" />;
    }
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
              {isRTL ? "سجل نشاط الفريق الحي" : "Team Activity Timeline"}
            </h1>
            <span className="badge badge-accent text-xs">
              {total} {isRTL ? "نشاط مسجل" : "Live Events"}
            </span>
          </div>
          <p className="text-sm text-muted" style={{ marginTop: '2px' }}>
            {isRTL
              ? "متابعة لحظية وموحدة لكافة مكالمات الفريق، المهام المنجزة، العروض المحجوزة، وإجراءات إعادة التعيين."
              : "Real-time consolidated stream of all team calls, completed tasks, scheduled demos, and portfolio management actions."}
          </p>
        </div>

        {/* Date Presets */}
        <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
          {['today', 'this_week', 'last_7_days', 'this_month', 'all'].map((p) => {
            const labels: Record<string, { en: string; ar: string }> = {
              today: { en: 'Today', ar: 'اليوم' },
              this_week: { en: 'This Week', ar: 'هذا الأسبوع' },
              last_7_days: { en: 'Last 7 Days', ar: 'آخر 7 أيام' },
              this_month: { en: 'This Month', ar: 'هذا الشهر' },
              all: { en: 'All Time', ar: 'الكل' },
            };
            return (
              <button
                key={p}
                onClick={() => {
                  setPreset(p);
                  setPage(1);
                }}
                className={`btn btn-sm ${preset === p ? 'btn-primary' : 'btn-secondary'}`}
                style={{ fontSize: '12px', padding: '4px 10px' }}
              >
                {isRTL ? labels[p].ar : labels[p].en}
              </button>
            );
          })}
        </div>
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
          value={selectedUserId}
          onChange={(e) => {
            setSelectedUserId(e.target.value);
            setPage(1);
          }}
        >
          <option value="">{isRTL ? "جميع الموظفين" : "All Sales Reps"}</option>
          {usersList.map((u) => (
            <option key={u.id} value={u.id}>
              👤 {u.full_name} ({u.role})
            </option>
          ))}
        </select>

        {/* Activity Type Filter */}
        <select
          className="form-select text-xs"
          style={{ width: '180px' }}
          value={activityType}
          onChange={(e) => {
            setActivityType(e.target.value);
            setPage(1);
          }}
        >
          <option value="ALL">{isRTL ? "جميع أنواع الأنشطة" : "All Activity Types"}</option>
          <option value="CALL">{isRTL ? "المكالمات الصادرة" : "Calls"}</option>
          <option value="TASK">{isRTL ? "المهام المكتملة" : "Completed Tasks"}</option>
          <option value="DEMO">{isRTL ? "العروض التجريبية" : "Demos"}</option>
          <option value="OPPORTUNITY">{isRTL ? "محطات الفرص البيعية" : "Opportunity Milestones"}</option>
          <option value="ASSIGNMENT">{isRTL ? "إجراءات التعيين والإدارة" : "Management Actions"}</option>
        </select>

        {(selectedUserId || activityType !== 'ALL' || preset !== 'today') && (
          <button
            onClick={() => {
              setSelectedUserId('');
              setActivityType('ALL');
              setPreset('today');
              setPage(1);
            }}
            className="btn btn-secondary btn-sm text-xs"
          >
            {isRTL ? "إلغاء التصفية" : "Clear Filters"}
          </button>
        )}
      </div>

      {/* Activities Timeline Feed */}
      {isLoading ? (
        <LoadingSpinner message={isRTL ? "جاري تحميل سجل النشاط..." : "Loading live activity feed..."} />
      ) : activities.length === 0 ? (
        <EmptyState
          title={isRTL ? "لا توجد أنشطة مسجلة للفترة المحددة" : "No activity events recorded"}
          description={isRTL ? "جرب توسيع نطاق الفترة الزمنية أو إزالة فلاتر الموظفين." : "Try selecting a broader date preset or removing user filters."}
        />
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
          {activities.map((act) => (
            <div
              key={act.id}
              className="card"
              style={{
                padding: 'var(--space-4) var(--space-5)',
                display: 'flex',
                alignItems: 'flex-start',
                justifyContent: 'space-between',
                gap: 'var(--space-4)',
                transition: 'all 0.15s ease',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: 'var(--space-3)' }}>
                {/* Type Icon Badge */}
                <div
                  style={{
                    width: '36px',
                    height: '36px',
                    borderRadius: 'var(--radius-md)',
                    backgroundColor: 'var(--neutral-100)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    flexShrink: 0,
                    marginTop: '2px',
                  }}
                >
                  {getActivityIcon(act.type)}
                </div>

                {/* Event Details */}
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', flexWrap: 'wrap' }}>
                    <span className="font-semibold text-sm" style={{ color: 'var(--neutral-900)' }}>
                      {act.title}
                    </span>
                    {act.subtitle && (
                      <span className="text-xs text-muted">
                        • {act.subtitle}
                      </span>
                    )}
                  </div>

                  {act.notes && (
                    <p className="text-xs text-muted" style={{ marginTop: '4px', lineHeight: '1.4' }}>
                      📝 {act.notes}
                    </p>
                  )}

                  <div className="text-xs text-muted" style={{ display: 'flex', gap: 'var(--space-3)', marginTop: '4px' }}>
                    <span>{act.details}</span>
                    {act.actor_name && (
                      <>
                        <span>•</span>
                        <span>By: <strong>{act.actor_name}</strong></span>
                      </>
                    )}
                  </div>
                </div>
              </div>

              {/* Timestamp & Outcome Badge */}
              <div style={{ textAlign: isRTL ? 'left' : 'right', flexShrink: 0 }}>
                {act.outcome && (
                  <Badge variant={act.outcome === 'INTERESTED' || act.outcome === 'COMPLETED' ? 'success' : 'accent'}>
                    {act.outcome}
                  </Badge>
                )}
                <div className="text-xs text-muted" style={{ marginTop: '4px' }}>
                  {new Date(act.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} •{' '}
                  {new Date(act.timestamp).toLocaleDateString()}
                </div>
              </div>
            </div>
          ))}

          {/* Pagination */}
          <div
            style={{
              padding: 'var(--space-3) var(--space-4)',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              backgroundColor: 'var(--neutral-50)',
              borderRadius: 'var(--radius-lg)',
              border: '1px solid var(--border-color)',
              fontSize: 'var(--text-xs)',
              color: 'var(--neutral-600)',
            }}
          >
            <div>
              {isRTL ? `عرض ${activities.length} من أصل ${total} نشاط` : `Showing ${activities.length} of ${total} events`}
            </div>
            <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
              <button
                disabled={page <= 1}
                onClick={() => setPage((p) => p - 1)}
                className="btn btn-secondary btn-sm"
              >
                {isRTL ? "السابق" : "Previous"}
              </button>
              <span style={{ display: 'flex', alignItems: 'center', padding: '0 8px' }}>
                {isRTL ? `صفحة ${page} من ${totalPages}` : `Page ${page} of ${totalPages}`}
              </span>
              <button
                disabled={page >= totalPages}
                onClick={() => setPage((p) => p + 1)}
                className="btn btn-secondary btn-sm"
              >
                {isRTL ? "التالي" : "Next"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
