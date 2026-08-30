import React, { useState, useEffect } from 'react';
import { api } from '../../lib/apiClient';
import { LoadingSpinner } from '../../components/feedback/LoadingSpinner';
import { BarChart3, Users, PhoneCall, CheckCircle2, TrendingUp } from 'lucide-react';

export const ReportsPage: React.FC = () => {
  const [userStats, setUserStats] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchReports = async () => {
      setIsLoading(true);
      try {
        const res = await api.get<any>('/reports/user-performance');
        setUserStats(res.data || []);
      } catch (e) {
        console.error('Failed to load reports', e);
      } finally {
        setIsLoading(false);
      }
    };
    fetchReports();
  }, []);

  if (isLoading) return <LoadingSpinner message="Aggregating management performance metrics..." />;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-6)' }}>
      <div>
        <h1 className="font-display font-bold text-2xl" style={{ color: 'var(--neutral-900)' }}>
          Management Performance Analytics
        </h1>
        <p className="text-sm text-muted">
          Compare sales representatives activity, answer rates, and conversion performance.
        </p>
      </div>

      <div className="table-container">
        <table className="data-table">
          <thead>
            <tr>
              <th>Sales Representative</th>
              <th>System Role</th>
              <th>Total Calls Logged</th>
              <th>Unique Leads Contacted</th>
              <th>Performance Standing</th>
            </tr>
          </thead>
          <tbody>
            {userStats.map((u, idx) => (
              <tr key={u.user_id}>
                <td>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                    <div
                      style={{
                        width: '28px',
                        height: '28px',
                        borderRadius: 'var(--radius-full)',
                        backgroundColor: 'var(--color-primary-subtle)',
                        color: 'var(--color-primary)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        fontSize: '11px',
                        fontWeight: 700,
                      }}
                    >
                      #{idx + 1}
                    </div>
                    <span className="font-semibold text-sm text-dark">{u.user_name}</span>
                  </div>
                </td>
                <td>
                  <span className="badge badge-new">{u.role}</span>
                </td>
                <td>
                  <span className="font-bold text-sm text-primary">{u.total_calls} calls</span>
                </td>
                <td>
                  <span className="font-medium text-sm text-dark">{u.unique_contacts} leads</span>
                </td>
                <td>
                  <span
                    style={{
                      fontSize: '11px',
                      fontWeight: 600,
                      color: idx === 0 ? 'var(--color-success-text)' : 'var(--neutral-600)',
                      backgroundColor: idx === 0 ? 'var(--color-success-bg)' : 'var(--neutral-100)',
                      padding: '2px 8px',
                      borderRadius: 'var(--radius-full)',
                    }}
                  >
                    {idx === 0 ? '🌟 Top Performer' : 'Active Outreach'}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
