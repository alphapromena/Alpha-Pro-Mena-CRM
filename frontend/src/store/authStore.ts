/**
 * Auth state management via Zustand.
 * Handles user identity, persistent themes, and persistent language (RTL/LTR).
 */
import { create } from 'zustand';
import { User } from '../types';
import { api } from '../lib/apiClient';

interface AuthState {
  user: User | null;
  theme: string;
  language: 'en' | 'ar';
  isLoading: boolean;
  isAuthenticated: boolean;
  fetchMe: () => Promise<void>;
  setTheme: (theme: string) => Promise<void>;
  setLanguage: (language: 'en' | 'ar') => Promise<void>;
  logout: () => Promise<void>;
  setUser: (user: User | null) => void;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  theme: localStorage.getItem('crm_theme') || 'black_beige',
  language: (localStorage.getItem('crm_lang') as 'en' | 'ar') || 'en',
  isLoading: true,
  isAuthenticated: false,

  fetchMe: async () => {
    set({ isLoading: true });
    try {
      const user = await api.get<User>('/auth/me');
      const activeTheme = user.theme_preference || get().theme || 'black_beige';
      const activeLang = ((user as any).preferred_language as 'en' | 'ar') || get().language || 'en';

      document.documentElement.setAttribute('data-theme', activeTheme);
      document.documentElement.setAttribute('dir', activeLang === 'ar' ? 'rtl' : 'ltr');
      document.documentElement.setAttribute('lang', activeLang);

      localStorage.setItem('crm_theme', activeTheme);
      localStorage.setItem('crm_lang', activeLang);

      set({
        user,
        theme: activeTheme,
        language: activeLang,
        isAuthenticated: true,
        isLoading: false,
      });
    } catch {
      const savedTheme = localStorage.getItem('crm_theme') || 'black_beige';
      const savedLang = (localStorage.getItem('crm_lang') as 'en' | 'ar') || 'en';

      document.documentElement.setAttribute('data-theme', savedTheme);
      document.documentElement.setAttribute('dir', savedLang === 'ar' ? 'rtl' : 'ltr');
      document.documentElement.setAttribute('lang', savedLang);

      set({ user: null, isAuthenticated: false, isLoading: false });
    }
  },

  setTheme: async (newTheme: string) => {
    document.documentElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('crm_theme', newTheme);
    set((state) => ({
      theme: newTheme,
      user: state.user ? { ...state.user, theme_preference: newTheme } : null,
    }));
    // Anonymous visitors can still switch theme; it just stays local. Calling the
    // authenticated endpoint here was one of the 401 sources on the login page.
    if (!get().isAuthenticated) return;
    try {
      await api.patch('/auth/theme', { theme_preference: newTheme });
    } catch (err) {
      console.warn('Failed to persist theme to backend', err);
    }
  },

  setLanguage: async (newLang: 'en' | 'ar') => {
    document.documentElement.setAttribute('dir', newLang === 'ar' ? 'rtl' : 'ltr');
    document.documentElement.setAttribute('lang', newLang);
    localStorage.setItem('crm_lang', newLang);
    set((state) => ({
      language: newLang,
      user: state.user ? ({ ...state.user, preferred_language: newLang } as any) : null,
    }));
    if (!get().isAuthenticated) return;
    try {
      await api.patch('/auth/language', { preferred_language: newLang });
    } catch (err) {
      console.warn('Failed to persist language to backend', err);
    }
  },

  logout: async () => {
    try {
      await api.post('/auth/logout');
    } catch (e) {
      console.error('Logout error', e);
    } finally {
      set({ user: null, isAuthenticated: false });
      window.location.href = '/login';
    }
  },

  setUser: (user) => {
    if (user?.theme_preference) {
      document.documentElement.setAttribute('data-theme', user.theme_preference);
      localStorage.setItem('crm_theme', user.theme_preference);
    }
    if ((user as any)?.preferred_language) {
      const l = (user as any).preferred_language;
      document.documentElement.setAttribute('dir', l === 'ar' ? 'rtl' : 'ltr');
      document.documentElement.setAttribute('lang', l);
      localStorage.setItem('crm_lang', l);
    }
    set({
      user,
      theme: user?.theme_preference || get().theme || 'black_beige',
      language: ((user as any)?.preferred_language as 'en' | 'ar') || get().language || 'en',
      isAuthenticated: !!user,
      // A definitive answer about the session, so bootstrapping is over. Without
      // this, an anonymous start that calls setUser(null) instead of fetchMe would
      // leave isLoading true and the app stuck on the loading screen.
      isLoading: false,
    });
  },
}));
