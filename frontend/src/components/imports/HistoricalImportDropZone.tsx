import React, { useCallback, useRef, useState } from 'react';
import { UploadCloud, FileSpreadsheet, AlertTriangle, CheckCircle2, Download, X, RefreshCw } from 'lucide-react';
import { useTranslation } from '../../i18n';

/**
 * Drag-and-drop import for historical demos and follow-ups.
 *
 * Two steps on purpose. Dropping a file only ever previews it; the server writes
 * nothing until the user presses the confirm button, and the confirm sends back
 * the checksum the preview returned so it cannot act on a different file than
 * the one on screen.
 */

type ActivityKind = 'DEMO' | 'FOLLOW_UP' | 'ALL';

interface PreviewRow {
  sheet: string;
  source_row: number;
  activity_type: string;
  name: string;
  company: string;
  email: string;
  phone: string;
  salesperson: string;
  activity_date: string | null;
  outcome: string;
  notes: string;
  next_step: string;
  matched_contact: string | null;
  match_rule: string | null;
  owner_conflict: boolean;
  already_imported: boolean;
  problems: string[];
  importable: boolean;
}

interface PreviewResult {
  source_file_checksum: string;
  filename: string;
  sheets: Array<{ sheet: string; activity_type: string; rows: number; importable: number; missing_date: number }>;
  summary: Record<string, number>;
  rows: PreviewRow[];
}

interface Props {
  /** Which activity type this page cares about. ALL shows everything. */
  kind?: ActivityKind;
  onImported?: () => void;
}

const API_BASE = '/api/v1';

export const HistoricalImportDropZone: React.FC<Props> = ({ kind = 'ALL', onImported }) => {
  const { isRTL } = useTranslation();
  const inputRef = useRef<HTMLInputElement>(null);
  const fileRef = useRef<File | null>(null);

  const [isDragging, setIsDragging] = useState(false);
  const [isBusy, setIsBusy] = useState(false);
  const [phase, setPhase] = useState<'idle' | 'previewing' | 'preview' | 'importing' | 'done'>('idle');
  const [preview, setPreview] = useState<PreviewResult | null>(null);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  const reset = () => {
    fileRef.current = null;
    setPreview(null);
    setResult(null);
    setError(null);
    setPhase('idle');
    if (inputRef.current) inputRef.current.value = '';
  };

  const runPreview = useCallback(async (file: File) => {
    setError(null);
    setIsBusy(true);
    setPhase('previewing');
    try {
      const body = new FormData();
      body.append('file', file);
      const res = await fetch(`${API_BASE}/imports/historical/preview`, {
        method: 'POST',
        credentials: 'include',
        body,
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.error?.message || 'Could not read that file.');
      fileRef.current = file;
      setPreview(data);
      setPhase('preview');
    } catch (e: any) {
      setError(e?.message || 'Could not read that file.');
      setPhase('idle');
    } finally {
      setIsBusy(false);
    }
  }, []);

  const runCommit = useCallback(async () => {
    if (!preview || !fileRef.current) return;
    setError(null);
    setIsBusy(true);
    setPhase('importing');
    try {
      const body = new FormData();
      body.append('file', fileRef.current);
      // Sending the previewed checksum back is what ties the write to what was reviewed.
      body.append('confirm_checksum', preview.source_file_checksum);
      const res = await fetch(`${API_BASE}/imports/historical/commit`, {
        method: 'POST',
        credentials: 'include',
        body,
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.error?.message || 'Import failed.');
      setResult(data);
      setPhase('done');
      onImported?.();
    } catch (e: any) {
      setError(e?.message || 'Import failed.');
      setPhase('preview');
    } finally {
      setIsBusy(false);
    }
  }, [preview, onImported]);

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) runPreview(file);
  };

  /** Rows the user could not import, as a CSV they can hand back to whoever owns the sheet. */
  const downloadErrorReport = () => {
    const rows = (preview?.rows || []).filter((r) => !r.importable);
    const header = ['sheet', 'source_row', 'activity_type', 'name', 'company', 'email', 'salesperson', 'activity_date', 'problems'];
    const escape = (v: any) => `"${String(v ?? '').replace(/"/g, '""')}"`;
    const csv = [
      header.join(','),
      ...rows.map((r) =>
        [r.sheet, r.source_row, r.activity_type, r.name, r.company, r.email, r.salesperson, r.activity_date || '', r.problems.join('; ')]
          .map(escape)
          .join(',')
      ),
    ].join('\n');

    const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `historical-import-issues-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const visibleRows = (preview?.rows || []).filter(
    (r) => kind === 'ALL' || r.activity_type === kind
  );
  const s = preview?.summary || {};

  return (
    <div style={{ marginBottom: 'var(--space-4)' }}>
      {phase === 'idle' && (
        <div
          onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={onDrop}
          onClick={() => inputRef.current?.click()}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') inputRef.current?.click(); }}
          style={{
            border: `2px dashed ${isDragging ? 'var(--color-primary)' : 'var(--border-color)'}`,
            backgroundColor: isDragging ? 'rgba(255,30,87,0.06)' : 'var(--bg-surface)',
            borderRadius: 'var(--radius-lg)',
            padding: 'var(--space-5)',
            textAlign: 'center',
            cursor: 'pointer',
            transition: 'all 0.15s ease',
          }}
        >
          <input
            ref={inputRef}
            type="file"
            accept=".xlsx,.xlsm"
            hidden
            onChange={(e) => { const f = e.target.files?.[0]; if (f) runPreview(f); }}
          />
          <UploadCloud size={28} style={{ color: 'var(--color-primary)', marginBottom: 8 }} />
          <div style={{ fontWeight: 700, fontSize: '14px' }}>
            {isRTL ? 'اسحب ملف الإكسل هنا لاستيراد السجلات التاريخية' : 'Drop the workbook here to import historical records'}
          </div>
          <div className="text-xs text-muted" style={{ marginTop: 4 }}>
            {isRTL
              ? 'يقرأ أوراق Demo و Ghaida fu و Amin fu. لن يُكتب أي شيء قبل أن تراجع وتؤكد.'
              : 'Reads the Demo, Ghaida fu and Amin fu sheets. Nothing is written until you review and confirm.'}
          </div>
        </div>
      )}

      {phase === 'previewing' && (
        <div style={{ padding: 'var(--space-4)', textAlign: 'center' }}>
          <RefreshCw size={20} className="spinning" />
          <div className="text-sm" style={{ marginTop: 8 }}>
            {isRTL ? 'جاري قراءة الملف...' : 'Reading the workbook...'}
          </div>
        </div>
      )}

      {error && (
        <div
          role="alert"
          style={{
            display: 'flex', alignItems: 'center', gap: 8, padding: 'var(--space-3)',
            border: '1px solid #ef4444', borderRadius: 'var(--radius-md)',
            backgroundColor: 'rgba(239,68,68,0.08)', color: '#b91c1c', fontSize: '13px',
            marginTop: 'var(--space-2)',
          }}
        >
          <AlertTriangle size={16} />
          <span>{error}</span>
        </div>
      )}

      {(phase === 'preview' || phase === 'importing') && preview && (
        <div style={{ border: '1px solid var(--border-color)', borderRadius: 'var(--radius-lg)', padding: 'var(--space-4)' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 'var(--space-3)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <FileSpreadsheet size={18} style={{ color: 'var(--color-primary)' }} />
              <strong style={{ fontSize: '14px' }}>{preview.filename}</strong>
            </div>
            <button onClick={reset} className="btn btn-ghost btn-sm" disabled={isBusy} aria-label="Cancel">
              <X size={15} />
            </button>
          </div>

          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-3)', marginBottom: 'var(--space-3)' }}>
            {[
              ['ready', isRTL ? 'جاهز' : 'Ready', '#10b981'],
              ['missing_contact', isRTL ? 'بدون جهة اتصال' : 'No contact', '#ef4444'],
              ['archived_contact', isRTL ? 'جهة مؤرشفة' : 'Archived contact', '#f59e0b'],
              ['missing_date', isRTL ? 'بدون تاريخ' : 'No date', '#f59e0b'],
              ['owner_conflicts', isRTL ? 'تعارض مالك' : 'Owner conflict', '#f59e0b'],
              ['already_imported', isRTL ? 'مستورد سابقاً' : 'Already imported', 'var(--neutral-500)'],
            ].map(([key, label, color]) => (
              <div key={key as string} style={{ minWidth: 96 }}>
                <div style={{ fontSize: '20px', fontWeight: 800, color: color as string, fontVariantNumeric: 'tabular-nums' }}>
                  {s[key as string] ?? 0}
                </div>
                <div className="text-xs text-muted">{label}</div>
              </div>
            ))}
          </div>

          <div style={{ maxHeight: 280, overflowY: 'auto', border: '1px solid var(--border-light)', borderRadius: 'var(--radius-md)' }}>
            <table style={{ width: '100%', fontSize: '12px', borderCollapse: 'collapse' }}>
              <thead style={{ position: 'sticky', top: 0, backgroundColor: 'var(--bg-surface-elevated)' }}>
                <tr>
                  {['', isRTL ? 'الورقة' : 'Sheet', isRTL ? 'صف' : 'Row', isRTL ? 'الاسم' : 'Name',
                    isRTL ? 'التاريخ' : 'Date', isRTL ? 'مرتبط بـ' : 'Matched', isRTL ? 'ملاحظات' : 'Issues'].map((h, i) => (
                    <th key={i} style={{ textAlign: isRTL ? 'right' : 'left', padding: '6px 8px', fontWeight: 700 }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {visibleRows.slice(0, 300).map((r, i) => (
                  <tr key={`${r.sheet}-${r.source_row}-${i}`} style={{ borderTop: '1px solid var(--border-light)' }}>
                    <td style={{ padding: '5px 8px' }}>
                      {r.importable
                        ? <CheckCircle2 size={13} style={{ color: '#10b981' }} />
                        : <AlertTriangle size={13} style={{ color: '#f59e0b' }} />}
                    </td>
                    <td style={{ padding: '5px 8px' }}>{r.sheet}</td>
                    <td style={{ padding: '5px 8px', fontVariantNumeric: 'tabular-nums' }}>{r.source_row}</td>
                    <td style={{ padding: '5px 8px' }}>{r.name}</td>
                    <td style={{ padding: '5px 8px', color: r.activity_date ? 'inherit' : 'var(--neutral-500)' }}>
                      {r.activity_date ? r.activity_date.slice(0, 10) : (isRTL ? 'بدون تاريخ' : 'no date')}
                    </td>
                    <td style={{ padding: '5px 8px' }}>{r.matched_contact || '--'}</td>
                    <td style={{ padding: '5px 8px', color: 'var(--neutral-500)' }}>{r.problems.join(', ')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {visibleRows.length > 300 && (
            <div className="text-xs text-muted" style={{ marginTop: 6 }}>
              {isRTL ? `تُعرض أول 300 من ${visibleRows.length}` : `Showing the first 300 of ${visibleRows.length}`}
            </div>
          )}

          <div style={{ display: 'flex', gap: 'var(--space-2)', marginTop: 'var(--space-3)', flexWrap: 'wrap' }}>
            <button onClick={runCommit} disabled={isBusy || !(s.ready > 0)} className="btn btn-accent">
              {phase === 'importing'
                ? (isRTL ? 'جاري الاستيراد...' : 'Importing...')
                : (isRTL ? `تأكيد استيراد ${s.ready ?? 0} سجل` : `Confirm import of ${s.ready ?? 0} records`)}
            </button>
            <button onClick={downloadErrorReport} className="btn btn-secondary" disabled={isBusy}>
              <Download size={14} /> {isRTL ? 'تقرير المشاكل' : 'Issue report'}
            </button>
            <button onClick={reset} className="btn btn-ghost" disabled={isBusy}>
              {isRTL ? 'إلغاء' : 'Cancel'}
            </button>
          </div>
        </div>
      )}

      {phase === 'done' && result && (
        <div
          style={{
            border: '1px solid #10b981', borderRadius: 'var(--radius-lg)',
            backgroundColor: 'rgba(16,185,129,0.06)', padding: 'var(--space-4)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
            <CheckCircle2 size={18} style={{ color: '#10b981' }} />
            <strong>{isRTL ? 'تم الاستيراد' : 'Import complete'}</strong>
          </div>
          <div className="text-sm">
            {isRTL
              ? `${result.imported.demos} ديمو و ${result.imported.follow_ups} متابعة.`
              : `${result.imported.demos} demos and ${result.imported.follow_ups} follow-ups.`}
          </div>
          <div className="text-xs text-muted" style={{ marginTop: 4 }}>
            {isRTL ? 'دفعة' : 'Batch'} {result.batch_id}
          </div>
          <button onClick={reset} className="btn btn-secondary btn-sm" style={{ marginTop: 'var(--space-3)' }}>
            {isRTL ? 'استيراد ملف آخر' : 'Import another file'}
          </button>
        </div>
      )}
    </div>
  );
};
