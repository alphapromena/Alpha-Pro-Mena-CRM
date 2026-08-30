import React, { useState, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  UploadCloud,
  FileSpreadsheet,
  CheckCircle2,
  AlertTriangle,
  FileText,
  X,
  ArrowRight,
  RefreshCw,
  Eye,
  SlidersHorizontal,
  Layers,
  Database,
} from 'lucide-react';
import { useTranslation } from '../../i18n';

interface PreviewData {
  filename: string;
  total_rows: number;
  headers: string[];
  preview_rows: Record<string, any>[];
  detected_mapping: Record<string, string>;
}

interface ImportResult {
  filename: string;
  total_processed: number;
  rows_ready: number;
  rows_duplicate: number;
  rows_invalid: number;
  rows_error: number;
  error_details?: string[];
}

interface DragDropDataImportProps {
  onImportSuccess?: (result: ImportResult) => void;
  onSwitchToGoogleSheets?: () => void;
}

export const DragDropDataImport: React.FC<DragDropDataImportProps> = ({
  onImportSuccess,
  onSwitchToGoogleSheets,
}) => {
  const { isRTL } = useTranslation();
  const fileInputRef = useRef<HTMLInputElement>(null);

  // States: 'idle' | 'dragover' | 'previewing' | 'processing' | 'success' | 'error'
  const [dragState, setDragState] = useState<'idle' | 'dragover' | 'previewing' | 'processing' | 'success' | 'error'>('idle');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewData, setPreviewData] = useState<PreviewData | null>(null);
  const [columnMapping, setColumnMapping] = useState<Record<string, string>>({});
  const [importResult, setImportResult] = useState<ImportResult | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [processingStep, setProcessingStep] = useState<string>('Reading file...');

  const crmFields = [
    { key: 'first_name', labelEn: 'First Name', labelAr: 'الاسم الأول', required: true },
    { key: 'last_name', labelEn: 'Last Name', labelAr: 'اسم العائلة', required: false },
    { key: 'email', labelEn: 'Email Address', labelAr: 'البريد الإلكتروني', required: false },
    { key: 'phone', labelEn: 'Phone Number', labelAr: 'رقم الهاتف', required: false },
    { key: 'company', labelEn: 'Company Name', labelAr: 'اسم الشركة', required: false },
    { key: 'position', labelEn: 'Job Position', labelAr: 'المنصب الوظيفي', required: false },
    { key: 'country', labelEn: 'Country', labelAr: 'الدولة', required: false },
    { key: 'industry', labelEn: 'Industry / Sector', labelAr: 'القطاع', required: false },
    { key: 'source', labelEn: 'Lead Source', labelAr: 'المصدر', required: false },
  ];

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (dragState !== 'processing') {
      setDragState('dragover');
    }
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (dragState === 'dragover') {
      setDragState('idle');
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (dragState === 'processing') return;
    setDragState('idle');

    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      processFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      processFile(e.target.files[0]);
    }
  };

  const processFile = async (file: File) => {
    const validExtensions = ['.csv', '.xlsx', '.xls'];
    const fileName = file.name.toLowerCase();
    const isValid = validExtensions.some((ext) => fileName.endsWith(ext));

    if (!isValid) {
      setErrorMessage(
        isRTL
          ? 'نوع الملف غير مدعوم. يرجى رفع ملف بصيغة CSV أو XLSX أو XLS.'
          : 'Unsupported file format. Please upload a .csv, .xlsx, or .xls file.'
      );
      setDragState('error');
      return;
    }

    setSelectedFile(file);
    setDragState('processing');
    setProcessingStep(isRTL ? 'جاري قراءة الملف واستخراج البيانات...' : 'Reading file and extracting schema...');

    try {
      const formData = new FormData();
      formData.append('file', file);

      const token = localStorage.getItem('token');
      const response = await fetch('/api/v1/admin/import/preview', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
        },
        body: formData,
      });

      if (!response.ok) {
        const errJson = await response.json().catch(() => ({}));
        throw new Error(errJson.error?.message || 'Failed to parse file preview.');
      }

      const resData = await response.json();
      const pData: PreviewData = resData.data;
      setPreviewData(pData);
      setColumnMapping(pData.detected_mapping || {});
      setDragState('previewing');
    } catch (err: any) {
      setErrorMessage(err.message || 'Error occurred while previewing file.');
      setDragState('error');
    }
  };

  const handleCommitImport = async () => {
    if (!selectedFile) return;
    setDragState('processing');

    setProcessingStep(isRTL ? 'جاري التحقق من صحة البيانات وتنسيق الحقول...' : 'Validating rows and normalizing fields...');
    await new Promise((r) => setTimeout(r, 400));
    setProcessingStep(isRTL ? 'فحص جهات الاتصال المكررة ومنع التكرار...' : 'Checking duplicate leads and matching companies...');
    await new Promise((r) => setTimeout(r, 400));
    setProcessingStep(isRTL ? 'إدراج العملاء في مجمع البيانات غير المعين...' : 'Importing leads into New Leads Pool...');

    try {
      const formData = new FormData();
      formData.append('file', selectedFile);
      formData.append('mapping', JSON.stringify(columnMapping));

      const token = localStorage.getItem('token');
      const response = await fetch('/api/v1/admin/import/commit', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
        },
        body: formData,
      });

      if (!response.ok) {
        const errJson = await response.json().catch(() => ({}));
        throw new Error(errJson.error?.message || 'Failed to commit file import.');
      }

      const resData = await response.json();
      const result: ImportResult = resData.data;
      setImportResult(result);
      setDragState('success');
      if (onImportSuccess) {
        onImportSuccess(result);
      }
    } catch (err: any) {
      setErrorMessage(err.message || 'Error occurred while importing leads.');
      setDragState('error');
    }
  };

  const resetAll = () => {
    setSelectedFile(null);
    setPreviewData(null);
    setColumnMapping({});
    setImportResult(null);
    setErrorMessage(null);
    setDragState('idle');
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
      {/* Dual Ingestion Selector Bar */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: 'var(--space-3) var(--space-4)',
          backgroundColor: 'var(--bg-surface)',
          border: '1px solid var(--border-color)',
          borderRadius: 'var(--radius-lg)',
          flexWrap: 'wrap',
          gap: 'var(--space-3)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
          <div
            style={{
              width: '36px',
              height: '36px',
              borderRadius: 'var(--radius-md)',
              backgroundColor: 'var(--color-primary-subtle)',
              color: 'var(--color-primary)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <Database size={20} />
          </div>
          <div>
            <div style={{ fontSize: '14px', fontWeight: 700, color: 'var(--neutral-900)' }}>
              {isRTL ? 'استيراد وإدخال بيانات العملاء' : 'Lead Ingestion & Inactive Pool'}
            </div>
            <div style={{ fontSize: '12px', color: 'var(--neutral-400)' }}>
              {isRTL ? 'إدخال موحد عبر الملفات وقنوات Google Sheets' : 'Unified ingestion pipeline via File Upload or Google Sheets'}
            </div>
          </div>
        </div>

        {onSwitchToGoogleSheets && (
          <button
            type="button"
            onClick={onSwitchToGoogleSheets}
            className="btn btn-outline"
            style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', fontSize: '12px', padding: '6px 12px' }}
          >
            <FileSpreadsheet size={15} />
            {isRTL ? 'الربط مع Google Sheets' : 'Connect Google Sheet'}
          </button>
        )}
      </div>

      <AnimatePresence mode="wait">
        {/* STATE 1: IDLE / DRAG ACTIVE */}
        {(dragState === 'idle' || dragState === 'dragover') && (
          <motion.div
            key="dropzone"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            style={{
              border: dragState === 'dragover' ? '2px dashed var(--color-primary)' : '2px dashed var(--border-strong)',
              backgroundColor: dragState === 'dragover' ? 'var(--color-primary-subtle)' : 'var(--bg-surface)',
              borderRadius: 'var(--radius-xl)',
              padding: 'var(--space-10) var(--space-6)',
              textAlign: 'center',
              cursor: 'pointer',
              transition: 'all var(--transition-fast)',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 'var(--space-3)',
            }}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv,.xlsx,.xls"
              onChange={handleFileSelect}
              style={{ display: 'none' }}
            />

            <motion.div
              animate={{ scale: dragState === 'dragover' ? 1.1 : 1 }}
              transition={{ duration: 0.15 }}
              style={{
                width: '64px',
                height: '64px',
                borderRadius: 'var(--radius-full)',
                backgroundColor: 'var(--bg-surface-elevated)',
                border: '1px solid var(--border-color)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: 'var(--color-primary)',
              }}
            >
              <UploadCloud size={32} />
            </motion.div>

            <div>
              <div style={{ fontSize: '16px', fontWeight: 800, color: 'var(--neutral-900)', marginBottom: '4px' }}>
                {isRTL ? 'إسقاط ملف البيانات هنا' : 'Upload New Lead Data'}
              </div>
              <div style={{ fontSize: '13px', color: 'var(--neutral-500)' }}>
                {isRTL ? 'اسحب وأسقط الملف أو ' : 'Drag & drop your data file here or '}
                <span style={{ color: 'var(--color-primary)', fontWeight: 700, textDecoration: 'underline' }}>
                  {isRTL ? 'تصفح من جهازك' : 'Browse Files'}
                </span>
              </div>
            </div>

            <div
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 'var(--space-2)',
                padding: '4px 12px',
                borderRadius: 'var(--radius-full)',
                backgroundColor: 'var(--bg-surface-elevated)',
                border: '1px solid var(--border-light)',
                fontSize: '11px',
                fontWeight: 700,
                color: 'var(--neutral-400)',
                letterSpacing: '0.5px',
              }}
            >
              CSV • XLSX • XLS
            </div>
          </motion.div>
        )}

        {/* STATE 2: PROCESSING / PROGRESS */}
        {dragState === 'processing' && (
          <motion.div
            key="processing"
            initial={{ opacity: 0, scale: 0.96 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0 }}
            style={{
              padding: 'var(--space-10) var(--space-6)',
              backgroundColor: 'var(--bg-surface)',
              border: '1px solid var(--border-color)',
              borderRadius: 'var(--radius-xl)',
              textAlign: 'center',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 'var(--space-4)',
            }}
          >
            <div
              style={{
                width: '56px',
                height: '56px',
                borderRadius: 'var(--radius-full)',
                backgroundColor: 'var(--color-primary-subtle)',
                color: 'var(--color-primary)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <RefreshCw size={28} className="animate-spin" />
            </div>

            <div>
              <div style={{ fontSize: '16px', fontWeight: 800, color: 'var(--neutral-900)' }}>
                {selectedFile?.name || 'Processing Lead Ingestion...'}
              </div>
              <div style={{ fontSize: '13px', color: 'var(--neutral-500)', marginTop: '4px' }}>
                {processingStep}
              </div>
            </div>
          </motion.div>
        )}

        {/* STATE 3: PREVIEW & COLUMN MAPPING */}
        {dragState === 'previewing' && previewData && (
          <motion.div
            key="preview"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            style={{
              backgroundColor: 'var(--bg-surface)',
              border: '1px solid var(--border-color)',
              borderRadius: 'var(--radius-xl)',
              padding: 'var(--space-5)',
              display: 'flex',
              flexDirection: 'column',
              gap: 'var(--space-4)',
            }}
          >
            {/* Header info */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 'var(--space-2)' }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <FileText size={18} color="var(--color-primary)" />
                  <span style={{ fontSize: '15px', fontWeight: 800, color: 'var(--neutral-900)' }}>
                    {previewData.filename}
                  </span>
                  <span
                    style={{
                      fontSize: '11px',
                      fontWeight: 700,
                      backgroundColor: 'var(--bg-surface-elevated)',
                      color: 'var(--neutral-600)',
                      padding: '2px 8px',
                      borderRadius: 'var(--radius-full)',
                    }}
                  >
                    {previewData.total_rows} {isRTL ? 'صف تم رصده' : 'rows detected'}
                  </span>
                </div>
                <div style={{ fontSize: '12px', color: 'var(--neutral-400)', marginTop: '2px' }}>
                  {isRTL
                    ? 'تحقق من مطابقة الحقول أدناه ثم اضغط على استيراد البيانات'
                    : 'Verify detected column mappings and preview the first rows before importing.'}
                </div>
              </div>

              <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
                <button
                  type="button"
                  onClick={resetAll}
                  className="btn btn-outline"
                  style={{ fontSize: '13px', padding: '6px 14px' }}
                >
                  <X size={15} /> {isRTL ? 'إلغاء' : 'Cancel'}
                </button>
                <button
                  type="button"
                  onClick={handleCommitImport}
                  className="btn btn-primary"
                  style={{ fontSize: '13px', padding: '6px 18px', fontWeight: 800 }}
                >
                  <CheckCircle2 size={16} /> {isRTL ? 'تأكيد الاستيراد' : 'Confirm & Import Leads'}
                </button>
              </div>
            </div>

            {/* Column Mapping Selectors */}
            <div
              style={{
                backgroundColor: 'var(--bg-surface-elevated)',
                border: '1px solid var(--border-light)',
                borderRadius: 'var(--radius-lg)',
                padding: 'var(--space-4)',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: 'var(--space-3)' }}>
                <SlidersHorizontal size={15} color="var(--color-primary)" />
                <span style={{ fontSize: '12px', fontWeight: 800, color: 'var(--neutral-700)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                  {isRTL ? 'مطابقة أعمدة الملف مع حقول CRM' : 'CRM Field Column Mapping'}
                </span>
              </div>

              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))',
                  gap: 'var(--space-3)',
                }}
              >
                {crmFields.map((field) => (
                  <div key={field.key} style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                    <label style={{ fontSize: '11px', fontWeight: 700, color: 'var(--neutral-600)' }}>
                      {isRTL ? field.labelAr : field.labelEn}
                      {field.required && <span style={{ color: 'var(--color-danger)', marginLeft: '2px' }}>*</span>}
                    </label>
                    <select
                      value={columnMapping[field.key] || ''}
                      onChange={(e) =>
                        setColumnMapping((prev) => ({
                          ...prev,
                          [field.key]: e.target.value,
                        }))
                      }
                      style={{
                        padding: '6px 10px',
                        fontSize: '12px',
                        borderRadius: 'var(--radius-md)',
                        border: '1px solid var(--border-color)',
                        backgroundColor: 'var(--bg-surface)',
                        color: 'var(--neutral-900)',
                      }}
                    >
                      <option value="">{isRTL ? '— غير محدد —' : '— Not Mapped —'}</option>
                      {previewData.headers.map((header) => (
                        <option key={header} value={header}>
                          {header}
                        </option>
                      ))}
                    </select>
                  </div>
                ))}
              </div>
            </div>

            {/* Row Preview Table */}
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: 'var(--space-2)' }}>
                <Eye size={15} color="var(--neutral-400)" />
                <span style={{ fontSize: '12px', fontWeight: 700, color: 'var(--neutral-600)' }}>
                  {isRTL ? 'معاينة أول 20 سجلاً' : 'Preview (First 20 Rows)'}
                </span>
              </div>

              <div
                style={{
                  overflowX: 'auto',
                  border: '1px solid var(--border-color)',
                  borderRadius: 'var(--radius-lg)',
                  maxHeight: '320px',
                }}
              >
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
                  <thead style={{ position: 'sticky', top: 0, backgroundColor: 'var(--bg-surface-elevated)', zIndex: 2 }}>
                    <tr>
                      <th style={{ padding: '8px 12px', textAlign: isRTL ? 'right' : 'left', borderBottom: '1px solid var(--border-color)', color: 'var(--neutral-500)' }}>#</th>
                      {previewData.headers.map((h) => (
                        <th
                          key={h}
                          style={{
                            padding: '8px 12px',
                            textAlign: isRTL ? 'right' : 'left',
                            borderBottom: '1px solid var(--border-color)',
                            color: 'var(--neutral-800)',
                            fontWeight: 700,
                            whiteSpace: 'nowrap',
                          }}
                        >
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {previewData.preview_rows.map((row, rIdx) => (
                      <tr
                        key={rIdx}
                        style={{
                          backgroundColor: rIdx % 2 === 0 ? 'var(--bg-surface)' : 'var(--bg-surface-elevated)',
                          borderBottom: '1px solid var(--border-light)',
                        }}
                      >
                        <td style={{ padding: '6px 12px', color: 'var(--neutral-400)' }}>{rIdx + 1}</td>
                        {previewData.headers.map((h) => (
                          <td
                            key={h}
                            style={{
                              padding: '6px 12px',
                              color: 'var(--neutral-700)',
                              whiteSpace: 'nowrap',
                              maxWidth: '220px',
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                            }}
                          >
                            {row[h] || '—'}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </motion.div>
        )}

        {/* STATE 4: SUCCESS SUMMARY */}
        {dragState === 'success' && importResult && (
          <motion.div
            key="success"
            initial={{ opacity: 0, scale: 0.98 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0 }}
            style={{
              backgroundColor: 'var(--bg-surface)',
              border: '1px solid var(--border-color)',
              borderRadius: 'var(--radius-xl)',
              padding: 'var(--space-6)',
              display: 'flex',
              flexDirection: 'column',
              gap: 'var(--space-4)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
              <div
                style={{
                  width: '44px',
                  height: '44px',
                  borderRadius: 'var(--radius-full)',
                  backgroundColor: 'var(--color-success-bg)',
                  border: '1px solid var(--color-success-border)',
                  color: 'var(--color-success)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <CheckCircle2 size={24} />
              </div>
              <div>
                <div style={{ fontSize: '16px', fontWeight: 800, color: 'var(--neutral-900)' }}>
                  {isRTL ? 'تمت معالجة واستيراد البيانات بنجاح!' : 'Lead Ingestion Completed Successfully!'}
                </div>
                <div style={{ fontSize: '13px', color: 'var(--neutral-500)' }}>
                  {importResult.filename} • {importResult.total_processed} {isRTL ? 'سجلاً تمت معالجتها' : 'rows processed'}
                </div>
              </div>
            </div>

            {/* Metrics Breakdown */}
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
                gap: 'var(--space-3)',
              }}
            >
              <div
                style={{
                  padding: 'var(--space-3) var(--space-4)',
                  borderRadius: 'var(--radius-lg)',
                  backgroundColor: 'var(--color-success-bg)',
                  border: '1px solid var(--color-success-border)',
                }}
              >
                <div style={{ fontSize: '11px', fontWeight: 700, color: 'var(--color-success-text)' }}>
                  {isRTL ? 'جاهزة في المجمع' : 'Ready Leads'}
                </div>
                <div style={{ fontSize: '20px', fontWeight: 800, color: 'var(--color-success)' }}>
                  {importResult.rows_ready}
                </div>
              </div>

              <div
                style={{
                  padding: 'var(--space-3) var(--space-4)',
                  borderRadius: 'var(--radius-lg)',
                  backgroundColor: 'var(--bg-surface-elevated)',
                  border: '1px solid var(--border-color)',
                }}
              >
                <div style={{ fontSize: '11px', fontWeight: 700, color: 'var(--neutral-500)' }}>
                  {isRTL ? 'مكررة (تم تخطيها)' : 'Duplicates (Skipped)'}
                </div>
                <div style={{ fontSize: '20px', fontWeight: 800, color: 'var(--neutral-700)' }}>
                  {importResult.rows_duplicate}
                </div>
              </div>

              <div
                style={{
                  padding: 'var(--space-3) var(--space-4)',
                  borderRadius: 'var(--radius-lg)',
                  backgroundColor: 'var(--color-warning-bg)',
                  border: '1px solid var(--color-warning-border)',
                }}
              >
                <div style={{ fontSize: '11px', fontWeight: 700, color: 'var(--color-warning-text)' }}>
                  {isRTL ? 'غير صالحة' : 'Invalid / Incomplete'}
                </div>
                <div style={{ fontSize: '20px', fontWeight: 800, color: 'var(--color-warning)' }}>
                  {importResult.rows_invalid}
                </div>
              </div>

              <div
                style={{
                  padding: 'var(--space-3) var(--space-4)',
                  borderRadius: 'var(--radius-lg)',
                  backgroundColor: 'var(--bg-surface-elevated)',
                  border: '1px solid var(--border-color)',
                }}
              >
                <div style={{ fontSize: '11px', fontWeight: 700, color: 'var(--neutral-500)' }}>
                  {isRTL ? 'أخطاء المعالجة' : 'Errors'}
                </div>
                <div style={{ fontSize: '20px', fontWeight: 800, color: 'var(--neutral-700)' }}>
                  {importResult.rows_error}
                </div>
              </div>
            </div>

            {importResult.error_details && importResult.error_details.length > 0 && (
              <div
                style={{
                  padding: 'var(--space-3)',
                  borderRadius: 'var(--radius-md)',
                  backgroundColor: 'var(--bg-surface-elevated)',
                  border: '1px solid var(--border-light)',
                  fontSize: '11px',
                  color: 'var(--neutral-600)',
                }}
              >
                <div style={{ fontWeight: 700, marginBottom: '4px' }}>{isRTL ? 'تفاصيل الملاحظات:' : 'Review Notes:'}</div>
                {importResult.error_details.map((err, i) => (
                  <div key={i} style={{ fontFamily: 'var(--font-mono)' }}>• {err}</div>
                ))}
              </div>
            )}

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 'var(--space-2)', marginTop: 'var(--space-2)' }}>
              <button
                type="button"
                onClick={resetAll}
                className="btn btn-outline"
                style={{ fontSize: '13px', padding: '6px 16px' }}
              >
                {isRTL ? 'استيراد ملف آخر' : 'Upload Another File'}
              </button>
            </div>
          </motion.div>
        )}

        {/* STATE 5: ERROR */}
        {dragState === 'error' && (
          <motion.div
            key="error"
            initial={{ opacity: 0, scale: 0.98 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0 }}
            style={{
              padding: 'var(--space-6)',
              backgroundColor: 'var(--color-danger-bg)',
              border: '1px solid var(--color-danger-border)',
              borderRadius: 'var(--radius-xl)',
              display: 'flex',
              flexDirection: 'column',
              gap: 'var(--space-3)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', color: 'var(--color-danger)' }}>
              <AlertTriangle size={20} />
              <span style={{ fontSize: '14px', fontWeight: 800 }}>
                {isRTL ? 'تعذر إتمام استيراد الملف' : 'File Ingestion Failed'}
              </span>
            </div>
            <div style={{ fontSize: '13px', color: 'var(--color-danger-text)' }}>
              {errorMessage || 'An unexpected error occurred during processing.'}
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 'var(--space-2)' }}>
              <button
                type="button"
                onClick={resetAll}
                className="btn btn-primary"
                style={{ fontSize: '12px', padding: '6px 14px' }}
              >
                {isRTL ? 'إعادة المحاولة' : 'Try Again'}
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};
