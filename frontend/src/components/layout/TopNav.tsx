import React, { useState, useEffect, useRef } from 'react';
import { Search, Bell, LogOut, Plus, CheckCircle2, AlertCircle, Palette, Globe } from 'lucide-react';
import { useAuthStore } from '../../store/authStore';
import { api } from '../../lib/apiClient';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from '../../i18n';

export const TopNav: React.FC = () => {
  const { user, theme, setTheme, language, setLanguage, logout } = useAuthStore();
  const { t, isRTL } = useTranslation();
  const navigate = useNavigate();

  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<any>(null);
  const [isSearching, setIsSearching] = useState(false);
  const [showSearchDropdown, setShowSearchDropdown] = useState(false);

  const [unreadCount, setUnreadCount] = useState(0);
  const [notifications, setNotifications] = useState<any[]>([]);
  const [showNotifDropdown, setShowNotifDropdown] = useState(false);

  const searchRef = useRef<HTMLDivElement>(null);
  const notifRef = useRef<HTMLDivElement>(null);

  // Poll notifications
  const fetchNotifications = async () => {
    try {
      const res = await api.get<any>('/notifications', { per_page: 5 });
      setNotifications(res.data || []);
      setUnreadCount(res.meta?.unread_count || 0);
    } catch (e) {
      console.error('Failed to load notifications', e);
    }
  };

  useEffect(() => {
    fetchNotifications();
    const interval = setInterval(fetchNotifications, 60000);
    return () => clearInterval(interval);
  }, []);

  // Debounced search
  useEffect(() => {
    if (!searchQuery.trim()) {
      setSearchResults(null);
      setShowSearchDropdown(false);
      return;
    }
    const timer = setTimeout(async () => {
      setIsSearching(true);
      try {
        const res = await api.get<any>('/search', { q: searchQuery.trim() });
        setSearchResults(res.data);
        setShowSearchDropdown(true);
      } catch (e) {
        console.error('Search error', e);
      } finally {
        setIsSearching(false);
      }
    }, 250);

    return () => clearTimeout(timer);
  }, [searchQuery]);

  // Click outside listener
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (searchRef.current && !searchRef.current.contains(e.target as Node)) {
        setShowSearchDropdown(false);
      }
      if (notifRef.current && !notifRef.current.contains(e.target as Node)) {
        setShowNotifDropdown(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return (
    <header className="app-header">
      {/* Global Search Bar */}
      <div ref={searchRef} style={{ position: 'relative', width: '380px' }}>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            backgroundColor: 'var(--neutral-100)',
            borderRadius: 'var(--radius-lg)',
            padding: '0 var(--space-3)',
            height: '38px',
            border: '1px solid var(--neutral-200)',
          }}
        >
          <Search size={17} style={{ color: 'var(--neutral-400)', marginRight: isRTL ? 0 : 'var(--space-2)', marginLeft: isRTL ? 'var(--space-2)' : 0 }} />
          <input
            type="text"
            placeholder={isRTL ? "بحث في جهات الاتصال، الشركات، الفرص..." : "Search contacts, companies, opportunities..."}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onFocus={() => {
              if (searchResults) setShowSearchDropdown(true);
            }}
            style={{
              border: 'none',
              background: 'transparent',
              outline: 'none',
              width: '100%',
              fontSize: 'var(--text-sm)',
              color: 'var(--neutral-900)',
            }}
          />
        </div>

        {/* Search Results Dropdown */}
        {showSearchDropdown && searchResults && (
          <div
            style={{
              position: 'absolute',
              top: '46px',
              left: 0,
              right: 0,
              backgroundColor: 'var(--bg-surface)',
              borderRadius: 'var(--radius-xl)',
              boxShadow: 'var(--shadow-xl)',
              border: '1px solid var(--border-color)',
              maxHeight: '400px',
              overflowY: 'auto',
              zIndex: 50,
              padding: 'var(--space-2)',
            }}
          >
            {searchResults.contacts?.length > 0 && (
              <div>
                <div style={{ fontSize: '11px', fontWeight: 700, color: 'var(--neutral-500)', padding: 'var(--space-2) var(--space-3)' }}>
                  CONTACTS
                </div>
                {searchResults.contacts.map((c: any) => (
                  <div
                    key={c.id}
                    onClick={() => {
                      setShowSearchDropdown(false);
                      setSearchQuery('');
                      navigate(`/contacts/${c.id}`);
                    }}
                    style={{
                      padding: 'var(--space-2) var(--space-3)',
                      borderRadius: 'var(--radius-md)',
                      cursor: 'pointer',
                      fontSize: 'var(--text-sm)',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = 'var(--bg-subtle)')}
                    onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
                  >
                    <div>
                      <span className="font-semibold">{c.full_name}</span>
                      {c.company_name && <span className="text-muted text-xs"> — {c.company_name}</span>}
                    </div>
                    <span className="text-xs text-muted">{c.status}</span>
                  </div>
                ))}
              </div>
            )}

            {searchResults.companies?.length > 0 && (
              <div style={{ marginTop: 'var(--space-2)' }}>
                <div style={{ fontSize: '11px', fontWeight: 700, color: 'var(--neutral-500)', padding: 'var(--space-2) var(--space-3)' }}>
                  COMPANIES
                </div>
                {searchResults.companies.map((comp: any) => (
                  <div
                    key={comp.id}
                    onClick={() => {
                      setShowSearchDropdown(false);
                      setSearchQuery('');
                      navigate(`/companies/${comp.id}`);
                    }}
                    style={{
                      padding: 'var(--space-2) var(--space-3)',
                      borderRadius: 'var(--radius-md)',
                      cursor: 'pointer',
                      fontSize: 'var(--text-sm)',
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = 'var(--bg-subtle)')}
                    onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
                  >
                    <span className="font-semibold">{comp.name}</span>
                    {comp.industry && <span className="text-muted text-xs"> ({comp.industry})</span>}
                  </div>
                ))}
              </div>
            )}

            {searchResults.contacts?.length === 0 && searchResults.companies?.length === 0 && (
              <div style={{ padding: 'var(--space-4)', textAlign: 'center', color: 'var(--neutral-500)', fontSize: 'var(--text-sm)' }}>
                No matching results found.
              </div>
            )}
          </div>
        )}
      </div>

      {/* Right Controls */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-4)' }}>
        {/* Notifications Icon & Dropdown */}
        <div ref={notifRef} style={{ position: 'relative' }}>
          <button
            onClick={() => setShowNotifDropdown(!showNotifDropdown)}
            style={{
              position: 'relative',
              width: '38px',
              height: '38px',
              borderRadius: 'var(--radius-md)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              backgroundColor: 'var(--neutral-100)',
              color: 'var(--neutral-700)',
            }}
          >
            <Bell size={18} />
            {unreadCount > 0 && (
              <span
                style={{
                  position: 'absolute',
                  top: '6px',
                  right: '6px',
                  width: '8px',
                  height: '8px',
                  borderRadius: 'var(--radius-full)',
                  backgroundColor: 'var(--color-danger)',
                }}
              />
            )}
          </button>

          {showNotifDropdown && (
            <div
              style={{
                position: 'absolute',
                top: '46px',
                right: 0,
                width: '320px',
                backgroundColor: 'var(--bg-surface)',
                borderRadius: 'var(--radius-xl)',
                boxShadow: 'var(--shadow-xl)',
                border: '1px solid var(--border-color)',
                zIndex: 50,
                overflow: 'hidden',
              }}
            >
              <div
                style={{
                  padding: 'var(--space-3) var(--space-4)',
                  borderBottom: '1px solid var(--border-color)',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                }}
              >
                <span className="font-semibold text-sm">Notifications ({unreadCount})</span>
                <button
                  onClick={async () => {
                    await api.post('/notifications/read-all');
                    setUnreadCount(0);
                    fetchNotifications();
                  }}
                  className="text-xs text-accent font-medium"
                >
                  Mark all read
                </button>
              </div>
              <div style={{ maxHeight: '280px', overflowY: 'auto' }}>
                {notifications.length === 0 ? (
                  <div style={{ padding: 'var(--space-6)', textAlign: 'center', color: 'var(--neutral-400)', fontSize: 'var(--text-xs)' }}>
                    No notifications
                  </div>
                ) : (
                  notifications.map((n) => (
                    <div
                      key={n.id}
                      style={{
                        padding: 'var(--space-3) var(--space-4)',
                        borderBottom: '1px solid var(--border-light)',
                        backgroundColor: n.is_read ? 'transparent' : 'var(--color-primary-subtle)',
                        fontSize: 'var(--text-xs)',
                      }}
                    >
                      <div className="font-semibold" style={{ color: 'var(--neutral-900)' }}>
                        {n.title}
                      </div>
                      <div className="text-muted" style={{ marginTop: '2px' }}>
                        {n.message}
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          )}
        </div>

        {/* Language Selector Dropdown */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <Globe size={16} style={{ color: 'var(--neutral-500)' }} />
          <select
            value={language}
            onChange={(e) => setLanguage(e.target.value as 'en' | 'ar')}
            className="form-select text-xs"
            style={{
              height: '34px',
              padding: '2px 8px',
              fontSize: '12px',
              fontWeight: '600',
              backgroundColor: 'var(--bg-surface)',
              color: 'var(--neutral-900)',
              borderColor: 'var(--border-color)',
              borderRadius: 'var(--radius-md)',
            }}
          >
            <option value="en">🇬🇧 English</option>
            <option value="ar">🇸🇦 العربية</option>
          </select>
        </div>

        {/* Theme Selector Dropdown */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <Palette size={16} style={{ color: 'var(--neutral-500)' }} />
          <select
            value={theme}
            onChange={(e) => setTheme(e.target.value)}
            className="form-select text-xs"
            style={{
              height: '34px',
              padding: '2px 8px',
              fontSize: '12px',
              fontWeight: '600',
              backgroundColor: 'var(--bg-surface)',
              color: 'var(--neutral-900)',
              borderColor: 'var(--border-color)',
              borderRadius: 'var(--radius-md)',
            }}
          >
            <option value="black_beige">{isRTL ? "السمة: الأسود والبيج الفاخر" : "Theme: Black & Beige"}</option>
            <option value="alpha_pro">{isRTL ? "السمة: ألفا برو مينا" : "Theme: Alpha Pro MENA"}</option>
            <option value="pro_light">{isRTL ? "السمة: الفاتح الاحترافي" : "Theme: Professional Light"}</option>
            <option value="pro_dark">{isRTL ? "السمة: الداكن الاحترافي" : "Theme: Professional Dark"}</option>
          </select>
        </div>

        {/* Quick Add Contact Button */}
        <button
          onClick={() => navigate('/contacts?action=new')}
          className="btn btn-accent btn-sm"
        >
          <Plus size={16} />
          <span>{isRTL ? "إضافة عميل" : "New Contact"}</span>
        </button>

        {/* Logout Button */}
        <button
          onClick={logout}
          title={isRTL ? "تسجيل الخروج" : "Sign out"}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 'var(--space-1)',
            padding: 'var(--space-2) var(--space-3)',
            borderRadius: 'var(--radius-md)',
            color: 'var(--neutral-600)',
            fontSize: 'var(--text-xs)',
            fontWeight: 500,
          }}
          onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = 'var(--neutral-100)')}
          onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
        >
          <LogOut size={16} />
          <span>{isRTL ? "خروج" : "Logout"}</span>
        </button>
      </div>
    </header>
  );
};
