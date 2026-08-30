import React from 'react';
import { Inbox } from 'lucide-react';

interface EmptyStateProps {
  title?: string;
  description?: string;
  icon?: React.ReactNode;
  action?: React.ReactNode;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  title = 'No records found',
  description = 'There are currently no items matching your criteria.',
  icon,
  action,
}) => {
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 'var(--space-12) var(--space-6)',
        textAlign: 'center',
        backgroundColor: 'var(--bg-surface)',
        borderRadius: 'var(--radius-xl)',
        border: '1px dashed var(--neutral-300)',
      }}
    >
      <div
        style={{
          width: '56px',
          height: '56px',
          borderRadius: 'var(--radius-full)',
          backgroundColor: 'var(--color-primary-subtle)',
          color: 'var(--color-primary)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          marginBottom: 'var(--space-4)',
        }}
      >
        {icon || <Inbox size={28} />}
      </div>
      <h4
        className="font-display font-semibold text-lg"
        style={{ color: 'var(--neutral-800)', marginBottom: 'var(--space-1)' }}
      >
        {title}
      </h4>
      <p
        className="text-sm text-muted"
        style={{ maxWidth: '380px', marginBottom: action ? 'var(--space-5)' : 0 }}
      >
        {description}
      </p>
      {action && <div>{action}</div>}
    </div>
  );
};
