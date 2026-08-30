import React, { useState, useEffect } from 'react';
import { api } from '../../lib/apiClient';
import { Contact, User } from '../../types';
import { Badge } from '../../components/ui/Badge';
import { Modal } from '../../components/ui/Modal';
import { LoadingSpinner } from '../../components/feedback/LoadingSpinner';
import { EmptyState } from '../../components/feedback/EmptyState';
import {
  Users,
  Layers,
  CheckSquare,
  ArrowRight,
  Shuffle,
  Percent,
  Globe,
  Briefcase,
  FileSpreadsheet,
  RefreshCw,
  Plus,
  CheckCircle2,
  AlertTriangle,
  ExternalLink,
  ShieldCheck,
  History,
  Inbox,
  UploadCloud,
} from 'lucide-react';
import { useTranslation } from '../../i18n';
import { DragDropDataImport } from '../../components/leads/DragDropDataImport';

interface GoogleSheetConfig {
  id: string;
  name: string;
  spreadsheet_id: string;
  sheet_name: string;
  range: string;
  column_mapping: Record<string, string>;
  sync_every_minutes: number;
  is_active: boolean;
  last_synced_at?: string;
  created_at: string;
}

interface SyncRun {
  id: string;
  config_id: string;
  config_name?: string;
  status: string;
  triggered_by: string;
  rows_read: number;
  rows_imported: number;
  rows_duplicate: number;
  rows_error: number;
  started_at?: string;
  completed_at?: string;
  error_message?: string;
}

export const LeadPoolPage: React.FC = () => {
  const { t, isRTL } = useTranslation();

  // Active Main Tab
  const [activeTab, setActiveTab] = useState<'pool' | 'upload' | 'sheets' | 'my_pool'>('pool');

  // Personal Pool (PENDING_CLAIM leads assigned to current user)
  const [personalPool, setPersonalPool] = useState<Contact[]>([]);
  const [personalPoolTotal, setPersonalPoolTotal] = useState(0);
  const [isLoadingPersonalPool, setIsLoadingPersonalPool] = useState(false);
  const [selectedPoolIds, setSelectedPoolIds] = useState<string[]>([]);
  const [isClaimingSelected, setIsClaimingSelected] = useState(false);

  const handleToggleSelectPool = (id: string) => {
    setSelectedPoolIds((prev) =>
      prev.includes(id) ? prev.filter((i) => i !== id) : [...prev, id]
    );
  };

  const handleSelectAllPool = (checked: boolean) => {
    if (checked) {
      setSelectedPoolIds(personalPool.map((c) => c.id));
    } else {
      setSelectedPoolIds([]);
    }
  };

  const handleClaimSelected = async () => {
    if (selectedPoolIds.length === 0) return;
    setIsClaimingSelected(true);
    try {
      await api.post('/contacts/claim-bulk', { contact_ids: selectedPoolIds });
      setPersonalPool((prev) => prev.filter((c) => !selectedPoolIds.includes(c.id)));
      setPersonalPoolTotal((prev) => Math.max(0, prev - selectedPoolIds.length));
      setSelectedPoolIds([]);
      alert(isRTL ? 'تمت إضافة جهات الاتصال المختارة بنجاح إلى دليلك النشط!' : 'Selected leads successfully added to your active contacts!');
    } catch (err: any) {
      alert(err.message || 'Failed to claim selected leads');
    } finally {
      setIsClaimingSelected(false);
    }
  };

  // Leads & Distribution State
  const [leads, setLeads] = useState<Contact[]>([]);
  const [total, setTotal] = useState(0);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [salesUsers, setSalesUsers] = useState<User[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  // Distribution Modal
  const [showDistributeModal, setShowDistributeModal] = useState(false);
  const [strategy, setStrategy] = useState<'MANUAL' | 'ROUND_ROBIN' | 'PERCENTAGE' | 'COUNTRY' | 'INDUSTRY'>('ROUND_ROBIN');
  const [targetUserId, setTargetUserId] = useState('');
  const [isDistributing, setIsDistributing] = useState(false);

  // Percentage Split State
  const [percentageMap, setPercentageMap] = useState<Record<string, number>>({});

  // Google Sheets State
  const [configs, setConfigs] = useState<GoogleSheetConfig[]>([]);
  const [syncRuns, setSyncRuns] = useState<SyncRun[]>([]);
  const [showAddSheetModal, setShowAddSheetModal] = useState(false);
  const [isSyncing, setIsSyncing] = useState<string | null>(null);
  const [syncResult, setSyncResult] = useState<any | null>(null);

  // New Google Sheet Form State
  const [newSheet, setNewSheet] = useState({
    name: 'Enterprise Leads Master Sheet',
    spreadsheet_id: '1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms',
    sheet_name: 'Sheet1',
    range: 'A:Z',
    sync_every_minutes: 60,
  });

  const fetchLeadsAndUsers = async () => {
    setIsLoading(true);
    try {
      const [lRes, uRes] = await Promise.all([
        api.get<any>('/admin/leads/unassigned', { per_page: 100 }),
        api.get<any>('/users'),
      ]);
      setLeads(lRes.data || []);
      setTotal(lRes.meta?.total || 0);
      
      const salesOnly = (uRes.data || []).filter((u: any) => u.role === 'SALES_USER' || u.role === 'TEAM_LEADER');
      setSalesUsers(salesOnly.length > 0 ? salesOnly : (uRes.data || []));
      if (salesOnly.length > 0) {
        setTargetUserId(salesOnly[0].id);
        // Default even percentage
        const evenPct = Math.floor(100 / salesOnly.length);
        const map: Record<string, number> = {};
        salesOnly.forEach((u: any, idx: number) => {
          map[u.id] = idx === 0 ? 100 - evenPct * (salesOnly.length - 1) : evenPct;
        });
        setPercentageMap(map);
      }
    } catch (e) {
      console.error('Failed to load lead pool', e);
    } finally {
      setIsLoading(false);
    }
  };

  const fetchGoogleSheetsData = async () => {
    try {
      const [cRes, rRes] = await Promise.all([
        api.get<any>('/integrations/google-sheets/configs'),
        api.get<any>('/integrations/google-sheets/runs'),
      ]);
      setConfigs(cRes.data || []);
      setSyncRuns(rRes.data || []);
    } catch (e) {
      console.error('Failed to load Google Sheets configs', e);
    }
  };

  const fetchPersonalPool = async () => {
    setIsLoadingPersonalPool(true);
    try {
      const res = await api.get<any>('/contacts', { pending_claim_only: true, per_page: 200 });
      setPersonalPool(res.data || []);
      setPersonalPoolTotal(res.meta?.total || 0);
    } catch (e) {
      console.error('Failed to load personal pool', e);
    } finally {
      setIsLoadingPersonalPool(false);
    }
  };

  const handleClaimContact = async (contactId: string) => {
    try {
      await api.post(`/contacts/${contactId}/claim`);
      setPersonalPool((prev) => prev.filter((c) => c.id !== contactId));
      setPersonalPoolTotal((prev) => prev - 1);
    } catch (err: any) {
      alert(err.message || 'Failed to claim contact');
    }
  };

  useEffect(() => {
    fetchLeadsAndUsers();
    fetchGoogleSheetsData();
    fetchPersonalPool();
  }, []);

  const handleSelectAll = (checked: boolean) => {
    if (checked) {
      setSelectedIds(leads.map((l) => l.id));
    } else {
      setSelectedIds([]);
    }
  };

  const toggleSelectOne = (id: string) => {
    if (selectedIds.includes(id)) {
      setSelectedIds(selectedIds.filter((item) => item !== id));
    } else {
      setSelectedIds([...selectedIds, id]);
    }
  };

  const handleDistribute = async () => {
    setIsDistributing(true);
    try {
      await api.post('/admin/leads/distribute', {
        contact_ids: selectedIds.length > 0 ? selectedIds : undefined,
        strategy,
        target_user_id: strategy === 'MANUAL' ? targetUserId : undefined,
        user_percentage_map: strategy === 'PERCENTAGE' ? percentageMap : undefined,
        country_mapping:
          strategy === 'COUNTRY' && salesUsers.length >= 2
            ? { 'Saudi Arabia': salesUsers[0].id, UAE: salesUsers[1].id }
            : undefined,
      });
      setShowDistributeModal(false);
      setSelectedIds([]);
      await fetchLeadsAndUsers();
      alert(isRTL ? 'تم توزيع جهات الاتصال بنجاح على فريق المبيعات!' : 'Leads successfully distributed to sales team!');
    } catch (err: any) {
      alert(err.message || 'Failed to distribute leads');
    } finally {
      setIsDistributing(false);
    }
  };

  const handleCreateSheetConfig = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.post('/integrations/google-sheets/configs', newSheet);
      setShowAddSheetModal(false);
      await fetchGoogleSheetsData();
      alert(isRTL ? 'تم حفظ إعداد ورقة جوجل بنجاح!' : 'Google Sheet connected successfully!');
    } catch (err: any) {
      alert(err.message || 'Failed to create sheet config');
    }
  };

  const handleTriggerSync = async (configId: string) => {
    setIsSyncing(configId);
    setSyncResult(null);
    try {
      const res = await api.post<any>(`/integrations/google-sheets/sync/${configId}`, {});
      setSyncResult(res.data);
      await fetchGoogleSheetsData();
      await fetchLeadsAndUsers();
    } catch (err: any) {
      alert(err.message || 'Sync failed');
    } finally {
      setIsSyncing(null);
    }
  };

  if (isLoading && leads.length === 0 && configs.length === 0) {
    return <LoadingSpinner message={isRTL ? "جاري مسح مستودع العملاء وتكامل جوجل..." : "Scanning unassigned lead pool & Google Sheets..."} />;
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-6)' }}>
      {/* ── Header & Primary Actions ──────────────────────────────────── */}
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
              {isRTL ? "مستودع العملاء الجدد وتكامل أوراق جوجل" : "New Leads Pool & Ingestion Hub"}
            </h1>
            <span className="badge badge-accent text-xs">
              {total} {isRTL ? "عميل غير مخصص" : "Unassigned Leads"}
            </span>
          </div>
          <p className="text-sm text-muted" style={{ marginTop: '2px' }}>
            {isRTL
              ? "استيراد وتدقيق العملاء الجدد من أوراق جوجل وتوزيعهم بشكل آلي أو يدوي على مندوبي المبيعات."
              : "Ingest, validate, and distribute new prospective leads from Google Sheets to sales representatives."}
          </p>
        </div>

        <div style={{ display: 'flex', gap: 'var(--space-3)', flexWrap: 'wrap' }}>
          {activeTab === 'sheets' && (
            <button onClick={() => setShowAddSheetModal(true)} className="btn btn-secondary btn-md">
              <Plus size={16} />
              <span>{isRTL ? "ربط ورقة جوجل جديدة" : "Connect Google Sheet"}</span>
            </button>
          )}

          <button
            disabled={leads.length === 0}
            onClick={() => setShowDistributeModal(true)}
            className="btn btn-accent btn-md"
          >
            <Layers size={18} />
            <span>
              {isRTL
                ? `توزيع العملاء (${selectedIds.length > 0 ? selectedIds.length : 'الكل'})`
                : `Distribute Leads (${selectedIds.length > 0 ? selectedIds.length : 'All'})`}
            </span>
          </button>
        </div>
      </div>

      {/* ── Main Navigation Tabs ────────────────────────────────────────── */}
      <div style={{ display: 'flex', borderBottom: '1px solid var(--border-color)', gap: 'var(--space-6)' }}>
        <button
          onClick={() => setActiveTab('pool')}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: 'var(--space-3) var(--space-2)',
            borderBottom: activeTab === 'pool' ? '3px solid var(--color-accent)' : '3px solid transparent',
            color: activeTab === 'pool' ? 'var(--color-accent)' : 'var(--neutral-600)',
            fontWeight: activeTab === 'pool' ? 700 : 500,
            fontSize: '14px',
            background: 'none',
            borderTop: 'none',
            borderLeft: 'none',
            borderRight: 'none',
            cursor: 'pointer',
          }}
        >
          <Users size={17} />
          {isRTL ? `مستودع العملاء غير المخصصين (${total})` : `Unassigned Lead Pool (${total})`}
        </button>

        {/* Drag & Drop Data Ingestion Tab */}
        <button
          onClick={() => setActiveTab('upload')}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: 'var(--space-3) var(--space-2)',
            borderBottom: activeTab === 'upload' ? '3px solid var(--color-accent)' : '3px solid transparent',
            color: activeTab === 'upload' ? 'var(--color-accent)' : 'var(--neutral-600)',
            fontWeight: activeTab === 'upload' ? 700 : 500,
            fontSize: '14px',
            background: 'none',
            borderTop: 'none',
            borderLeft: 'none',
            borderRight: 'none',
            cursor: 'pointer',
          }}
        >
          <UploadCloud size={17} />
          {isRTL ? 'رفع ملف بيانات (CSV / Excel)' : 'Drag & Drop Data Import'}
        </button>

        <button
          onClick={() => setActiveTab('sheets')}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: 'var(--space-3) var(--space-2)',
            borderBottom: activeTab === 'sheets' ? '3px solid var(--color-accent)' : '3px solid transparent',
            color: activeTab === 'sheets' ? 'var(--color-accent)' : 'var(--neutral-600)',
            fontWeight: activeTab === 'sheets' ? 700 : 500,
            fontSize: '14px',
            background: 'none',
            borderTop: 'none',
            borderLeft: 'none',
            borderRight: 'none',
            cursor: 'pointer',
          }}
        >
          <FileSpreadsheet size={17} />
          {isRTL ? `تكامل واستيراد أوراق جوجل (${configs.length})` : `Google Sheets Ingestion & Sync (${configs.length})`}
        </button>

        {/* Personal Pool Tab */}
        <button
          onClick={() => setActiveTab('my_pool')}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: 'var(--space-3) var(--space-2)',
            borderBottom: activeTab === 'my_pool' ? '3px solid var(--color-accent)' : '3px solid transparent',
            color: activeTab === 'my_pool' ? 'var(--color-accent)' : 'var(--neutral-600)',
            fontWeight: activeTab === 'my_pool' ? 700 : 500,
            fontSize: '14px',
            background: 'none',
            borderTop: 'none',
            borderLeft: 'none',
            borderRight: 'none',
            cursor: 'pointer',
          }}
        >
          <Inbox size={17} />
          {isRTL
            ? `قائمة انتظاري الشخصية (${personalPoolTotal})`
            : `My Personal Pool (${personalPoolTotal})`}
        </button>
      </div>

      {/* ── TAB: DRAG & DROP FILE IMPORT ──────────────────────────────── */}
      {activeTab === 'upload' && (
        <DragDropDataImport
          onImportSuccess={async (result) => {
            await fetchLeadsAndUsers();
          }}
          onSwitchToGoogleSheets={() => setActiveTab('sheets')}
        />
      )}

      {/* ── TAB 1: UNASSIGNED LEAD POOL ───────────────────────────────── */}
      {activeTab === 'pool' && (
        <>
          {leads.length === 0 ? (
            <EmptyState
              title={isRTL ? "مستودع العملاء فارغ حالياً" : "Unassigned Pool is Empty"}
              description={
                isRTL
                  ? "جميع العملاء المستوردين تم تعيينهم لمندوبي المبيعات بنجاح. يمكنك استيراد المزيد من تبويب أوراق جوجل."
                  : "All imported leads have been distributed to sales representatives. Ingest fresh leads via the Google Sheets tab."
              }
              icon={<Users size={32} />}
              action={
                <button onClick={() => setActiveTab('sheets')} className="btn btn-secondary btn-sm">
                  {isRTL ? "الانتقال لتبويب أوراق جوجل" : "Go to Google Sheets Sync"}
                </button>
              }
            />
          ) : (
            <div className="card" style={{ padding: 0 }}>
              <div className="table-container custom-scrollbar" style={{ overflowX: 'auto' }}>
                <table className="data-table">
                  <thead>
                    <tr>
                      <th style={{ width: '40px' }}>
                        <input
                          type="checkbox"
                          checked={selectedIds.length === leads.length && leads.length > 0}
                          onChange={(e) => handleSelectAll(e.target.checked)}
                        />
                      </th>
                      <th>{isRTL ? "اسم العميل والمنصب" : "Lead Name & Title"}</th>
                      <th>{isRTL ? "الشركة" : "Company"}</th>
                      <th>{isRTL ? "بيانات التواصل" : "Contact Details"}</th>
                      <th>{isRTL ? "الدولة" : "Country"}</th>
                      <th>{isRTL ? "القطاع" : "Industry"}</th>
                      <th>{isRTL ? "المصدر" : "Source"}</th>
                      <th>{isRTL ? "تاريخ الاستيراد" : "Import Date"}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {leads.map((l) => (
                      <tr key={l.id}>
                        <td>
                          <input
                            type="checkbox"
                            checked={selectedIds.includes(l.id)}
                            onChange={() => toggleSelectOne(l.id)}
                          />
                        </td>
                        <td>
                          <div className="font-semibold text-dark">{l.full_name}</div>
                          <div className="text-xs text-muted">{l.position || '—'}</div>
                        </td>
                        <td>
                          <span className="font-medium text-sm">{l.company_name || '—'}</span>
                        </td>
                        <td>
                          <div className="text-xs font-mono">{l.phone || '—'}</div>
                          <div className="text-xs text-muted">{l.email || '—'}</div>
                        </td>
                        <td>
                          <span className="text-xs font-medium">{l.country || '—'}</span>
                        </td>
                        <td>
                          <span className="text-xs text-muted">{l.industry || '—'}</span>
                        </td>
                        <td>
                          <span className="badge badge-new">{l.source || 'Google Sheet'}</span>
                        </td>
                        <td>
                          <span className="text-xs text-muted">
                            {new Date(l.created_at).toLocaleDateString()}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}

      {/* ── TAB: PERSONAL POOL (PENDING_CLAIM leads assigned to me) ──────── */}
      {activeTab === 'my_pool' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
          {/* Explanation Card */}
          <div
            className="card"
            style={{
              backgroundColor: 'var(--color-accent-light)',
              border: '1px solid var(--color-accent)',
              padding: 'var(--space-4) var(--space-5)',
              display: 'flex',
              alignItems: 'flex-start',
              gap: 'var(--space-3)',
            }}
          >
            <Inbox size={20} style={{ color: 'var(--color-accent)', flexShrink: 0, marginTop: '2px' }} />
            <div>
              <div className="font-semibold text-sm" style={{ color: 'var(--neutral-900)' }}>
                {isRTL ? 'قائمة انتظاري الشخصية' : 'Your Personal Lead Pool'}
              </div>
              <div className="text-xs text-muted" style={{ marginTop: '2px' }}>
                {isRTL
                  ? 'هذه قائمة العملاء الذين تم توزيعهم عليك بشكل مباشر، لكنهم ليسوا في قائمة جهات اتصالك النشطة بعد. اضغط "أضف لقائمتي" لنقل العميل إلى قائمتك الرئيسية.'
                  : 'These are leads that were distributed directly to you, pending your confirmation. Click "Claim into My Contacts" to move them to your active contacts list at the end of your current sequence.'}
              </div>
            </div>
          </div>

          {isLoadingPersonalPool ? (
            <LoadingSpinner message={isRTL ? 'جاري تحميل قائمة الانتظار...' : 'Loading your personal pool...'} />
          ) : personalPool.length === 0 ? (
            <EmptyState
              title={isRTL ? 'لا يوجد عملاء في انتظارك' : 'Your Personal Pool is Empty'}
              description={isRTL
                ? 'لا توجد عملاء موزعون عليك بانتظار المطالبة. عندما يقوم مشرفك بتوزيع عملاء عليك مباشرة، ستظهر هنا قبل إضافتهم لقائمتك.'
                : 'No leads are waiting in your personal pool. When your manager distributes leads directly to you, they will appear here before being added to your contacts list.'}
              icon={<Inbox size={32} />}
            />
          ) : (
            <div className="card" style={{ padding: 0 }}>
              <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: 'var(--space-4) var(--space-5)', flexWrap: 'wrap', gap: 'var(--space-3)' }}>
                <div>
                  <h3 className="card-title">{isRTL ? 'العملاء في انتظار موافقتك' : 'Leads Awaiting Your Claim'}</h3>
                  <p className="text-xs text-muted" style={{ marginTop: '2px' }}>
                    {isRTL
                      ? `${personalPoolTotal} عميل في قائمتك الشخصية — حدد العملاء المطلوبين واضغط "إضافة للقائمة النشطة"`
                      : `${personalPoolTotal} lead(s) in your pool — select leads and add to your active contacts`}
                  </p>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                  {selectedPoolIds.length > 0 && (
                    <button
                      disabled={isClaimingSelected}
                      onClick={handleClaimSelected}
                      className="btn btn-accent btn-sm"
                      style={{ display: 'inline-flex', alignItems: 'center', gap: '5px', fontWeight: 700 }}
                    >
                      <CheckCircle2 size={14} />
                      <span>
                        {isRTL
                          ? `إضافة المحدد (${selectedPoolIds.length}) لقائمتي`
                          : `Claim Selected (${selectedPoolIds.length})`}
                      </span>
                    </button>
                  )}
                  <button onClick={fetchPersonalPool} className="btn btn-secondary btn-sm" style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <RefreshCw size={13} />
                    {isRTL ? 'تحديث' : 'Refresh'}
                  </button>
                </div>
              </div>
              <div className="table-container custom-scrollbar" style={{ overflowX: 'auto' }}>
                <table className="data-table">
                  <thead>
                    <tr>
                      <th style={{ width: '40px' }}>
                        <input
                          type="checkbox"
                          checked={selectedPoolIds.length === personalPool.length && personalPool.length > 0}
                          onChange={(e) => handleSelectAllPool(e.target.checked)}
                        />
                      </th>
                      <th>{isRTL ? 'اسم العميل' : 'Lead Name'}</th>
                      <th>{isRTL ? 'الشركة' : 'Company'}</th>
                      <th>{isRTL ? 'رقم الهاتف' : 'Phone'}</th>
                      <th>{isRTL ? 'البريد' : 'Email'}</th>
                      <th>{isRTL ? 'الدولة' : 'Country'}</th>
                      <th>{isRTL ? 'المصدر' : 'Source Sheet'}</th>
                      <th>{isRTL ? 'الإجراء' : 'Action'}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {personalPool.map((lead) => (
                      <tr key={lead.id}>
                        <td>
                          <input
                            type="checkbox"
                            checked={selectedPoolIds.includes(lead.id)}
                            onChange={() => handleToggleSelectPool(lead.id)}
                          />
                        </td>
                        <td>
                          <div className="font-semibold text-sm">{lead.full_name}</div>
                          <div className="text-xs text-muted">{(lead as any).position || '—'}</div>
                        </td>
                        <td className="text-sm">{(lead as any).company_name || '—'}</td>
                        <td className="text-xs font-mono">{lead.phone || '—'}</td>
                        <td className="text-xs text-muted">{lead.email || '—'}</td>
                        <td className="text-xs">{lead.country || '—'}</td>
                        <td className="text-xs text-muted">{(lead as any).source_sheet || '—'}</td>
                        <td>
                          <button
                            onClick={() => handleClaimContact(lead.id)}
                            className="btn btn-accent btn-sm"
                            style={{ display: 'inline-flex', alignItems: 'center', gap: '5px', fontSize: '12px' }}
                          >
                            <CheckCircle2 size={13} />
                            {isRTL ? 'أضف لقائمتي' : 'Claim into My Contacts'}
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── TAB 2: GOOGLE SHEETS INGESTION & SYNC ──────────────────────── */}
      {activeTab === 'sheets' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-6)' }}>
          {/* Sync Result Banner */}
          {syncResult && (
            <div
              className="card"
              style={{
                backgroundColor: 'var(--bg-surface)',
                borderLeft: '4px solid var(--color-success)',
                padding: 'var(--space-4) var(--space-5)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                flexWrap: 'wrap',
                gap: 'var(--space-3)',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
                <CheckCircle2 size={24} style={{ color: 'var(--color-success)' }} />
                <div>
                  <h4 className="font-semibold text-sm" style={{ color: 'var(--neutral-900)' }}>
                    {isRTL ? "اكتملت المزامنة بنجاح!" : "Synchronization Finished Successfully!"}
                  </h4>
                  <div className="text-xs text-muted" style={{ display: 'flex', gap: 'var(--space-3)', marginTop: '2px' }}>
                    <span>{isRTL ? "الأسطر المقروءة:" : "Rows Read:"} <strong>{syncResult.rows_read}</strong></span>
                    <span>•</span>
                    <span style={{ color: 'var(--color-success)' }}>
                      {isRTL ? "تم الاستيراد:" : "Imported:"} <strong>{syncResult.rows_imported}</strong>
                    </span>
                    <span>•</span>
                    <span>{isRTL ? "مكرر تم تجاوزه:" : "Duplicates Skipped:"} <strong>{syncResult.rows_duplicate}</strong></span>
                    {syncResult.rows_error > 0 && (
                      <>
                        <span>•</span>
                        <span style={{ color: '#ef4444' }}>
                          {isRTL ? "أخطاء في السطور:" : "Errors:"} <strong>{syncResult.rows_error}</strong>
                        </span>
                      </>
                    )}
                  </div>
                </div>
              </div>

              <button onClick={() => setSyncResult(null)} className="btn btn-ghost btn-sm text-xs">
                {isRTL ? "إغلاق" : "Dismiss"}
              </button>
            </div>
          )}

          {/* Active Configs Grid */}
          <div className="card">
            <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <h3 className="card-title">{isRTL ? "أوراق جوجل المتصلة بالنظام" : "Connected Google Sheets Workbooks"}</h3>
                <p className="text-xs text-muted" style={{ marginTop: '2px' }}>
                  {isRTL ? "انقر على 'مزامنة فورية' لجلب السطور الجديدة تلقائياً" : "Click 'Sync Now' to pull new leads immediately"}
                </p>
              </div>

              <button onClick={() => setShowAddSheetModal(true)} className="btn btn-accent btn-sm">
                <Plus size={14} />
                <span>{isRTL ? "إضافة ورقة" : "Add Sheet"}</span>
              </button>
            </div>

            {configs.length === 0 ? (
              <div className="text-center py-6 text-muted">
                {isRTL ? "لم يتم ربط أوراق جوجل بعد. اضغط على 'إضافة ورقة' للبدء." : "No Google Sheets connected yet. Click 'Add Sheet' to connect."}
              </div>
            ) : (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 'var(--space-4)' }}>
                {configs.map((c) => (
                  <div
                    key={c.id}
                    style={{
                      padding: 'var(--space-4)',
                      borderRadius: 'var(--radius-lg)',
                      border: '1px solid var(--border-color)',
                      backgroundColor: 'var(--neutral-50)',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: 'var(--space-3)',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                      <div>
                        <h4 className="font-semibold text-sm" style={{ color: 'var(--neutral-900)' }}>
                          {c.name}
                        </h4>
                        <div className="text-xs text-muted" style={{ marginTop: '2px' }}>
                          Sheet: <strong>{c.sheet_name}</strong> (Range: {c.range})
                        </div>
                      </div>
                      <Badge variant="success">Active</Badge>
                    </div>

                    <div className="text-xs font-mono text-muted" style={{ wordBreak: 'break-all' }}>
                      ID: {c.spreadsheet_id}
                    </div>

                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 'var(--space-2)' }}>
                      <span className="text-xs text-muted">
                        {c.last_synced_at ? (
                          <>
                            {isRTL ? "آخر مزامنة:" : "Last Synced:"} {new Date(c.last_synced_at).toLocaleTimeString()}
                          </>
                        ) : (
                          <span className="text-amber-600">{isRTL ? "لم تتم المزامنة بعد" : "Never Synced"}</span>
                        )}
                      </span>

                      <button
                        disabled={isSyncing === c.id}
                        onClick={() => handleTriggerSync(c.id)}
                        className="btn btn-primary btn-sm"
                        style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
                      >
                        <RefreshCw size={13} className={isSyncing === c.id ? 'animate-spin' : ''} />
                        <span>{isSyncing === c.id ? (isRTL ? 'جاري السحب...' : 'Syncing...') : (isRTL ? 'مزامنة فورية' : 'Sync Now')}</span>
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Sync History Logs */}
          <div className="card">
            <div className="card-header">
              <h3 className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                <History size={17} style={{ color: 'var(--color-accent)' }} />
                {isRTL ? "سجل عمليات المزامنة السابقة" : "Google Sheets Sync Execution History"}
              </h3>
            </div>

            {syncRuns.length === 0 ? (
              <div className="text-center py-6 text-muted">{isRTL ? "لا توجد عمليات سابقة" : "No sync runs recorded yet"}</div>
            ) : (
              <div className="table-container">
                <table className="table">
                  <thead>
                    <tr>
                      <th>{isRTL ? "الحالة" : "Status"}</th>
                      <th>{isRTL ? "المصدر / الورقة" : "Sheet Config"}</th>
                      <th>{isRTL ? "الأسطر المقروءة" : "Read"}</th>
                      <th>{isRTL ? "المستوردة" : "Imported"}</th>
                      <th>{isRTL ? "المكررة" : "Duplicates"}</th>
                      <th>{isRTL ? "الأخطاء" : "Errors"}</th>
                      <th>{isRTL ? "وقت التنفيذ" : "Completed At"}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {syncRuns.map((r) => (
                      <tr key={r.id}>
                        <td>
                          <Badge variant={r.status === 'SUCCESS' ? 'success' : 'error'}>{r.status}</Badge>
                        </td>
                        <td className="font-medium text-xs">{r.config_name || 'Workbook Sync'}</td>
                        <td className="text-xs">{r.rows_read}</td>
                        <td className="text-xs font-semibold text-success">{r.rows_imported}</td>
                        <td className="text-xs text-muted">{r.rows_duplicate}</td>
                        <td className="text-xs">
                          <span className={r.rows_error > 0 ? 'text-error font-semibold' : 'text-muted'}>
                            {r.rows_error}
                          </span>
                        </td>
                        <td className="text-xs text-muted">
                          {r.completed_at ? new Date(r.completed_at).toLocaleString() : '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── Connect Google Sheet Modal ─────────────────────────────────── */}
      <Modal
        isOpen={showAddSheetModal}
        onClose={() => setShowAddSheetModal(false)}
        title={isRTL ? "ربط ورقة جوجل جديدة للنظام" : "Connect Google Spreadsheet"}
        footer={
          <>
            <button
              type="button"
              onClick={() => setShowAddSheetModal(false)}
              className="btn btn-secondary"
            >
              {isRTL ? "إلغاء" : "Cancel"}
            </button>
            <button
              type="button"
              onClick={handleCreateSheetConfig}
              className="btn btn-accent"
            >
              {isRTL ? "حفظ وتفعيل التكامل" : "Save & Activate Integration"}
            </button>
          </>
        }
      >
        <form onSubmit={handleCreateSheetConfig}>
          <div className="form-group">
            <label className="form-label">{isRTL ? "اسم الإعداد / الورقة *" : "Configuration Name *"}</label>
            <input
              type="text"
              required
              className="form-input"
              value={newSheet.name}
              onChange={(e) => setNewSheet({ ...newSheet, name: e.target.value })}
              placeholder="e.g. Saudi Banking Executives Q3"
            />
          </div>

          <div className="form-group">
            <label className="form-label">{isRTL ? "معرف ورقة جوجل (Spreadsheet ID) *" : "Google Spreadsheet ID / URL *"}</label>
            <input
              type="text"
              required
              className="form-input font-mono text-xs"
              value={newSheet.spreadsheet_id}
              onChange={(e) => setNewSheet({ ...newSheet, spreadsheet_id: e.target.value })}
              placeholder="1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms"
            />
            <span className="text-xs text-muted mt-1 block">
              {isRTL
                ? "يمكنك نسخ المعرف من رابط جدول جوجل بين /d/ و /edit"
                : "The long alphanumeric string between /d/ and /edit in your Google Sheets URL."}
            </span>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-4)' }}>
            <div className="form-group">
              <label className="form-label">{isRTL ? "اسم الصفحة (Sheet Name)" : "Sheet Tab Name"}</label>
              <input
                type="text"
                className="form-input"
                value={newSheet.sheet_name}
                onChange={(e) => setNewSheet({ ...newSheet, sheet_name: e.target.value })}
                placeholder="Sheet1"
              />
            </div>

            <div className="form-group">
              <label className="form-label">{isRTL ? "نطاق الأعمدة (Range)" : "Cell Range"}</label>
              <input
                type="text"
                className="form-input"
                value={newSheet.range}
                onChange={(e) => setNewSheet({ ...newSheet, range: e.target.value })}
                placeholder="A:Z"
              />
            </div>
          </div>

          <div
            style={{
              padding: 'var(--space-3) var(--space-4)',
              backgroundColor: 'var(--color-primary-subtle)',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--color-accent-light)',
              fontSize: 'var(--text-xs)',
              color: 'var(--neutral-800)',
              marginTop: 'var(--space-2)',
            }}
          >
            <div className="font-semibold mb-1">⚡ Smart Auto-Column Mapping:</div>
            Columns named First Name, Last Name, Phone, Email, Company, Position, Country, and historical call attempts (1st Attempts, 2nd Attempts) are automatically mapped and converted.
          </div>
        </form>
      </Modal>

      {/* ── Lead Distribution Modal ────────────────────────────────────── */}
      <Modal
        isOpen={showDistributeModal}
        onClose={() => setShowDistributeModal(false)}
        title={isRTL ? "توزيع العملاء على مندوبي المبيعات" : "Distribute Leads to Sales Agents"}
        footer={
          <>
            <button
              type="button"
              onClick={() => setShowDistributeModal(false)}
              className="btn btn-secondary"
            >
              {isRTL ? "إلغاء" : "Cancel"}
            </button>
            <button
              type="button"
              disabled={isDistributing}
              onClick={handleDistribute}
              className="btn btn-accent"
            >
              {isDistributing
                ? (isRTL ? 'جاري التوزيع...' : 'Distributing...')
                : (isRTL ? 'تنفيذ توزيع العملاء' : 'Execute Lead Distribution')}
            </button>
          </>
        }
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
          <div>
            <label className="form-label">{isRTL ? "اختر استراتيجية التوزيع" : "Select Distribution Strategy"}</label>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 'var(--space-2)' }}>
              <StrategyOption
                title={isRTL ? "توزيع دوري (Round Robin)" : "Round Robin"}
                desc={isRTL ? "توزيع متساوي بالتناوب على جميع المندوبين" : "Evenly distribute across all active sales agents"}
                selected={strategy === 'ROUND_ROBIN'}
                onClick={() => setStrategy('ROUND_ROBIN')}
                icon={<Shuffle size={18} />}
              />
              <StrategyOption
                title={isRTL ? "تعيين مباشر / يدوي" : "Direct / Manual"}
                desc={isRTL ? "إسناد جميع العملاء المحددين لموظف واحد" : "Assign all selected leads to one specific agent"}
                selected={strategy === 'MANUAL'}
                onClick={() => setStrategy('MANUAL')}
                icon={<CheckSquare size={18} />}
              />
              <StrategyOption
                title={isRTL ? "توزيع جغرافي حسب الدولة" : "Country-Based"}
                desc={isRTL ? "السعودية للموظف 1، الإمارات للموظف 2..." : "Distribute according to regional territories"}
                selected={strategy === 'COUNTRY'}
                onClick={() => setStrategy('COUNTRY')}
                icon={<Globe size={18} />}
              />
              <StrategyOption
                title={isRTL ? "تقسيم بالنسب المئوية" : "Percentage Split"}
                desc={isRTL ? "تخصيص نسب معينة لكل موظف (مثلاً 40% صالح، 30% أمين)" : "Distribute according to capacity weight"}
                selected={strategy === 'PERCENTAGE'}
                onClick={() => setStrategy('PERCENTAGE')}
                icon={<Percent size={18} />}
              />
            </div>
          </div>

          {strategy === 'MANUAL' && (
            <div className="form-group" style={{ marginTop: 'var(--space-2)' }}>
              <label className="form-label">{isRTL ? "اختر الموظف المستلم" : "Select Target Sales Agent"}</label>
              <select
                className="form-select"
                value={targetUserId}
                onChange={(e) => setTargetUserId(e.target.value)}
              >
                {salesUsers.map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.full_name} ({u.role}) — Max Capacity: {u.lead_capacity || 50}
                  </option>
                ))}
              </select>
            </div>
          )}

          {strategy === 'PERCENTAGE' && (
            <div style={{ marginTop: 'var(--space-2)', display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
              <label className="form-label">{isRTL ? "حدد النسبة المئوية لكل موظف (%)" : "Set Percentage Allocation per Rep (%)"}</label>
              {salesUsers.map((u) => (
                <div key={u.id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 'var(--space-3)' }}>
                  <span className="text-xs font-semibold text-dark">{u.full_name}</span>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <input
                      type="number"
                      min={0}
                      max={100}
                      value={percentageMap[u.id] || 0}
                      onChange={(e) =>
                        setPercentageMap({
                          ...percentageMap,
                          [u.id]: parseInt(e.target.value) || 0,
                        })
                      }
                      className="form-input text-xs"
                      style={{ width: '80px', textAlign: 'center' }}
                    />
                    <span className="text-xs text-muted">%</span>
                  </div>
                </div>
              ))}
            </div>
          )}

          <div
            style={{
              padding: 'var(--space-3) var(--space-4)',
              backgroundColor: 'var(--color-primary-subtle)',
              borderRadius: 'var(--radius-lg)',
              border: '1px solid var(--color-accent-light)',
              fontSize: 'var(--text-xs)',
              color: 'var(--neutral-800)',
            }}
          >
            <strong>{isRTL ? "ملاحظة أمان وتدقيق:" : "Audit Trail Guarantee:"}</strong>{' '}
            {isRTL
              ? "عمليات التوزيع تسجل بشكل دائم في سجل التدقيق (Audit Log) مع إشعار الموظفين فورياً."
              : "Lead assignment events are immutably recorded in the Audit Log and notify assigned agents automatically."}
          </div>
        </div>
      </Modal>
    </div>
  );
};

const StrategyOption: React.FC<{
  title: string;
  desc: string;
  selected: boolean;
  onClick: () => void;
  icon: React.ReactNode;
}> = ({ title, desc, selected, onClick, icon }) => (
  <div
    onClick={onClick}
    style={{
      padding: 'var(--space-3)',
      borderRadius: 'var(--radius-lg)',
      border: `2px solid ${selected ? 'var(--color-accent)' : 'var(--border-color)'}`,
      backgroundColor: selected ? 'var(--color-primary-subtle)' : 'var(--bg-surface)',
      cursor: 'pointer',
      display: 'flex',
      flexDirection: 'column',
      gap: 'var(--space-1)',
    }}
  >
    <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', color: selected ? 'var(--color-accent)' : 'var(--neutral-700)' }}>
      {icon}
      <span className="font-semibold text-sm">{title}</span>
    </div>
    <span className="text-xs text-muted">{desc}</span>
  </div>
);
