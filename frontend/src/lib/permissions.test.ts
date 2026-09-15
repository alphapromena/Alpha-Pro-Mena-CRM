import { describe, it, expect } from 'vitest';
import {
  normalizeUserRole,
  canViewUserDirectory,
  isManagerOrAbove,
  canManageTeam,
  isDataOps,
} from './permissions';

describe('Role Normalization & Permissions', () => {
  it('normalizes canonical and legacy aliases correctly', () => {
    expect(normalizeUserRole('ADMIN')).toBe('TEAM_LEAD');
    expect(normalizeUserRole('TEAM_LEADER')).toBe('TEAM_LEAD');
    expect(normalizeUserRole('TEAM_LEAD')).toBe('TEAM_LEAD');
    expect(normalizeUserRole('MANAGER')).toBe('MANAGER');
    expect(normalizeUserRole('USER')).toBe('USER');
    expect(normalizeUserRole('SALES_USER')).toBe('USER');
    expect(normalizeUserRole('DATA_OPS')).toBe('DATA_OPS');
    expect(normalizeUserRole(null)).toBe('USER');
    expect(normalizeUserRole(undefined)).toBe('USER');
  });

  it('restricts user directory (/api/v1/users) access strictly to managers and team leads', () => {
    // Authorized roles
    expect(canViewUserDirectory('MANAGER')).toBe(true);
    expect(canViewUserDirectory('TEAM_LEAD')).toBe(true);
    expect(canViewUserDirectory('ADMIN')).toBe(true);
    expect(canViewUserDirectory('TEAM_LEADER')).toBe(true);

    // Restricted roles
    expect(canViewUserDirectory('USER')).toBe(false);
    expect(canViewUserDirectory('SALES_USER')).toBe(false);
    expect(canViewUserDirectory('DATA_OPS')).toBe(false);
    expect(canViewUserDirectory(null)).toBe(false);
    expect(canViewUserDirectory(undefined)).toBe(false);
  });

  it('correctly reports manager or above privileges', () => {
    expect(isManagerOrAbove('MANAGER')).toBe(true);
    expect(isManagerOrAbove('TEAM_LEAD')).toBe(true);
    expect(isManagerOrAbove('USER')).toBe(false);
    expect(isManagerOrAbove('SALES_USER')).toBe(false);
    expect(isManagerOrAbove('DATA_OPS')).toBe(false);
  });

  it('identifies DATA_OPS role exclusively', () => {
    expect(isDataOps('DATA_OPS')).toBe(true);
    expect(isDataOps('USER')).toBe(false);
    expect(isDataOps('MANAGER')).toBe(false);
    expect(isDataOps('TEAM_LEAD')).toBe(false);
  });
});
