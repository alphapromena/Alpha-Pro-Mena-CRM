import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { useAuthStore } from '../../store/authStore';
import { api, ApiError } from '../../lib/apiClient';
import { Lock, Mail, AlertCircle, ArrowRight, Shield, Globe } from 'lucide-react';
import { BrandLogo } from '../../components/common/BrandLogo';
import { Login3DVisual } from './Login3DVisual';
import { useTranslation } from '../../i18n';

const VIDEO_WALLPAPERS = [
  { id: 'wall1', label: 'Motion Wall 1', mp4: '/videos/wall.mp4', webm: '/videos/wall.webm' },
  { id: 'wall2', label: 'Motion Wall 2', mp4: '/videos/wall2.mp4', webm: '/videos/wall2.webm' },
];

export const LoginPage: React.FC = () => {
  const navigate = useNavigate();
  const { fetchMe, language, setLanguage } = useAuthStore();
  const { isRTL } = useTranslation();

  // Start empty. These previously defaulted to a real employee's address and a
  // working plaintext password, which shipped in the public bundle and arrived
  // pre-filled on the live login form.
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  // Dynamic alternating video state — automatically cycles on every visit & reload
  const [videoIdx, setVideoIdx] = useState<number>(() => {
    const saved = localStorage.getItem('crm_login_video_idx');
    const nextIdx = saved !== null ? (parseInt(saved, 10) + 1) % VIDEO_WALLPAPERS.length : 0;
    localStorage.setItem('crm_login_video_idx', nextIdx.toString());
    return nextIdx;
  });

  const toggleVideo = () => {
    setVideoIdx((prev) => {
      const next = (prev + 1) % VIDEO_WALLPAPERS.length;
      localStorage.setItem('crm_login_video_idx', next.toString());
      return next;
    });
  };

  const handleVideoEnded = () => {
    toggleVideo();
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsLoading(true);

    try {
      const res = await api.post<any>('/auth/login', { email, password });
      await fetchMe();
      const currentUser = useAuthStore.getState().user;
      if (res?.must_change_password || currentUser?.must_change_password) {
        navigate('/set-password');
        return;
      }
      if (res?.email_verified === false || currentUser?.email_verified === false) {
        navigate('/verify-email');
        return;
      }
      if (currentUser?.role === 'DATA_OPS') {
        navigate('/leads/pool');
      } else {
        navigate('/dashboard');
      }
    } catch (err: any) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError(isRTL ? 'فشل الاتصال بخدمة المصادقة.' : 'Failed to connect to authentication service.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleQuickSelect = (roleEmail: string) => {
    setEmail(roleEmail);
    setPassword('');
    setError(null);
  };

  const quickAccounts = [
    { label: 'Saleh', email: 'saleh@alphapromena.com', role: 'SALES' },
    { label: 'Amin', email: 'amin@alphapromena.com', role: 'SALES' },
    { label: 'Aseel', email: 'aseel@alphapromena.com', role: 'DATA OPS' },
    { label: 'Abdallah', email: 'abdallah@alphapromena.com', role: 'MANAGER' },
    { label: 'Qusai', email: 'qusai@alphapromena.com', role: 'TEAM LEAD' },
    { label: 'Ghaida', email: 'ghaida@alphapromena.com', role: 'SALES' },
    { label: 'Hassan', email: 'hassan@alphapromena.com', role: 'SALES' },
  ];

  return (
    <div
      style={{
        minHeight: '100vh',
        width: '100vw',
        display: 'flex',
        flexDirection: 'row',
        backgroundColor: '#313234', // Official Brand Kit Dark Charcoal Fallback
        color: 'var(--neutral-900)',
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      {/* ── 0. Full-Bleed High-Brightness Moving Video Wallpaper ── */}
      <video
        key={VIDEO_WALLPAPERS[videoIdx].id}
        autoPlay
        muted
        loop={false}
        onEnded={handleVideoEnded}
        playsInline
        preload="auto"
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          width: '100%',
          height: '100%',
          objectFit: 'cover',
          zIndex: 0,
          pointerEvents: 'none',
          filter: 'brightness(1.26) contrast(1.10) saturate(1.15)',
        }}
      >
        <source src={VIDEO_WALLPAPERS[videoIdx].webm} type="video/webm" />
        <source src={VIDEO_WALLPAPERS[videoIdx].mp4} type="video/mp4" />
      </video>

      {/* ── High-Contrast Ambient Overlay for Ultra Vibrancy ── */}
      <div
        style={{
          position: 'absolute',
          inset: 0,
          background: 'radial-gradient(circle at 65% 50%, rgba(49, 50, 52, 0.18) 0%, rgba(12, 14, 18, 0.50) 100%)',
          backdropFilter: 'blur(1.5px)',
          WebkitBackdropFilter: 'blur(1.5px)',
          zIndex: 1,
          pointerEvents: 'none',
        }}
      />

      {/* ── Top Header Controls (Language Switcher) ── */}
      <div
        style={{
          position: 'absolute',
          top: '20px',
          right: isRTL ? 'auto' : '24px',
          left: isRTL ? '24px' : 'auto',
          zIndex: 20,
        }}
      >
        <button
          type="button"
          onClick={() => setLanguage(language === 'ar' ? 'en' : 'ar')}
          className="btn btn-ghost btn-sm"
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '6px',
            fontSize: '12px',
            fontWeight: 600,
            color: 'var(--neutral-300)',
            backgroundColor: 'rgba(25, 27, 34, 0.65)',
            border: '1px solid rgba(255, 255, 255, 0.16)',
            backdropFilter: 'blur(12px)',
            borderRadius: 'var(--radius-full)',
            padding: '6px 14px',
            boxShadow: '0 2px 8px rgba(0, 0, 0, 0.4)',
            cursor: 'pointer',
          }}
        >
          <Globe size={14} style={{ color: '#D4AF37' }} />
          <span>{language === 'ar' ? 'English' : 'العربية'}</span>
        </button>
      </div>

      {/* ── Main Two-Column Split Layout ── */}
      <div
        className="login-split-container"
        style={{
          display: 'flex',
          flexDirection: isRTL ? 'row-reverse' : 'row',
          width: '100%',
          height: '100vh',
          flexWrap: 'wrap',
          position: 'relative',
          zIndex: 2,
        }}
      >
        {/* ── LEFT SIDE: Enterprise Translucent Glass Login Interface (42% Desktop) ── */}
        <div
          style={{
            flex: '0 0 42%',
            minWidth: '380px',
            maxWidth: '560px',
            height: '100%',
            overflowY: 'auto',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'center',
            alignItems: 'center',
            padding: 'var(--space-6) var(--space-8)',
            backgroundColor: 'rgba(10, 12, 16, 0.38)', // Translucent column background
            backdropFilter: 'blur(14px)',
            WebkitBackdropFilter: 'blur(14px)',
            borderRight: isRTL ? 'none' : '1px solid rgba(255, 255, 255, 0.10)',
            borderLeft: isRTL ? '1px solid rgba(255, 255, 255, 0.10)' : 'none',
            zIndex: 10,
            boxShadow: '10px 0 40px rgba(0, 0, 0, 0.5)',
          }}
        >
          <motion.div
            initial={{ opacity: 0, x: isRTL ? 20 : -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.4 }}
            style={{
              width: '100%',
              maxWidth: '420px',
              display: 'flex',
              flexDirection: 'column',
              gap: 'var(--space-5)',
            }}
          >
            {/* Official Brand Logo */}
            <div style={{ marginBottom: 'var(--space-1)' }}>
              <BrandLogo variant="stacked" size="lg" theme="dark-bg" is3D={true} />
            </div>

            {/* Main Translucent Glass Login Card */}
            <div
              style={{
                width: '100%',
                backgroundColor: 'rgba(18, 22, 30, 0.52)', // Translucent glass window
                backdropFilter: 'blur(24px)',
                WebkitBackdropFilter: 'blur(24px)',
                borderRadius: 'var(--radius-xl)',
                border: '1px solid rgba(255, 255, 255, 0.14)',
                boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.65), 0 0 35px rgba(255, 30, 87, 0.08)',
                overflow: 'hidden',
              }}
            >
              <div style={{ height: '3px', backgroundColor: 'var(--color-accent)' }} />

              <div style={{ padding: 'var(--space-7)' }}>
                <div style={{ textAlign: 'center', marginBottom: 'var(--space-5)' }}>
                  <h2
                    style={{
                      fontFamily: 'var(--font-display)',
                      fontSize: '19px',
                      fontWeight: 800,
                      color: '#FFFFFF',
                      margin: '0 0 4px 0',
                      letterSpacing: '-0.01em',
                    }}
                  >
                    {isRTL ? 'تسجيل الدخول إلى النظام' : 'Enterprise Sign In'}
                  </h2>
                  <p style={{ margin: 0, fontSize: '13px', color: 'rgba(255, 255, 255, 0.75)', lineHeight: 1.4 }}>
                    {isRTL ? 'أدخل بيانات الاعتماد للمتابعة' : 'Enter your enterprise credentials to access your workspace.'}
                  </p>
                </div>

                {/* Error Message */}
                <AnimatePresence>
                  {error && (
                    <motion.div
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: 'auto' }}
                      exit={{ opacity: 0, height: 0 }}
                      style={{
                        padding: 'var(--space-3) var(--space-4)',
                        backgroundColor: 'rgba(239, 68, 68, 0.25)',
                        border: '1px solid rgba(239, 68, 68, 0.45)',
                        borderRadius: 'var(--radius-md)',
                        color: '#FECACA',
                        fontSize: '13px',
                        display: 'flex',
                        alignItems: 'center',
                        gap: 'var(--space-2)',
                        marginBottom: 'var(--space-4)',
                      }}
                    >
                      <AlertCircle size={16} style={{ flexShrink: 0 }} />
                      <span>{error}</span>
                    </motion.div>
                  )}
                </AnimatePresence>

                <form onSubmit={handleSubmit}>
                  {/* Email field */}
                  <div style={{ marginBottom: 'var(--space-4)' }}>
                    <label
                      htmlFor="login-email"
                      style={{
                        display: 'block',
                        fontSize: '12px',
                        fontWeight: 700,
                        color: 'rgba(255, 255, 255, 0.85)',
                        marginBottom: '6px',
                      }}
                    >
                      {isRTL ? 'البريد الإلكتروني' : 'Email Address'}
                    </label>
                    <div style={{ position: 'relative' }}>
                      <Mail
                        size={15}
                        style={{
                          position: 'absolute',
                          left: isRTL ? 'auto' : '12px',
                          right: isRTL ? '12px' : 'auto',
                          top: '50%',
                          transform: 'translateY(-50%)',
                          color: 'rgba(255, 255, 255, 0.55)',
                          pointerEvents: 'none',
                        }}
                      />
                      <input
                        id="login-email"
                        type="email"
                        required
                        autoComplete="email"
                        aria-label="Email address"
                        className="form-input"
                        style={{
                          paddingLeft: isRTL ? '12px' : '36px',
                          paddingRight: isRTL ? '36px' : '12px',
                          width: '100%',
                          height: '42px',
                          fontSize: '14px',
                          backgroundColor: 'rgba(12, 15, 20, 0.55)',
                          color: '#FFFFFF',
                          borderColor: 'rgba(255, 255, 255, 0.16)',
                          backdropFilter: 'blur(8px)',
                        }}
                        placeholder="name@alphapromena.com"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                      />
                    </div>
                  </div>

                  {/* Password field */}
                  <div style={{ marginBottom: 'var(--space-5)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                      <label
                        htmlFor="login-password"
                        style={{
                          display: 'block',
                          fontSize: '12px',
                          fontWeight: 700,
                          color: 'rgba(255, 255, 255, 0.85)',
                          margin: 0,
                        }}
                      >
                        {isRTL ? 'كلمة المرور' : 'Password'}
                      </label>
                      <button
                        type="button"
                        onClick={() => navigate('/forgot-password')}
                        style={{
                          background: 'none',
                          border: 'none',
                          padding: 0,
                          fontSize: '11px',
                          color: '#FF1E57',
                          cursor: 'pointer',
                          textDecoration: 'underline',
                          fontWeight: 600,
                        }}
                      >
                        {isRTL ? 'نسيت كلمة المرور؟' : 'Forgot Password?'}
                      </button>
                    </div>
                    <div style={{ position: 'relative' }}>
                      <Lock
                        size={15}
                        style={{
                          position: 'absolute',
                          left: isRTL ? 'auto' : '12px',
                          right: isRTL ? '12px' : 'auto',
                          top: '50%',
                          transform: 'translateY(-50%)',
                          color: 'rgba(255, 255, 255, 0.55)',
                          pointerEvents: 'none',
                        }}
                      />
                      <input
                        id="login-password"
                        type="password"
                        required
                        autoComplete="current-password"
                        aria-label="Password"
                        className="form-input"
                        style={{
                          paddingLeft: isRTL ? '12px' : '36px',
                          paddingRight: isRTL ? '36px' : '12px',
                          width: '100%',
                          height: '42px',
                          fontSize: '14px',
                          backgroundColor: 'rgba(12, 15, 20, 0.55)',
                          color: '#FFFFFF',
                          borderColor: 'rgba(255, 255, 255, 0.16)',
                          backdropFilter: 'blur(8px)',
                        }}
                        placeholder="••••••••••••"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                      />
                    </div>
                  </div>

                  {/* Submit button */}
                  <button
                    id="login-submit"
                    type="submit"
                    disabled={isLoading}
                    style={{
                      width: '100%',
                      height: '44px',
                      fontWeight: 700,
                      fontSize: '14px',
                      backgroundColor: isLoading ? 'var(--neutral-600)' : '#FF1E57', // Authentic Brand Crimson
                      color: '#FFFFFF',
                      border: 'none',
                      borderRadius: 'var(--radius-md)',
                      boxShadow: '0 4px 16px rgba(255, 30, 87, 0.45)',
                      cursor: isLoading ? 'not-allowed' : 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: '8px',
                      transition: 'background-color 0.2s ease, transform 0.15s ease',
                    }}
                  >
                    <span>{isLoading ? (isRTL ? 'جاري التحقق...' : 'Authenticating...') : (isRTL ? 'تسجيل الدخول' : 'Sign In')}</span>
                    {!isLoading && <ArrowRight size={16} />}
                  </button>

                  <div style={{ display: 'flex', justifyContent: 'center', marginTop: 'var(--space-3)' }}>
                    <button
                      type="button"
                      onClick={() => navigate('/verify-email')}
                      style={{
                        background: 'none',
                        border: 'none',
                        padding: 0,
                        fontSize: '11px',
                        color: 'rgba(255, 255, 255, 0.7)',
                        cursor: 'pointer',
                        textDecoration: 'underline',
                      }}
                    >
                      {isRTL ? 'تأكيد البريد الإلكتروني / إعادة إرسال الرمز' : 'Verify Email / Resend Token'}
                    </button>
                  </div>
                </form>
              </div>
            </div>

            {/* Translucent Quick Account Switcher (Real Team Accounts) */}
            <div
              style={{
                width: '100%',
                padding: 'var(--space-3) var(--space-4)',
                backgroundColor: 'rgba(18, 22, 30, 0.46)', // Translucent glass
                backdropFilter: 'blur(16px)',
                WebkitBackdropFilter: 'blur(16px)',
                borderRadius: 'var(--radius-lg)',
                border: '1px solid rgba(255, 255, 255, 0.12)',
                boxShadow: '0 8px 24px rgba(0, 0, 0, 0.35)',
              }}
            >
              <div
                style={{
                  fontSize: '10px',
                  fontWeight: 800,
                  color: 'rgba(255, 255, 255, 0.7)',
                  textAlign: 'center',
                  letterSpacing: '1px',
                  marginBottom: 'var(--space-2)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '6px',
                }}
              >
                <Shield size={12} style={{ color: '#D4AF37' }} />
                <span>{isRTL ? 'التبديل السريع لفريق العمل' : 'TEAM QUICK LOGIN'}</span>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '6px' }}>
                {quickAccounts.slice(0, 4).map((acc) => (
                  <button
                    key={acc.label}
                    type="button"
                    onClick={() => handleQuickSelect(acc.email)}
                    className="btn btn-ghost btn-sm"
                    style={{
                      flexDirection: 'column',
                      height: 'auto',
                      padding: '6px 4px',
                      gap: '2px',
                      borderRadius: 'var(--radius-md)',
                      border: email === acc.email ? '1px solid #FF1E57' : '1px solid rgba(255, 255, 255, 0.12)',
                      backgroundColor: email === acc.email ? 'rgba(255, 30, 87, 0.28)' : 'rgba(255, 255, 255, 0.05)',
                      backdropFilter: 'blur(8px)',
                      transition: 'all 0.15s ease',
                    }}
                  >
                    <span style={{ fontSize: '9px', color: 'rgba(255, 255, 255, 0.65)', fontWeight: 600 }}>{acc.role}</span>
                    <span style={{ fontSize: '11px', fontWeight: 700, color: '#FFFFFF' }}>{acc.label}</span>
                  </button>
                ))}
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '6px', marginTop: '6px' }}>
                {quickAccounts.slice(4).map((acc) => (
                  <button
                    key={acc.label}
                    type="button"
                    onClick={() => handleQuickSelect(acc.email)}
                    className="btn btn-ghost btn-sm"
                    style={{
                      flexDirection: 'column',
                      height: 'auto',
                      padding: '6px 4px',
                      gap: '2px',
                      borderRadius: 'var(--radius-md)',
                      border: email === acc.email ? '1px solid #FF1E57' : '1px solid rgba(255, 255, 255, 0.12)',
                      backgroundColor: email === acc.email ? 'rgba(255, 30, 87, 0.28)' : 'rgba(255, 255, 255, 0.05)',
                      backdropFilter: 'blur(8px)',
                      transition: 'all 0.15s ease',
                    }}
                  >
                    <span style={{ fontSize: '9px', color: 'rgba(255, 255, 255, 0.65)', fontWeight: 600 }}>{acc.role}</span>
                    <span style={{ fontSize: '11px', fontWeight: 700, color: '#FFFFFF' }}>{acc.label}</span>
                  </button>
                ))}
              </div>
            </div>

            {/* Minimal Footer */}
            <div style={{ fontSize: '11px', color: 'var(--neutral-500)', textAlign: 'center' }}>
              &copy; {new Date().getFullYear()} Alpha Pro MENA · CRM Platform
            </div>
          </motion.div>
        </div>

        {/* ── RIGHT SIDE: Large 3D Visual Stage (58% Desktop) ── */}
        <div
          style={{
            flex: '1 1 58%',
            height: '100%',
            position: 'relative',
            backgroundColor: 'transparent',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            minHeight: '400px',
          }}
        >
          <Login3DVisual />
        </div>
      </div>
    </div>
  );
};
