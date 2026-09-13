/**
 * AsyncContactSelector — searchable, async, drag-and-drop-enabled contact picker.
 *
 * Features:
 * - Debounced server-side search via GET /contacts/selector
 * - Displays: Company — Contact Name · Phone
 * - Drag a result item into the drop zone to select
 * - Keyboard navigation (ArrowUp, ArrowDown, Enter, Escape)
 * - Stale-response prevention via sequence counter
 * - Filters contacts to a given company if company_id is provided
 * - Persists selected value across rerenders
 * - Arabic + English text support
 */
import React, { useState, useEffect, useRef, useCallback } from 'react';
import { api } from '../../lib/apiClient';
import { Search, X, GripVertical, User } from 'lucide-react';

export interface ContactSelectorItem {
  id: string;
  full_name: string;
  phone?: string | null;
  email?: string | null;
  company_id?: string | null;
  company_name?: string | null;
  display: string;
}

interface Props {
  /** Currently selected contact id */
  value: string;
  /** Called when selection changes with the selected item (or null to clear) */
  onChange: (item: ContactSelectorItem | null) => void;
  /** Optional filter: restrict search results to this company */
  companyId?: string;
  /** Placeholder text */
  placeholder?: string;
  /** Whether this field is required */
  required?: boolean;
  /** Whether the selector is disabled */
  disabled?: boolean;
  /** Label for accessibility */
  label?: string;
  /** Initially selected item object (used to display label without a separate API call) */
  initialItem?: ContactSelectorItem | null;
}

const DEBOUNCE_MS = 280;

export const AsyncContactSelector: React.FC<Props> = ({
  value,
  onChange,
  companyId,
  placeholder = 'Search by name, phone, email, or company...',
  required = false,
  disabled = false,
  label,
  initialItem,
}) => {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<ContactSelectorItem[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const [selectedItem, setSelectedItem] = useState<ContactSelectorItem | null>(initialItem || null);
  const [isDragOver, setIsDragOver] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const seqRef = useRef(0);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLUListElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // If value is cleared externally, clear selected item
  useEffect(() => {
    if (!value) {
      setSelectedItem(null);
      setQuery('');
    }
  }, [value]);

  // Re-sync initialItem when it changes (e.g. editing an existing record)
  useEffect(() => {
    if (initialItem && initialItem.id === value) {
      setSelectedItem(initialItem);
    }
  }, [initialItem, value]);

  const search = useCallback(async (q: string, cId?: string) => {
    const seq = ++seqRef.current;
    if (!q.trim() && !cId) {
      setResults([]);
      setIsLoading(false);
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      const params: Record<string, any> = { per_page: 20 };
      if (q.trim()) params.search = q.trim();
      if (cId) params.company_id = cId;
      const res = await api.get<any>('/contacts/selector', params);
      // Stale response guard
      if (seq !== seqRef.current) return;
      setResults(res.data || []);
      setActiveIndex(-1);
    } catch (e: any) {
      if (seq !== seqRef.current) return;
      setError('Failed to load contacts');
      setResults([]);
    } finally {
      if (seq === seqRef.current) setIsLoading(false);
    }
  }, []);

  // Debounced search on query change
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      if (isOpen) search(query, companyId);
    }, DEBOUNCE_MS);
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, [query, companyId, isOpen, search]);

  // When company changes, clear query and current selection if it doesn't belong to new company
  useEffect(() => {
    if (companyId && selectedItem && selectedItem.company_id !== companyId) {
      setSelectedItem(null);
      onChange(null);
      setQuery('');
    }
    // If dropdown is open, re-run search with new company filter
    if (isOpen) search(query, companyId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [companyId]);

  const handleOpen = () => {
    if (disabled) return;
    setIsOpen(true);
    // Load initial results when opening (show contacts for this company or top matches)
    search(query, companyId);
    setTimeout(() => inputRef.current?.focus(), 50);
  };

  const handleSelect = (item: ContactSelectorItem) => {
    setSelectedItem(item);
    setQuery('');
    setIsOpen(false);
    setResults([]);
    onChange(item);
  };

  const handleClear = (e: React.MouseEvent) => {
    e.stopPropagation();
    setSelectedItem(null);
    setQuery('');
    setResults([]);
    onChange(null);
    setIsOpen(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!isOpen) {
      if (e.key === 'Enter' || e.key === ' ' || e.key === 'ArrowDown') {
        e.preventDefault();
        handleOpen();
      }
      return;
    }
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActiveIndex((i) => Math.min(i + 1, results.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActiveIndex((i) => Math.max(i - 1, 0));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (activeIndex >= 0 && results[activeIndex]) {
        handleSelect(results[activeIndex]);
      }
    } else if (e.key === 'Escape') {
      setIsOpen(false);
      setResults([]);
    }
  };

  // Close on outside click
  useEffect(() => {
    const handleOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleOutside);
    return () => document.removeEventListener('mousedown', handleOutside);
  }, []);

  // Scroll active item into view
  useEffect(() => {
    if (activeIndex >= 0 && listRef.current) {
      const li = listRef.current.children[activeIndex] as HTMLElement;
      li?.scrollIntoView({ block: 'nearest' });
    }
  }, [activeIndex]);

  // ── Drag-and-Drop ──────────────────────────────────────────────────────
  const handleDragStart = (e: React.DragEvent, item: ContactSelectorItem) => {
    e.dataTransfer.setData('application/x-contact-selector', JSON.stringify(item));
    e.dataTransfer.effectAllowed = 'copy';
  };

  const handleDropZoneDragOver = (e: React.DragEvent) => {
    if (disabled) return;
    if (e.dataTransfer.types.includes('application/x-contact-selector')) {
      e.preventDefault();
      e.dataTransfer.dropEffect = 'copy';
      setIsDragOver(true);
    }
  };

  const handleDropZoneDragLeave = () => setIsDragOver(false);

  const handleDropZoneDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    if (disabled) return;
    try {
      const raw = e.dataTransfer.getData('application/x-contact-selector');
      if (!raw) return;
      const item: ContactSelectorItem = JSON.parse(raw);
      // Validate company match if a company filter is active
      if (companyId && item.company_id && item.company_id !== companyId) {
        // Contact doesn't belong to the selected company — reject
        return;
      }
      if (!item.id) return;
      handleSelect(item);
    } catch {
      // Malformed drag data — ignore
    }
  };

  return (
    <div ref={containerRef} style={{ position: 'relative', width: '100%' }}>
      {/* ── Drop zone / selection display ─────────────────────────── */}
      <div
        role="combobox"
        aria-expanded={isOpen}
        aria-haspopup="listbox"
        aria-label={label || 'Contact selector'}
        tabIndex={disabled ? -1 : 0}
        onClick={selectedItem ? undefined : handleOpen}
        onKeyDown={handleKeyDown}
        onDragOver={handleDropZoneDragOver}
        onDragLeave={handleDropZoneDragLeave}
        onDrop={handleDropZoneDrop}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          padding: '8px 12px',
          borderRadius: 'var(--radius-md)',
          border: isDragOver
            ? '2px dashed var(--color-accent)'
            : selectedItem
            ? '1px solid var(--color-accent)'
            : '1px solid var(--border-color)',
          backgroundColor: isDragOver
            ? 'var(--color-accent-light)'
            : 'var(--bg-surface)',
          cursor: disabled ? 'not-allowed' : selectedItem ? 'default' : 'pointer',
          minHeight: '40px',
          transition: 'border-color 0.15s, background 0.15s',
          opacity: disabled ? 0.6 : 1,
        }}
      >
        {selectedItem ? (
          <>
            <User size={14} style={{ color: 'var(--color-accent)', flexShrink: 0 }} />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div
                style={{
                  fontSize: '13px',
                  fontWeight: 600,
                  color: 'var(--neutral-900)',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}
              >
                {selectedItem.full_name}
              </div>
              {(selectedItem.company_name || selectedItem.phone) && (
                <div
                  style={{
                    fontSize: '11px',
                    color: 'var(--neutral-500)',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {[selectedItem.company_name, selectedItem.phone].filter(Boolean).join(' · ')}
                </div>
              )}
            </div>
            {!disabled && (
              <button
                type="button"
                onClick={handleClear}
                style={{
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  color: 'var(--neutral-400)',
                  padding: '2px',
                  display: 'flex',
                  alignItems: 'center',
                  flexShrink: 0,
                }}
                title="Clear selection"
              >
                <X size={14} />
              </button>
            )}
          </>
        ) : (
          <>
            <Search size={14} style={{ color: 'var(--neutral-400)', flexShrink: 0 }} />
            <span style={{ fontSize: '13px', color: 'var(--neutral-400)', flex: 1 }}>
              {isDragOver ? '📌 Drop contact here' : placeholder}
            </span>
            {required && (
              <span style={{ color: 'var(--color-danger)', fontSize: '12px' }}>*</span>
            )}
          </>
        )}
      </div>

      {/* ── Search input (shown when open) ────────────────────────── */}
      {isOpen && (
        <div
          style={{
            position: 'absolute',
            top: '100%',
            left: 0,
            right: 0,
            zIndex: 1000,
            backgroundColor: 'var(--bg-surface)',
            border: '1px solid var(--border-color)',
            borderRadius: 'var(--radius-md)',
            boxShadow: 'var(--shadow-lg)',
            marginTop: '4px',
            overflow: 'hidden',
          }}
        >
          {/* Search input */}
          <div
            style={{
              padding: '8px',
              borderBottom: '1px solid var(--border-light)',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
            }}
          >
            <Search size={14} style={{ color: 'var(--neutral-400)', flexShrink: 0 }} />
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={placeholder}
              style={{
                flex: 1,
                border: 'none',
                outline: 'none',
                fontSize: '13px',
                backgroundColor: 'transparent',
                color: 'var(--neutral-900)',
              }}
              dir="auto"
            />
            {isLoading && (
              <span style={{ fontSize: '11px', color: 'var(--neutral-400)' }}>…</span>
            )}
            <button
              type="button"
              onClick={() => setIsOpen(false)}
              style={{
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                color: 'var(--neutral-400)',
                padding: '2px',
              }}
            >
              <X size={13} />
            </button>
          </div>

          {/* Results list */}
          <ul
            ref={listRef}
            role="listbox"
            style={{
              listStyle: 'none',
              margin: 0,
              padding: '4px 0',
              maxHeight: '260px',
              overflowY: 'auto',
            }}
          >
            {error ? (
              <li style={{ padding: '10px 12px', fontSize: '12px', color: 'var(--color-danger)' }}>
                {error}
              </li>
            ) : results.length === 0 && !isLoading ? (
              <li style={{ padding: '10px 12px', fontSize: '12px', color: 'var(--neutral-400)', fontStyle: 'italic' }}>
                {query.trim() ? 'No contacts match your search.' : 'Type to search contacts…'}
              </li>
            ) : (
              results.map((item, idx) => (
                <li
                  key={item.id}
                  role="option"
                  aria-selected={idx === activeIndex}
                  draggable
                  onDragStart={(e) => handleDragStart(e, item)}
                  onClick={() => handleSelect(item)}
                  onMouseEnter={() => setActiveIndex(idx)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    padding: '8px 12px',
                    cursor: 'pointer',
                    backgroundColor:
                      idx === activeIndex ? 'var(--color-accent-light)' : 'transparent',
                    borderLeft:
                      idx === activeIndex
                        ? '3px solid var(--color-accent)'
                        : '3px solid transparent',
                    transition: 'background 0.1s',
                  }}
                >
                  <span title="Drag to select">
                    <GripVertical
                      size={12}
                      style={{ color: 'var(--neutral-300)', flexShrink: 0, cursor: 'grab' }}
                    />
                  </span>
                  <User size={13} style={{ color: 'var(--neutral-400)', flexShrink: 0 }} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div
                      style={{
                        fontSize: '13px',
                        fontWeight: 600,
                        color: 'var(--neutral-900)',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {item.full_name}
                    </div>
                    <div
                      style={{
                        fontSize: '11px',
                        color: 'var(--neutral-500)',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {[item.company_name, item.phone].filter(Boolean).join(' · ')}
                    </div>
                  </div>
                </li>
              ))
            )}
          </ul>

          {/* Drag hint */}
          {results.length > 0 && (
            <div
              style={{
                padding: '6px 12px',
                borderTop: '1px solid var(--border-light)',
                fontSize: '10px',
                color: 'var(--neutral-400)',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
              }}
            >
              <GripVertical size={10} />
              <span>Drag a result to the field above, or click to select</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
