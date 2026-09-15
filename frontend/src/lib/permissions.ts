/**
 * Centralized, type-safe role and permission helpers.
 *
 * Canonical Backend Roles:
 * - USER (Legacy alias: SALES_USER)
 * - TEAM_LEAD (Legacy aliases: ADMIN, TEAM_LEADER)
 * - MANAGER
 * - DATA_OPS
 */

import { CanonicalUserRole, UserRole } from '../types';

/**
 * Normalizes any role (including legacy aliases) to the backend canonical UserRole.
 */
export function normalizeUserRole(role?: string | null): CanonicalUserRole {
  if (!role) return 'USER';
  const upper = role.toUpperCase();
  if (upper === 'ADMIN' || upper === 'TEAM_LEADER' || upper === 'TEAM_LEAD') {
    return 'TEAM_LEAD';
  }
  if (upper === 'MANAGER') {
    return 'MANAGER';
  }
  if (upper === 'DATA_OPS') {
    return 'DATA_OPS';
  }
  return 'USER';
}

/**
 * Returns true if the user role is authorized to view the user directory (/api/v1/users).
 * Backend endpoint requires `require_manager_or_above` (TEAM_LEAD, MANAGER).
 * Regular USER, SALES_USER, and DATA_OPS return false.
 */
export function canViewUserDirectory(role?: UserRole | string | null): boolean {
  const canonical = normalizeUserRole(role);
  return canonical === 'TEAM_LEAD' || canonical === 'MANAGER';
}

/**
 * Returns true if the user role is Manager or above (TEAM_LEAD or MANAGER).
 */
export function isManagerOrAbove(role?: UserRole | string | null): boolean {
  return canViewUserDirectory(role);
}

/**
 * Returns true if the user role can manage teams and distribute leads.
 */
export function canManageTeam(role?: UserRole | string | null): boolean {
  return canViewUserDirectory(role);
}

/**
 * Returns true if the user is a dedicated Data Operations user.
 */
export function isDataOps(role?: UserRole | string | null): boolean {
  return normalizeUserRole(role) === 'DATA_OPS';
}
