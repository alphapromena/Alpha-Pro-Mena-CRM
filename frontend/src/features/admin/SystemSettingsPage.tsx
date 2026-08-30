import React, { useState, useEffect } from 'react';
import { api } from '../../lib/apiClient';
import { useTranslation } from '../../i18n';
import { LoadingSpinner } from '../../components/feedback/LoadingSpinner';
import {
  Settings,
  Shield,
  Save,
  Clock,
  PhoneCall,
  Mail,
  MessageSquare,
  Users,
  CheckCircle2,
  AlertCircle,
  Palette,
  Globe,
} from 'lucide-react';

export const SystemSettingsPage: React.FC = () => {
  const { t, isRTL } = useTranslation();
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const [settings, setSettings] = useState({
    call_outcomes: [] as any[],
    no_answer_retry_hours: 48,
    max_no_answer_attempts: 5,
    email_followup_delay_hours: 24,
    whatsapp_followup_delay_hours: 24,
    default_lead_capacity: 500,
    default_theme: 'black_beige',
    default_language: 'ar',
    primary_team_lead: 'Qusai',
    auto_assignment_enabled: true,
  });

  const fetchSettings = async () => {
    setIsLoading(true);
    try {
      const res = await api.get<any>('/admin/settings');
      if (res.data) {
        setSettings((prev) => ({ ...prev, ...res.data }));
      }
    } catch (err: any) {
      console.error('Failed to load system settings', err);
      setErrorMsg(err.message || 'Failed to load system settings');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchSettings();
  }, []);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    setSuccessMsg(null);
    setErrorMsg(null);

    try {
      await api.patch('/admin/settings', {
        no_answer_retry_hours: Number(settings.no_answer_retry_hours),
        max_no_answer_attempts: Number(settings.max_no_answer_attempts),
        email_followup_delay_hours: Number(settings.email_followup_delay_hours),
        whatsapp_followup_delay_hours: Number(settings.whatsapp_followup_delay_hours),
        default_lead_capacity: Number(settings.default_lead_capacity),
        default_theme: settings.default_theme,
        default_language: settings.default_language,
        auto_assignment_enabled: settings.auto_assignment_enabled,
      });
      setSuccessMsg(isRTL ? 'تم حفظ إعدادات النظام وتحديث سجلات التدقيق بنجاح' : 'System configuration saved and audit logged successfully.');
      setTimeout(() => setSuccessMsg(null), 5000);
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to update system settings');
    } finally {
      setIsSaving(false);
    }
  };

  if (isLoading) return <LoadingSpinner message={isRTL ? 'جاري تحميل إعدادات النظام...' : 'Loading system settings...'} />;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-6)', maxWidth: '1000px', margin: '0 auto' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 'var(--space-4)' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
            <span style={{ padding: '6px', backgroundColor: 'rgba(14, 135, 235, 0.1)', borderRadius: 'var(--radius-md)', color: 'var(--color-accent)' }}>
              <Settings size={22} />
            </span>
            <h1 className="font-display font-bold text-2xl" style={{ color: 'var(--neutral-900)' }}>
              {isRTL ? 'إعدادات النظام العامة — قائد الفريق' : 'CRM System Settings — Team Lead'}
            </h1>
          </div>
          <p className="text-sm text-muted" style={{ marginTop: '4px' }}>
            {isRTL
              ? 'إدارة محددات سير العمل، قنوات التواصل، مهل إعادة المحاولة، وقواعد توزيع العملاء'
              : 'Manage operational workflows, retry cadences, follow-up timers, and CRM defaults.'}
          </p>
        </div>

        <button
          type="button"
          disabled={isSaving}
          onClick={handleSave}
          className="btn btn-accent btn-md"
          style={{ display: 'inline-flex', alignItems: 'center', gap: 'var(--space-2)' }}
        >
          <Save size={18} />
          <span>{isSaving ? (isRTL ? 'جاري الحفظ...' : 'Saving Changes...') : (isRTL ? 'حفظ التعديلات' : 'Save Changes')}</span>
        </button>
      </div>

      {/* Feedback Banners */}
      {successMsg && (
        <div style={{ padding: 'var(--space-3) var(--space-4)', backgroundColor: 'var(--color-success-bg)', border: '1px solid var(--color-success-border)', borderRadius: 'var(--radius-md)', color: 'var(--color-success-text)', fontSize: 'var(--text-sm)', display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
          <CheckCircle2 size={18} />
          <span>{successMsg}</span>
        </div>
      )}

      {errorMsg && (
        <div style={{ padding: 'var(--space-3) var(--space-4)', backgroundColor: 'var(--color-danger-bg)', border: '1px solid var(--color-danger-border)', borderRadius: 'var(--radius-md)', color: 'var(--color-danger-text)', fontSize: 'var(--text-sm)', display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
          <AlertCircle size={18} />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* Authority Banner */}
      <div className="card" style={{ padding: 'var(--space-4) var(--space-5)', display: 'flex', alignItems: 'center', gap: 'var(--space-4)', backgroundColor: 'rgba(14, 135, 235, 0.05)', border: '1px solid rgba(14, 135, 235, 0.2)' }}>
        <div style={{ width: '40px', height: '40px', borderRadius: 'var(--radius-full)', backgroundColor: 'var(--color-accent)', color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '18px', fontWeight: 800 }}>
          👑
        </div>
        <div>
          <div style={{ fontSize: 'var(--text-sm)', fontWeight: 700, color: 'var(--neutral-900)' }}>
            {isRTL ? 'صلاحيات قائد الفريق (Team Lead)' : 'Team Lead System Authority'}
          </div>
          <div style={{ fontSize: '12px', color: 'var(--neutral-600)', marginTop: '2px' }}>
            {isRTL
              ? 'الحساب الرئيسي المعين: قصي (Qusai). يملك هذا الحساب كامل الصلاحيات لتعديل محددات النظام والتحكم بتوزيع العملاء والفرق.'
              : 'Primary Account: Qusai. Holds full system authority for automation rules, lead redistribution, team structure, and audit governance.'}
          </div>
        </div>
      </div>

      <form onSubmit={handleSave} style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-6)' }}>
        {/* Section 1: Retry Cadence & No-Answer Queue */}
        <div className="card" style={{ padding: 'var(--space-6)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', marginBottom: 'var(--space-4)', borderBottom: '1px solid var(--border-color)', paddingBottom: 'var(--space-3)' }}>
            <PhoneCall size={18} color="var(--color-accent)" />
            <h3 className="card-title text-base">
              {isRTL ? 'إعدادات طابور عدم الرد وإعادة المحاولة' : 'No-Answer & Retry Cadence Rules'}
            </h3>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 'var(--space-4)' }}>
            <div className="form-group">
              <label className="form-label" style={{ fontWeight: 600 }}>
                {isRTL ? 'مهلة إعادة الاتصال بعد عدم الرد (ساعات)' : 'No-Answer Retry Delay (Hours)'}
              </label>
              <input
                type="number"
                min="1"
                max="168"
                className="form-input"
                value={settings.no_answer_retry_hours}
                onChange={(e) => setSettings({ ...settings, no_answer_retry_hours: Number(e.target.value) })}
              />
              <span className="text-xs text-muted" style={{ marginTop: '4px', display: 'block' }}>
                {isRTL ? 'المحدد القياسي: 48 ساعة قبل جدولة المحاولة التالية تلقائياً.' : 'Default: 48 hours before scheduling the next call attempt.'}
              </span>
            </div>

            <div className="form-group">
              <label className="form-label" style={{ fontWeight: 600 }}>
                {isRTL ? 'الحد الأقصى لمحاولات عدم الرد' : 'Max No-Answer Retries'}
              </label>
              <input
                type="number"
                min="1"
                max="10"
                className="form-input"
                value={settings.max_no_answer_attempts}
                onChange={(e) => setSettings({ ...settings, max_no_answer_attempts: Number(e.target.value) })}
              />
              <span className="text-xs text-muted" style={{ marginTop: '4px', display: 'block' }}>
                {isRTL ? 'بعد بلوغ هذا الحد يتم تحويل العميل إلى غير متاح أو أرشيف.' : 'Max attempts before marking contact uncontactable.'}
              </span>
            </div>
          </div>
        </div>

        {/* Section 2: Communication Timers */}
        <div className="card" style={{ padding: 'var(--space-6)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', marginBottom: 'var(--space-4)', borderBottom: '1px solid var(--border-color)', paddingBottom: 'var(--space-3)' }}>
            <Clock size={18} color="var(--color-accent)" />
            <h3 className="card-title text-base">
              {isRTL ? 'مهل متابعة طلبات الإيميل والواتساب' : 'Communication Follow-up Automation Timers'}
            </h3>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 'var(--space-4)' }}>
            <div className="form-group">
              <label className="form-label" style={{ display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 600 }}>
                <Mail size={16} color="#0ea5e9" />
                <span>{isRTL ? 'مهلة متابعة طلب الإيميل (ساعات)' : 'Email Requested Follow-up (Hours)'}</span>
              </label>
              <input
                type="number"
                min="1"
                max="72"
                className="form-input"
                value={settings.email_followup_delay_hours}
                onChange={(e) => setSettings({ ...settings, email_followup_delay_hours: Number(e.target.value) })}
              />
              <span className="text-xs text-muted" style={{ marginTop: '4px', display: 'block' }}>
                {isRTL ? 'إنشاء مهمة متابعة تلقائية بعد إرسال العرض عبر الإيميل.' : 'Triggers automated follow-up task after sending email quote.'}
              </span>
            </div>

            <div className="form-group">
              <label className="form-label" style={{ display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 600 }}>
                <MessageSquare size={16} color="#22c55e" />
                <span>{isRTL ? 'مهلة متابعة رسائل الواتساب (ساعات)' : 'WhatsApp Follow-up (Hours)'}</span>
              </label>
              <input
                type="number"
                min="1"
                max="72"
                className="form-input"
                value={settings.whatsapp_followup_delay_hours}
                onChange={(e) => setSettings({ ...settings, whatsapp_followup_delay_hours: Number(e.target.value) })}
              />
              <span className="text-xs text-muted" style={{ marginTop: '4px', display: 'block' }}>
                {isRTL ? 'إنشاء تذكير بالاتصال بالمستفيد بعد إرسال تفاصيل الواتساب.' : 'Triggers follow-up check after WhatsApp outreach.'}
              </span>
            </div>
          </div>
        </div>

        {/* Section 3: Capacity & Lead Distribution Defaults */}
        <div className="card" style={{ padding: 'var(--space-6)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', marginBottom: 'var(--space-4)', borderBottom: '1px solid var(--border-color)', paddingBottom: 'var(--space-3)' }}>
            <Users size={18} color="var(--color-accent)" />
            <h3 className="card-title text-base">
              {isRTL ? 'الطاقة الاستيعابية وقواعد توزيع العملاء' : 'Lead Capacity & Distribution Defaults'}
            </h3>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 'var(--space-4)' }}>
            <div className="form-group">
              <label className="form-label" style={{ fontWeight: 600 }}>
                {isRTL ? 'السعة الافتراضية للمندوب (عدد العملاء)' : 'Default Sales Rep Lead Capacity'}
              </label>
              <input
                type="number"
                min="50"
                max="2000"
                className="form-input"
                value={settings.default_lead_capacity}
                onChange={(e) => setSettings({ ...settings, default_lead_capacity: Number(e.target.value) })}
              />
              <span className="text-xs text-muted" style={{ marginTop: '4px', display: 'block' }}>
                {isRTL ? 'الحد الأقصى للعملاء النشطين المخصصين للمندوب في نفس الوقت.' : 'Maximum active concurrent leads assigned to a sales representative.'}
              </span>
            </div>

            <div className="form-group" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', cursor: 'pointer', fontWeight: 600 }}>
                <input
                  type="checkbox"
                  checked={settings.auto_assignment_enabled}
                  onChange={(e) => setSettings({ ...settings, auto_assignment_enabled: e.target.checked })}
                  style={{ width: '18px', height: '18px', accentColor: 'var(--color-accent)' }}
                />
                <span>{isRTL ? 'تفعيل التوزيع التلقائي الفوري للعملاء الجدد' : 'Enable Automated Ingestion Lead Distribution'}</span>
              </label>
              <span className="text-xs text-muted" style={{ marginTop: '6px' }}>
                {isRTL ? 'توزيع العملاء فور استيرادهم من Google Sheets حسب القواعد النشطة.' : 'Auto-routes incoming Google Sheet rows according to distribution rules.'}
              </span>
            </div>
          </div>
        </div>

        {/* Section 4: Call Outcomes Configuration Matrix */}
        <div className="card" style={{ padding: 'var(--space-6)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', marginBottom: 'var(--space-4)', borderBottom: '1px solid var(--border-color)', paddingBottom: 'var(--space-3)' }}>
            <Palette size={18} color="var(--color-accent)" />
            <h3 className="card-title text-base">
              {isRTL ? 'مصفوفة نتائج المكالمات المعتمدة (Call Outcomes)' : 'Approved Call Outcomes Matrix'}
            </h3>
          </div>

          <div className="table-container">
            <table className="data-table">
              <thead>
                <tr>
                  <th>{isRTL ? 'معرف النتيجة' : 'Outcome Key'}</th>
                  <th>{isRTL ? 'التسمية الإنجليزية' : 'English Label'}</th>
                  <th>{isRTL ? 'التسمية العربية' : 'Arabic Label'}</th>
                  <th>{isRTL ? 'لون التمييز' : 'Color Tag'}</th>
                  <th>{isRTL ? 'تصنيف التحويل' : 'Conversion Impact'}</th>
                </tr>
              </thead>
              <tbody>
                {settings.call_outcomes?.map((outcome) => (
                  <tr key={outcome.id}>
                    <td>
                      <code style={{ fontSize: '11px', fontWeight: 700, padding: '2px 6px', backgroundColor: 'var(--bg-secondary)', borderRadius: '4px' }}>
                        {outcome.id}
                      </code>
                    </td>
                    <td className="font-semibold text-dark text-sm">{outcome.label_en}</td>
                    <td className="font-semibold text-dark text-sm">{outcome.label_ar}</td>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <span style={{ width: '14px', height: '14px', borderRadius: '50%', backgroundColor: outcome.color }} />
                        <span style={{ fontSize: '11px', color: 'var(--neutral-600)' }}>{outcome.color}</span>
                      </div>
                    </td>
                    <td>
                      <span className={`badge ${outcome.is_positive ? 'badge-won' : 'badge-new'}`}>
                        {outcome.is_positive ? (isRTL ? 'تحويل إيجابي' : 'Positive Lead') : (isRTL ? 'متابعة / استبعاد' : 'Follow-up / Disqualified')}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </form>
    </div>
  );
};
