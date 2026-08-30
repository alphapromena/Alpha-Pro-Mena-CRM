/**
 * Alpha Pro MENA CRM — i18n Hook
 */
import { useAuthStore } from '../store/authStore';
import { translations, TranslationKey } from './translations';

export const useTranslation = () => {
  const language = useAuthStore((state) => state.language) || 'en';

  const t = (key: TranslationKey, fallback?: string): string => {
    const currentDict = translations[language] || translations.en;
    return (currentDict as any)[key] || (translations.en as any)[key] || fallback || key;
  };

  const isRTL = language === 'ar';

  return { t, language, isRTL };
};
