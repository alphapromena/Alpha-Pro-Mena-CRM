import React, { useState, useEffect } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { api, ApiError } from '../../lib/apiClient';
import { useAuthStore } from '../../store/authStore';
import { DemoItem, DemoStatus, DemoReportStatus } from '../../types';
import { Badge } from '../../components/ui/Badge';
import { Modal } from '../../components/ui/Modal';
import { LoadingSpinner } from '../../components/feedback/LoadingSpinner';
import { EmptyState } from '../../components/feedback/EmptyState';
import {
  Presentation,
  CheckCircle2,
  AlertCircle,
  Edit3,
  Plus,
  Calendar,
  Clock,
  Search,
  History,
  FileSpreadsheet,
  FileText,
  AlertTriangle,
  User,
  Building,
  ArrowRight,
  Download,
  Upload,
} from 'lucide-react';
import { useTranslation } from '../../i18n';

interface DemoCounts {
  ALL: number;
  INTERESTED_NEXT_STEP: number;
  NOT_INTERESTED: number;
  CANCELLED: number;
  POSTPONED: number;
  PENDING: number;
  NEEDS_REPORT: number;
  REPORT_COMPLETE: number;
  HISTORICAL: number;
}

export const DemosPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const { user } = useAuthStore();
  const { t, isRTL } = useTranslation();

  // Filters State — URL persisted
  const currentStatusParam = searchParams.get('status') || 'ALL';
  const currentReportStatusParam = searchParams.get('report_status') || '';
  const currentHistoricalParam = searchParams.get('is_historical') === 'true' ? true : undefined;

  const [statusFilter, setStatusFilter] = useState<string>(currentStatusParam);
  const [reportStatusFilter, setReportStatusFilter] = useState<string>(currentReportStatusParam);
  const [isHistoricalFilter, setIsHistoricalFilter] = useState<boolean | undefined>(currentHistoricalParam);
  const [searchQuery, setSearchQuery] = useState<string>(searchParams.get('search') || '');
  const [assignedUserFilter, setAssignedUserFilter] = useState<string>(searchParams.get('user_id') || '');

  // Data State
  const [demos, setDemos] = useState<DemoItem[]>([]);
  const [counts, setCounts] = useState<DemoCounts>({
    ALL: 0,
    INTERESTED_NEXT_STEP: 0,
    NOT_INTERESTED: 0,
    CANCELLED: 0,
    POSTPONED: 0,
    PENDING: 0,
    NEEDS_REPORT: 0,
    REPORT_COMPLETE: 0,
    HISTORICAL: 0,
  });
  const [usersList, setUsersList] = useState<any[]>([]);
  const [contactsList, setContactsList] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  // New Demo Modal
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [isHistoricalCreate, setIsHistoricalCreate] = useState(false);
  const [createForm, setCreateForm] = useState({
    contact_id: '',
    company_name: '',
    owner_id: user?.id || '',
    scheduled_at: '',
    historical_date: '',
    presenter: user?.full_name || '',
    attendees: '',
    topics_covered: '',
    summary: '',
    status: 'PENDING',
    result: '',
    reason: '',
    next_step: '',
    next_step_due_date: '',
    notes: '',
    historical_source: '',
  });
  const [createError, setCreateError] = useState<string | null>(null);
  const [isCreating, setIsCreating] = useState(false);

  // Complete Report / Edit Modal
  const [editingDemo, setEditingDemo] = useState<DemoItem | null>(null);
  const [reportForm, setReportForm] = useState({
    summary: '',
    presenter: '',
    attendees: '',
    topics_covered: '',
    status: 'PENDING',
    result: '',
    reason: '',
    next_step: '',
    next_step_due_date: '',
    notes: '',
  });
  const [reportError, setReportError] = useState<string | null>(null);
  const [isUpdatingReport, setIsUpdatingReport] = useState(false);

  // Import Modal State
  const [showImportModal, setShowImportModal] = useState(false);
  const [importText, setImportText] = useState('');
  const [importDryRun, setImportDryRun] = useState(true);
  const [importResult, setImportResult] = useState<any>(null);
  const [isImporting, setIsImporting] = useState(false);

  // Sync state to URL search parameters
  const updateQueryParams = (newStatus: string, newReportStatus?: string, newHistorical?: boolean, newSearch?: string, newUser?: string) => {
    const params: Record<string, string> = {};
    if (newStatus && newStatus !== 'ALL') params.status = newStatus;
    if (newReportStatus) params.report_status = newReportStatus;
    if (newHistorical) params.is_historical = 'true';
    if (newSearch) params.search = newSearch;
    if (newUser) params.user_id = newUser;
    setSearchParams(params, { replace: true });
  };

  // Load initial dropdowns
  useEffect(() => {
    const loadDropdowns = async () => {
      try {
        const [uRes, cRes] = await Promise.all([
          api.get<any>('/users'),
          api.get<any>('/contacts?per_page=100'),
        ]);
        setUsersList(uRes.data || []);
        setContactsList(cRes.data || []);
      } catch (e) {
        console.error('Failed to load metadata', e);
      }
    };
    loadDropdowns();
  }, []);

  // Fetch demo counts
  const fetchCounts = async () => {
    try {
      const params: Record<string, string> = {};
      if (assignedUserFilter) params.user_id = assignedUserFilter;
      const res = await api.get<any>('/demos/counts', params);
      if (res.data) setCounts(res.data);
    } catch (e) {
      console.error('Failed to fetch demo counts', e);
    }
  };

  // Fetch demos list
  const fetchDemos = async () => {
    setIsLoading(true);
    try {
      const params: Record<string, any> = {};
      if (statusFilter !== 'ALL') params.status = statusFilter;
      if (reportStatusFilter) params.report_status = reportStatusFilter;
      if (isHistoricalFilter !== undefined) params.is_historical = isHistoricalFilter;
      if (assignedUserFilter) params.user_id = assignedUserFilter;
      if (searchQuery.trim()) params.search = searchQuery.trim();

      const res = await api.get<any>('/demos', params);
      setDemos(res.data || []);
    } catch (e) {
      console.error('Failed to load demos', e);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchCounts();
    fetchDemos();
  }, [statusFilter, reportStatusFilter, isHistoricalFilter, assignedUserFilter, searchQuery]);

  const handleTabSelect = (st: string) => {
    setStatusFilter(st);
    setReportStatusFilter('');
    setIsHistoricalFilter(undefined);
    updateQueryParams(st, '', false, searchQuery, assignedUserFilter);
  };

  const handleToggleNeedsReport = () => {
    const nextVal = reportStatusFilter === 'NEEDS_REPORT' ? '' : 'NEEDS_REPORT';
    setReportStatusFilter(nextVal);
    updateQueryParams(statusFilter, nextVal, isHistoricalFilter, searchQuery, assignedUserFilter);
  };

  const handleToggleHistorical = () => {
    const nextVal = isHistoricalFilter ? undefined : true;
    setIsHistoricalFilter(nextVal);
    updateQueryParams(statusFilter, reportStatusFilter, nextVal, searchQuery, assignedUserFilter);
  };

  // Open Edit / Report modal
  const handleOpenReportModal = (demo: DemoItem) => {
    setEditingDemo(demo);
    setReportForm({
      summary: demo.summary || '',
      presenter: demo.presenter || user?.full_name || '',
      attendees: demo.attendees || '',
      topics_covered: demo.topics_covered || '',
      status: demo.status || 'PENDING',
      result: demo.result || '',
      reason: demo.reason || '',
      next_step: demo.next_step || '',
      next_step_due_date: demo.next_step_due_date ? demo.next_step_due_date.slice(0, 10) : '',
      notes: demo.notes || '',
    });
    setReportError(null);
  };

  const handleSubmitReport = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingDemo) return;

    // Report Summary validation
    if (!reportForm.summary.trim()) {
      setReportError('A complete summary of what was demonstrated is mandatory.');
      return;
    }

    // Status-conditional validations
    if (reportForm.status === 'INTERESTED_NEXT_STEP' && !reportForm.next_step.trim()) {
      setReportError('Interested / Next Step status requires specifying the agreed Next Step.');
      return;
    }
    if ((reportForm.status === 'POSTPONED' || reportForm.status === 'NOT_INTERESTED' || reportForm.status === 'CANCELLED') && !reportForm.reason.trim()) {
      setReportError(`${reportForm.status.replace(/_/g, ' ')} requires a detailed reason.`);
      return;
    }

    setReportError(null);
    setIsUpdatingReport(true);

    try {
      await api.patch(`/demos/${editingDemo.id}/report`, {
        summary: reportForm.summary.trim(),
        presenter: reportForm.presenter.trim() || undefined,
        attendees: reportForm.attendees.trim() || undefined,
        topics_covered: reportForm.topics_covered.trim() || undefined,
        status: reportForm.status,
        result: reportForm.result.trim() || undefined,
        reason: reportForm.reason.trim() || undefined,
        next_step: reportForm.next_step.trim() || undefined,
        next_step_due_date: reportForm.next_step_due_date ? new Date(reportForm.next_step_due_date).toISOString() : undefined,
        notes: reportForm.notes.trim() || undefined,
      });

      setEditingDemo(null);
      await Promise.all([fetchCounts(), fetchDemos()]);
    } catch (err: any) {
      if (err instanceof ApiError) {
        setReportError(err.message);
      } else {
        setReportError('Failed to save demo report.');
      }
    } finally {
      setIsUpdatingReport(false);
    }
  };

  const handleOpenCreateModal = (isHist: boolean = false) => {
    setIsHistoricalCreate(isHist);
    setCreateForm({
      contact_id: contactsList[0]?.id || '',
      company_name: '',
      owner_id: user?.id || '',
      scheduled_at: '',
      historical_date: new Date().toISOString().slice(0, 10),
      presenter: user?.full_name || '',
      attendees: '',
      topics_covered: '',
      summary: '',
      status: isHist ? 'INTERESTED_NEXT_STEP' : 'PENDING',
      result: '',
      reason: '',
      next_step: '',
      next_step_due_date: '',
      notes: '',
      historical_source: isHist ? 'Archived Sales Records' : '',
    });
    setCreateError(null);
    setShowCreateModal(true);
  };

  const handleSaveNewDemo = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!createForm.contact_id) {
      setCreateError('Target Contact is required.');
      return;
    }

    // Historical Demos require mandatory summary and date
    if (isHistoricalCreate) {
      if (!createForm.historical_date) {
        setCreateError('Original Historical Demo Date is required.');
        return;
      }
      if (!createForm.summary.trim()) {
        setCreateError('Summary of what was explained is mandatory for historical records.');
        return;
      }
    }

    setCreateError(null);
    setIsCreating(true);

    try {
      if (isHistoricalCreate) {
        await api.post('/demos/historical', {
          contact_id: createForm.contact_id,
          owner_id: createForm.owner_id || undefined,
          historical_date: new Date(createForm.historical_date).toISOString(),
          presenter: createForm.presenter.trim() || undefined,
          attendees: createForm.attendees.trim() || undefined,
          topics_covered: createForm.topics_covered.trim() || undefined,
          summary: createForm.summary.trim(),
          status: createForm.status,
          result: createForm.result.trim() || undefined,
          reason: createForm.reason.trim() || undefined,
          next_step: createForm.next_step.trim() || undefined,
          next_step_due_date: createForm.next_step_due_date ? new Date(createForm.next_step_due_date).toISOString() : undefined,
          notes: createForm.notes.trim() || undefined,
          historical_source: createForm.historical_source.trim() || 'Manual Historical Entry',
        });
      } else {
        await api.post('/demos', {
          contact_id: createForm.contact_id,
          owner_id: createForm.owner_id || undefined,
          scheduled_at: createForm.scheduled_at ? new Date(createForm.scheduled_at).toISOString() : undefined,
          presenter: createForm.presenter.trim() || undefined,
          attendees: createForm.attendees.trim() || undefined,
          topics_covered: createForm.topics_covered.trim() || undefined,
          summary: createForm.summary.trim() || undefined,
          status: createForm.status,
          result: createForm.result.trim() || undefined,
          reason: createForm.reason.trim() || undefined,
          next_step: createForm.next_step.trim() || undefined,
          next_step_due_date: createForm.next_step_due_date ? new Date(createForm.next_step_due_date).toISOString() : undefined,
          notes: createForm.notes.trim() || undefined,
        });
      }

      setShowCreateModal(false);
      await Promise.all([fetchCounts(), fetchDemos()]);
    } catch (err: any) {
      if (err instanceof ApiError) {
        setCreateError(err.message);
      } else {
        setCreateError('Failed to create demo record.');
      }
    } finally {
      setIsCreating(false);
    }
  };

  const handleImportSubmit = async (dryRun: boolean) => {
    if (!importText.trim()) return;
    setIsImporting(true);
    try {
      const res = await api.post<any>('/demos/import', {
        format: 'json',
        data: importText.trim(),
        dry_run: dryRun,
      });
      setImportResult(res.data);
      if (!dryRun && res.data?.imported_count > 0) {
        await Promise.all([fetchCounts(), fetchDemos()]);
      }
    } catch (e: any) {
      alert(e.message || 'Import failed.');
    } finally {
      setIsImporting(false);
    }
  };

  const sampleCsvTemplate = `contact_email,date,presenter,summary,status,next_step,historical_source
saleh@alphapromena.com,2025-11-15,Saleh,"Demonstrated CRM sales pipeline & bulk messaging",INTERESTED_NEXT_STEP,"Send commercial quotation by Monday","Historical 2025 Log"
amin@alphapromena.com,2025-10-20,Amin,"Overview of lead distribution module",POSTPONED,"Recall after budget approval in Q1","Pre-CRM Spreadsheet"`;

  const downloadTemplate = () => {
    const blob = new Blob([sampleCsvTemplate], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.setAttribute('href', url);
    link.setAttribute('download', 'historical_demos_template.csv');
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-6)' }}>
      {/* ── Top Header ─────────────────────────────────────────────────── */}
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
              {isRTL ? "العروض التوضيحية للمنتج (Demos)" : "Product Demonstrations"}
            </h1>
            <span
              style={{
                fontSize: '11px',
                fontWeight: 700,
                padding: '2px 8px',
                borderRadius: 'var(--radius-full)',
                backgroundColor: 'var(--color-accent-light)',
                color: 'var(--color-accent)',
                border: '1px solid var(--color-accent)',
              }}
            >
              {counts.ALL} {isRTL ? "عرض تجريبي" : "Total Demos"}
            </span>
          </div>
          <p className="text-sm text-muted" style={{ marginTop: '2px' }}>
            {isRTL
              ? "متابعة دورة حياة العروض التوضيحية، تقارير النتائج الإلزامية، وتوثيق العروض التاريخية السابقة."
              : "Enterprise demo operations: mandatory reports, outcome-based follow-ups, and historical tracking."}
          </p>
        </div>

        {/* Header Action Buttons */}
        <div style={{ display: 'flex', gap: 'var(--space-2)', alignItems: 'center', flexWrap: 'wrap' }}>
          <button
            onClick={() => handleOpenCreateModal(false)}
            className="btn btn-accent btn-sm"
            style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
          >
            <Plus size={15} />
            <span>{isRTL ? "إضافة عرض جديد" : "Schedule Demo"}</span>
          </button>

          <button
            onClick={() => handleOpenCreateModal(true)}
            className="btn btn-secondary btn-sm"
            style={{ display: 'flex', alignItems: 'center', gap: '6px', borderColor: '#D4AF37', color: '#B8860B' }}
          >
            <History size={15} />
            <span>{isRTL ? "إضافة عرض تاريخي" : "Add Historical Demo"}</span>
          </button>

          <button
            onClick={() => {
              setImportText('');
              setImportResult(null);
              setShowImportModal(true);
            }}
            className="btn btn-secondary btn-sm"
            style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
          >
            <FileSpreadsheet size={15} />
            <span>{isRTL ? "استيراد CSV" : "Import"}</span>
          </button>
        </div>
      </div>

      {/* ── Search & Filter Bar ────────────────────────────────────────── */}
      <div
        className="card"
        style={{
          padding: 'var(--space-3) var(--space-4)',
          backgroundColor: 'var(--bg-surface)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: 'var(--space-3)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)', flex: 1, minWidth: '260px' }}>
          <div style={{ position: 'relative', width: '100%', maxWidth: '380px' }}>
            <Search
              size={15}
              style={{
                position: 'absolute',
                left: isRTL ? 'auto' : '10px',
                right: isRTL ? '10px' : 'auto',
                top: '50%',
                transform: 'translateY(-50%)',
                color: 'var(--neutral-400)',
              }}
            />
            <input
              type="text"
              placeholder={isRTL ? "بحث بالعميل، الشركة، المسؤول، أو الملخص..." : "Search by contact, company, owner, summary..."}
              className="form-input text-xs"
              style={{
                paddingLeft: isRTL ? '10px' : '32px',
                paddingRight: isRTL ? '32px' : '10px',
                width: '100%',
              }}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>

          {user?.role === 'MANAGER' && (
            <select
              className="form-select text-xs"
              style={{ width: '180px' }}
              value={assignedUserFilter}
              onChange={(e) => setAssignedUserFilter(e.target.value)}
            >
              <option value="">{isRTL ? "جميع الموظفين" : "All Sales Reps"}</option>
              {usersList.map((u) => (
                <option key={u.id} value={u.id}>
                  👤 {u.full_name} ({u.role})
                </option>
              ))}
            </select>
          )}
        </div>

        {/* Sub-Filters: Needs Report & Historical */}
        <div style={{ display: 'flex', gap: 'var(--space-2)', alignItems: 'center' }}>
          <button
            onClick={handleToggleNeedsReport}
            className={`btn btn-sm ${reportStatusFilter === 'NEEDS_REPORT' ? 'btn-danger' : 'btn-secondary'}`}
            style={{
              fontSize: '11px',
              fontWeight: 700,
              padding: '4px 10px',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            <AlertTriangle size={13} />
            <span>{isRTL ? "يحتاج تقرير" : "Needs Report"}</span>
            <span
              style={{
                padding: '1px 6px',
                borderRadius: '10px',
                backgroundColor: 'rgba(0,0,0,0.15)',
                fontSize: '10px',
              }}
            >
              {counts.NEEDS_REPORT}
            </span>
          </button>

          <button
            onClick={handleToggleHistorical}
            className={`btn btn-sm ${isHistoricalFilter ? 'btn-primary' : 'btn-secondary'}`}
            style={{
              fontSize: '11px',
              fontWeight: 700,
              padding: '4px 10px',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            <History size={13} />
            <span>{isRTL ? "عروض تاريخية" : "Historical"}</span>
            <span
              style={{
                padding: '1px 6px',
                borderRadius: '10px',
                backgroundColor: 'rgba(0,0,0,0.15)',
                fontSize: '10px',
              }}
            >
              {counts.HISTORICAL}
            </span>
          </button>
        </div>
      </div>

      {/* ── 6 Required Status Navigation Tabs ───────────────────────────── */}
      <div
        style={{
          display: 'flex',
          gap: 'var(--space-2)',
          borderBottom: '1px solid var(--border-color)',
          paddingBottom: 'var(--space-2)',
          overflowX: 'auto',
        }}
      >
        {[
          { id: 'ALL', label: isRTL ? 'جميع العروض' : 'All', count: counts.ALL },
          { id: 'INTERESTED_NEXT_STEP', label: isRTL ? 'مهتم / خطوة تالية' : 'Interested / Next Step', count: counts.INTERESTED_NEXT_STEP },
          { id: 'PENDING', label: isRTL ? 'قيد الانتظار' : 'Pending', count: counts.PENDING },
          { id: 'POSTPONED', label: isRTL ? 'مؤجل' : 'Postponed', count: counts.POSTPONED },
          { id: 'NOT_INTERESTED', label: isRTL ? 'غير مهتم' : 'Not Interested', count: counts.NOT_INTERESTED },
          { id: 'CANCELLED', label: isRTL ? 'ملغي / لم يحضر' : 'Cancelled', count: counts.CANCELLED },
        ].map((tab) => {
          const isSelected = statusFilter === tab.id && !reportStatusFilter && !isHistoricalFilter;
          return (
            <button
              key={tab.id}
              onClick={() => handleTabSelect(tab.id)}
              className={`btn btn-sm ${isSelected ? 'btn-accent' : 'btn-secondary'}`}
              style={{
                fontSize: '12px',
                fontWeight: 700,
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                whiteSpace: 'nowrap',
              }}
            >
              <span>{tab.label}</span>
              <span
                style={{
                  padding: '1px 6px',
                  borderRadius: '10px',
                  backgroundColor: isSelected ? 'rgba(255,255,255,0.25)' : 'var(--neutral-200)',
                  color: isSelected ? '#FFFFFF' : 'var(--neutral-800)',
                  fontSize: '11px',
                }}
              >
                {tab.count}
              </span>
            </button>
          );
        })}
      </div>

      {/* ── Demos Data Table ───────────────────────────────────────────── */}
      {isLoading ? (
        <LoadingSpinner message={isRTL ? "جاري تحميل سجل العروض..." : "Loading demo reports & schedule..."} />
      ) : demos.length === 0 ? (
        <EmptyState
          title={isRTL ? "لا توجد سجلات عروض مطابقة" : "No demo records found"}
          description={isRTL ? "استخدم زر إضافة عرض أو تغيير التصفية لعرض السجلات." : "Create a new demonstration or adjust filters to review past demos."}
        />
      ) : (
        <div className="table-container custom-scrollbar" style={{ overflowX: 'auto' }}>
          <table className="data-table">
            <thead>
              <tr>
                <th style={{ minWidth: '130px' }}>{isRTL ? "الحالة والتقرير" : "Status & Report"}</th>
                <th style={{ minWidth: '180px' }}>{isRTL ? "الجهة والشركة" : "Contact & Account"}</th>
                <th style={{ minWidth: '140px' }}>{isRTL ? "المسؤول والمقدم" : "Owner & Presenter"}</th>
                <th style={{ minWidth: '140px' }}>{isRTL ? "تاريخ العرض" : "Demo Date"}</th>
                <th style={{ minWidth: '220px' }}>{isRTL ? "الملخص والشرح" : "Summary & Topics"}</th>
                <th style={{ minWidth: '180px' }}>{isRTL ? "الخطوة التالية" : "Next Step"}</th>
                <th style={{ minWidth: '110px', textAlign: 'center' }}>{isRTL ? "الإجراء" : "Actions"}</th>
              </tr>
            </thead>
            <tbody>
              {demos.map((d) => {
                const isNeedsReport = d.report_status === 'NEEDS_REPORT';
                return (
                  <tr key={d.id} style={{ backgroundColor: isNeedsReport ? 'rgba(245, 158, 11, 0.04)' : undefined }}>
                    {/* Status & Badges */}
                    <td>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', alignItems: 'flex-start' }}>
                        <span
                          style={{
                            fontSize: '11px',
                            fontWeight: 700,
                            padding: '2px 8px',
                            borderRadius: 'var(--radius-sm)',
                            backgroundColor:
                              d.status === 'INTERESTED_NEXT_STEP'
                                ? 'var(--status-interested-bg)'
                                : d.status === 'CANCELLED' || d.status === 'NOT_INTERESTED'
                                ? 'rgba(239, 68, 68, 0.12)'
                                : 'var(--bg-subtle)',
                            color:
                              d.status === 'INTERESTED_NEXT_STEP'
                                ? 'var(--status-interested-text)'
                                : d.status === 'CANCELLED' || d.status === 'NOT_INTERESTED'
                                ? 'var(--color-danger)'
                                : 'var(--neutral-800)',
                          }}
                        >
                          {d.status?.replace(/_/g, ' ') || d.stage}
                        </span>

                        {/* Mandatory Report Badge */}
                        {isNeedsReport ? (
                          <span
                            style={{
                              fontSize: '10px',
                              fontWeight: 800,
                              padding: '1px 6px',
                              borderRadius: '4px',
                              backgroundColor: '#FEF3C7',
                              color: '#B45309',
                              border: '1px solid #F59E0B',
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '3px',
                            }}
                          >
                            <AlertTriangle size={10} />
                            Needs Report
                          </span>
                        ) : (
                          <span
                            style={{
                              fontSize: '10px',
                              fontWeight: 800,
                              padding: '1px 6px',
                              borderRadius: '4px',
                              backgroundColor: '#ECFDF5',
                              color: '#065F46',
                              border: '1px solid #10B981',
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '3px',
                            }}
                          >
                            <CheckCircle2 size={10} />
                            Report Complete
                          </span>
                        )}

                        {d.is_historical && (
                          <span
                            style={{
                              fontSize: '9px',
                              fontWeight: 800,
                              padding: '1px 5px',
                              borderRadius: '4px',
                              backgroundColor: 'rgba(212, 175, 55, 0.15)',
                              color: '#B8860B',
                              border: '1px solid rgba(212, 175, 55, 0.4)',
                            }}
                          >
                            HISTORICAL
                          </span>
                        )}
                      </div>
                    </td>

                    {/* Contact & Company */}
                    <td>
                      <button
                        onClick={() => navigate(`/contacts/${d.contact_id}`)}
                        className="font-semibold text-xs text-left"
                        style={{
                          color: 'var(--neutral-900)',
                          background: 'none',
                          border: 'none',
                          padding: 0,
                          cursor: 'pointer',
                          textDecoration: 'underline',
                        }}
                      >
                        {d.contact_name || 'Contact'}
                      </button>
                      <div className="text-xs text-muted" style={{ marginTop: '2px' }}>
                        {d.company_name || '—'}
                      </div>
                      {d.contact_phone && (
                        <div className="text-xs font-mono text-muted">{d.contact_phone}</div>
                      )}
                    </td>

                    {/* Owner & Presenter */}
                    <td>
                      <span className="badge badge-secondary text-xs font-semibold">
                        {d.owner_name || 'Sales Rep'}
                      </span>
                      {d.presenter && d.presenter !== d.owner_name && (
                        <div className="text-xs text-muted" style={{ marginTop: '2px' }}>
                          By: {d.presenter}
                        </div>
                      )}
                    </td>

                    {/* Demo Date */}
                    <td>
                      {d.is_historical ? (
                        <div>
                          <div className="text-xs font-semibold text-primary">
                            {d.historical_date ? new Date(d.historical_date).toLocaleDateString() : 'Historical'}
                          </div>
                          <div className="text-xs text-muted" style={{ fontSize: '10px' }}>
                            Logged: {new Date(d.created_at).toLocaleDateString()}
                          </div>
                        </div>
                      ) : (
                        <div>
                          <div className="text-xs font-semibold text-primary">
                            {d.scheduled_at ? new Date(d.scheduled_at).toLocaleString([], { dateStyle: 'short', timeStyle: 'short' }) : 'TBD'}
                          </div>
                          {d.completed_at && (
                            <div className="text-xs text-muted" style={{ fontSize: '10px' }}>
                              Done: {new Date(d.completed_at).toLocaleDateString()}
                            </div>
                          )}
                        </div>
                      )}
                    </td>

                    {/* Summary & Topics */}
                    <td>
                      {d.summary ? (
                        <div className="text-xs" style={{ color: 'var(--neutral-900)', maxWidth: '280px' }}>
                          {d.summary}
                        </div>
                      ) : (
                        <span className="text-xs text-muted italic">No summary reported yet.</span>
                      )}
                      {d.reason && (
                        <div className="text-xs text-muted" style={{ marginTop: '3px', color: 'var(--color-danger)' }}>
                          Reason: {d.reason}
                        </div>
                      )}
                    </td>

                    {/* Next Step */}
                    <td>
                      {d.next_step ? (
                        <div>
                          <div className="text-xs font-semibold" style={{ color: 'var(--neutral-900)' }}>
                            {d.next_step}
                          </div>
                          {d.next_step_due_date && (
                            <div className="text-xs text-muted" style={{ fontSize: '10px', marginTop: '2px' }}>
                              Due: {new Date(d.next_step_due_date).toLocaleDateString()}
                            </div>
                          )}
                        </div>
                      ) : (
                        <span className="text-xs text-muted">—</span>
                      )}
                    </td>

                    {/* Action */}
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px' }}>
                        {isNeedsReport ? (
                          <button
                            onClick={() => handleOpenReportModal(d)}
                            className="btn btn-accent btn-sm"
                            style={{ fontSize: '11px', padding: '4px 8px', display: 'flex', alignItems: 'center', gap: '4px' }}
                          >
                            <FileText size={12} />
                            <span>Complete Report</span>
                          </button>
                        ) : (
                          <button
                            onClick={() => handleOpenReportModal(d)}
                            className="btn btn-secondary btn-sm"
                            style={{ fontSize: '11px', padding: '4px 8px', display: 'flex', alignItems: 'center', gap: '4px' }}
                          >
                            <Edit3 size={12} />
                            <span>Edit</span>
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* ── Complete Report / Edit Demo Modal ─────────────────────────── */}
      <Modal
        isOpen={!!editingDemo}
        onClose={() => setEditingDemo(null)}
        title={editingDemo?.report_status === 'NEEDS_REPORT' ? 'Complete Demo Report' : 'Edit Demo Report & Details'}
        footer={
          <>
            <button
              type="button"
              onClick={() => setEditingDemo(null)}
              className="btn btn-secondary"
            >
              Cancel
            </button>
            <button
              type="button"
              disabled={isUpdatingReport}
              onClick={handleSubmitReport}
              className="btn btn-accent"
            >
              {isUpdatingReport ? 'Saving Report...' : 'Save & Complete Report'}
            </button>
          </>
        }
      >
        <form onSubmit={handleSubmitReport} style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
          {reportError && (
            <div
              style={{
                padding: 'var(--space-3)',
                backgroundColor: '#fee2e2',
                border: '1px solid #ef4444',
                borderRadius: 'var(--radius-md)',
                color: '#991b1b',
                fontSize: '13px',
              }}
            >
              {reportError}
            </div>
          )}

          <div style={{ padding: 'var(--space-3)', backgroundColor: 'var(--bg-subtle)', borderRadius: 'var(--radius-md)' }}>
            <div className="text-xs text-muted">TARGET CONTACT & ACCOUNT</div>
            <div className="font-bold text-sm" style={{ color: 'var(--neutral-900)', marginTop: '2px' }}>
              {editingDemo?.contact_name} ({editingDemo?.company_name || 'No Company'})
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-3)' }}>
            <div className="form-group">
              <label className="form-label font-semibold text-xs">Demo Status *</label>
              <select
                className="form-select"
                value={reportForm.status}
                onChange={(e) => setReportForm({ ...reportForm, status: e.target.value })}
              >
                <option value="INTERESTED_NEXT_STEP">INTERESTED / NEXT STEP</option>
                <option value="PENDING">PENDING (Awaiting Decision)</option>
                <option value="POSTPONED">POSTPONED (Rescheduled)</option>
                <option value="NOT_INTERESTED">NOT INTERESTED (Declined)</option>
                <option value="CANCELLED">CANCELLED (Client Cancelled)</option>
              </select>
            </div>
            <div className="form-group">
              <label className="form-label font-semibold text-xs">Presenter</label>
              <input
                type="text"
                className="form-input"
                value={reportForm.presenter}
                onChange={(e) => setReportForm({ ...reportForm, presenter: e.target.value })}
              />
            </div>
          </div>

          <div className="form-group">
            <label className="form-label font-semibold text-xs">
              Demonstration Summary * <span style={{ color: 'var(--color-danger)' }}>(Mandatory)</span>
            </label>
            <textarea
              required
              rows={3}
              className="form-textarea"
              placeholder="What modules were demonstrated? What questions did the client ask? What was their engagement level?..."
              value={reportForm.summary}
              onChange={(e) => setReportForm({ ...reportForm, summary: e.target.value })}
            />
          </div>

          {(reportForm.status === 'POSTPONED' || reportForm.status === 'NOT_INTERESTED' || reportForm.status === 'CANCELLED') && (
            <div className="form-group">
              <label className="form-label font-semibold text-xs">
                Reason * <span style={{ color: 'var(--color-danger)' }}>({reportForm.status.replace(/_/g, ' ')} Reason Required)</span>
              </label>
              <input
                type="text"
                required
                className="form-input"
                placeholder="Reason for postponement, decline, or cancellation..."
                value={reportForm.reason}
                onChange={(e) => setReportForm({ ...reportForm, reason: e.target.value })}
              />
            </div>
          )}

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-3)' }}>
            <div className="form-group">
              <label className="form-label font-semibold text-xs">Agreed Next Step</label>
              <input
                type="text"
                className="form-input"
                placeholder="e.g. Send enterprise proposal by Wednesday"
                value={reportForm.next_step}
                onChange={(e) => setReportForm({ ...reportForm, next_step: e.target.value })}
              />
            </div>
            <div className="form-group">
              <label className="form-label font-semibold text-xs">Next Step Due Date</label>
              <input
                type="date"
                className="form-input"
                value={reportForm.next_step_due_date}
                onChange={(e) => setReportForm({ ...reportForm, next_step_due_date: e.target.value })}
              />
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-3)' }}>
            <div className="form-group">
              <label className="form-label font-semibold text-xs">Client Attendees / Participants</label>
              <input
                type="text"
                className="form-input"
                placeholder="e.g. CTO, Finance Director, 3 engineers"
                value={reportForm.attendees}
                onChange={(e) => setReportForm({ ...reportForm, attendees: e.target.value })}
              />
            </div>
            <div className="form-group">
              <label className="form-label font-semibold text-xs">Topics Covered</label>
              <input
                type="text"
                className="form-input"
                placeholder="e.g. Security, Multi-tenant, Arabic UX"
                value={reportForm.topics_covered}
                onChange={(e) => setReportForm({ ...reportForm, topics_covered: e.target.value })}
              />
            </div>
          </div>

          <div className="form-group">
            <label className="form-label font-semibold text-xs">Internal Notes</label>
            <textarea
              rows={2}
              className="form-textarea"
              placeholder="Commercial considerations, stakeholder politics, pricing objections..."
              value={reportForm.notes}
              onChange={(e) => setReportForm({ ...reportForm, notes: e.target.value })}
            />
          </div>
        </form>
      </Modal>

      {/* ── Add New / Historical Demo Modal ────────────────────────────── */}
      <Modal
        isOpen={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        title={isHistoricalCreate ? 'Add Historical Demo (Pre-CRM Record)' : 'Schedule New Product Demo'}
        footer={
          <>
            <button
              type="button"
              onClick={() => setShowCreateModal(false)}
              className="btn btn-secondary"
            >
              Cancel
            </button>
            <button
              type="button"
              disabled={isCreating}
              onClick={handleSaveNewDemo}
              className="btn btn-accent"
            >
              {isCreating ? 'Saving...' : isHistoricalCreate ? 'Record Historical Demo' : 'Create Demo'}
            </button>
          </>
        }
      >
        <form onSubmit={handleSaveNewDemo} style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
          {createError && (
            <div
              style={{
                padding: 'var(--space-3)',
                backgroundColor: '#fee2e2',
                border: '1px solid #ef4444',
                borderRadius: 'var(--radius-md)',
                color: '#991b1b',
                fontSize: '13px',
              }}
            >
              {createError}
            </div>
          )}

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-3)' }}>
            <div className="form-group">
              <label className="form-label font-semibold text-xs">Target Contact *</label>
              <select
                required
                className="form-select"
                value={createForm.contact_id}
                onChange={(e) => setCreateForm({ ...createForm, contact_id: e.target.value })}
              >
                <option value="">Select Contact</option>
                {contactsList.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.full_name} ({c.company_name || 'No Company'})
                  </option>
                ))}
              </select>
            </div>

            <div className="form-group">
              <label className="form-label font-semibold text-xs">Demo Owner *</label>
              <select
                className="form-select"
                value={createForm.owner_id}
                onChange={(e) => setCreateForm({ ...createForm, owner_id: e.target.value })}
              >
                {usersList.map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.full_name} ({u.role})
                  </option>
                ))}
              </select>
            </div>
          </div>

          {isHistoricalCreate ? (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-3)' }}>
              <div className="form-group">
                <label className="form-label font-semibold text-xs">
                  Original Demo Date * <span style={{ color: 'var(--color-danger)' }}>(When it happened)</span>
                </label>
                <input
                  type="date"
                  required
                  className="form-input"
                  value={createForm.historical_date}
                  onChange={(e) => setCreateForm({ ...createForm, historical_date: e.target.value })}
                />
              </div>
              <div className="form-group">
                <label className="form-label font-semibold text-xs">Historical Source / Archive Notes</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="e.g. Q4 2025 Excel Log, WhatsApp agreement"
                  value={createForm.historical_source}
                  onChange={(e) => setCreateForm({ ...createForm, historical_source: e.target.value })}
                />
              </div>
            </div>
          ) : (
            <div className="form-group">
              <label className="form-label font-semibold text-xs">Scheduled Date & Time</label>
              <input
                type="datetime-local"
                className="form-input"
                value={createForm.scheduled_at}
                onChange={(e) => setCreateForm({ ...createForm, scheduled_at: e.target.value })}
              />
            </div>
          )}

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-3)' }}>
            <div className="form-group">
              <label className="form-label font-semibold text-xs">Initial Status</label>
              <select
                className="form-select"
                value={createForm.status}
                onChange={(e) => setCreateForm({ ...createForm, status: e.target.value })}
              >
                <option value="PENDING">PENDING</option>
                <option value="INTERESTED_NEXT_STEP">INTERESTED / NEXT STEP</option>
                <option value="POSTPONED">POSTPONED</option>
                <option value="NOT_INTERESTED">NOT INTERESTED</option>
                <option value="CANCELLED">CANCELLED</option>
              </select>
            </div>
            <div className="form-group">
              <label className="form-label font-semibold text-xs">Presenter</label>
              <input
                type="text"
                className="form-input"
                value={createForm.presenter}
                onChange={(e) => setCreateForm({ ...createForm, presenter: e.target.value })}
              />
            </div>
          </div>

          <div className="form-group">
            <label className="form-label font-semibold text-xs">
              Summary / What was Explained {isHistoricalCreate && <span style={{ color: 'var(--color-danger)' }}>*</span>}
            </label>
            <textarea
              rows={3}
              required={isHistoricalCreate}
              className="form-textarea"
              placeholder="Summary of presentation, client reactions, and questions..."
              value={createForm.summary}
              onChange={(e) => setCreateForm({ ...createForm, summary: e.target.value })}
            />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-3)' }}>
            <div className="form-group">
              <label className="form-label font-semibold text-xs">Next Step</label>
              <input
                type="text"
                className="form-input"
                placeholder="e.g. Schedule commercial follow-up"
                value={createForm.next_step}
                onChange={(e) => setCreateForm({ ...createForm, next_step: e.target.value })}
              />
            </div>
            <div className="form-group">
              <label className="form-label font-semibold text-xs">Next Step Due Date</label>
              <input
                type="date"
                className="form-input"
                value={createForm.next_step_due_date}
                onChange={(e) => setCreateForm({ ...createForm, next_step_due_date: e.target.value })}
              />
            </div>
          </div>
        </form>
      </Modal>

      {/* ── CSV / JSON Import Modal with Preview ───────────────────────── */}
      <Modal
        isOpen={showImportModal}
        onClose={() => setShowImportModal(false)}
        title="Import Demos (Historical or Bulk)"
        footer={
          <>
            <button
              type="button"
              onClick={() => setShowImportModal(false)}
              className="btn btn-secondary"
            >
              Close
            </button>
            <button
              type="button"
              disabled={isImporting || !importText.trim()}
              onClick={() => handleImportSubmit(true)}
              className="btn btn-secondary"
            >
              Preview Validation
            </button>
            <button
              type="button"
              disabled={isImporting || !importText.trim()}
              onClick={() => handleImportSubmit(false)}
              className="btn btn-accent"
            >
              {isImporting ? 'Importing...' : 'Commit Import'}
            </button>
          </>
        }
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span className="text-xs text-muted">
              Paste JSON or CSV data containing demo records. Download template below for reference.
            </span>
            <button
              type="button"
              onClick={downloadTemplate}
              className="btn btn-ghost btn-xs"
              style={{ display: 'flex', alignItems: 'center', gap: '4px', color: 'var(--color-primary)' }}
            >
              <Download size={12} />
              <span>Download Template</span>
            </button>
          </div>

          <textarea
            rows={8}
            className="form-textarea font-mono text-xs"
            placeholder={sampleCsvTemplate}
            value={importText}
            onChange={(e) => setImportText(e.target.value)}
          />

          {importResult && (
            <div
              style={{
                padding: 'var(--space-3)',
                backgroundColor: 'var(--bg-subtle)',
                borderRadius: 'var(--radius-md)',
                fontSize: '12px',
                border: '1px solid var(--border-light)',
              }}
            >
              <div className="font-bold mb-1" style={{ color: importResult.dry_run ? 'var(--color-accent)' : 'var(--color-success)' }}>
                {importResult.dry_run ? 'Dry-Run Preview Result:' : 'Import Completed:'}
              </div>
              <div>Valid rows: <strong>{importResult.valid_count || 0}</strong></div>
              <div>Imported: <strong>{importResult.imported_count || 0}</strong></div>
              {importResult.errors?.length > 0 && (
                <div style={{ marginTop: 'var(--space-2)', color: 'var(--color-danger)' }}>
                  <div className="font-semibold">Errors detected ({importResult.errors.length}):</div>
                  <ul style={{ paddingLeft: '16px', margin: '4px 0' }}>
                    {importResult.errors.map((err: string, i: number) => (
                      <li key={i}>{err}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
      </Modal>
    </div>
  );
};
