import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { api } from '../../lib/apiClient';
import { Company, Contact } from '../../types';
import { Badge } from '../../components/ui/Badge';
import { LoadingSpinner } from '../../components/feedback/LoadingSpinner';
import { EmptyState } from '../../components/feedback/EmptyState';
import {
  Building2,
  ArrowLeft,
  Globe,
  MapPin,
  Users,
  ShieldCheck,
  ShieldAlert,
  TrendingUp,
  Phone,
  Mail,
  Copy,
  Check,
} from 'lucide-react';

export const CompanyDetailPage: React.FC = () => {
  const { companyId } = useParams<{ companyId: string }>();
  const navigate = useNavigate();

  const [company, setCompany] = useState<any>(null);
  const [contacts, setContacts] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  useEffect(() => {
    const fetchCompanyData = async () => {
      setIsLoading(true);
      try {
        const [compRes, contactsRes] = await Promise.all([
          api.get<any>(`/companies/${companyId}`),
          api.get<any>(`/companies/${companyId}/contacts`),
        ]);
        setCompany(compRes.data);
        setContacts(contactsRes.data || []);
      } catch (e) {
        console.error('Failed to load company details', e);
      } finally {
        setIsLoading(false);
      }
    };
    if (companyId) {
      fetchCompanyData();
    }
  }, [companyId]);

  const handleCopy = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 1500);
  };

  if (isLoading) {
    return <LoadingSpinner message="Loading enterprise account profile..." />;
  }

  if (!company) {
    return (
      <EmptyState
        title="Company not found"
        description="The requested enterprise account could not be found."
        action={
          <button onClick={() => navigate('/companies')} className="btn btn-secondary btn-sm">
            Back to Companies
          </button>
        }
      />
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-6)' }}>
      {/* Top Breadcrumb & Actions */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <button
          onClick={() => navigate('/companies')}
          className="btn btn-secondary btn-sm"
          style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
        >
          <ArrowLeft size={16} />
          <span>Back to Companies</span>
        </button>

        <div style={{ display: 'flex', gap: 'var(--space-3)' }}>
          <button
            onClick={() => navigate('/opportunities')}
            className="btn btn-accent btn-sm"
            style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
          >
            <TrendingUp size={16} />
            <span>Open Opportunity Roadmap</span>
          </button>
        </div>
      </div>

      {/* Company Header Profile Card */}
      <div
        className="card"
        style={{
          padding: 'var(--space-6)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          flexWrap: 'wrap',
          gap: 'var(--space-4)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-4)' }}>
          <div
            style={{
              width: '56px',
              height: '56px',
              borderRadius: 'var(--radius-xl)',
              backgroundColor: 'var(--color-accent-light)',
              color: 'var(--color-primary)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <Building2 size={28} />
          </div>
          <div>
            <h1 className="font-display font-bold text-2xl" style={{ color: 'var(--neutral-900)' }}>
              {company.name}
            </h1>
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)', marginTop: '4px' }}>
              <span className="text-sm font-medium" style={{ color: 'var(--color-primary)' }}>
                {company.industry || 'Enterprise'}
              </span>
              {company.country && (
                <span className="text-xs text-muted" style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <MapPin size={13} />
                  {company.country}
                </span>
              )}
              {company.website && (
                <span className="text-xs text-muted" style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <Globe size={13} />
                  <a href={company.website} target="_blank" rel="noreferrer" style={{ color: 'var(--color-accent)' }}>
                    {company.website}
                  </a>
                </span>
              )}
            </div>
          </div>
        </div>

        <div style={{ textAlign: 'right' }}>
          <div className="text-xs text-muted">Account Owner</div>
          <div className="font-semibold text-sm" style={{ color: 'var(--neutral-900)' }}>
            {company.account_owner_name || 'Unassigned'}
          </div>
        </div>
      </div>

      {/* Associated Contacts Section with RBAC Ownership Indicators */}
      <div className="card" style={{ padding: 'var(--space-6)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-4)' }}>
          <div>
            <h3 className="font-display font-bold text-lg" style={{ color: 'var(--neutral-900)' }}>
              Associated Contacts ({contacts.length})
            </h3>
            <p className="text-xs text-muted">
              Broad visibility across all company leads. Permissions and ownership are clearly indicated per sales rep.
            </p>
          </div>
        </div>

        {contacts.length === 0 ? (
          <EmptyState
            title="No contacts found"
            description="No individual leads or decision-makers have been added for this company."
          />
        ) : (
          <div className="table-container">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Contact Name & Role</th>
                  <th>Contact Details</th>
                  <th>Status</th>
                  <th>Assigned Owner</th>
                  <th>Access Permission</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {contacts.map((c) => (
                  <tr key={c.id}>
                    <td>
                      <div className="font-semibold text-sm" style={{ color: 'var(--neutral-900)' }}>
                        {c.full_name}
                      </div>
                      <div className="text-xs text-muted">{c.position || 'No Title'}</div>
                    </td>
                    <td>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                        {c.phone && (
                          <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                            <span className="text-xs font-mono" style={{ color: 'var(--neutral-800)' }}>
                              {c.phone}
                            </span>
                            <button
                              onClick={() => handleCopy(c.phone, `${c.id}-phone`)}
                              style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '1px' }}
                            >
                              {copiedId === `${c.id}-phone` ? <Check size={12} color="var(--color-success)" /> : <Copy size={12} color="var(--neutral-400)" />}
                            </button>
                          </div>
                        )}
                        {c.email && (
                          <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                            <span className="text-xs text-muted">{c.email}</span>
                            <button
                              onClick={() => handleCopy(c.email, `${c.id}-email`)}
                              style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '1px' }}
                            >
                              {copiedId === `${c.id}-email` ? <Check size={12} color="var(--color-success)" /> : <Copy size={12} color="var(--neutral-400)" />}
                            </button>
                          </div>
                        )}
                      </div>
                    </td>
                    <td>
                      <Badge status={c.status} />
                    </td>
                    <td>
                      <span className="text-xs font-medium" style={{ color: 'var(--neutral-800)' }}>
                        {c.owner_name || 'Unassigned'}
                      </span>
                    </td>
                    <td>
                      {c.can_edit ? (
                        <span
                          style={{
                            fontSize: '11px',
                            fontWeight: '600',
                            padding: '2px 8px',
                            borderRadius: 'var(--radius-sm)',
                            backgroundColor: 'var(--color-success-bg)',
                            color: 'var(--color-success-text)',
                            border: '1px solid var(--color-success-border)',
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '4px',
                          }}
                        >
                          <ShieldCheck size={13} />
                          Full Edit
                        </span>
                      ) : (
                        <span
                          style={{
                            fontSize: '11px',
                            fontWeight: '500',
                            padding: '2px 8px',
                            borderRadius: 'var(--radius-sm)',
                            backgroundColor: 'var(--bg-subtle)',
                            color: 'var(--neutral-500)',
                            border: '1px solid var(--border-color)',
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '4px',
                          }}
                        >
                          <ShieldAlert size={13} />
                          View Only
                        </span>
                      )}
                    </td>
                    <td>
                      <button
                        onClick={() => navigate(`/contacts/${c.id}`)}
                        className="btn btn-secondary btn-sm"
                      >
                        Open Profile
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
