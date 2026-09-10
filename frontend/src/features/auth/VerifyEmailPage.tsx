import React, { useState, useEffect } from 'react';
import { useNavigate, useSearchParams, useLocation, Link } from 'react-router-dom';
import { useAuthStore } from '../../store/authStore';
import { api, ApiError } from '../../lib/apiClient';
import { Mail, CheckCircle2, AlertCircle, RefreshCw, ArrowRight } from 'lucide-react';
import { BrandLogo } from '../../components/common/BrandLogo';
import { useTranslation } from '../../i18n';

export const VerifyEmailPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { user, fetchMe } = useAuthStore();
  const { isRTL } = useTranslation();

  const location = useLocation();
  const navState = (location.state || {}) as { verificationSent?: boolean; email?: string };

  const [token, setToken] = useState(searchParams.get('token') || '');
  // Three possible sources, in order of reliability: the signed-in session, the
  // address login just handed over, then the ?email= on an emailed link. Someone who
  // followed a link from their inbox has no session, so the store alone was the wrong
  // source and left the resend action with nothing to send to.
  const [email, setEmail] = useState(
    user?.email || navState.email || searchParams.get('email') || ''
  );
  // Signed-in users never type their address; the field is only for the anonymous
  // case, where someone opened the page without a session.
  const isAuthenticated = Boolean(user?.email);
  const [justSent, setJustSent] = useState(Boolean(navState.verificationSent));
  const [isLoading, setIsLoading] = useState(false);
  const [isResending, setIsResending] = useState(false);
  const [cooldown, setCooldown] = useState(0);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isSuccess, setIsSuccess] = useState(false);

  // Auto-verify if token is present in URL
  useEffect(() => {
    const urlToken = searchParams.get('token');
    if (urlToken && !isSuccess) {
      setToken(urlToken);
      handleVerify(urlToken);
    }
  }, [searchParams]);

  // fetchMe resolves after this component mounts, so the initial state above can be
  // empty for a signed-in user. Adopt the session address as soon as it arrives.
  useEffect(() => {
    if (user?.email && user.email !== email) {
      setEmail(user.email);
    }
  }, [user?.email]);

  // A code dispatched by login starts the same cooldown the resend button uses, so
  // the user is not invited to immediately request another one.
  useEffect(() => {
    if (navState.verificationSent) {
      setCooldown(60);
    }
  }, []);

  // Cooldown countdown timer
  useEffect(() => {
    if (cooldown <= 0) return;
    const timer = setInterval(() => {
      setCooldown((prev) => prev - 1);
    }, 1000);
    return () => clearInterval(timer);
  }, [cooldown]);

  const handleVerify = async (tokenToVerify?: string) => {
    const tok = (tokenToVerify || token).trim();
    if (!tok) {
      setError(isRTL ? 'يرجى إدخال رمز التحقق.' : 'Please provide a valid verification token.');
      return;
    }

    setError(null);
    setMessage(null);
    setIsLoading(true);

    try {
      await api.post('/auth/verify-email', { token: tok });
      setIsSuccess(true);
      setMessage(isRTL ? 'تم تأكيد البريد الإلكتروني بنجاح!' : 'Email verified successfully! Redirecting...');
      await fetchMe();
      setTimeout(() => {
        const currentUser = useAuthStore.getState().user;
        if (currentUser?.must_change_password) {
          navigate('/set-password');
        } else {
          navigate('/dashboard');
        }
      }, 1800);
    } catch (err: any) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError(isRTL ? 'فشل تأكيد الرمز. قد يكون منتهي الصلاحية أو تم استخدامه.' : 'Verification failed. Token may be invalid or expired.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleResend = async () => {
    if (cooldown > 0) return;
    const targetEmail = (email || user?.email || '').trim();
    if (!targetEmail) {
      setError(isRTL ? 'يرجى كتابة البريد الإلكتروني لإعادة الإرسال.' : 'Please specify an email address to resend verification.');
      return;
    }

    setError(null);
    setMessage(null);
    setIsResending(true);

    try {
      const res = await api.post<any>('/auth/resend-verification', { email: targetEmail });
      setMessage(res?.message || (isRTL ? 'إذا كان الحساب مؤهلاً، تم إرسال رمز تحقق جديد.' : 'If eligible, a fresh verification token has been sent.'));
      setJustSent(true);
      setCooldown(60); // 60s cooldown
    } catch (err: any) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError(isRTL ? 'فشل إعادة الإرسال. يرجى المحاولة لاحقاً.' : 'Failed to resend. Please wait before retrying.');
      }
    } finally {
      setIsResending(false);
    }
  };

  return (
    <div
      style={{
        minHeight: '100vh',
        width: '100vw',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: '#313234',
        padding: 'var(--space-4)',
      }}
    >
      <div
        className="card"
        style={{
          width: '100%',
          maxWidth: '460px',
          backgroundColor: '#ffffff',
          borderRadius: 'var(--radius-xl)',
          padding: 'var(--space-8)',
          boxShadow: '0 20px 40px rgba(0,0,0,0.3)',
          border: '1px solid rgba(255, 30, 87, 0.15)',
        }}
      >
        <div style={{ textAlign: 'center', marginBottom: 'var(--space-6)' }}>
          <BrandLogo size="md" />
          <h2
            className="font-display font-bold text-2xl"
            style={{ color: 'var(--neutral-900)', marginTop: 'var(--space-4)' }}
          >
            {isRTL ? 'تأكيد البريد الإلكتروني' : 'Verify Your Email'}
          </h2>
          <p className="text-sm text-muted" style={{ marginTop: 'var(--space-1)' }}>
            {isRTL
              ? 'أدخل رمز التحقق المرسل إلى بريدك للوصول إلى لوحة التحكم'
              : 'Enter the one-time verification token sent to your company inbox.'}
          </p>
        </div>

        {error && (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 'var(--space-2)',
              padding: 'var(--space-3)',
              backgroundColor: '#fee2e2',
              border: '1px solid #ef4444',
              borderRadius: 'var(--radius-md)',
              color: '#991b1b',
              fontSize: '13px',
              marginBottom: 'var(--space-4)',
            }}
          >
            <AlertCircle size={16} style={{ flexShrink: 0 }} />
            <span>{error}</span>
          </div>
        )}

        {message && (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 'var(--space-2)',
              padding: 'var(--space-3)',
              backgroundColor: '#ecfdf5',
              border: '1px solid #10b981',
              borderRadius: 'var(--radius-md)',
              color: '#065f46',
              fontSize: '13px',
              marginBottom: 'var(--space-4)',
            }}
          >
            <CheckCircle2 size={16} style={{ flexShrink: 0 }} />
            <span>{message}</span>
          </div>
        )}

        {isSuccess ? (
          <div style={{ textAlign: 'center', padding: 'var(--space-4) 0' }}>
            <div
              style={{
                width: '60px',
                height: '60px',
                borderRadius: '50%',
                backgroundColor: 'rgba(16, 185, 129, 0.15)',
                color: '#10b981',
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                marginBottom: 'var(--space-3)',
              }}
            >
              <CheckCircle2 size={32} />
            </div>
            <p className="text-sm font-semibold" style={{ color: 'var(--neutral-800)' }}>
              {isRTL ? 'جاري تحويلك إلى النظام...' : 'Redirecting to your workspace...'}
            </p>
          </div>
        ) : (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleVerify();
            }}
            style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}
          >
            {justSent && email && (
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 'var(--space-2)',
                  padding: 'var(--space-3)',
                  backgroundColor: '#eff6ff',
                  border: '1px solid #3b82f6',
                  borderRadius: 'var(--radius-md)',
                  color: '#1e3a8a',
                  fontSize: '13px',
                }}
              >
                <Mail size={16} style={{ flexShrink: 0 }} />
                <span>
                  {isRTL ? 'أرسلنا رمز تحقق إلى ' : 'We sent a verification code to '}
                  <strong style={{ wordBreak: 'break-all' }}>{email}</strong>
                </span>
              </div>
            )}

            {!isAuthenticated && (
              <div className="form-group">
                <label className="form-label" style={{ fontWeight: 600 }}>
                  {isRTL ? 'البريد الإلكتروني' : 'Email Address'}
                </label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="name@alphapromena.com"
                  className="form-input"
                  autoComplete="email"
                />
              </div>
            )}

            <div className="form-group">
              <label className="form-label" style={{ fontWeight: 600 }}>
                {isRTL ? 'رمز التحقق (Verification Token)' : 'Verification Token'}
              </label>
              <div style={{ position: 'relative' }}>
                <input
                  type="text"
                  required
                  value={token}
                  onChange={(e) => setToken(e.target.value)}
                  placeholder={isRTL ? 'الصق الرمز السري هنا...' : 'Paste your 32-character token...'}
                  className="form-input"
                  style={{ fontFamily: 'monospace', fontSize: '13px', letterSpacing: '0.5px' }}
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={isLoading || !token.trim()}
              className="btn btn-accent"
              style={{
                width: '100%',
                padding: '12px',
                fontWeight: 700,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '8px',
              }}
            >
              {isLoading ? (
                <>
                  <RefreshCw size={16} className="animate-spin" />
                  <span>{isRTL ? 'جاري التحقق...' : 'Verifying...'}</span>
                </>
              ) : (
                <>
                  <span>{isRTL ? 'تأكيد الرمز' : 'Verify Token'}</span>
                  <ArrowRight size={16} />
                </>
              )}
            </button>

            <div
              style={{
                marginTop: 'var(--space-2)',
                paddingTop: 'var(--space-4)',
                borderTop: '1px solid var(--border-light)',
                display: 'flex',
                flexDirection: 'column',
                gap: 'var(--space-2)',
              }}
            >
              <span className="text-xs text-muted" style={{ textAlign: 'center' }}>
                {isRTL ? 'لم يصلك الرمز؟' : "Didn't receive a token?"}
              </span>
              <button
                type="button"
                disabled={isResending || cooldown > 0 || !email.trim()}
                onClick={handleResend}
                className="btn btn-secondary"
                style={{
                  width: '100%',
                  padding: '10px',
                  fontWeight: 600,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '8px',
                  opacity: cooldown > 0 || !email.trim() ? 0.6 : 1,
                }}
              >
                {isResending ? (
                  <>
                    <RefreshCw size={15} className="animate-spin" />
                    <span>{isRTL ? 'جاري الإرسال...' : 'Sending...'}</span>
                  </>
                ) : cooldown > 0 ? (
                  <span>
                    {isRTL ? `إعادة الإرسال خلال ${cooldown} ثانية` : `Resend in ${cooldown}s`}
                  </span>
                ) : (
                  <>
                    <Mail size={15} />
                    <span>{isRTL ? 'إعادة إرسال الرمز' : 'Resend verification code'}</span>
                  </>
                )}
              </button>

              <div style={{ display: 'flex', justifyContent: 'center', marginTop: 'var(--space-2)' }}>
                <Link to="/login" className="text-xs text-muted hover:underline">
                  {isRTL ? 'العودة لتسجيل الدخول' : 'Back to Login'}
                </Link>
              </div>
            </div>
          </form>
        )}
      </div>
    </div>
  );
};
