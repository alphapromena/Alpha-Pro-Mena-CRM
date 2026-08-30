import React, { useState, useEffect } from 'react';
import { api } from '../../lib/apiClient';
import { Campaign } from '../../types';
import { Badge } from '../../components/ui/Badge';
import { LoadingSpinner } from '../../components/feedback/LoadingSpinner';
import { EmptyState } from '../../components/feedback/EmptyState';
import { Flame, Plus, Globe, Briefcase } from 'lucide-react';

export const CampaignsPage: React.FC = () => {
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const fetchCampaigns = async () => {
    setIsLoading(true);
    try {
      const res = await api.get<any>('/campaigns');
      setCampaigns(res.data || []);
    } catch (e) {
      console.error('Failed to load campaigns', e);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchCampaigns();
  }, []);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-6)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1 className="font-display font-bold text-2xl" style={{ color: 'var(--neutral-900)' }}>
            Sales Outreach Campaigns ({campaigns.length})
          </h1>
          <p className="text-sm text-muted">
            Targeted regional sales drives, vertical outreach campaigns, and lead segmentation.
          </p>
        </div>
      </div>

      {isLoading ? (
        <LoadingSpinner message="Loading outreach campaigns..." />
      ) : campaigns.length === 0 ? (
        <EmptyState title="No campaigns found" description="Create targeted outreach campaigns to organize outreach." />
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 'var(--space-4)' }}>
          {campaigns.map((camp) => (
            <div key={camp.id} className="card" style={{ padding: 'var(--space-5)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 'var(--space-2)' }}>
                <h3 className="font-display font-bold text-base text-dark">{camp.name}</h3>
                <span className="badge badge-won">{camp.status}</span>
              </div>
              <p className="text-xs text-muted" style={{ marginBottom: 'var(--space-4)', minHeight: '36px' }}>
                {camp.description || 'No description provided.'}
              </p>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)', fontSize: 'var(--text-xs)', borderTop: '1px solid var(--border-light)', paddingTop: 'var(--space-3)' }}>
                {camp.target_country && (
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span className="text-muted">Target Territory:</span>
                    <span className="font-medium">{camp.target_country}</span>
                  </div>
                )}
                {camp.target_industry && (
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span className="text-muted">Target Industry:</span>
                    <span className="font-medium">{camp.target_industry}</span>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
