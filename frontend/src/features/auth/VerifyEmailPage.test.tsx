import React from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Routes, Route } from 'react-router-dom';

import { VerifyEmailPage } from './VerifyEmailPage';
import { useAuthStore } from '../../store/authStore';
import { api } from '../../lib/apiClient';

vi.mock('../../lib/apiClient', async () => {
  const actual = await vi.importActual<typeof import('../../lib/apiClient')>('../../lib/apiClient');
  return {
    ...actual,
    api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
  };
});

const SIGNED_IN_EMAIL = 'staffer@alphapromena.com';

function setUser(email: string | null) {
  // Wrapped in act: a store write re-renders subscribed components, and React warns
  // about state updates made outside act during a test.
  act(() => {
    useAuthStore.setState({
      user: email
        ? ({ id: 'u1', email, first_name: 'Staff', email_verified: false } as any)
        : null,
      isAuthenticated: Boolean(email),
      isLoading: false,
    });
  });
}

/** Render at /verify-email with optional router state, as LoginPage passes it. */
function renderPage(state?: { verificationSent?: boolean; email?: string }, search = '') {
  return render(
    <MemoryRouter initialEntries={[{ pathname: '/verify-email', search, state }]}>
      <Routes>
        <Route path="/verify-email" element={<VerifyEmailPage />} />
      </Routes>
    </MemoryRouter>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.useFakeTimers({ shouldAdvanceTime: true });
  useAuthStore.setState({ fetchMe: vi.fn() as any });
});

afterEach(() => {
  vi.useRealTimers();
  setUser(null);
});

describe('VerifyEmailPage', () => {
  it('never asks a signed-in user to type their address', () => {
    setUser(SIGNED_IN_EMAIL);
    renderPage();

    // The whole point of the fix: no email input for someone we already identify.
    expect(screen.queryByPlaceholderText('name@alphapromena.com')).not.toBeInTheDocument();
  });

  it('shows the address a code was just sent to', () => {
    setUser(SIGNED_IN_EMAIL);
    renderPage({ verificationSent: true, email: SIGNED_IN_EMAIL });

    expect(screen.getByText(/we sent a verification code to/i)).toBeInTheDocument();
    expect(screen.getByText(SIGNED_IN_EMAIL)).toBeInTheDocument();
  });

  it('does not claim a code was sent when login did not send one', () => {
    setUser(SIGNED_IN_EMAIL);
    renderPage({ verificationSent: false, email: SIGNED_IN_EMAIL });

    expect(screen.queryByText(/we sent a verification code to/i)).not.toBeInTheDocument();
  });

  it('starts the cooldown when login already dispatched a code', () => {
    setUser(SIGNED_IN_EMAIL);
    renderPage({ verificationSent: true, email: SIGNED_IN_EMAIL });

    // The button must not invite an immediate second request.
    expect(screen.getByRole('button', { name: /resend in \d+s/i })).toBeDisabled();
  });

  it('counts the cooldown down and re-enables the resend button', async () => {
    setUser(SIGNED_IN_EMAIL);
    renderPage({ verificationSent: true, email: SIGNED_IN_EMAIL });

    expect(screen.getByRole('button', { name: /resend in 60s/i })).toBeInTheDocument();

    await vi.advanceTimersByTimeAsync(59_000);
    expect(screen.getByRole('button', { name: /resend in 1s/i })).toBeInTheDocument();

    await vi.advanceTimersByTimeAsync(1_000);
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /resend verification code/i })).toBeEnabled()
    );
  });

  it('resends using the session address, with no typing required', async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    (api.post as any).mockResolvedValue({ message: 'sent' });
    setUser(SIGNED_IN_EMAIL);
    renderPage();

    await user.click(screen.getByRole('button', { name: /resend verification code/i }));

    await waitFor(() =>
      expect(api.post).toHaveBeenCalledWith('/auth/resend-verification', {
        email: SIGNED_IN_EMAIL,
      })
    );
  });

  it('offers an email field to an anonymous visitor', () => {
    setUser(null);
    renderPage();

    expect(screen.getByPlaceholderText('name@alphapromena.com')).toBeInTheDocument();
  });

  it('seeds the anonymous field from the emailed link', () => {
    setUser(null);
    renderPage(undefined, '?email=linked%40alphapromena.com');

    expect(screen.getByPlaceholderText('name@alphapromena.com')).toHaveValue(
      'linked@alphapromena.com'
    );
  });

  it('adopts the session address when /auth/me resolves after mount', async () => {
    setUser(null);
    (api.post as any).mockResolvedValue({ message: 'sent' });
    renderPage();

    // Anonymous first render shows the field.
    expect(screen.getByPlaceholderText('name@alphapromena.com')).toBeInTheDocument();

    // fetchMe lands a moment later, as it does in the real app.
    setUser(SIGNED_IN_EMAIL);

    await waitFor(() =>
      expect(screen.queryByPlaceholderText('name@alphapromena.com')).not.toBeInTheDocument()
    );
  });

  it('cannot resend with no address to send to', () => {
    setUser(null);
    renderPage();

    expect(screen.getByRole('button', { name: /resend verification code/i })).toBeDisabled();
  });
});
