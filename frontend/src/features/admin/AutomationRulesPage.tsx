import React, { useState, useEffect } from 'react';
import { api } from '../../lib/apiClient';
import { LoadingSpinner } from '../../components/feedback/LoadingSpinner';
import { Zap, Plus, CheckCircle2 } from 'lucide-react';

export const AutomationRulesPage: React.FC = () => {
  const [rules, setRules] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchRules = async () => {
      setIsLoading(true);
      try {
        const res = await api.get<any>('/automation/rules');
        setRules(res.data || []);
      } catch (e) {
        console.error('Failed to load automation rules', e);
      } finally {
        setIsLoading(false);
      }
    };
    fetchRules();
  }, []);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-6)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1 className="font-display font-bold text-2xl" style={{ color: 'var(--neutral-900)' }}>
            CRM Automation & Workflow Rules
          </h1>
          <p className="text-sm text-muted">
            Configurable business event triggers, automated task dispatch, and follow-up chains.
          </p>
        </div>
      </div>

      <div className="table-container">
        <table className="data-table">
          <thead>
            <tr>
              <th>Status</th>
              <th>Rule Name & Purpose</th>
              <th>Trigger Event</th>
              <th>Action Dispatched</th>
              <th>Execution Delay</th>
            </tr>
          </thead>
          <tbody>
            {rules.map((r) => (
              <tr key={r.id}>
                <td>
                  <span className={`badge ${r.is_active ? 'badge-won' : 'badge-lost'}`}>
                    {r.is_active ? 'Active' : 'Disabled'}
                  </span>
                </td>
                <td>
                  <div className="font-semibold text-sm text-dark">{r.name}</div>
                  <div className="text-xs text-muted">{r.description}</div>
                </td>
                <td>
                  <code className="font-mono text-xs text-primary" style={{ backgroundColor: 'var(--color-primary-subtle)', padding: '2px 6px', borderRadius: '4px' }}>
                    {r.trigger_event}
                  </code>
                </td>
                <td>
                  <span className="text-xs font-semibold text-dark">{r.action_type}</span>
                </td>
                <td>
                  <span className="text-xs text-muted">
                    {r.delay_minutes > 0 ? `${r.delay_minutes} mins` : 'Immediate'}
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
