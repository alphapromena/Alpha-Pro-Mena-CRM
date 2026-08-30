import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../../lib/apiClient';
import { Company } from '../../types';
import { LoadingSpinner } from '../../components/feedback/LoadingSpinner';
import { EmptyState } from '../../components/feedback/EmptyState';
import { Building2, Search, ArrowUpDown, Globe, MapPin, Users, ArrowRight, ChevronDown, RefreshCw } from 'lucide-react';

export const CompaniesPage: React.FC = () => {
  const navigate = useNavigate();
  const [companies, setCompanies] = useState<Company[]>([]);
  const [search, setSearch] = useState('');
  const [sortBy, setSortBy] = useState('name');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc');
  const [countryFilter, setCountryFilter] = useState('');
  const [industryFilter, setIndustryFilter] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(1);

  const PER_PAGE = 50;

  const fetchCompanies = useCallback(async (targetPage: number = 1, append: boolean = false) => {
    if (append) setIsLoadingMore(true);
    else setIsLoading(true);

    try {
      const sortParts = sortBy.split('_');
      const sortField = sortParts.slice(0, -1).join('_') || sortParts[0];
      const dir = sortDir;

      const res = await api.get<any>('/companies', {
        page: targetPage,
        per_page: PER_PAGE,
        search: search || undefined,
        sort_by: sortField,
        sort_dir: dir,
        country: countryFilter || undefined,
        industry: industryFilter || undefined,
      });

      const newItems = res.data || [];
      if (append) {
        setCompanies((prev) => [...prev, ...newItems]);
      } else {
        setCompanies(newItems);
      }
      setTotal(res.meta?.total || 0);
      setTotalPages(res.meta?.total_pages || 1);
      setPage(targetPage);
    } catch (e) {
      console.error('Failed to load companies', e);
    } finally {
      setIsLoading(false);
      setIsLoadingMore(false);
    }
  }, [search, sortBy, sortDir, countryFilter, industryFilter]);

  useEffect(() => {
    fetchCompanies(1, false);
  }, [sortBy, sortDir, countryFilter, industryFilter]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    fetchCompanies(1, false);
  };

  const handleLoadMore = () => {
    if (page < totalPages && !isLoadingMore) {
      fetchCompanies(page + 1, true);
    }
  };

  const handleLoadAll = () => {
    api.get<any>('/companies', {
      page: 1,
      per_page: 500,
      search: search || undefined,
      sort_by: sortBy,
      sort_dir: sortDir,
      country: countryFilter || undefined,
      industry: industryFilter || undefined,
    }).then((res) => {
      setCompanies(res.data || []);
      setTotal(res.meta?.total || 0);
      setPage(res.meta?.total_pages || 1);
      setTotalPages(1);
    });
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-6)' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 'var(--space-4)' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
            <h1 className="font-display font-bold text-2xl" style={{ color: 'var(--neutral-900)' }}>
              Companies & Accounts
            </h1>
            <span className="badge badge-accent text-xs">
              {total > 0 ? `${companies.length} / ${total}` : companies.length} shown
            </span>
          </div>
          <p className="text-sm text-muted">
            All enterprise client accounts across MENA — broad visibility for all sales representatives.
          </p>
        </div>
        <button
          onClick={() => fetchCompanies(1, false)}
          className="btn btn-ghost btn-sm"
          title="Refresh companies"
        >
          <RefreshCw size={14} />
        </button>
      </div>

      {/* Filter and Sorting Toolbar */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 'var(--space-3)',
          flexWrap: 'wrap',
        }}
      >
        <form onSubmit={handleSearchSubmit} style={{ display: 'flex', flex: 1, minWidth: '240px' }}>
          <div style={{ position: 'relative', width: '100%' }}>
            <Search
              size={16}
              style={{
                position: 'absolute',
                left: 'var(--space-3)',
                top: '50%',
                transform: 'translateY(-50%)',
                color: 'var(--neutral-400)',
              }}
            />
            <input
              type="text"
              className="form-input"
              style={{ paddingLeft: 'var(--space-8)' }}
              placeholder="Search companies by name, domain, industry..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
        </form>

        {/* Sorting */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <ArrowUpDown size={15} color="var(--neutral-500)" />
          <select
            className="form-select"
            style={{ width: '180px' }}
            value={`${sortBy}_${sortDir}`}
            onChange={(e) => {
              const val = e.target.value;
              const lastUnderscore = val.lastIndexOf('_');
              setSortBy(val.substring(0, lastUnderscore));
              setSortDir(val.substring(lastUnderscore + 1) as 'asc' | 'desc');
            }}
          >
            <option value="name_asc">Name (A → Z)</option>
            <option value="name_desc">Name (Z → A)</option>
            <option value="country_asc">Country (A → Z)</option>
            <option value="industry_asc">Industry</option>
            <option value="created_at_desc">Recently Created</option>
          </select>
        </div>

        {/* Country Filter */}
        <select
          className="form-select"
          style={{ width: '150px' }}
          value={countryFilter}
          onChange={(e) => setCountryFilter(e.target.value)}
        >
          <option value="">All Countries</option>
          <option value="Saudi Arabia">Saudi Arabia</option>
          <option value="United Arab Emirates">UAE</option>
          <option value="Qatar">Qatar</option>
          <option value="Jordan">Jordan</option>
          <option value="Oman">Oman</option>
          <option value="Bahrain">Bahrain</option>
          <option value="Kuwait">Kuwait</option>
        </select>

        {/* Industry Filter */}
        <select
          className="form-select"
          style={{ width: '160px' }}
          value={industryFilter}
          onChange={(e) => setIndustryFilter(e.target.value)}
        >
          <option value="">All Industries</option>
          <option value="Banking">Banking</option>
          <option value="Financial Services">Financial Services</option>
          <option value="Telecom">Telecom</option>
          <option value="Technology">Technology</option>
          <option value="Government">Government</option>
          <option value="Oil & Gas">Oil & Gas</option>
        </select>

        {(search || countryFilter || industryFilter) && (
          <button
            onClick={() => {
              setSearch('');
              setCountryFilter('');
              setIndustryFilter('');
              setSortBy('name');
              setSortDir('asc');
            }}
            className="btn btn-secondary btn-sm"
          >
            Clear Filters
          </button>
        )}
      </div>

      {isLoading ? (
        <LoadingSpinner message="Loading enterprise accounts..." />
      ) : companies.length === 0 ? (
        <EmptyState title="No companies found" description="No accounts currently match your search criteria." />
      ) : (
        <>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 'var(--space-4)' }}>
            {companies.map((comp) => (
              <div
                key={comp.id}
                onClick={() => navigate(`/companies/${comp.id}`)}
                className="card"
                style={{
                  padding: 'var(--space-5)',
                  cursor: 'pointer',
                  transition: 'transform 0.15s ease, box-shadow 0.15s ease',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)', marginBottom: 'var(--space-3)' }}>
                  <div
                    style={{
                      width: '42px',
                      height: '42px',
                      borderRadius: 'var(--radius-lg)',
                      backgroundColor: 'var(--color-accent-light)',
                      color: 'var(--color-primary)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      flexShrink: 0,
                    }}
                  >
                    <Building2 size={22} />
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <h3 className="font-bold text-base text-dark" style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {comp.name}
                    </h3>
                    <span className="text-xs text-muted font-medium">{comp.industry || 'Enterprise'}</span>
                  </div>
                  <ArrowRight size={16} className="text-muted" />
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)', fontSize: 'var(--text-xs)', color: 'var(--neutral-600)' }}>
                  {comp.country && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-1)' }}>
                      <MapPin size={13} className="text-muted" />
                      <span>{comp.country}</span>
                    </div>
                  )}
                  {comp.website && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-1)' }}>
                      <Globe size={13} className="text-muted" />
                      <span style={{ color: 'var(--color-accent)' }}>
                        {comp.website.replace('https://', '').replace('http://', '')}
                      </span>
                    </div>
                  )}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 'var(--space-2)', paddingTop: 'var(--space-2)', borderTop: '1px solid var(--border-light)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                      <Users size={12} className="text-muted" />
                      <span className="text-xs text-muted">
                        {(comp as any).total_contacts ?? 0} contacts
                      </span>
                    </div>
                    <span className="text-xs font-semibold" style={{ color: 'var(--color-primary)' }}>
                      View Details →
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Pagination footer */}
          {companies.length < total && (
            <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 'var(--space-3)', paddingTop: 'var(--space-4)' }}>
              <span className="text-xs text-muted">
                Showing {companies.length} of {total} companies
              </span>
              <button
                onClick={handleLoadMore}
                disabled={isLoadingMore}
                className="btn btn-secondary btn-sm"
                style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
              >
                {isLoadingMore ? <RefreshCw size={13} className="spinning" /> : <ChevronDown size={13} />}
                {isLoadingMore ? 'Loading...' : 'Load More'}
              </button>
              {total > PER_PAGE && (
                <button
                  onClick={handleLoadAll}
                  className="btn btn-ghost btn-sm text-xs"
                >
                  Load All ({total})
                </button>
              )}
            </div>
          )}
          {companies.length >= total && total > 0 && (
            <div style={{ textAlign: 'center' }}>
              <span className="text-xs text-muted">All {total} companies loaded</span>
            </div>
          )}
        </>
      )}
    </div>
  );
};

