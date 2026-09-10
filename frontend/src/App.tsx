import React, { useEffect } from 'react';
import { RouterProvider } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { router } from './router';
import { useAuthStore } from './store/authStore';
import { hasSessionHint } from './lib/apiClient';
import { LoadingScreen } from './components/feedback/LoadingScreen';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
      staleTime: 30000,
    },
  },
});

export const App: React.FC = () => {
  const { fetchMe, isLoading } = useAuthStore();

  useEffect(() => {
    // Only ask the server who we are when the browser says a session exists.
    // Calling this unconditionally meant every anonymous visit to the login page
    // fired /auth/me and then /auth/refresh, both 401, before the router mounted.
    if (hasSessionHint()) {
      fetchMe();
    } else {
      useAuthStore.getState().setUser(null);
    }
  }, []);

  // Session ended (refresh token expired/revoked): drop the user so the route guard
  // sends them to /login instead of leaving a half-dead UI behind.
  useEffect(() => {
    const onExpired = () => useAuthStore.getState().setUser(null);
    window.addEventListener('auth:expired', onExpired);
    return () => window.removeEventListener('auth:expired', onExpired);
  }, []);

  if (isLoading) {
    return <LoadingScreen message="Initializing Alpha Pro MENA CRM System..." />;
  }

  return (
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  );
};
