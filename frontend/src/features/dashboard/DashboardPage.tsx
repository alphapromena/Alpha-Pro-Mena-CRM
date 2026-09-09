import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip as RechartsTooltip,
  PieChart,
  Pie,
  Cell,
  Legend,
  AreaChart,
  Area,
} from 'recharts';
import { api } from '../../lib/apiClient';
import { useAuthStore } from '../../store/authStore';
import { LoadingSpinner } from '../../components/feedback/LoadingSpinner';
import { Badge } from '../../components/ui/Badge';
import {
  PhoneCall,
  Users,
  Presentation,
  TrendingUp,
  AlertCircle,
  CheckCircle2,
  Mail,
  MessageSquare,
  Flame,
  Building,
  Clock,
  Filter,
  RefreshCw,
  Eye,
  Calendar,
  Award,
  ChevronRight,
  X,
  Target,
  ArrowUpRight,
  ArrowRight,
  AlertTriangle,
  CheckCircle,
  FileText,
  UserCheck,
  Zap,
  PhoneOff,
  Info,
  Briefcase,
  PieChart as PieChartIcon,
  BarChart2,
} from 'lucide-react';
import { useTranslation } from '../../i18n';

interface UserPerformanceRow {
  user_id: string;
  user_name: string;
  email: string;
  role: string;
  team_name?: string;
  calls: number;
  answered: number;
  interested: number;
  emails: number;
  whatsapp: number;
  demo_agreed: number;
  demo_done: number;
  demo_cancelled: number;
  demos_total?: number;
  demos_interested?: number;
  demos_pending?: number;
  demos_postponed?: number;
  demos_not_interested?: number;
  demos_cancelled_status?: number;
  demos_needs_report?: number;
  demos_report_complete?: number;
  report_completion_rate?: number;
  follow_ups: number;
  recalls: number;
  opportunities: number;
  opportunities_won: number;
  overdue_tasks: number;
  performance_score: number;
  answer_rate: number;
  interest_rate: number;
  conversions: {
    answer_rate: number;
    calls_to_interested: number;
    interested_to_demo: number;
    demo_to_opportunity: number;
  };
}

export const DashboardPage: React.FC = () => {
  const navigate = useNavigate();
  const { user } = useAuthStore();
  const { t, isRTL } = useTranslation();

  // Filters State — default to live operations ('today')
  const [preset, setPreset] = useState<string>('today');
  const [dateFrom, setDateFrom] = useState<string>('');
  const [dateTo, setDateTo] = useState<string>('');
  const [selectedUserId, setSelectedUserId] = useState<string>('');
  const [selectedTeamId, setSelectedTeamId] = useState<string>('');
  const [selectedCountry, setSelectedCountry] = useState<string>('');
  const [selectedOutcome, setSelectedOutcome] = useState<string>('');
  const [selectedDemoStage, setSelectedDemoStage] = useState<string>('');

  // Data State
  const [data, setData] = useState<any>(null);
  const [usersList, setUsersList] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);

  // Drilldown Modal State
  const [drilldownUserId, setDrilldownUserId] = useState<string | null>(null);
  const [drilldownData, setDrilldownData] = useState<any>(null);
  const [drilldownLoading, setDrilldownLoading] = useState<boolean>(false);
  const [drilldownTab, setDrilldownTab] = useState<'calls' | 'contacts' | 'tasks' | 'demos' | 'timeline'>('calls');
  const [activePerfTab, setActivePerfTab] = useState<'users' | 'managers'>('users');

  // Fetch Users for filter dropdown
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

  // Fetch Dashboard Data
  const fetchDashboard = async () => {
    setIsRefreshing(true);
    try {
      const params: Record<string, string> = {};
      if (preset) params.preset = preset;
      if (dateFrom) params.date_from = dateFrom;
      if (dateTo) params.date_to = dateTo;
      if (selectedUserId) params.user_id = selectedUserId;
      if (selectedTeamId) params.team_id = selectedTeamId;
      if (selectedCountry) params.country = selectedCountry;
      if (selectedOutcome) params.outcome = selectedOutcome;
      if (selectedDemoStage) params.demo_stage = selectedDemoStage;

      const queryString = new URLSearchParams(params).toString();
      const res = await api.get<any>(`/reports/dashboard?${queryString}`);
      setData(res.data);
    } catch (e) {
      console.error('Failed to load dashboard data', e);
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  };

  useEffect(() => {
    fetchDashboard();
  }, [preset, dateFrom, dateTo, selectedUserId, selectedTeamId, selectedCountry, selectedOutcome, selectedDemoStage]);

  // Fetch Drilldown details when selected
  useEffect(() => {
    if (!drilldownUserId) {
      setDrilldownData(null);
      return;
    }
    const fetchDrilldown = async () => {
      setDrilldownLoading(true);
      try {
        const res = await api.get<any>(`/reports/user-drilldown/${drilldownUserId}?preset=${preset}`);
        setDrilldownData(res.data);
      } catch (e) {
        console.error('Failed to load user drilldown data', e);
      } finally {
        setDrilldownLoading(false);
      }
    };
    fetchDrilldown();
  }, [drilldownUserId, preset]);

  if (isLoading && !data) {
    return <LoadingSpinner message={isRTL ? "جاري تحميل لوحة تحكم الإدارة..." : "Loading Manager Command Center..."} />;
  }

  const kpis = data?.kpis || {};
  const callsBreakdown = data?.calls_breakdown || {};
  const conversions = data?.conversion_metrics || {};
  const userPerformance: UserPerformanceRow[] = data?.user_performance || [];

  const resetFilters = () => {
    setPreset('this_month');
    setDateFrom('');
    setDateTo('');
    setSelectedUserId('');
    setSelectedTeamId('');
    setSelectedCountry('');
    setSelectedOutcome('');
    setSelectedDemoStage('');
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-6)' }}>
      {/* ── Top Header & Greeting ───────────────────────────────────────── */}
      <div
        style={{
          backgroundColor: 'var(--bg-surface)',
          padding: 'var(--space-5) var(--space-6)',
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
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
            <h1 className="font-display font-bold text-2xl" style={{ color: 'var(--neutral-900)' }}>
              {isRTL ? `مركز قيادة المبيعات — ${user?.first_name || 'المدير'}` : `Sales Team Command Center — ${user?.first_name || 'Manager'}`}
            </h1>
            <Badge variant="accent">{user?.role || 'MANAGER'}</Badge>
          </div>
          <p className="text-sm text-muted" style={{ marginTop: '2px' }}>
            {isRTL
              ? "مراقبة شاملة لأداء الفريق، المكالمات، رسائل البريد، الواتساب، العروض التوضيحية والفرص البيعية."
              : "Live operational intelligence: monitor team calls, emails, WhatsApp outreach, demos, and conversions."}
          </p>
        </div>

        <div style={{ display: 'flex', gap: 'var(--space-3)', alignItems: 'center', flexWrap: 'wrap' }}>
          <button
            onClick={() => navigate('/team-activity')}
            className="btn btn-secondary btn-sm"
            style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
          >
            <Clock size={15} />
            {isRTL ? "سجل نشاط الفريق" : "Team Activity Feed"}
          </button>

          <button
            onClick={() => navigate('/leads/pool')}
            className="btn btn-secondary btn-sm"
            style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
          >
            <Users size={15} />
            {isRTL ? "مستودع العملاء وتوزيعهم" : "Lead Pool & Distribute"}
          </button>

          <button
            onClick={fetchDashboard}
            disabled={isRefreshing}
            className="btn btn-primary btn-sm"
            style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
          >
            <RefreshCw size={15} className={isRefreshing ? 'animate-spin' : ''} />
            {isRTL ? "تحديث البيانات" : "Refresh"}
          </button>
        </div>
      </div>

      {/* ── Multi-Dimensional Filter Bar ───────────────────────────────── */}
      <div
        className="card"
        style={{
          padding: 'var(--space-4) var(--space-5)',
          backgroundColor: 'var(--bg-surface)',
          display: 'flex',
          flexDirection: 'column',
          gap: 'var(--space-3)',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 'var(--space-3)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
            <Filter size={18} style={{ color: 'var(--color-accent)' }} />
            <span className="font-semibold text-sm" style={{ color: 'var(--neutral-900)' }}>
              {isRTL ? "تصفية لوحة التحكم" : "Dashboard Filters"}
            </span>
          </div>

          <div style={{ display: 'flex', gap: 'var(--space-2)', alignItems: 'center', flexWrap: 'wrap' }}>
            {/* Date Preset Buttons */}
            {['today', 'this_week', 'last_7_days', 'this_month', 'all'].map((p) => {
              const labels: Record<string, { en: string; ar: string }> = {
                today: { en: 'Today', ar: 'اليوم' },
                this_week: { en: 'This Week', ar: 'هذا الأسبوع' },
                last_7_days: { en: 'Last 7 Days', ar: 'آخر 7 أيام' },
                this_month: { en: 'This Month', ar: 'هذا الشهر' },
                all: { en: 'All Time', ar: 'كل الفترات' },
              };
              const isSelected = preset === p && !dateFrom;
              return (
                <button
                  key={p}
                  onClick={() => {
                    setPreset(p);
                    setDateFrom('');
                    setDateTo('');
                  }}
                  className={`btn btn-sm ${isSelected ? 'btn-primary' : 'btn-secondary'}`}
                  style={{ fontSize: '12px', padding: '4px 10px' }}
                >
                  {isRTL ? labels[p].ar : labels[p].en}
                </button>
              );
            })}

            {(preset !== 'this_month' || selectedUserId || selectedCountry || selectedOutcome || selectedDemoStage || dateFrom) && (
              <button
                onClick={resetFilters}
                className="btn btn-ghost btn-sm text-xs text-muted"
                style={{ padding: '4px 8px' }}
              >
                {isRTL ? "إعادة تعيين" : "Reset Filters"}
              </button>
            )}
          </div>
        </div>

        {/* Filter Dropdowns Row */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))',
            gap: 'var(--space-3)',
            marginTop: 'var(--space-1)',
          }}
        >
          {/* User Filter */}
          <div>
            <label className="text-xs font-semibold text-muted block mb-1">
              {isRTL ? "المندوب / الموظف" : "Sales Agent / Rep"}
            </label>
            <select
              value={selectedUserId}
              onChange={(e) => setSelectedUserId(e.target.value)}
              className="input text-xs w-full"
            >
              <option value="">{isRTL ? "جميع المندوبين" : "All Sales Reps"}</option>
              {usersList.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.full_name} ({u.role})
                </option>
              ))}
            </select>
          </div>

          {/* Call Outcome Filter */}
          <div>
            <label className="text-xs font-semibold text-muted block mb-1">
              {isRTL ? "نتيجة الاتصال" : "Call Outcome"}
            </label>
            <select
              value={selectedOutcome}
              onChange={(e) => setSelectedOutcome(e.target.value)}
              className="input text-xs w-full"
            >
              <option value="">{isRTL ? "جميع النتائج" : "All Call Outcomes"}</option>
              <option value="INTERESTED">{isRTL ? "مهتم (Interested)" : "Interested"}</option>
              <option value="EMAIL_REQUESTED">{isRTL ? "طلب إيميل (Email Req)" : "Email Requested"}</option>
              <option value="WHATSAPP_REQUESTED">{isRTL ? "طلب واتساب (WhatsApp Req)" : "WhatsApp Requested"}</option>
              <option value="DEMO_REQUESTED">{isRTL ? "طلب عرض (Demo Req)" : "Demo Requested"}</option>
              <option value="CALL_LATER">{isRTL ? "إعادة اتصال (Call Later)" : "Call Later"}</option>
              <option value="NO_ANSWER">{isRTL ? "لم يرد (No Answer)" : "No Answer"}</option>
              <option value="ANSWERED">{isRTL ? "تم الرد (Answered)" : "General Answered"}</option>
              <option value="NOT_INTERESTED">{isRTL ? "غير مهتم (Not Interested)" : "Not Interested"}</option>
            </select>
          </div>

          {/* Demo Stage Filter */}
          <div>
            <label className="text-xs font-semibold text-muted block mb-1">
              {isRTL ? "حالة العرض التجريبي" : "Demo Stage"}
            </label>
            <select
              value={selectedDemoStage}
              onChange={(e) => setSelectedDemoStage(e.target.value)}
              className="input text-xs w-full"
            >
              <option value="">{isRTL ? "جميع العروض" : "All Demo Stages"}</option>
              <option value="AGREED">{isRTL ? "تم الاتفاق / مطلوب" : "Agreed / Requested"}</option>
              <option value="SCHEDULED">{isRTL ? "مجدول ومؤكد" : "Scheduled"}</option>
              <option value="COMPLETED">{isRTL ? "مكتمل بنجاح" : "Completed"}</option>
              <option value="CANCELLED">{isRTL ? "ملغي / لم يحضر" : "Cancelled / No Show"}</option>
            </select>
          </div>

          {/* Country Filter */}
          <div>
            <label className="text-xs font-semibold text-muted block mb-1">
              {isRTL ? "الدولة" : "Country"}
            </label>
            <select
              value={selectedCountry}
              onChange={(e) => setSelectedCountry(e.target.value)}
              className="input text-xs w-full"
            >
              <option value="">{isRTL ? "جميع الدول" : "All Countries"}</option>
              <option value="Saudi Arabia">{isRTL ? "المملكة العربية السعودية" : "Saudi Arabia"}</option>
              <option value="UAE">{isRTL ? "الإمارات العربية المتحدة" : "United Arab Emirates"}</option>
              <option value="Qatar">{isRTL ? "قطر" : "Qatar"}</option>
              <option value="Kuwait">{isRTL ? "الكويت" : "Kuwait"}</option>
              <option value="Bahrain">{isRTL ? "البحرين" : "Bahrain"}</option>
              <option value="Oman">{isRTL ? "عمان" : "Oman"}</option>
            </select>
          </div>

          {/* Custom Date Range */}
          <div>
            <label className="text-xs font-semibold text-muted block mb-1">
              {isRTL ? "من تاريخ" : "From Date"}
            </label>
            <input
              type="date"
              value={dateFrom}
              onChange={(e) => {
                setDateFrom(e.target.value);
                setPreset('');
              }}
              className="input text-xs w-full"
            />
          </div>

          <div>
            <label className="text-xs font-semibold text-muted block mb-1">
              {isRTL ? "إلى تاريخ" : "To Date"}
            </label>
            <input
              type="date"
              value={dateTo}
              onChange={(e) => {
                setDateTo(e.target.value);
                setPreset('');
              }}
              className="input text-xs w-full"
            />
          </div>
        </div>
      </div>

      {/* ── PRIMARY KPI Cards (4 most critical manager metrics) ─────────── */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
          gap: 'var(--space-4)',
        }}
      >
        {/* 1. Total Calls — primary outreach volume */}
        <MetricCard
          title={isRTL ? "إجمالي المكالمات الصادرة" : "Total Outbound Calls"}
          value={kpis.total_calls || 0}
          subtitle={`${kpis.unique_contacts || 0} ${isRTL ? 'جهة اتصال فريدة' : 'unique contacts'}`}
          icon={<PhoneCall size={22} />}
          color="var(--color-accent)"
          onClick={() => navigate('/contacts')}
          primary
        />

        {/* 2. Demo Agreed — pipeline entry signal */}
        <MetricCard
          title={isRTL ? "عروض تم الاتفاق عليها" : "Demos Agreed / Requested"}
          value={kpis.demo_agreed || 0}
          subtitle={isRTL ? "في انتظار الجدولة" : "Awaiting scheduling"}
          icon={<Presentation size={22} />}
          color="var(--color-accent)"
          onClick={() => navigate('/demos?status=PENDING')}
          primary
        />

        {/* 3. Opportunities — real pipeline value */}
        <MetricCard
          title={isRTL ? "الفرص وقيمة الصفقات" : "Opportunities & Pipeline"}
          value={kpis.opportunities || 0}
          subtitle={`$${(kpis.pipeline_value || 0).toLocaleString()} ${isRTL ? 'القيمة' : 'pipeline value'}`}
          icon={<TrendingUp size={22} />}
          color="var(--color-accent)"
          onClick={() => navigate('/opportunities')}
          primary
        />

        {/* 4. Overdue Team Tasks — urgency signal: red only when genuinely overdue */}
        <MetricCard
          title={isRTL ? "المهام المتأخرة للتنفيذ" : "Overdue Team Tasks"}
          value={kpis.overdue_tasks || 0}
          subtitle={isRTL ? "تتطلب متابعة إدارية" : "Urgent manager review"}
          icon={<AlertCircle size={22} />}
          color={kpis.overdue_tasks > 0 ? 'var(--color-danger)' : 'var(--color-accent)'}
          onClick={() => navigate('/tasks?overdue_only=true')}
          primary
          urgent={kpis.overdue_tasks > 0}
        />
      </div>

      {/* ── Personalized Sales Rep View (if not manager) ───────────────── */}
      {!data?.is_manager && data?.my_metrics && (
        <div
          className="card"
          style={{
            padding: 'var(--space-4) var(--space-5)',
            backgroundColor: 'rgba(255, 30, 87, 0.04)',
            border: '1px solid rgba(255, 30, 87, 0.25)',
            borderRadius: 'var(--radius-xl)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 'var(--space-3)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
              <Presentation size={18} style={{ color: '#FF1E57' }} />
              <h3 className="font-bold text-base" style={{ color: 'var(--neutral-900)' }}>
                {isRTL ? `مؤشرات عروضي الشخصية — ${user?.first_name}` : `My Personal Demo & Pipeline Overview — ${user?.first_name}`}
              </h3>
            </div>
            <span className="badge badge-accent text-xs">Personal Focus</span>
          </div>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
              gap: 'var(--space-3)',
            }}
          >
            <div
              onClick={() => navigate('/demos?status=ALL')}
              style={{ cursor: 'pointer', padding: 'var(--space-3)', backgroundColor: 'var(--bg-surface)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-light)' }}
            >
              <div className="text-xs text-muted">My Total Demos</div>
              <div className="font-bold text-xl" style={{ color: 'var(--neutral-900)', marginTop: '2px' }}>
                {data.my_metrics.my_total_demos || 0}
              </div>
            </div>

            <div
              onClick={() => navigate('/demos?status=INTERESTED_NEXT_STEP')}
              style={{ cursor: 'pointer', padding: 'var(--space-3)', backgroundColor: 'var(--bg-surface)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-light)' }}
            >
              <div className="text-xs text-muted">Interested / Next Step</div>
              <div className="font-bold text-xl" style={{ color: 'var(--color-success)', marginTop: '2px' }}>
                {data.my_metrics.my_interested_demos || 0}
              </div>
            </div>

            <div
              onClick={() => navigate('/demos?status=PENDING')}
              style={{ cursor: 'pointer', padding: 'var(--space-3)', backgroundColor: 'var(--bg-surface)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-light)' }}
            >
              <div className="text-xs text-muted">Pending Demos</div>
              <div className="font-bold text-xl" style={{ color: 'var(--color-primary)', marginTop: '2px' }}>
                {data.my_metrics.my_pending_demos || 0}
              </div>
            </div>

            <div
              onClick={() => navigate('/demos?report_status=NEEDS_REPORT')}
              style={{
                cursor: 'pointer',
                padding: 'var(--space-3)',
                backgroundColor: data.my_metrics.my_demos_needing_reports > 0 ? '#FEF3C7' : 'var(--bg-surface)',
                borderRadius: 'var(--radius-md)',
                border: data.my_metrics.my_demos_needing_reports > 0 ? '1px solid #F59E0B' : '1px solid var(--border-light)',
              }}
            >
              <div className="text-xs font-semibold" style={{ color: data.my_metrics.my_demos_needing_reports > 0 ? '#B45309' : 'var(--neutral-500)' }}>
                Demos Needing Reports
              </div>
              <div className="font-bold text-xl" style={{ color: data.my_metrics.my_demos_needing_reports > 0 ? '#B45309' : 'var(--neutral-900)', marginTop: '2px' }}>
                {data.my_metrics.my_demos_needing_reports || 0}
              </div>
            </div>

            <div
              onClick={() => navigate('/demos')}
              style={{ cursor: 'pointer', padding: 'var(--space-3)', backgroundColor: 'var(--bg-surface)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-light)' }}
            >
              <div className="text-xs text-muted">Upcoming Next Steps</div>
              <div className="font-bold text-xl" style={{ color: 'var(--color-accent)', marginTop: '2px' }}>
                {data.my_metrics.my_upcoming_next_steps || 0}
              </div>
            </div>

            <div
              onClick={() => navigate('/demos')}
              style={{
                cursor: 'pointer',
                padding: 'var(--space-3)',
                backgroundColor: data.my_metrics.my_overdue_next_steps > 0 ? '#FEE2E2' : 'var(--bg-surface)',
                borderRadius: 'var(--radius-md)',
                border: data.my_metrics.my_overdue_next_steps > 0 ? '1px solid #EF4444' : '1px solid var(--border-light)',
              }}
            >
              <div className="text-xs font-semibold" style={{ color: data.my_metrics.my_overdue_next_steps > 0 ? '#991B1B' : 'var(--neutral-500)' }}>
                Overdue Next Steps
              </div>
              <div className="font-bold text-xl" style={{ color: data.my_metrics.my_overdue_next_steps > 0 ? '#991B1B' : 'var(--neutral-900)', marginTop: '2px' }}>
                {data.my_metrics.my_overdue_next_steps || 0}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── Demo Performance & Status Filters Section ──────────────────── */}
      <div
        className="card"
        style={{
          padding: 'var(--space-4) var(--space-5)',
          backgroundColor: 'var(--bg-surface)',
          borderRadius: 'var(--radius-xl)',
          border: '1px solid var(--border-color)',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-3)', flexWrap: 'wrap', gap: 'var(--space-2)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
            <Presentation size={18} style={{ color: 'var(--color-accent)' }} />
            <h3 className="font-bold text-base" style={{ color: 'var(--neutral-900)' }}>
              {isRTL ? "مركز تقارير العروض التوضيحية (Demos Intelligence)" : "Demo Performance & Status Command"}
            </h3>
          </div>
          <button
            onClick={() => navigate('/demos')}
            className="btn btn-ghost btn-sm text-xs"
            style={{ display: 'flex', alignItems: 'center', gap: '4px', color: 'var(--color-primary)' }}
          >
            <span>{isRTL ? "فتح جدول العروض كاملاً" : "View Full Demos Workspace"}</span>
            <ArrowRight size={13} />
          </button>
        </div>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
            gap: 'var(--space-3)',
          }}
        >
          <MetricCard
            title={isRTL ? "إجمالي العروض" : "All Demos"}
            value={kpis.demos_total || (kpis.demo_agreed || 0) + (kpis.demo_completed || 0)}
            subtitle={isRTL ? "عرض شامل" : "Complete records"}
            icon={<Presentation size={16} />}
            color="var(--color-accent)"
            onClick={() => navigate('/demos?status=ALL')}
          />
          <MetricCard
            title={isRTL ? "مهتم / خطوة تالية" : "Interested / Next Step"}
            value={kpis.demos_interested || 0}
            subtitle={isRTL ? "فرص ذات أولوية" : "High potential deals"}
            icon={<CheckCircle size={16} />}
            color="var(--color-success)"
            onClick={() => navigate('/demos?status=INTERESTED_NEXT_STEP')}
          />
          <MetricCard
            title={isRTL ? "قيد الانتظار" : "Pending Demos"}
            value={kpis.demos_pending || kpis.demo_agreed || 0}
            subtitle={isRTL ? "تحت المتابعة" : "Awaiting decision"}
            icon={<Clock size={16} />}
            color="var(--color-accent)"
            onClick={() => navigate('/demos?status=PENDING')}
          />
          <MetricCard
            title={isRTL ? "مؤجل" : "Postponed Demos"}
            value={kpis.demos_postponed || 0}
            subtitle={isRTL ? "تتطلب إعادة جدولة" : "Rescheduled calls"}
            icon={<Calendar size={16} />}
            color="var(--color-accent)"
            onClick={() => navigate('/demos?status=POSTPONED')}
          />
          <MetricCard
            title={isRTL ? "غير مهتم" : "Not Interested"}
            value={kpis.demos_not_interested || 0}
            subtitle={isRTL ? "تم توثيق السبب" : "Documented reasons"}
            icon={<PhoneOff size={16} />}
            color="var(--neutral-500)"
            onClick={() => navigate('/demos?status=NOT_INTERESTED')}
          />
          <MetricCard
            title={isRTL ? "ملغي / لم يحضر" : "Cancelled Demos"}
            value={kpis.demos_cancelled_status || kpis.demo_cancelled || 0}
            subtitle={isRTL ? "فرص ضائعة" : "No-shows & cancels"}
            icon={<AlertCircle size={16} />}
            color="var(--color-danger)"
            onClick={() => navigate('/demos?status=CANCELLED')}
          />
          <MetricCard
            title={isRTL ? "تحتاج إلى تقرير" : "Needs Report"}
            value={kpis.demos_needs_report || 0}
            subtitle={isRTL ? "توثيق إلزامي" : "Mandatory reports"}
            icon={<AlertTriangle size={16} />}
            color={kpis.demos_needs_report > 0 ? 'var(--color-danger)' : 'var(--color-accent)'}
            urgent={kpis.demos_needs_report > 0}
            onClick={() => navigate('/demos?report_status=NEEDS_REPORT')}
          />
          <MetricCard
            title={isRTL ? "تقارير مكتملة" : "Report Complete"}
            value={kpis.demos_report_complete || kpis.demo_completed || 0}
            subtitle={isRTL ? "موثقة بالكامل" : "Audited & complete"}
            icon={<CheckCircle2 size={16} />}
            color="var(--color-success)"
            onClick={() => navigate('/demos?report_status=REPORT_COMPLETE')}
          />
        </div>
      </div>

      {/* ── Section Divider ─────────────────────────────────────────────── */}
      <div className="section-divider">
        <span className="section-divider-label">
          {isRTL ? "مؤشرات ثانوية" : "Secondary Metrics"}
        </span>
      </div>

      {/* ── SECONDARY KPI Cards (8 supporting metrics) ───────────────────── */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))',
          gap: 'var(--space-3)',
        }}
      >
        {/* Emails — muted accent, not blue info */}
        <MetricCard
          title={isRTL ? "البريد المكتمل" : "Emails Sent"}
          value={kpis.emails || 0}
          subtitle={isRTL ? "متابعات وطلبات بريد" : "Tasks & direct outreach"}
          icon={<Mail size={18} />}
          color="var(--color-accent)"
          onClick={() => (window.location.href = '/tasks?category=COMMUNICATION')}
        />

        {/* WhatsApp — muted accent, not green */}
        <MetricCard
          title={isRTL ? "رسائل الواتساب" : "WhatsApp Outreach"}
          value={kpis.whatsapp || 0}
          subtitle={isRTL ? "محادثات مباشرة" : "Direct WhatsApp chats"}
          icon={<MessageSquare size={18} />}
          color="var(--color-accent)"
          onClick={() => (window.location.href = '/tasks?category=COMMUNICATION')}
        />

        {/* Demo Completed — accent (positive signal, not confused with success green) */}
        <MetricCard
          title={isRTL ? "عروض منجزة" : "Demos Completed"}
          value={kpis.demo_completed || 0}
          subtitle={isRTL ? "جاهزة للفرص" : "Ready for proposals"}
          icon={<CheckCircle2 size={18} />}
          color="var(--color-accent)"
          onClick={() => (window.location.href = '/demos?stage=COMPLETED')}
        />

        {/* Demo Cancelled — red is justified: actual alert state */}
        <MetricCard
          title={isRTL ? "عروض ملغية" : "Demos Cancelled"}
          value={kpis.demo_cancelled || 0}
          subtitle={isRTL ? "تحتاج إعادة جدولة" : "Need re-engagement"}
          icon={<AlertCircle size={18} />}
          color="var(--color-danger)"
          onClick={() => (window.location.href = '/demos?stage=CANCELLED')}
        />

        {/* Follow-ups — accent */}
        <MetricCard
          title={isRTL ? "المتابعات" : "Follow-ups"}
          value={kpis.pending_follow_ups || kpis.follow_ups || 0}
          subtitle={`${kpis.overdue_follow_ups || 0} ${isRTL ? 'متأخرة' : 'overdue'}`}
          icon={<Calendar size={18} />}
          color="var(--color-accent)"
          onClick={() => (window.location.href = '/follow-ups')}
        />

        {/* Recalls — accent */}
        <MetricCard
          title={isRTL ? "إعادة الاتصال" : "Scheduled Recalls"}
          value={kpis.pending_recalls || kpis.recalls || 0}
          subtitle={`${kpis.overdue_recalls || 0} ${isRTL ? 'متأخرة' : 'overdue'}`}
          icon={<Clock size={18} />}
          color="var(--color-accent)"
          onClick={() => (window.location.href = '/recalls')}
        />

        {/* Unassigned Leads Pool — accent */}
        <MetricCard
          title={isRTL ? "غير موزعين" : "Unassigned Leads"}
          value={kpis.unassigned_leads || 0}
          subtitle={isRTL ? "جاهز للتوزيع" : "Ready for distribution"}
          icon={<Users size={18} />}
          color="var(--color-accent)"
          onClick={() => (window.location.href = '/leads/pool')}
        />

        {/* Total Active CRM Contacts — accent */}
        <MetricCard
          title={isRTL ? "العملاء النشطون" : "Active CRM Contacts"}
          value={kpis.active_leads || kpis.total_contacts || 0}
          subtitle={isRTL ? "مخصصين للمناديب" : "Assigned across reps"}
          icon={<UserCheck size={18} />}
          color="var(--color-accent)"
          onClick={() => (window.location.href = '/contacts')}
        />
      </div>

      {/* ── Conversion Funnel & Call Outcomes ───────────────────────────── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: 'var(--space-6)' }}>
        {/* Conversion Funnel */}
        <div className="card">
          <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <h3 className="card-title">{isRTL ? "قمع التحويل ومعدلات الكفاءة" : "Sales Team Conversion Funnel"}</h3>
              <p className="text-xs text-muted" style={{ marginTop: '2px' }}>
                {isRTL ? "معدلات التحويل المحتسبة بدقة عبر مراحل المبيعات" : "Transparent conversion rates across each stage of the outreach cycle"}
              </p>
            </div>
            <span className="badge badge-accent text-xs">
              <Zap size={13} style={{ marginRight: '4px' }} />
              {isRTL ? "مؤشرات حية" : "Live Funnel"}
            </span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)', padding: 'var(--space-2) 0' }}>
          {/* Funnel Bar 1: Total Calls -> Answered */}
            <FunnelStep
              label={isRTL ? "1. معدل الرد على المكالمات (Answer Rate)" : "1. Call Answer Rate"}
              count={`${callsBreakdown.answered ?? 0} / ${callsBreakdown.total ?? 0}`}
              pct={conversions.answer_rate ?? null}
              desc={isRTL ? "نسبة العملاء الذين أجابوا من إجمالي الاتصالات الصادرة" : "Contacts who answered out of total outreach attempts"}
              color="#3b82f6"
            />

            {/* Funnel Bar 2: Answered -> Engaged / Interested */}
            <FunnelStep
              label={isRTL ? "2. نسبة الاهتمام والتفاعل (Calls → Engaged)" : "2. Engagement Rate (Answered → Engaged)"}
              count={`${(callsBreakdown.interested ?? 0) + (callsBreakdown.email_requested ?? 0) + (callsBreakdown.whatsapp_requested ?? 0) + (callsBreakdown.demo_requested ?? 0)} / ${callsBreakdown.answered ?? 0}`}
              pct={conversions.calls_to_interested ?? null}
              desc={isRTL ? "العملاء المهتمين والمستجيبين من إجمالي المكالمات التي تم الرد عليها" : "High-intent engaged prospects (interested, email, WhatsApp, demo requests)"}
              color="#10b981"
            />

            {/* Funnel Bar 3: Engaged -> Demo (Company Level) */}
            <FunnelStep
              label={isRTL ? "3. تحويل العروض على مستوى الشركات (Engaged → Demo)" : "3. Demo Conversion (Engaged → Demo)"}
              count={
                kpis.unique_engaged_companies !== undefined && kpis.unique_demo_companies !== undefined
                  ? `${kpis.unique_demo_companies} / ${kpis.unique_engaged_companies} ${isRTL ? 'شركة' : 'companies'}`
                  : `${kpis.demo_agreed ?? 0} / ${(callsBreakdown.interested ?? 0) + (callsBreakdown.email_requested ?? 0) + (callsBreakdown.whatsapp_requested ?? 0) + (callsBreakdown.demo_requested ?? 0)}`
              }
              pct={conversions.interested_to_demo ?? null}
              desc={isRTL ? "محسوبة على مستوى الشركات الفريدة (Unique Companies) لمنع تضخيم الأرقام من جهات الاتصال المتعددة للشركة الواحدة" : "Calculated using unique companies, not individual contacts"}
              color="#8b5cf6"
            />

            {/* Funnel Bar 4: Demo Completed -> Opportunity */}
            <FunnelStep
              label={isRTL ? "4. تحويل الصفقات (Demo → Opportunity)" : "4. Pipeline Conversion (Demo → Opportunity)"}
              count={kpis.demo_completed > 0
                ? `${kpis.opportunities ?? 0} / ${kpis.demo_completed}`
                : isRTL ? '— (لا عروض مكتملة)' : '— (No completed demos)'}
              pct={conversions.demo_to_opportunity ?? null}
              desc={isRTL ? "الفرص والصفقات المنشأة من العروض المكتملة" : "Deals and opportunities created from completed demos"}
              color="#0284c7"
            />
          </div>
        </div>

        {/* Call Outcomes Breakdown & Donut Chart */}
        <div className="card">
          <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h3 className="card-title">{isRTL ? "توزيع نتائج الاتصال" : "Call Outcomes Breakdown"}</h3>
            <span className="badge text-xs" style={{ backgroundColor: 'var(--bg-subtle)', color: 'var(--neutral-600)' }}>
              <PieChartIcon size={13} style={{ marginRight: '4px' }} />
              {isRTL ? "رسم بياني تفاعلي" : "Visual Distribution"}
            </span>
          </div>

          {/* Recharts Donut Visualizer */}
          {((callsBreakdown.interested || 0) + (callsBreakdown.email_requested || 0) + (callsBreakdown.whatsapp_requested || 0) + (callsBreakdown.demo_requested || 0) + (callsBreakdown.call_later || 0) + (callsBreakdown.no_answer || 0)) > 0 ? (
            <div style={{ height: 160, width: '100%', marginBottom: 'var(--space-2)' }}>
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={[
                      { name: isRTL ? 'مهتم' : 'Interested', value: callsBreakdown.interested || 0, color: 'var(--color-accent)' },
                      { name: isRTL ? 'طلب إيميل' : 'Email Requested', value: callsBreakdown.email_requested || 0, color: 'var(--color-info)' },
                      { name: isRTL ? 'طلب واتساب' : 'WhatsApp Req', value: callsBreakdown.whatsapp_requested || 0, color: 'var(--color-success)' },
                      { name: isRTL ? 'طلب عرض' : 'Demo Req', value: callsBreakdown.demo_requested || 0, color: 'var(--color-accent)' },
                      { name: isRTL ? 'إعادة اتصال' : 'Call Later', value: callsBreakdown.call_later || 0, color: 'var(--color-warning)' },
                      { name: isRTL ? 'لم يرد' : 'No Answer', value: callsBreakdown.no_answer || 0, color: 'var(--neutral-400)' },
                    ].filter((d) => d.value > 0)}
                    cx="50%"
                    cy="50%"
                    innerRadius={45}
                    outerRadius={70}
                    paddingAngle={3}
                    dataKey="value"
                  >
                    {[
                      { color: 'var(--color-accent)' },
                      { color: 'var(--color-info)' },
                      { color: 'var(--color-success)' },
                      { color: 'var(--color-accent)' },
                      { color: 'var(--color-warning)' },
                      { color: 'var(--neutral-400)' },
                    ].map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Pie>
                  <RechartsTooltip
                    contentStyle={{
                      backgroundColor: 'var(--bg-surface-elevated, #1F2024)',
                      borderColor: 'var(--border-color, #383D40)',
                      borderRadius: '8px',
                      color: 'var(--neutral-900, #F3F2F1)',
                      fontSize: '12px',
                      boxShadow: '0 4px 12px rgba(0,0,0,0.3)',
                    }}
                  />
                </PieChart>
              </ResponsiveContainer>
            </div>
          ) : null}

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 'var(--space-3)' }}>
            <OutcomeStat
              label={isRTL ? "مهتم" : "Interested"}
              count={callsBreakdown.interested || 0}
              icon={<Flame size={15} />}
              bg="var(--status-interested-bg)"
              color="var(--status-interested-text)"
            />
            <OutcomeStat
              label={isRTL ? "طلب إيميل" : "Email Requested"}
              count={callsBreakdown.email_requested || 0}
              icon={<Mail size={15} />}
              bg="var(--color-info-bg)"
              color="var(--color-info-text)"
            />
            <OutcomeStat
              label={isRTL ? "طلب واتساب" : "WhatsApp Requested"}
              count={callsBreakdown.whatsapp_requested || 0}
              icon={<MessageSquare size={15} />}
              bg="var(--status-interested-bg)"
              color="var(--status-interested-text)"
            />
            <OutcomeStat
              label={isRTL ? "طلب عرض" : "Demo Requested"}
              count={callsBreakdown.demo_requested || 0}
              icon={<Target size={15} />}
              bg="var(--status-demo-bg)"
              color="var(--status-demo-text)"
            />
            <OutcomeStat
              label={isRTL ? "إعادة اتصال" : "Call Later"}
              count={callsBreakdown.call_later || 0}
              icon={<Clock size={15} />}
              bg="var(--status-noanswer-bg)"
              color="var(--status-noanswer-text)"
            />
            <OutcomeStat
              label={isRTL ? "لم يرد" : "No Answer"}
              count={callsBreakdown.no_answer || 0}
              icon={<PhoneOff size={15} />}
              bg="var(--status-noanswer-bg)"
              color="var(--status-noanswer-text)"
            />
          </div>

          <div
            style={{
              marginTop: 'var(--space-4)',
              padding: 'var(--space-3) var(--space-4)',
              borderRadius: 'var(--radius-md)',
              backgroundColor: 'var(--bg-subtle)',
              border: '1px solid var(--border-color)',
              display: 'flex',
              gap: 'var(--space-2)',
              alignItems: 'flex-start',
            }}
          >
            <Info size={14} style={{ color: 'var(--color-info)', marginTop: '2px', flexShrink: 0 }} />
            <p className="text-xs text-muted" style={{ lineHeight: '1.5', margin: 0 }}>
              {isRTL
                ? "يمكنك الضغط على أي موظف في جدول المقارنة أدناه لعرض محطة عمله بالكامل وتدقيق مكالماته والمهام دون الحاجة لتسجيل الدخول بحسابه."
                : "Click any sales user row in the comparison table below to open a full drill-down of their calls, contacts, tasks, and conversion history."}
            </p>
          </div>
        </div>
      </div>

      {/* ── Dual-Tab Performance Evaluation Section ────────────────────── */}
      <div className="card">
        <div
          className="card-header"
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            flexWrap: 'wrap',
            gap: 'var(--space-3)',
            borderBottom: '1px solid var(--border-color)',
            paddingBottom: 'var(--space-4)',
          }}
        >
          <div>
            <h3 className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
              <Award size={18} style={{ color: 'var(--color-accent)' }} />
              {isRTL ? "مقارنة وتقييم الأداء التشغيلي (Performance Evaluation)" : "Operational Performance Evaluation & Oversight"}
            </h3>
            <p className="text-xs text-muted" style={{ marginTop: '2px' }}>
              {isRTL
                ? "تقييم أداء مناديب المبيعات والمدراء الإداريين وفق معادلة الأداء الموضوعية"
                : "Objective scoring of sales reps and operational managers based on outreach, conversions, and SLAs."}
            </p>
          </div>

          {/* Tab Switcher */}
          <div style={{ display: 'flex', gap: 'var(--space-1)', backgroundColor: 'var(--bg-subtle)', padding: '3px', borderRadius: 'var(--radius-lg)' }}>
            <button
              type="button"
              onClick={() => setActivePerfTab('users')}
              className={`btn btn-sm ${activePerfTab === 'users' ? 'btn-primary' : 'btn-ghost'}`}
              style={{ fontSize: '12px', padding: '4px 12px', borderRadius: 'var(--radius-md)', display: 'inline-flex', alignItems: 'center', gap: '5px' }}
            >
              <UserCheck size={13} />
              {isRTL ? "أداء مناديب المبيعات" : "Sales Users"} ({userPerformance.length})
            </button>
            <button
              type="button"
              onClick={() => setActivePerfTab('managers')}
              className={`btn btn-sm ${activePerfTab === 'managers' ? 'btn-primary' : 'btn-ghost'}`}
              style={{ fontSize: '12px', padding: '4px 12px', borderRadius: 'var(--radius-md)', display: 'inline-flex', alignItems: 'center', gap: '5px' }}
            >
              <Briefcase size={13} />
              {isRTL ? "تقييم المدراء والفرق" : "Managers & Teams"} ({data?.manager_performance?.length || 0})
            </button>
          </div>
        </div>

        {/* Tab 1: Sales Rep Performance Table */}
        {activePerfTab === 'users' ? (
          <div className="table-container" style={{ overflowX: 'auto' }}>
            <table className="table">
              <thead>
                <tr>
                  <th>{isRTL ? "الموظف" : "Sales User"}</th>
                  <th>{isRTL ? "المكالمات" : "Calls"}</th>
                  <th>{isRTL ? "إيميل" : "Emails"}</th>
                  <th>{isRTL ? "واتساب" : "WhatsApp"}</th>
                  <th>{isRTL ? "إجمالي العروض" : "Total Demos"}</th>
                  <th>{isRTL ? "تحتاج تقرير" : "Needs Report"}</th>
                  <th>{isRTL ? "نسبة إكمال التقرير" : "Report Done %"}</th>
                  <th>{isRTL ? "عروض مكتملة" : "Demo Done"}</th>
                  <th>{isRTL ? "متابعات" : "Follow-ups"}</th>
                  <th>{isRTL ? "الفرص" : "Opps"}</th>
                  <th>{isRTL ? "مهام متأخرة" : "Overdue"}</th>
                  <th>{isRTL ? "النتيجة الإجمالية" : "Score"}</th>
                  <th>{isRTL ? "الإجراء" : "Action"}</th>
                </tr>
              </thead>
              <tbody>
                {userPerformance.length === 0 ? (
                  <tr>
                    <td colSpan={12} style={{ textAlign: 'center', padding: 'var(--space-6)' }} className="text-muted">
                      {isRTL ? "لا توجد بيانات للفترة المحددة" : "No performance records found for the selected period"}
                    </td>
                  </tr>
                ) : (
                  userPerformance.map((row) => {
                    const score = row.performance_score;
                    let badgeVariant: 'success' | 'accent' | 'warning' | 'error' = 'accent';
                    let scoreLabel = 'Steady';
                    if (score >= 85) {
                      badgeVariant = 'success';
                      scoreLabel = isRTL ? 'ممتاز' : 'Outstanding';
                    } else if (score >= 65) {
                      badgeVariant = 'accent';
                      scoreLabel = isRTL ? 'عالي' : 'High';
                    } else if (score >= 40) {
                      badgeVariant = 'warning';
                      scoreLabel = isRTL ? 'متوسط' : 'Moderate';
                    } else {
                      badgeVariant = 'error';
                      scoreLabel = isRTL ? 'يحتاج مراجعة' : 'Needs Review';
                    }

                    return (
                      <tr
                        key={row.user_id}
                        style={{ cursor: 'pointer', transition: 'background-color 0.15s ease' }}
                        onClick={() => setDrilldownUserId(row.user_id)}
                        className="hover:bg-neutral-50"
                      >
                        <td>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
                            <div
                              style={{
                                width: '32px',
                                height: '32px',
                                borderRadius: 'var(--radius-full)',
                                backgroundColor: 'var(--color-primary-subtle)',
                                color: 'var(--color-primary)',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                fontWeight: 700,
                                fontSize: '13px',
                                flexShrink: 0,
                              }}
                            >
                              {row.user_name.charAt(0)}
                            </div>
                            <div>
                              <div className="font-semibold text-sm" style={{ color: 'var(--neutral-900)' }}>
                                {row.user_name}
                              </div>
                              <div className="text-xs text-muted">
                                {row.role} {row.team_name ? `• ${row.team_name}` : ''}
                              </div>
                            </div>
                          </div>
                        </td>
                        <td>
                          <span className="font-semibold">{row.calls}</span>
                          <div className="text-xs text-muted">{row.answer_rate}% {isRTL ? 'إجابة' : 'ans'}</div>
                        </td>
                        <td>{row.emails}</td>
                        <td>{row.whatsapp}</td>
                        <td>
                          <span className="font-semibold" style={{ color: '#8b5cf6' }}>
                            {row.demos_total ?? row.demo_agreed}
                          </span>
                        </td>
                        <td>
                          {(row.demos_needs_report || 0) > 0 ? (
                            <span className="badge badge-error text-xs font-bold">
                              {row.demos_needs_report}
                            </span>
                          ) : (
                            <span className="text-xs text-muted">0</span>
                          )}
                        </td>
                        <td>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                            <span className="text-xs font-bold" style={{ color: (row.report_completion_rate || 100) >= 80 ? 'var(--color-success)' : 'var(--color-danger)' }}>
                              {row.report_completion_rate ?? 100}%
                            </span>
                          </div>
                        </td>
                        <td>
                          <span className="font-semibold text-success">
                            {row.demo_done}
                          </span>
                        </td>
                        <td>{row.follow_ups}</td>
                        <td>
                          <span className="font-semibold">{row.opportunities}</span>
                          {row.opportunities_won > 0 && (
                            <span className="text-xs text-success" style={{ marginLeft: '4px' }}>
                              ({row.opportunities_won} won)
                            </span>
                          )}
                        </td>
                        <td>
                          <span className={row.overdue_tasks > 0 ? 'badge badge-error text-xs' : 'text-muted'}>
                            {row.overdue_tasks}
                          </span>
                        </td>
                        <td>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                            <span className="font-bold text-sm" style={{ minWidth: '24px' }}>
                              {score}
                            </span>
                            <Badge variant={badgeVariant}>{scoreLabel}</Badge>
                          </div>
                        </td>
                        <td>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              setDrilldownUserId(row.user_id);
                            }}
                            className="btn btn-secondary btn-sm"
                            style={{ padding: '4px 8px', display: 'flex', alignItems: 'center', gap: '4px' }}
                          >
                            <Eye size={14} />
                            {isRTL ? "فحص" : "Inspect"}
                          </button>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        ) : (
          /* Tab 2: Manager & Team Performance Table */
          <div className="table-container" style={{ overflowX: 'auto' }}>
            <table className="table">
              <thead>
                <tr>
                  <th>{isRTL ? "الفريق والمدير" : "Team & Manager"}</th>
                  <th>{isRTL ? "عدد المناديب" : "Active Reps"}</th>
                  <th>{isRTL ? "مكالمات الفريق" : "Team Calls"}</th>
                  <th>{isRTL ? "إيميل / واتساب" : "Emails / WhatsApp"}</th>
                  <th>{isRTL ? "عروض منجزة" : "Demos Done"}</th>
                  <th>{isRTL ? "الصفقات وقيمتها" : "Opps / Value"}</th>
                  <th>{isRTL ? "مهام متأخرة" : "Team Overdue"}</th>
                  <th>{isRTL ? "كفاءة التحويل" : "Conversion"}</th>
                  <th>{isRTL ? "تقييم المدير" : "Manager Score"}</th>
                </tr>
              </thead>
              <tbody>
                {(!data?.manager_performance || data.manager_performance.length === 0) ? (
                  <tr>
                    <td colSpan={9} style={{ textAlign: 'center', padding: 'var(--space-6)' }} className="text-muted">
                      {isRTL ? "لا توجد فرق عمل مسجلة" : "No teams or managers found."}
                    </td>
                  </tr>
                ) : (
                  data.manager_performance.map((m: any) => (
                    <tr key={m.team_id}>
                      <td>
                        <div>
                          <div className="font-semibold text-sm text-dark">{m.team_name}</div>
                          <div className="text-xs text-muted" style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                            <Briefcase size={11} />
                            <span>{m.manager_name}</span>
                          </div>
                        </div>
                      </td>
                      <td>
                        <span className="badge badge-secondary">{m.members_count} {isRTL ? 'مناديب' : 'reps'}</span>
                      </td>
                      <td>
                        <span className="font-semibold">{m.calls}</span>
                        <div className="text-xs text-muted">{m.answer_rate}% {isRTL ? 'إجابة' : 'ans'}</div>
                      </td>
                      <td>
                        <div className="text-xs">
                          <span>✉️ {m.emails}</span>
                          <span style={{ margin: '0 4px' }}>•</span>
                          <span>💬 {m.whatsapp}</span>
                        </div>
                      </td>
                      <td>
                        <span className="font-semibold text-success">{m.demos_completed}</span>
                        <div className="text-xs text-muted">/ {m.demos_agreed} {isRTL ? 'متفق عليها' : 'booked'}</div>
                      </td>
                      <td>
                        <span className="font-semibold">{m.opportunities_count}</span>
                        <div className="text-xs text-muted">${(m.pipeline_value || 0).toLocaleString()}</div>
                      </td>
                      <td>
                        <span className={m.overdue_tasks > 0 ? 'badge badge-error text-xs' : 'text-muted'}>
                          {m.overdue_tasks}
                        </span>
                      </td>
                      <td>
                        <div className="text-xs font-semibold" style={{ color: 'var(--color-accent)' }}>
                          {m.interest_rate}% {isRTL ? 'اهتمام' : 'interest'}
                        </div>
                      </td>
                      <td>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                          <span className="font-bold text-sm">{m.team_performance_score}</span>
                          <Badge variant={m.team_performance_score >= 70 ? 'success' : m.team_performance_score >= 50 ? 'accent' : 'warning'}>
                            {m.team_performance_score >= 70 ? (isRTL ? 'قوي' : 'Strong') : (isRTL ? 'مقبول' : 'Fair')}
                          </Badge>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* ── User Drill-Down Modal / Drawer ──────────────────────────────── */}
      {drilldownUserId && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.5)',
            backdropFilter: 'blur(3px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
            padding: 'var(--space-4)',
          }}
          onClick={() => setDrilldownUserId(null)}
        >
          <div
            className="card"
            style={{
              width: '100%',
              maxWidth: '900px',
              maxHeight: '90vh',
              overflowY: 'auto',
              backgroundColor: 'var(--bg-surface)',
              borderRadius: 'var(--radius-xl)',
              padding: '0',
              display: 'flex',
              flexDirection: 'column',
              boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.25)',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div
              style={{
                padding: 'var(--space-5) var(--space-6)',
                borderBottom: '1px solid var(--border-color)',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                backgroundColor: 'var(--neutral-50)',
              }}
            >
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
                  <div
                    style={{
                      width: '40px',
                      height: '40px',
                      borderRadius: '50%',
                      backgroundColor: 'var(--color-primary)',
                      color: '#ffffff',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontWeight: 700,
                      fontSize: '16px',
                    }}
                  >
                    {drilldownData?.user?.full_name?.charAt(0) || 'U'}
                  </div>
                  <div>
                    <h2 className="font-display font-bold text-xl" style={{ color: 'var(--neutral-900)' }}>
                      {drilldownData?.user?.full_name || 'Loading Rep Profile...'}
                    </h2>
                    <div className="text-xs text-muted" style={{ display: 'flex', gap: 'var(--space-2)', marginTop: '2px' }}>
                      <span>{drilldownData?.user?.email}</span>
                      <span>•</span>
                      <span>{drilldownData?.user?.role}</span>
                      {drilldownData?.user?.team_name && (
                        <>
                          <span>•</span>
                          <span>{drilldownData?.user?.team_name}</span>
                        </>
                      )}
                    </div>
                  </div>
                </div>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
                {drilldownData?.performance_score !== undefined && (
                  <div style={{ textAlign: 'right' }}>
                    <div className="text-xs text-muted">{isRTL ? "مؤشر الأداء" : "Score"}</div>
                    <span className="font-display font-bold text-xl" style={{ color: 'var(--color-accent)' }}>
                      {drilldownData.performance_score} / 100
                    </span>
                  </div>
                )}
                <button
                  onClick={() => setDrilldownUserId(null)}
                  className="btn btn-ghost btn-sm"
                  style={{ borderRadius: '50%', padding: '6px' }}
                >
                  <X size={20} />
                </button>
              </div>
            </div>

            {/* Modal Body */}
            {drilldownLoading ? (
              <div style={{ padding: 'var(--space-8)' }}>
                <LoadingSpinner message={isRTL ? "جاري تحميل تفاصيل الموظف..." : "Fetching salesperson workstation data..."} />
              </div>
            ) : drilldownData ? (
              <div style={{ padding: 'var(--space-6)', display: 'flex', flexDirection: 'column', gap: 'var(--space-5)' }}>
                {/* Summary Mini-Cards */}
                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))',
                    gap: 'var(--space-3)',
                  }}
                >
                  <MiniMetric label={isRTL ? "المكالمات" : "Calls"} value={drilldownData.summary_kpis?.total_calls || 0} />
                  <MiniMetric label={isRTL ? "المهتمين" : "Interested"} value={drilldownData.summary_kpis?.interested || 0} color="#10b981" />
                  <MiniMetric label={isRTL ? "العروض" : "Demos"} value={drilldownData.summary_kpis?.demos_total || 0} color="#8b5cf6" />
                  <MiniMetric label={isRTL ? "الفرص" : "Opps"} value={drilldownData.summary_kpis?.opportunities || 0} color="#0284c7" />
                  <MiniMetric label={isRTL ? "العملاء المخصصين" : "Contacts"} value={drilldownData.summary_kpis?.assigned_contacts || 0} />
                  <MiniMetric
                    label={isRTL ? "مهام متأخرة" : "Overdue"}
                    value={drilldownData.summary_kpis?.overdue_tasks || 0}
                    color={drilldownData.summary_kpis?.overdue_tasks > 0 ? '#ef4444' : 'var(--neutral-900)'}
                  />
                </div>

                {/* Modal Navigation Tabs */}
                <div style={{ display: 'flex', borderBottom: '1px solid var(--border-color)', gap: 'var(--space-4)' }}>
                  {[
                    { id: 'calls', label: isRTL ? 'المكالمات الأخيرة' : 'Recent Calls', count: drilldownData.recent_calls?.length },
                    { id: 'contacts', label: isRTL ? 'العملاء المسندين' : 'Assigned Contacts', count: drilldownData.assigned_contacts?.length },
                    { id: 'tasks', label: isRTL ? 'المهام' : 'Tasks', count: drilldownData.tasks?.length },
                    { id: 'demos', label: isRTL ? 'العروض والفرص' : 'Demos & Opps', count: (drilldownData.demos?.length || 0) + (drilldownData.opportunities?.length || 0) },
                    { id: 'timeline', label: isRTL ? 'الجدول الزمني' : 'Activity Stream', count: drilldownData.activity_timeline?.length },
                  ].map((tab) => (
                    <button
                      key={tab.id}
                      onClick={() => setDrilldownTab(tab.id as any)}
                      style={{
                        padding: 'var(--space-2) var(--space-3)',
                        borderBottom: drilldownTab === tab.id ? '2px solid var(--color-accent)' : '2px solid transparent',
                        color: drilldownTab === tab.id ? 'var(--color-accent)' : 'var(--neutral-600)',
                        fontWeight: drilldownTab === tab.id ? 600 : 400,
                        fontSize: '13px',
                        cursor: 'pointer',
                        background: 'none',
                        borderTop: 'none',
                        borderLeft: 'none',
                        borderRight: 'none',
                      }}
                    >
                      {tab.label} ({tab.count || 0})
                    </button>
                  ))}
                </div>

                {/* Tab Content: Recent Calls */}
                {drilldownTab === 'calls' && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
                    {drilldownData.recent_calls?.length === 0 ? (
                      <div className="text-center text-muted py-6">{isRTL ? "لا توجد مكالمات مسجلة" : "No recent calls found for this user"}</div>
                    ) : (
                      drilldownData.recent_calls.map((c: any) => (
                        <div
                          key={c.id}
                          style={{
                            padding: 'var(--space-3) var(--space-4)',
                            borderRadius: 'var(--radius-md)',
                            backgroundColor: 'var(--neutral-50)',
                            border: '1px solid var(--border-color)',
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'center',
                          }}
                        >
                          <div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                              <span className="font-semibold text-sm" style={{ color: 'var(--neutral-900)' }}>
                                {c.contact_name}
                              </span>
                              {c.company_name && <span className="text-xs text-muted">({c.company_name})</span>}
                              {c.phone && <span className="text-xs text-muted" dir="ltr">{c.phone}</span>}
                            </div>
                            {c.notes && (
                              <p className="text-xs text-muted" style={{ marginTop: '2px' }}>
                                📝 {c.notes}
                              </p>
                            )}
                          </div>

                          <div style={{ textAlign: 'right' }}>
                            <Badge variant={c.outcome === 'INTERESTED' ? 'success' : c.outcome === 'NO_ANSWER' ? 'neutral' : 'accent'}>
                              {c.outcome}
                            </Badge>
                            <div className="text-xs text-muted" style={{ marginTop: '2px' }}>
                              {new Date(c.called_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} • {c.duration_seconds || 0}s
                            </div>
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                )}

                {/* Tab Content: Assigned Contacts */}
                {drilldownTab === 'contacts' && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
                    {drilldownData.assigned_contacts?.length === 0 ? (
                      <div className="text-center text-muted py-6">{isRTL ? "لا توجد جهات اتصال مخصصة" : "No contacts assigned to this user"}</div>
                    ) : (
                      drilldownData.assigned_contacts.map((ct: any) => (
                        <div
                          key={ct.id}
                          style={{
                            padding: 'var(--space-3) var(--space-4)',
                            borderRadius: 'var(--radius-md)',
                            backgroundColor: 'var(--neutral-50)',
                            border: '1px solid var(--border-color)',
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'center',
                          }}
                        >
                          <div>
                            <div className="font-semibold text-sm">{ct.full_name}</div>
                            <div className="text-xs text-muted">
                              {ct.position || 'Contact'} {ct.company_name ? `• ${ct.company_name}` : ''}
                            </div>
                          </div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                            <span className="text-xs text-muted">{ct.attempt_count} {isRTL ? 'محاولات' : 'attempts'}</span>
                            <Badge variant="accent">{ct.status}</Badge>
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                )}

                {/* Tab Content: Tasks */}
                {drilldownTab === 'tasks' && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
                    {drilldownData.tasks?.length === 0 ? (
                      <div className="text-center text-muted py-6">{isRTL ? "لا توجد مهام" : "No tasks found"}</div>
                    ) : (
                      drilldownData.tasks.map((t: any) => (
                        <div
                          key={t.id}
                          style={{
                            padding: 'var(--space-3) var(--space-4)',
                            borderRadius: 'var(--radius-md)',
                            backgroundColor: 'var(--neutral-50)',
                            border: '1px solid var(--border-color)',
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'center',
                          }}
                        >
                          <div>
                            <div className="font-semibold text-sm">{t.title}</div>
                            <div className="text-xs text-muted">
                              {t.type} • Priority: {t.priority} {t.contact_name ? `• ${t.contact_name}` : ''}
                            </div>
                          </div>
                          <div>
                            <Badge variant={t.status === 'COMPLETED' ? 'success' : 'accent'}>{t.status}</Badge>
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                )}

                {/* Tab Content: Demos & Opps */}
                {drilldownTab === 'demos' && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
                    <div>
                      <h4 className="font-semibold text-sm mb-2">{isRTL ? "العروض التجريبية" : "Product Demonstrations"}</h4>
                      {drilldownData.demos?.length === 0 ? (
                        <div className="text-xs text-muted">{isRTL ? "لا توجد عروض" : "No demos"}</div>
                      ) : (
                        drilldownData.demos.map((d: any) => (
                          <div key={d.id} className="p-3 bg-neutral-50 rounded border mb-2 flex justify-between items-center">
                            <div>
                              <div className="font-semibold text-sm">{d.company_name || 'Account Demo'}</div>
                              <div className="text-xs text-muted">{d.contact_name}</div>
                            </div>
                            <Badge variant="accent">{d.stage}</Badge>
                          </div>
                        ))
                      )}
                    </div>

                    <div>
                      <h4 className="font-semibold text-sm mb-2">{isRTL ? "الفرص والصفقات" : "Pipeline Opportunities"}</h4>
                      {drilldownData.opportunities?.length === 0 ? (
                        <div className="text-xs text-muted">{isRTL ? "لا توجد فرص" : "No opportunities"}</div>
                      ) : (
                        drilldownData.opportunities.map((o: any) => (
                          <div key={o.id} className="p-3 bg-neutral-50 rounded border mb-2 flex justify-between items-center">
                            <div>
                              <div className="font-semibold text-sm">{o.title}</div>
                              <div className="text-xs text-muted">{o.company_name} • ${o.value?.toLocaleString()}</div>
                            </div>
                            <Badge variant={o.stage === 'WON' ? 'success' : 'accent'}>{o.stage}</Badge>
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                )}

                {/* Tab Content: Timeline */}
                {drilldownTab === 'timeline' && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
                    {drilldownData.activity_timeline?.length === 0 ? (
                      <div className="text-center text-muted py-6">{isRTL ? "لا يوجد سجل نشاط" : "No timeline events recorded"}</div>
                    ) : (
                      drilldownData.activity_timeline.map((act: any) => (
                        <div key={act.id} className="p-3 bg-neutral-50 rounded border flex justify-between items-center text-xs">
                          <div>
                            <span className="font-semibold">{act.type.toUpperCase()}:</span> {act.contact_name || act.title || 'Action'}
                            {act.notes && <div className="text-muted mt-1">{act.notes}</div>}
                          </div>
                          <span className="text-muted">{new Date(act.timestamp).toLocaleDateString()}</span>
                        </div>
                      ))
                    )}
                  </div>
                )}
              </div>
            ) : null}
          </div>
        </div>
      )}
    </div>
  );
};

/* ── Helper Mini Components ─────────────────────────────────────────── */

const MetricCard: React.FC<{
  title: string;
  value: number;
  subtitle: string;
  icon: React.ReactNode;
  color: string;
  onClick?: () => void;
  primary?: boolean;   // Primary tier: larger, more prominent
  urgent?: boolean;    // Urgent state: danger tint on border
}> = ({ title, value, subtitle, icon, color, onClick, primary = false, urgent = false }) => {
  return (
    <motion.div
      whileHover={{ y: -3, transition: { duration: 0.15 } }}
      whileTap={onClick ? { scale: 0.985 } : undefined}
      className={`card ${onClick ? 'card-interactive' : ''}`}
      onClick={onClick}
      role={onClick ? 'button' : undefined}
      aria-label={onClick ? title : undefined}
      tabIndex={onClick ? 0 : undefined}
      onKeyDown={onClick ? (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onClick(); } } : undefined}
      style={{
        padding: primary ? 'var(--space-6)' : 'var(--space-4)',
        borderColor: urgent ? 'var(--color-danger-border)' : undefined,
        cursor: onClick ? 'pointer' : 'default',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: primary ? 'var(--space-4)' : 'var(--space-3)' }}>
        <span
          className="text-xs font-semibold text-muted uppercase"
          style={{ letterSpacing: '0.06em', lineHeight: 1.3, maxWidth: '80%' }}
        >
          {title}
        </span>
        <div
          style={{
            width: primary ? '40px' : '32px',
            height: primary ? '40px' : '32px',
            borderRadius: 'var(--radius-md)',
            backgroundColor: `${color}18`,
            color: color,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0,
          }}
        >
          {icon}
        </div>
      </div>
      <div
        className="font-display font-bold"
        style={{
          color: urgent ? 'var(--color-danger)' : 'var(--neutral-900)',
          lineHeight: 1.1,
          fontSize: primary ? 'var(--text-4xl)' : 'var(--text-2xl)',
          letterSpacing: '-0.02em',
        }}
      >
        {typeof value === 'number' ? value.toLocaleString() : value}
      </div>
      <div className="text-xs text-muted" style={{ marginTop: 'var(--space-1)', lineHeight: 1.4 }}>
        {subtitle}
      </div>
    </motion.div>
  );
};

const OutcomeStat: React.FC<{ label: string; count: number; icon: React.ReactNode; bg: string; color: string }> = ({
  label,
  count,
  icon,
  bg,
  color,
}) => (
  <div
    style={{
      padding: 'var(--space-3) var(--space-4)',
      backgroundColor: bg,
      border: '1px solid var(--border-light)',
      borderRadius: 'var(--radius-lg)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
    }}
  >
    <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
      <span style={{ color, display: 'flex', alignItems: 'center' }}>{icon}</span>
      <span className="font-medium text-sm" style={{ color }}>
        {label}
      </span>
    </div>
    <span className="font-bold text-base" style={{ color }}>
      {count.toLocaleString()}
    </span>
  </div>
);

const FunnelStep: React.FC<{
  label: string;
  count: string;
  pct: number | null;
  desc: string;
  color: string;
}> = ({ label, count, pct, desc, color }) => (
  <div>
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
      <span className="font-semibold text-xs text-dark">{label}</span>
      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
        <span className="text-xs text-muted">{count}</span>
        <strong className="text-xs font-bold" style={{ color: pct !== null ? color : 'var(--neutral-400)' }}>
          {pct !== null ? `${pct}%` : '—'}
        </strong>
      </div>
    </div>
    <div
      style={{
        height: '8px',
        width: '100%',
        backgroundColor: 'var(--neutral-100)',
        borderRadius: '9999px',
        overflow: 'hidden',
      }}
    >
      <div
        style={{
          height: '100%',
          width: pct !== null ? `${Math.min(100, Math.max(2, pct))}%` : '0%',
          backgroundColor: pct !== null ? color : 'var(--neutral-300)',
          borderRadius: '9999px',
          transition: 'width 0.3s ease',
        }}
      />
    </div>
    <div className="text-xs text-muted" style={{ marginTop: '2px' }}>
      {pct === null ? (
        <span style={{ fontStyle: 'italic' }}>{desc} — N/A (no data for this period)</span>
      ) : desc}
    </div>
  </div>
);

const MiniMetric: React.FC<{ label: string; value: number; color?: string }> = ({ label, value, color }) => (
  <div
    style={{
      padding: 'var(--space-3)',
      backgroundColor: 'var(--neutral-50)',
      borderRadius: 'var(--radius-md)',
      border: '1px solid var(--border-color)',
      textAlign: 'center',
    }}
  >
    <div className="text-xs text-muted">{label}</div>
    <div className="font-bold text-lg" style={{ color: color || 'var(--neutral-900)', marginTop: '2px' }}>
      {value}
    </div>
  </div>
);
