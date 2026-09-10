import React, { useState, useEffect } from 'react';
import { useNavigate, useSearchParams, Link } from 'react-router-dom';
import { api, ApiError } from '../../lib/apiClient';
import { Lock, CheckCircle2, AlertCircle, ArrowLeft, Check, X } from 'lucide-react';
import { BrandLogo } from '../../components/common/BrandLogo';
import { useTranslation } from '../../i18n';

export const ResetPasswordPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { isRTL } = useTranslation();

  const [token, setToken] = useState(searchParams.get('token') || '');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    const urlToken = searchParams.get('token');
    if (urlToken) setToken(urlToken);
  }, [searchParams]);

  // Password rules validation
  const hasMinLen = newPassword.length >= 8;
  const hasUpper = /[A-Z]/.test(newPassword);
  const hasLower = /[a-z]/.test(newPassword);
  const hasDigit = /[0-9]/.test(newPassword);
  const hasSpecial = /[^A-Za-z0-9]/.test(newPassword);
  const isMatch = newPassword && newPassword === confirmPassword;
  const isPolicyValid = hasMinLen && hasUpper && hasLower && hasDigit && hasSpecial && isMatch;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token.trim()) {
      setError(isRTL ? 'رمز الاستعادة مفقود أو غير صالح.' : 'Reset token is required.');
      return;
    }
    if (!isPolicyValid) {
      setError(isRTL ? 'يرجى استيفاء جميع معايير كلمة المرور وتطابق التأكيد.' : 'Please satisfy all password strength criteria.');
      return;
    }

    setError(null);
    setIsLoading(true);

    try {
      await api.post('/auth/reset-password', {
        token: token.trim(),
        new_password: newPassword,
        confirm_password: confirmPassword,
      });

      setSuccess(true);
      setTimeout(() => {
        navigate('/login');
      }, 2000);
    } catch (err: any) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError(isRTL ? 'فشل إعادة تعيين كلمة المرور. قد يكون الرمز منتهي الصلاحية.' : 'Reset failed. The token may be expired or already used.');
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
            {isRTL ? 'تعيين كلمة المرور الجديدة' : 'Set New Password'}
          </h2>
          <p className="text-sm text-muted" style={{ marginTop: 'var(--space-1)' }}>
            {isRTL
              ? 'أدخل رمز الاستعادة وكلمة المرور الجديدة'
              : 'Enter your reset token and new secure password.'}
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

        {success ? (
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
              {isRTL ? 'تم تغيير كلمة المرور بنجاح! جاري تحويلك لتسجيل الدخول...' : 'Password updated! Redirecting to login...'}
            </p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
            <div className="form-group">
              <label className="form-label" style={{ fontWeight: 600 }}>
                {isRTL ? 'رمز الاستعادة (Reset Token)' : 'Reset Token'}
              </label>
              <input
                type="text"
                required
                value={token}
                onChange={(e) => setToken(e.target.value)}
                placeholder="Paste token here..."
                className="form-input"
                style={{ fontFamily: 'monospace', fontSize: '13px' }}
              />
            </div>

            <div className="form-group">
              <label className="form-label" style={{ fontWeight: 600 }}>
                {isRTL ? 'كلمة المرور الجديدة' : 'New Password'}
              </label>
              <input
                type="password"
                required
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder="••••••••"
                className="form-input"
              />
            </div>

            <div className="form-group">
              <label className="form-label" style={{ fontWeight: 600 }}>
                {isRTL ? 'تأكيد كلمة المرور' : 'Confirm Password'}
              </label>
              <input
                type="password"
                required
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="••••••••"
                className="form-input"
              />
            </div>

            {/* Criteria */}
            <div
              style={{
                padding: 'var(--space-3)',
                backgroundColor: 'var(--bg-subtle)',
                borderRadius: 'var(--radius-md)',
                fontSize: '11px',
                display: 'flex',
                flexDirection: 'column',
                gap: '4px',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: hasMinLen ? '#10b981' : 'var(--neutral-500)' }}>
                {hasMinLen ? <Check size={13} /> : <X size={13} />}
                <span>{isRTL ? '8 أحرف على الأقل' : 'At least 8 characters long'}</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: hasUpper && hasLower ? '#10b981' : 'var(--neutral-500)' }}>
                {hasUpper && hasLower ? <Check size={13} /> : <X size={13} />}
                <span>{isRTL ? 'أحرف كبيرة وصغيرة' : 'Uppercase & lowercase'}</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: hasDigit ? '#10b981' : 'var(--neutral-500)' }}>
                {hasDigit ? <Check size={13} /> : <X size={13} />}
                <span>{isRTL ? 'رقم واحد على الأقل' : 'At least one number'}</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: hasSpecial ? '#10b981' : 'var(--neutral-500)' }}>
                {hasSpecial ? <Check size={13} /> : <X size={13} />}
                <span>{isRTL ? 'رمز خاص (!@#$%...)' : 'At least one special symbol'}</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: isMatch ? '#10b981' : 'var(--neutral-500)' }}>
                {isMatch ? <Check size={13} /> : <X size={13} />}
                <span>{isRTL ? 'تطابق كلمتي المرور' : 'Passwords match'}</span>
              </div>
            </div>

            <button
              type="submit"
              disabled={isLoading || !isPolicyValid}
              className="btn btn-accent"
              style={{
                width: '100%',
                padding: '12px',
                fontWeight: 700,
                marginTop: 'var(--space-2)',
              }}
            >
              {isLoading ? (isRTL ? 'جاري الحفظ...' : 'Saving...') : (isRTL ? 'حفظ كلمة المرور' : 'Update Password')}
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
