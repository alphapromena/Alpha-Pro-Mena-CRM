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
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [sortBy, setSortBy] = useState('name');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc');
  const [countryFilter, setCountryFilter] = useState('');
  const [industryFilter, setIndustryFilter] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  // Paging is driven by how many records are on screen, never by a page number,
  // because Load More and Load All used different page sizes and a page number
  // means nothing unless you also know which size produced it.
  const [loadedCount, setLoadedCount] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  const PER_PAGE = 50;

  // Debounce search input (300ms)
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(search);
    }, 300);
    return () => clearTimeout(timer);
  }, [search]);

  const fetchCompanies = useCallback(async (targetPage: number = 1, append: boolean = false) => {
    if (append) setIsLoadingMore(true);
    else setIsLoading(true);

    try {
      const res = await api.get<any>('/companies', {
        page: targetPage,
        per_page: PER_PAGE,
        search: debouncedSearch.trim() || undefined,
        sort_by: sortBy,
        sort_dir: sortDir,
        country: countryFilter || undefined,
        industry: industryFilter || undefined,
      });

      const newItems: Company[] = res.data || [];
      const metaTotal = res.meta?.total || 0;
      let nextLoaded = newItems.length;
      if (append) {
        setCompanies((prev) => {
          const existingIds = new Set(prev.map((c) => c.id));
          const fresh = newItems.filter((c) => !existingIds.has(c.id));
          nextLoaded = prev.length + fresh.length;
          setLoadedCount(nextLoaded);
          return [...prev, ...fresh];
        });
      } else {
        setCompanies(newItems);
        setLoadedCount(newItems.length);
      }
      setTotal(metaTotal);
      setTotalPages(Math.max(1, Math.ceil(metaTotal / PER_PAGE)));
      setPage(targetPage);
      setHasMore(
        typeof res.meta?.has_more === 'boolean'
          ? res.meta.has_more
          : nextLoaded < metaTotal
      );
      setLoadError(null);
    } catch (e: any) {
      console.error('Failed to load companies', e);
      setLoadError(e?.message || 'Could not load companies. Please try again.');
    } finally {
      setIsLoading(false);
      setIsLoadingMore(false);
    }
  }, [debouncedSearch, sortBy, sortDir, countryFilter, industryFilter]);

  // Refetch from page 1 when search or any filter changes
  useEffect(() => {
    setPage(1);
    fetchCompanies(1, false);
  }, [debouncedSearch, sortBy, sortDir, countryFilter, industryFilter, fetchCompanies]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setDebouncedSearch(search);
  };

  const handleLoadMore = () => {
    // The next slice follows what is already on screen. Deriving the page number
    // from loadedCount keeps Load More and Load All on the same page size.
    if (hasMore && !isLoadingMore) {
      fetchCompanies(Math.floor(loadedCount / PER_PAGE) + 1, true);
    }
  };

  const handleLoadAll = async () => {
    if (isLoadingMore || !hasMore) return;
    setIsLoadingMore(true);
    setLoadError(null);
    try {
      // Previously this started at page + 1, where page counted PER_PAGE (50)
      // records, but requested per_page 100. With one page loaded it asked for
      // records 101-200 and silently skipped 51-100. Everything now walks in
      // PER_PAGE steps from the number of records actually held.
      let loaded = loadedCount;
      let more = true;
      const collected: Company[] = [];
      let guard = 0;

      while (more && guard < 500) {
        guard += 1;
        const res = await api.get<any>('/companies', {
          page: Math.floor(loaded / PER_PAGE) + 1,
          per_page: PER_PAGE,
          search: debouncedSearch.trim() || undefined,
          sort_by: sortBy,
          sort_dir: sortDir,
          country: countryFilter || undefined,
          industry: industryFilter || undefined,
        });
        const items: Company[] = res.data || [];
        if (items.length === 0) break;
        collected.push(...items);
        loaded += items.length;
        more =
          typeof res.meta?.has_more === 'boolean'
            ? res.meta.has_more
            : loaded < (res.meta?.total || 0);
        setLoadedCount(loaded);
      }

      setCompanies((prev) => {
        const existingIds = new Set(prev.map((c) => c.id));
        const fresh = collected.filter((c) => !existingIds.has(c.id));
        const merged = [...prev, ...fresh];
        setLoadedCount(merged.length);
        return merged;
      });
      setHasMore(more);
      setPage(Math.max(1, Math.ceil(loaded / PER_PAGE)));
    } catch (e: any) {
      console.error('Failed to load all companies', e);
      setLoadError(e?.message || 'Could not load all companies. Some may be missing.');
    } finally {
      setIsLoadingMore(false);
    }
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

          {/* A failed page must be visible, not silently missing rows. */}
          {loadError && (
            <div
              role="alert"
              style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                gap: 'var(--space-3)', padding: 'var(--space-3)',
                border: '1px solid #ef4444', borderRadius: 'var(--radius-md)',
                backgroundColor: 'rgba(239,68,68,0.08)', color: '#b91c1c',
                fontSize: '13px', marginTop: 'var(--space-3)',
              }}
            >
              <span>{loadError}</span>
              <button onClick={handleLoadMore} disabled={isLoadingMore} className="btn btn-secondary btn-sm">
                Retry
              </button>
            </div>
          )}

          {/* Pagination footer */}
          {hasMore && (
            <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 'var(--space-3)', paddingTop: 'var(--space-4)' }}>
              <span className="text-xs text-muted">
                Showing {companies.length} of {total} companies
              </span>
              <button
                onClick={handleLoadMore}
                disabled={isLoadingMore || !hasMore}
                className="btn btn-secondary btn-sm"
                style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
              >
                {isLoadingMore ? <RefreshCw size={13} className="spinning" /> : <ChevronDown size={13} />}
                {isLoadingMore ? 'Loading...' : 'Load More'}
              </button>
              {total > PER_PAGE && (
                <button
                  onClick={handleLoadAll}
                  disabled={isLoadingMore || !hasMore}
                  className="btn btn-ghost btn-sm text-xs"
                >
                  Load All ({total})
                </button>
              )}
            </div>
          )}
          {!hasMore && total > 0 && (
            <div style={{ textAlign: 'center' }}>
              <span className="text-xs text-muted">All {total} companies loaded</span>
            </div>
          )}
        </>
      )}
    </div>
  );
};

