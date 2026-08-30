import React from 'react';
import { ContactStatus } from '../../types';

interface BadgeProps {
  status?: ContactStatus | string;
  variant?: 'success' | 'warning' | 'error' | 'accent' | 'secondary' | string;
  className?: string;
  children?: React.ReactNode;
}

export const Badge: React.FC<BadgeProps> = ({ status, variant, className = '', children }) => {
  const getBadgeClass = (s?: string, v?: string) => {
    if (v) {
      switch (v) {
        case 'success':
          return 'badge-won';
        case 'warning':
          return 'badge-noanswer';
        case 'error':
          return 'badge-lost';
        case 'accent':
          return 'badge-interested';
        case 'secondary':
          return 'badge-new';
        default:
          return 'badge-new';
      }
    }

    if (!s) return 'badge-new';

    switch (s) {
      case 'NEW':
      case 'UNASSIGNED':
        return 'badge-new';
      case 'INTERESTED':
      case 'QUALIFIED':
        return 'badge-interested';
      case 'IN_PROGRESS':
      case 'CONTACTED':
        return 'badge-inprogress';
      case 'DEMO_SCHEDULED':
      case 'DEMO_DONE':
      case 'DEMO':
        return 'badge-demo';
      case 'PROPOSAL_SENT':
      case 'PROPOSAL':
      case 'NEGOTIATION':
        return 'badge-proposal';
      case 'WON':
      case 'COMPLETED':
      case 'ACTIVE':
        return 'badge-won';
      case 'LOST':
      case 'CANCELLED':
      case 'NOT_INTERESTED':
        return 'badge-lost';
      case 'DO_NOT_CONTACT':
        return 'badge-dnc';
      case 'NO_ANSWER':
      case 'OVERDUE':
      case 'RECALL_SCHEDULED':
        return 'badge-noanswer';
      default:
        return 'badge-new';
    }
  };

  const formatText = (s?: string) => {
    return s ? s.replace(/_/g, ' ') : '';
  };

  return (
    <span className={`badge ${getBadgeClass(status, variant)} ${className}`}>
      {children || (status ? formatText(status) : '')}
    </span>
  );
};
