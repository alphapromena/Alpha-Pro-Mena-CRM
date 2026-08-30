import React, { useState, useEffect } from 'react';
import { api } from '../../lib/apiClient';
import { LoadingSpinner } from '../../components/feedback/LoadingSpinner';
import { Layers, Shuffle, Globe, Percent, Plus, Users, Inbox, CheckCircle2, Clock, Activity } from 'lucide-react';
import { useTranslation } from '../../i18n';

export const LeadDistributionPage: React.FC = () => {
  const { isRTL } = useTranslation();
  const [statusData, setStatusData] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(true);

  const fetchStatus = async () => {
    setIsLoading(true);
    try {
      const res = await api.get<any>('/admin/distribution-status');
      setStatusData(res.data);
    } catch (e) {
      console.error('Failed to load distribution status', e);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();
  }, []);

  const getFirstName = (name: string) => (name ? name.trim().split(' ')[0] : 'User');

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-6)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 'var(--space-4)' }}>
        <div>
          <h1 className="font-display font-bold text-2xl" style={{ color: 'var(--neutral-900)' }}>
            {isRTL ? "عمليات وتوزيع العملاء على المناديب" : "Lead Distribution & Operations Telemetry"}
          </h1>
          <p className="text-sm text-muted">
            {isRTL
              ? "مراقبة مستودع العملاء، توزيع الحصص، ومتابعة قوائم الانتظار الشخصية للمناديب (Personal Pool)."
              : "Monitor unassigned leads, assign batches to sales personal pools, and track claim throughput."}
          </p>
        </div>
        <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
          <button
            onClick={() => (window.location.href = '/leads/pool')}
            className="btn btn-accent btn-md"
          >
            <Inbox size={16} />
            <span>{isRTL ? "فتح مستودع العملاء" : "Open Lead Pool & Ingestion"}</span>
          </button>
        </div>
      </div>

      {isLoading ? (
        <LoadingSpinner message={isRTL ? "جاري تحميل إحصائيات التوزيع..." : "Loading distribution telemetry..."} />
      ) : (
        <>
          {/* Top KPI Metric Cards */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 'var(--space-4)' }}>
            <div className="card" style={{ padding: 'var(--space-5)' }}>
              <div className="text-xs text-muted font-bold" style={{ textTransform: 'uppercase', marginBottom: 'var(--space-2)' }}>
                {isRTL ? "إجمالي العملاء في النظام" : "Total CRM Leads"}
              </div>
              <div className="font-display font-bold text-3xl" style={{ color: 'var(--neutral-900)' }}>
                {statusData?.total_leads || 0}
              </div>
              <div className="text-xs text-muted" style={{ marginTop: 'var(--space-1)' }}>
                {isRTL ? "كافة السجلات المستوردة" : "All imported records across sheets"}
              </div>
            </div>

            <div className="card" style={{ padding: 'var(--space-5)', borderLeft: '4px solid var(--color-accent)' }}>
              <div className="text-xs text-muted font-bold" style={{ textTransform: 'uppercase', marginBottom: 'var(--space-2)' }}>
                {isRTL ? "مستودع غير المخصصين" : "Unassigned Lead Pool"}
              </div>
              <div className="font-display font-bold text-3xl" style={{ color: 'var(--color-accent)' }}>
                {statusData?.unassigned_pool_count || 0}
              </div>
              <div className="text-xs text-muted" style={{ marginTop: 'var(--space-1)' }}>
                {isRTL ? "بانتظار التوزيع على المناديب" : "Awaiting distribution by Data Ops / Manager"}
              </div>
            </div>

            <div className="card" style={{ padding: 'var(--space-5)', borderLeft: '4px solid #8b5cf6' }}>
              <div className="text-xs text-muted font-bold" style={{ textTransform: 'uppercase', marginBottom: 'var(--space-2)' }}>
                {isRTL ? "قوائم الانتظار الشخصية" : "Total Waiting in Personal Pools"}
              </div>
              <div className="font-display font-bold text-3xl" style={{ color: '#8b5cf6' }}>
                {statusData?.sales_reps?.reduce((acc: number, r: any) => acc + (r.waiting_in_pool || 0), 0) || 0}
              </div>
              <div className="text-xs text-muted" style={{ marginTop: 'var(--space-1)' }}>
                {isRTL ? "بانتظار موافقة المناديب وإضافتها" : "Distributed to reps, awaiting reps claiming"}
              </div>
            </div>
          </div>

          {/* Sales Representatives Lead Telemetry Table */}
          <div className="card" style={{ padding: 0 }}>
            <div className="card-header" style={{ padding: 'var(--space-4) var(--space-5)' }}>
              <h3 className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                <Users size={18} style={{ color: 'var(--color-primary)' }} />
                <span>{isRTL ? "توزيع العملاء وحالة المطالبة لكل مندوب" : "Sales Representative Personal Pool & Claim Telemetry"}</span>
              </h3>
            </div>
            <div className="table-container custom-scrollbar" style={{ overflowX: 'auto' }}>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>{isRTL ? "مندوب المبيعات" : "Sales Rep"}</th>
                    <th>{isRTL ? "الدور الوظيفي" : "Role"}</th>
                    <th style={{ textAlign: 'center' }}>{isRTL ? "المعين له إجمالاً" : "Assigned Total"}</th>
                    <th style={{ textAlign: 'center' }}>{isRTL ? "تمت إضافته للقائمة النشطة" : "Claimed (Active)"}</th>
                    <th style={{ textAlign: 'center' }}>{isRTL ? "في قائمة الانتظار الشخصية" : "Waiting in Pool"}</th>
                    <th style={{ textAlign: 'center' }}>{isRTL ? "نسبة التفعيل" : "Claim Rate"}</th>
                  </tr>
                </thead>
                <tbody>
                  {statusData?.sales_reps?.map((rep: any) => (
                    <tr key={rep.user_id}>
                      <td>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                          <div
                            style={{
                              width: '28px',
                              height: '28px',
                              borderRadius: '50%',
                              backgroundColor: 'var(--color-primary-subtle)',
                              color: 'var(--color-primary)',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              fontWeight: 700,
                              fontSize: '12px',
                            }}
                          >
                            {getFirstName(rep.user_name)[0]}
                          </div>
                          <span className="font-semibold text-sm">{getFirstName(rep.user_name)}</span>
                        </div>
                      </td>
                      <td>
                        <span className="badge badge-secondary text-xs">{rep.role}</span>
                      </td>
                      <td style={{ textAlign: 'center', fontWeight: 600 }}>{rep.assigned_total}</td>
                      <td style={{ textAlign: 'center' }}>
                        <span className="badge badge-won text-xs">{rep.claimed_active}</span>
                      </td>
                      <td style={{ textAlign: 'center' }}>
                        {rep.waiting_in_pool > 0 ? (
                          <span className="badge badge-accent text-xs" style={{ fontWeight: 700 }}>
                            {rep.waiting_in_pool} {isRTL ? "في الانتظار" : "waiting"}
                          </span>
                        ) : (
                          <span className="text-xs text-muted">0</span>
                        )}
                      </td>
                      <td style={{ textAlign: 'center' }}>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 'var(--space-2)' }}>
                          <div style={{ width: '60px', height: '6px', backgroundColor: 'var(--neutral-200)', borderRadius: 'var(--radius-full)', overflow: 'hidden' }}>
                            <div
                              style={{
                                width: `${rep.claim_rate}%`,
                                height: '100%',
                                backgroundColor: rep.claim_rate >= 80 ? 'var(--color-success)' : 'var(--color-accent)',
                              }}
                            />
                          </div>
                          <span className="text-xs font-bold">{rep.claim_rate}%</span>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Strategy Definitions */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 'var(--space-4)' }}>
            <StrategyCard
              title="Round-Robin Engine"
              desc="Splits newly validated leads into sales reps' Personal Pools in alternating sequence."
              active={true}
              icon={<Shuffle size={24} />}
            />
            <StrategyCard
              title="Territory / Country Match"
              desc="Routes Saudi leads to Saudi sales personal pool, UAE leads to UAE personal pool."
              active={true}
              icon={<Globe size={24} />}
            />
            <StrategyCard
              title="Targeted User Batching"
              desc="Aseel or manager selects exact counts for Saleh, Amin, Hasan, and Ghaida."
              active={true}
              icon={<Percent size={24} />}
            />
          </div>
        </>
      )}
    </div>
  );
};

const StrategyCard: React.FC<{ title: string; desc: string; active: boolean; icon: React.ReactNode }> = ({
  title,
  desc,
  active,
  icon,
}) => (
  <div className="card" style={{ padding: 'var(--space-5)' }}>
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-3)' }}>
      <div style={{ color: 'var(--color-accent)' }}>{icon}</div>
      <span className="badge badge-won">Active Strategy</span>
    </div>
    <h3 className="font-bold text-base text-dark" style={{ marginBottom: 'var(--space-1)' }}>
      {title}
    </h3>
    <p className="text-xs text-muted" style={{ lineHeight: 1.4 }}>
      {desc}
    </p>
  </div>
);
