import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../../store/authStore';
import { api, ApiError } from '../../lib/apiClient';
import { Lock, CheckCircle2, AlertCircle, Shield, Check, X } from 'lucide-react';
import { BrandLogo } from '../../components/common/BrandLogo';
import { useTranslation } from '../../i18n';

export const SetPasswordPage: React.FC = () => {
  const navigate = useNavigate();
  const { user, fetchMe } = useAuthStore();
  const { isRTL } = useTranslation();

  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  // Password rules validation
  const hasMinLen = newPassword.length >= 8;
  const hasUpper = /[A-Z]/.test(newPassword);
  const hasLower = /[a-z]/.test(newPassword);
  const hasDigit = /[0-9]/.test(newPassword);
  const hasSpecial = /[^A-Za-z0-9]/.test(newPassword);
  const isMatch = Boolean(newPassword && newPassword === confirmPassword);
  const isPolicyValid = hasMinLen && hasUpper && hasLower && hasDigit && hasSpecial && isMatch;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (currentPassword && newPassword === currentPassword) {
      setError(
        isRTL
          ? 'يجب أن تختلف كلمة المرور الجديدة عن كلمة المرور الحالية.'
          : 'New password must be different from current password.'
      );
      return;
    }
    if (!isPolicyValid) {
      setError(
        isRTL
          ? 'يرجى استيفاء جميع معايير كلمة المرور القوية وتطابق التأكيد.'
          : 'Please satisfy all strong password policy criteria.'
      );
      return;
    }

    setError(null);
    setIsLoading(true);

    try {
      await api.post('/auth/activate-password', {
        current_password: currentPassword,
        new_password: newPassword,
        confirm_password: confirmPassword,
      });

      setSuccess(true);
      await fetchMe();
      setTimeout(() => {
        navigate('/dashboard');
      }, 1500);
    } catch (err: any) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError(isRTL ? 'فشل تعيين كلمة المرور. تحقق من كلمة المرور الحالية.' : 'Failed to set password. Verify current password.');
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
          maxWidth: '480px',
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
            {isRTL ? 'تعيين كلمة المرور الشخصية' : 'Set Your Personal Password'}
          </h2>
          <p className="text-sm text-muted" style={{ marginTop: 'var(--space-1)' }}>
            {isRTL
              ? `مرحباً ${user?.first_name || ''}، يرجى استبدال كلمة المرور المؤقتة بكلمة مرور سرية خاصة بك.`
              : `Welcome ${user?.first_name || ''}! Replace your temporary activation key with a personal password.`}
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
              {isRTL ? 'تم حفظ كلمة المرور بنجاح! جاري الدخول...' : 'Password activated! Loading your dashboard...'}
            </p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
            <div className="form-group">
              <label className="form-label" style={{ fontWeight: 600 }}>
                {isRTL ? 'كلمة المرور المؤقتة / الحالية' : 'Current / Activation Password'}
              </label>
              <div style={{ position: 'relative' }}>
                <input
                  type="password"
                  required
                  value={currentPassword}
                  onChange={(e) => setCurrentPassword(e.target.value)}
                  placeholder="••••••••"
                  className="form-input"
                />
              </div>
            </div>

            <div className="form-group">
              <label className="form-label" style={{ fontWeight: 600 }}>
                {isRTL ? 'كلمة المرور الجديدة' : 'New Personal Password'}
              </label>
              <div style={{ position: 'relative' }}>
                <input
                  type="password"
                  required
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  placeholder="••••••••"
                  className="form-input"
                />
              </div>
            </div>

            <div className="form-group">
              <label className="form-label" style={{ fontWeight: 600 }}>
                {isRTL ? 'تأكيد كلمة المرور الجديدة' : 'Confirm New Password'}
              </label>
              <div style={{ position: 'relative' }}>
                <input
                  type="password"
                  required
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="••••••••"
                  className="form-input"
                />
              </div>
            </div>

            {/* Password strength criteria checklist */}
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
                <span>{isRTL ? 'أحرف كبيرة وصغيرة (A-Z, a-z)' : 'Uppercase and lowercase letters'}</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: hasDigit ? '#10b981' : 'var(--neutral-500)' }}>
                {hasDigit ? <Check size={13} /> : <X size={13} />}
                <span>{isRTL ? 'رقم واحد على الأقل (0-9)' : 'At least one number (0-9)'}</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: hasSpecial ? '#10b981' : 'var(--neutral-500)' }}>
                {hasSpecial ? <Check size={13} /> : <X size={13} />}
                <span>{isRTL ? 'رمز خاص (!@#$%...)' : 'At least one special symbol (!@#$%...)'}</span>
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
              {isLoading ? (isRTL ? 'جاري الحفظ...' : 'Activating...') : (isRTL ? 'حفظ وتفعيل الحساب' : 'Save & Activate Account')}
            </button>
          </form>
        )}
      </div>
    </div>
  );
};
