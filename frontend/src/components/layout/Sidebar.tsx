import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  Briefcase,
  Users,
  Building2,
  UserPlus,
  CheckSquare,
  Clock,
  PhoneCall,
  PhoneMissed,
  Presentation,
  TrendingUp,
  BarChart3,
  ShieldCheck,
  Zap,
  FileSpreadsheet,
  Layers,
  UserCog,
  Settings,
  UploadCloud,
} from 'lucide-react';
import { useAuthStore } from '../../store/authStore';
import { useTranslation } from '../../i18n';
import { BrandLogo } from '../common/BrandLogo';

export const Sidebar: React.FC = () => {
  const { user } = useAuthStore();
  const { t, isRTL } = useTranslation();

  const isTeamLead = user?.role === 'TEAM_LEAD' || user?.role === 'ADMIN' || user?.role === 'TEAM_LEADER';
  const isManagerOrAbove = isTeamLead || user?.role === 'MANAGER';
  const isDataOps = user?.role === 'DATA_OPS';

  const formatRoleLabel = (role?: string) => {
    if (!role) return '';
    if (role === 'TEAM_LEAD' || role === 'ADMIN' || role === 'TEAM_LEADER') {
      return isRTL ? 'قائد الفريق' : 'Team Lead';
    }
    if (role === 'MANAGER') {
      return isRTL ? 'مدير عمليات' : 'Manager';
    }
    if (role === 'DATA_OPS') {
      return isRTL ? 'عمليات البيانات' : 'Data Operations';
    }
    return isRTL ? 'مندوب مبيعات' : 'Sales User';
  };

  return (
    <aside
      className="app-sidebar"
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        backgroundColor: 'var(--bg-sidebar)',
        borderInlineEnd: '1px solid var(--border-light)',
      }}
    >
      {/* Brand Header with Authentic Brand Logo */}
      <div
        style={{
          padding: 'var(--space-4) var(--space-5)',
          borderBottom: '1px solid var(--border-light)',
          display: 'flex',
          alignItems: 'center',
          backgroundColor: 'var(--bg-sidebar)',
        }}
      >
        <BrandLogo variant="horizontal" size="sm" theme="dark" />
      </div>

      {/* Navigation Links */}
      <div
        style={{
          flex: 1,
          overflowY: 'auto',
          padding: 'var(--space-3) var(--space-2)',
          display: 'flex',
          flexDirection: 'column',
          gap: '2px',
        }}
      >
        {isDataOps ? (
          <>
            {/* DATA OPERATIONS Section for Aseel */}
            <div
              style={{
                fontSize: '10px',
                fontWeight: 800,
                color: 'var(--neutral-400)',
                padding: 'var(--space-2) var(--space-3)',
                letterSpacing: '0.8px',
                textTransform: 'uppercase',
              }}
            >
              {isRTL ? 'عمليات البيانات' : 'DATA OPERATIONS'}
            </div>
            <NavItem to="/leads/pool" icon={<UserPlus size={17} />} label={isRTL ? 'مجمع العملاء والتحقق' : 'New Leads Pool'} isRTL={isRTL} />
            <NavItem to="/admin/google-sheets" icon={<FileSpreadsheet size={17} />} label={isRTL ? 'استيراد Google Sheets والملفات' : 'Data Ingestion & Sync'} isRTL={isRTL} />
            <NavItem to="/admin/distribution" icon={<Layers size={17} />} label={isRTL ? 'توزيع العملاء' : 'Lead Distribution'} isRTL={isRTL} />
          </>
        ) : (
          <>
            {/* CORE Section */}
            <div
              style={{
                fontSize: '10px',
                fontWeight: 800,
                color: 'var(--neutral-400)',
                padding: 'var(--space-2) var(--space-3)',
                letterSpacing: '0.8px',
                textTransform: 'uppercase',
              }}
            >
              {isRTL ? 'الرئيسية' : 'CORE'}
            </div>
            <NavItem to="/dashboard" icon={<LayoutDashboard size={17} />} label={t('nav_dashboard')} isRTL={isRTL} />
            <NavItem to="/my-work" icon={<Briefcase size={17} />} label={t('nav_my_work')} badge={isRTL ? 'يومي' : 'Daily'} isRTL={isRTL} />
            <NavItem to="/contacts" icon={<Users size={17} />} label={t('nav_contacts')} isRTL={isRTL} />
            <NavItem to="/companies" icon={<Building2 size={17} />} label={t('nav_companies')} isRTL={isRTL} />
            <NavItem to="/leads/pool" icon={<UserPlus size={17} />} label={t('nav_new_leads')} isRTL={isRTL} />

            {/* WORKFLOW Section */}
            <div
              style={{
                fontSize: '10px',
                fontWeight: 800,
                color: 'var(--neutral-400)',
                padding: 'var(--space-3) var(--space-3) var(--space-1)',
                letterSpacing: '0.8px',
                textTransform: 'uppercase',
              }}
            >
              {isRTL ? 'سير العمل' : 'WORKFLOW'}
            </div>
            <NavItem to="/tasks" icon={<CheckSquare size={17} />} label={t('nav_tasks')} isRTL={isRTL} />
            <NavItem to="/follow-ups" icon={<Clock size={17} />} label={t('nav_follow_ups')} isRTL={isRTL} />
            <NavItem to="/recalls" icon={<PhoneCall size={17} />} label={t('nav_recalls')} isRTL={isRTL} />
            <NavItem to="/no-answer" icon={<PhoneMissed size={17} />} label={t('nav_no_answer')} isRTL={isRTL} />
            <NavItem to="/demos" icon={<Presentation size={17} />} label={t('nav_demos')} isRTL={isRTL} />
            <NavItem to="/opportunities" icon={<TrendingUp size={17} />} label={t('nav_opportunities')} isRTL={isRTL} />

            {/* MANAGEMENT Section (Manager & Team Lead) */}
            {isManagerOrAbove && (
              <>
                <div
                  style={{
                    fontSize: '10px',
                    fontWeight: 800,
                    color: 'var(--neutral-400)',
                    padding: 'var(--space-3) var(--space-3) var(--space-1)',
                    letterSpacing: '0.8px',
                    textTransform: 'uppercase',
                  }}
                >
                  {isRTL ? 'الإدارة والعمليات' : 'MANAGEMENT'}
                </div>
                <NavItem to="/team-activity" icon={<Clock size={17} />} label={isRTL ? 'نشاط الفريق' : 'Team Activity'} isRTL={isRTL} />
                <NavItem to="/admin/users" icon={<UserCog size={17} />} label={isRTL ? 'المستخدمين والفرق' : 'Users & Teams'} isRTL={isRTL} />
                <NavItem to="/admin/distribution" icon={<Layers size={17} />} label={isRTL ? 'توزيع العملاء' : 'Lead Distribution'} isRTL={isRTL} />
                <NavItem to="/reports" icon={<BarChart3 size={17} />} label={isRTL ? 'تقارير الإدارة' : 'Reports'} isRTL={isRTL} />
              </>
            )}

            {/* SYSTEM Section (Team Lead Only) */}
            {isTeamLead && (
              <>
                <div
                  style={{
                    fontSize: '10px',
                    fontWeight: 800,
                    color: 'var(--neutral-400)',
                    padding: 'var(--space-3) var(--space-3) var(--space-1)',
                    letterSpacing: '0.8px',
                    textTransform: 'uppercase',
                  }}
                >
                  {isRTL ? 'إدارة النظام' : 'SYSTEM'}
                </div>
                <NavItem to="/admin/automation" icon={<Zap size={17} />} label={isRTL ? 'قواعد الأتمتة' : 'Automation Rules'} isRTL={isRTL} />
                <NavItem to="/admin/google-sheets" icon={<FileSpreadsheet size={17} />} label={t('nav_google_sheets')} isRTL={isRTL} />
                <NavItem to="/admin/settings" icon={<Settings size={17} />} label={isRTL ? 'إعدادات النظام' : 'System Settings'} isRTL={isRTL} />
                <NavItem to="/admin/audit-logs" icon={<ShieldCheck size={17} />} label={isRTL ? 'سجلات التدقيق' : 'Audit Logs'} isRTL={isRTL} />
              </>
            )}
          </>
        )}
      </div>

      {/* User Profile Card at Footer (Seamlessly Integrated into Dark Sidebar) */}
      <div
        style={{
          padding: 'var(--space-3) var(--space-4)',
          borderTop: '1px solid var(--border-light)',
          display: 'flex',
          alignItems: 'center',
          gap: 'var(--space-3)',
          backgroundColor: 'var(--bg-sidebar)',
        }}
      >
        <div
          style={{
            width: '34px',
            height: '34px',
            borderRadius: 'var(--radius-full)',
            backgroundColor: 'var(--color-primary-subtle)',
            border: '1px solid var(--color-primary)',
            color: 'var(--color-primary)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '13px',
            fontWeight: 800,
            flexShrink: 0,
          }}
        >
          {user?.first_name?.[0] || 'U'}
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div
            style={{
              fontSize: '13px',
              fontWeight: 700,
              color: 'var(--neutral-900)',
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
            }}
          >
            {user?.first_name || user?.full_name}
          </div>
          <div style={{ fontSize: '11px', color: 'var(--neutral-400)', fontWeight: 600 }}>
            {formatRoleLabel(user?.role)}
          </div>
        </div>
      </div>
    </aside>
  );
};

interface NavItemProps {
  to: string;
  icon: React.ReactNode;
  label: string;
  badge?: string;
  isRTL?: boolean;
}

const NavItem: React.FC<NavItemProps> = ({ to, icon, label, badge, isRTL }) => {
  return (
    <NavLink
      to={to}
      style={({ isActive }) => ({
        display: 'flex',
        alignItems: 'center',
        gap: 'var(--space-3)',
        padding: '8px 12px',
        borderRadius: 'var(--radius-md)',
        color: isActive ? '#FFFFFF' : 'var(--neutral-400)',
        backgroundColor: isActive ? 'var(--bg-sidebar-active)' : 'transparent',
        fontSize: '13px',
        fontWeight: isActive ? 700 : 500,
        textDecoration: 'none',
        transition: 'all 0.15s ease',
        borderInlineStart: isActive ? '3px solid var(--color-accent)' : '3px solid transparent',
      })}
    >
      <span
        style={{
          display: 'flex',
          alignItems: 'center',
          color: 'inherit',
          opacity: 0.9,
        }}
      >
        {icon}
      </span>
      <span style={{ flex: 1, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{label}</span>
      {badge && (
        <span
          style={{
            fontSize: '9px',
            fontWeight: 800,
            padding: '1px 6px',
            borderRadius: 'var(--radius-full)',
            backgroundColor: 'var(--color-primary)',
            color: '#FFFFFF',
            letterSpacing: '0.4px',
          }}
        >
          {badge}
        </span>
      )}
    </NavLink>
  );
};
