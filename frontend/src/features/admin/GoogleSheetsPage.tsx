import React, { useState, useEffect } from 'react';
import { api } from '../../lib/apiClient';
import { LoadingSpinner } from '../../components/feedback/LoadingSpinner';
import { Modal } from '../../components/ui/Modal';
import { FileSpreadsheet, RefreshCw, CheckCircle2, AlertCircle, Play, Plus, UploadCloud } from 'lucide-react';
import { DragDropDataImport } from '../../components/leads/DragDropDataImport';

export const GoogleSheetsPage: React.FC = () => {
  const [configs, setConfigs] = useState<any[]>([]);
  const [runs, setRuns] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSyncing, setIsSyncing] = useState<string | null>(null);
  const [showFileUpload, setShowFileUpload] = useState(false);

  const fetchSyncData = async () => {
    setIsLoading(true);
    try {
      const [cRes, rRes] = await Promise.all([
        api.get<any>('/integrations/google-sheets/configs'),
        api.get<any>('/integrations/google-sheets/runs'),
      ]);
      setConfigs(cRes.data || []);
      setRuns(rRes.data || []);
    } catch (e) {
      console.error('Failed to load sheets sync data', e);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchSyncData();
  }, []);

  const handleTriggerManualSync = async (configId: string) => {
    setIsSyncing(configId);
    try {
      // Trigger a real sync against the configured Google Sheet.
      // No mock_data payload — the backend will read from the actual spreadsheet
      // using the service account credentials configured in the environment.
      // If GOOGLE_SHEETS_ENABLED is not set, the backend returns 0 rows and logs a warning.
      const res = await api.post<any>(`/integrations/google-sheets/sync/${configId}`, {});
      const imported = res.data?.rows_imported ?? 0;
      const duplicates = res.data?.rows_duplicate ?? 0;
      const errors = res.data?.rows_error ?? 0;
      if (imported === 0 && duplicates === 0) {
        alert(
          `Sync completed.\n\nNo new leads were imported.\n\nThis is expected if:\n• Google Sheets API credentials are not yet configured (GOOGLE_SHEETS_ENABLED=false)\n• All rows in the sheet have already been imported previously\n\nRows read: ${res.data?.rows_read ?? 0} | Errors: ${errors}`
        );
      } else {
        alert(
          `Sync completed successfully!\n\n✓ Imported: ${imported} new leads\n⊘ Duplicates skipped: ${duplicates}\n✗ Errors: ${errors}\n\nNew leads are now in the Unassigned Pool.`
        );
      }
      await fetchSyncData();
    } catch (err: any) {
      alert(err.message || 'Sync failed');
    } finally {
      setIsSyncing(null);
    }
  };

  if (isLoading) return <LoadingSpinner message="Loading Google Sheets sync engines..." />;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-6)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 'var(--space-3)' }}>
        <div>
          <h1 className="font-display font-bold text-2xl" style={{ color: 'var(--neutral-900)' }}>
            Google Sheets Lead Synchronization Engine
          </h1>
          <p className="text-sm text-muted">
            Automated, idempotent ingestion pipeline for Google Sheets and File Uploads with field validation and duplicate detection.
          </p>
        </div>
        <button
          onClick={() => setShowFileUpload(!showFileUpload)}
          className={`btn ${showFileUpload ? 'btn-primary' : 'btn-outline'} btn-md`}
          style={{ display: 'inline-flex', alignItems: 'center', gap: '8px' }}
        >
          <UploadCloud size={16} />
          <span>{showFileUpload ? 'Hide File Upload' : 'Upload Data File (CSV / Excel)'}</span>
        </button>
      </div>

      {/* Drag & Drop Data Ingestion Component */}
      {showFileUpload && (
        <DragDropDataImport
          onImportSuccess={async () => {
            await fetchSyncData();
          }}
        />
      )}

      {/* Sync Configurations Card */}
      <div>
        <h3 className="card-title text-base" style={{ marginBottom: 'var(--space-3)' }}>
          Active Spreadsheet Connections
        </h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(360px, 1fr))', gap: 'var(--space-4)' }}>
          {configs.map((cfg) => (
            <div key={cfg.id} className="card" style={{ padding: 'var(--space-5)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 'var(--space-2)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                  <FileSpreadsheet size={20} style={{ color: 'var(--color-success)' }} />
                  <span className="font-bold text-base text-dark">{cfg.name}</span>
                </div>
                <span className="badge badge-won">Active Sync</span>
              </div>

              <div style={{ fontSize: '11px', color: 'var(--neutral-600)', margin: 'var(--space-2) 0' }}>
                Spreadsheet ID: <code className="font-mono text-muted">{cfg.spreadsheet_id.slice(0, 20)}...</code>
              </div>

              <div style={{ fontSize: '11px', color: 'var(--neutral-600)', marginBottom: 'var(--space-4)' }}>
                Last successful sync:{' '}
                <strong>
                  {cfg.last_synced_at ? new Date(cfg.last_synced_at).toLocaleString() : 'Never'}
                </strong>
              </div>

              <button
                disabled={isSyncing === cfg.id}
                onClick={() => handleTriggerManualSync(cfg.id)}
                className="btn btn-accent btn-sm"
                style={{ width: '100%' }}
              >
                <RefreshCw size={14} className={isSyncing === cfg.id ? 'animate-spin' : ''} />
                <span>{isSyncing === cfg.id ? 'Synchronizing...' : 'Trigger Sync Now'}</span>
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Sync Execution History */}
      <div>
        <h3 className="card-title text-base" style={{ marginBottom: 'var(--space-3)' }}>
          Recent Synchronization Runs ({runs.length})
        </h3>
        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Status</th>
                <th>Spreadsheet Name</th>
                <th>Triggered By</th>
                <th>Rows Read</th>
                <th>Imported</th>
                <th>Duplicates</th>
                <th>Errors</th>
                <th>Execution Time</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((r) => (
                <tr key={r.id}>
                  <td>
                    <span className={`badge ${r.status === 'COMPLETED' ? 'badge-won' : 'badge-lost'}`}>
                      {r.status}
                    </span>
                  </td>
                  <td>
                    <span className="font-semibold text-sm text-dark">{r.config_name || 'Inbound Leads Sheet'}</span>
                  </td>
                  <td>
                    <span className="text-xs text-muted font-medium">{r.triggered_by}</span>
                  </td>
                  <td>
                    <span className="text-xs font-bold">{r.rows_read}</span>
                  </td>
                  <td>
                    <span className="text-xs font-bold text-success" style={{ color: 'var(--color-success)' }}>
                      +{r.rows_imported}
                    </span>
                  </td>
                  <td>
                    <span className="text-xs text-muted">{r.rows_duplicate}</span>
                  </td>
                  <td>
                    <span className="text-xs font-semibold" style={{ color: r.rows_error > 0 ? 'var(--color-danger)' : 'var(--neutral-400)' }}>
                      {r.rows_error}
                    </span>
                  </td>
                  <td>
                    <span className="text-xs text-muted">
                      {r.completed_at ? new Date(r.completed_at).toLocaleTimeString() : '—'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
