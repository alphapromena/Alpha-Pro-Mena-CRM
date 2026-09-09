import React from 'react';
import { createBrowserRouter, Navigate } from 'react-router-dom';
import { AppLayout } from './components/layout/AppLayout';
import { LoginPage } from './features/auth/LoginPage';
import { DashboardPage } from './features/dashboard/DashboardPage';
import { MyWorkPage } from './features/my-work/MyWorkPage';
import { ContactsPage } from './features/contacts/ContactsPage';
import { ContactDetailPage } from './features/contacts/ContactDetailPage';
import { CompaniesPage } from './features/companies/CompaniesPage';
import { CompanyDetailPage } from './features/companies/CompanyDetailPage';
import { TasksPage } from './features/tasks/TasksPage';
import { FollowUpsPage } from './features/follow-ups/FollowUpsPage';
import { RecallsPage } from './features/recalls/RecallsPage';
import { NoAnswerPage } from './features/no-answer/NoAnswerPage';
import { DemosPage } from './features/demos/DemosPage';
import { OpportunitiesPage } from './features/opportunities/OpportunitiesPage';
import { CampaignsPage } from './features/campaigns/CampaignsPage';
import { ReportsPage } from './features/reports/ReportsPage';
import { TeamActivityPage } from './features/reports/TeamActivityPage';
import { UsersTeamsPage } from './features/admin/UsersTeamsPage';
import { LeadDistributionPage } from './features/admin/LeadDistributionPage';
import { GoogleSheetsPage } from './features/admin/GoogleSheetsPage';
import { AutomationRulesPage } from './features/admin/AutomationRulesPage';
import { AuditLogsPage } from './features/admin/AuditLogsPage';
import { SystemSettingsPage } from './features/admin/SystemSettingsPage';
import { LeadPoolPage } from './features/leads/LeadPoolPage';
import { VerifyEmailPage } from './features/auth/VerifyEmailPage';
import { SetPasswordPage } from './features/auth/SetPasswordPage';
import { ForgotPasswordPage } from './features/auth/ForgotPasswordPage';
import { ResetPasswordPage } from './features/auth/ResetPasswordPage';
import { useAuthStore } from './store/authStore';

// Protected Route Guard
const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated, isLoading, user } = useAuthStore();
  if (isLoading) return null;
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  if (user?.must_change_password) {
    return <Navigate to="/set-password" replace />;
  }
  if (user?.email_verified === false) {
    return <Navigate to="/verify-email" replace />;
  }
  return <>{children}</>;
};

// Data Ops Restricted Route Guard (blocks Aseel from sales & management workflows)
const DataOpsRestrictedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { user } = useAuthStore();
  if (user?.role === 'DATA_OPS') {
    return <Navigate to="/leads/pool" replace />;
  }
  return <>{children}</>;
};

// Dynamic Home Index Redirect
const IndexRedirect: React.FC = () => {
  const { user } = useAuthStore();
  if (user?.must_change_password) {
    return <Navigate to="/set-password" replace />;
  }
  if (user?.email_verified === false) {
    return <Navigate to="/verify-email" replace />;
  }
  if (user?.role === 'DATA_OPS') {
    return <Navigate to="/leads/pool" replace />;
  }
  return <Navigate to="/dashboard" replace />;
};

export const router = createBrowserRouter([
  {
    path: '/login',
    element: <LoginPage />,
  },
  {
    path: '/verify-email',
    element: <VerifyEmailPage />,
  },
  {
    path: '/set-password',
    element: <SetPasswordPage />,
  },
  {
    path: '/forgot-password',
    element: <ForgotPasswordPage />,
  },
  {
    path: '/reset-password',
    element: <ResetPasswordPage />,
  },
  {
    path: '/',
    element: (
      <ProtectedRoute>
        <AppLayout />
      </ProtectedRoute>
    ),
    children: [
      { index: true, element: <IndexRedirect /> },
      { path: 'dashboard', element: <DataOpsRestrictedRoute><DashboardPage /></DataOpsRestrictedRoute> },
      { path: 'my-work', element: <DataOpsRestrictedRoute><MyWorkPage /></DataOpsRestrictedRoute> },
      { path: 'contacts', element: <DataOpsRestrictedRoute><ContactsPage /></DataOpsRestrictedRoute> },
      { path: 'contacts/:contactId', element: <DataOpsRestrictedRoute><ContactDetailPage /></DataOpsRestrictedRoute> },
      { path: 'companies', element: <DataOpsRestrictedRoute><CompaniesPage /></DataOpsRestrictedRoute> },
      { path: 'companies/:companyId', element: <DataOpsRestrictedRoute><CompanyDetailPage /></DataOpsRestrictedRoute> },
      { path: 'leads/pool', element: <LeadPoolPage /> },
      { path: 'tasks', element: <DataOpsRestrictedRoute><TasksPage /></DataOpsRestrictedRoute> },
      { path: 'follow-ups', element: <DataOpsRestrictedRoute><FollowUpsPage /></DataOpsRestrictedRoute> },
      { path: 'recalls', element: <DataOpsRestrictedRoute><RecallsPage /></DataOpsRestrictedRoute> },
      { path: 'no-answer', element: <DataOpsRestrictedRoute><NoAnswerPage /></DataOpsRestrictedRoute> },
      { path: 'demos', element: <DataOpsRestrictedRoute><DemosPage /></DataOpsRestrictedRoute> },
      { path: 'opportunities', element: <DataOpsRestrictedRoute><OpportunitiesPage /></DataOpsRestrictedRoute> },
      { path: 'team-activity', element: <DataOpsRestrictedRoute><TeamActivityPage /></DataOpsRestrictedRoute> },
      { path: 'campaigns', element: <DataOpsRestrictedRoute><CampaignsPage /></DataOpsRestrictedRoute> },
      { path: 'reports', element: <DataOpsRestrictedRoute><ReportsPage /></DataOpsRestrictedRoute> },
      { path: 'admin/users', element: <DataOpsRestrictedRoute><UsersTeamsPage /></DataOpsRestrictedRoute> },
      { path: 'admin/distribution', element: <LeadDistributionPage /> },
      { path: 'admin/google-sheets', element: <GoogleSheetsPage /> },
      { path: 'admin/automation', element: <DataOpsRestrictedRoute><AutomationRulesPage /></DataOpsRestrictedRoute> },
      { path: 'admin/settings', element: <DataOpsRestrictedRoute><SystemSettingsPage /></DataOpsRestrictedRoute> },
      { path: 'admin/audit-logs', element: <DataOpsRestrictedRoute><AuditLogsPage /></DataOpsRestrictedRoute> },
    ],
  },
  {
    path: '*',
    element: <IndexRedirect />,
  },
]);
