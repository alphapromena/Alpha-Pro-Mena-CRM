import React, { useState, useEffect } from 'react';
import { api } from '../../lib/apiClient';
import { LoadingSpinner } from '../../components/feedback/LoadingSpinner';
import { ShieldCheck, User } from 'lucide-react';

export const AuditLogsPage: React.FC = () => {
  const [logs, setLogs] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchLogs = async () => {
      setIsLoading(true);
      try {
        const res = await api.get<any>('/audit-logs', { per_page: 50 });
        setLogs(res.data || []);
      } catch (e) {
        console.error('Failed to load audit logs', e);
      } finally {
        setIsLoading(false);
      }
    };
    fetchLogs();
  }, []);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-6)' }}>
      <div>
        <h1 className="font-display font-bold text-2xl" style={{ color: 'var(--neutral-900)' }}>
          Security & Operational Audit Logs
        </h1>
        <p className="text-sm text-muted">
          Immutable append-only audit trail recording user logins, role assignments, lead distribution, and sensitive actions.
        </p>
      </div>

      <div className="table-container">
        <table className="data-table">
          <thead>
            <tr>
              <th>Timestamp</th>
              <th>Actor</th>
              <th>Action Executed</th>
              <th>Entity Type</th>
              <th>Details / Diff</th>
            </tr>
          </thead>
          <tbody>
            {logs.map((log) => (
              <tr key={log.id}>
                <td>
                  <span className="text-xs font-mono text-muted">
                    {new Date(log.created_at).toLocaleString()}
                  </span>
                </td>
                <td>
                  <span className="font-semibold text-xs text-dark">{log.actor_name}</span>
                </td>
                <td>
                  <span className="badge badge-new font-mono text-xs">{log.action}</span>
                </td>
                <td>
                  <span className="text-xs font-medium">{log.entity_type}</span>
                </td>
                <td>
                  <div style={{ maxWidth: '300px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontSize: '11px', color: 'var(--neutral-600)' }}>
                    {log.new_value ? JSON.stringify(log.new_value) : '—'}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
