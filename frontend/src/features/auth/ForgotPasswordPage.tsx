import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { api, ApiError } from '../../lib/apiClient';
import { Mail, CheckCircle2, AlertCircle, ArrowLeft } from 'lucide-react';
import { BrandLogo } from '../../components/common/BrandLogo';
import { useTranslation } from '../../i18n';

export const ForgotPasswordPage: React.FC = () => {
  const { isRTL } = useTranslation();
  const [email, setEmail] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsLoading(true);

    try {
      await api.post('/auth/forgot-password', { email: email.trim() });
      setSubmitted(true);
    } catch (err: any) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError(isRTL ? 'فشل إرسال طلب الاستعادة.' : 'Failed to request password reset.');
      }
    } finally {
      setIsLoading(false);
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
          maxWidth: '440px',
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
            {isRTL ? 'استعادة كلمة المرور' : 'Reset Password'}
          </h2>
          <p className="text-sm text-muted" style={{ marginTop: 'var(--space-1)' }}>
            {isRTL
              ? 'أدخل بريدك الإلكتروني المؤسسي لإرسال تعليمات الاستعادة'
              : 'Enter your company email to receive reset instructions.'}
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

        {submitted ? (
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
            <h3 className="font-bold text-base" style={{ color: 'var(--neutral-900)' }}>
              {isRTL ? 'تم استلام الطلب' : 'Check Your Inbox'}
            </h3>
            <p className="text-xs text-muted" style={{ marginTop: 'var(--space-2)' }}>
              {isRTL
                ? 'إذا كان هذا البريد مسجلاً في النظام، ستصلك رسالة تحتوي على رابط الاستعادة.'
                : 'If an active account exists for this address, a reset link has been dispatched.'}
            </p>
            <div style={{ marginTop: 'var(--space-6)' }}>
              <Link to="/login" className="btn btn-secondary btn-sm">
                <ArrowLeft size={14} />
                <span>{isRTL ? 'العودة لتسجيل الدخول' : 'Return to Login'}</span>
              </Link>
            </div>
          </div>
        ) : (
          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
            <div className="form-group">
              <label className="form-label" style={{ fontWeight: 600 }}>
                {isRTL ? 'البريد الإلكتروني المؤسسي' : 'Company Email'}
              </label>
              <div style={{ position: 'relative' }}>
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="name@alphapromena.com"
                  className="form-input"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={isLoading || !email.trim()}
              className="btn btn-accent"
              style={{
                width: '100%',
                padding: '12px',
                fontWeight: 700,
                marginTop: 'var(--space-2)',
              }}
            >
              {isLoading ? (isRTL ? 'جاري الإرسال...' : 'Sending Link...') : (isRTL ? 'إرسال رابط الاستعادة' : 'Send Reset Link')}
            </button>

            <div style={{ textAlign: 'center', marginTop: 'var(--space-2)' }}>
              <Link to="/login" className="text-xs text-muted hover:underline">
                {isRTL ? 'العودة لتسجيل الدخول' : 'Back to Login'}
              </Link>
            </div>
          </form>
        )}
      </div>
    </div>
  );
};
