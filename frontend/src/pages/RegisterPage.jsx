import React, { useState, useEffect } from 'react';
import { useNavigate, useSearchParams, Link } from 'react-router-dom';
import { api } from '../api/client';
import { Sparkles, CheckCircle, AlertCircle, ArrowRight, ArrowLeft, ShieldCheck, Key } from 'lucide-react';

export default function RegisterPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  const [tokenInput, setTokenInput] = useState(searchParams.get('token') || '');
  const [invitedEmail, setInvitedEmail] = useState('');
  const [isValidating, setIsValidating] = useState(false);
  const [tokenValidated, setTokenValidated] = useState(false);
  const [validationError, setValidationError] = useState('');

  const [fullName, setFullName] = useState('');
  const [password, setPassword] = useState('');
  const [passwordConfirm, setPasswordConfirm] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [registerError, setRegisterError] = useState('');
  const [successMessage, setSuccessMessage] = useState('');

  // Auto-validate token if present in query parameter
  useEffect(() => {
    const urlToken = searchParams.get('token');
    if (urlToken) {
      validateToken(urlToken);
    }
  }, [searchParams]);

  const validateToken = async (tok) => {
    const raw = (tok || tokenInput).trim();
    if (!raw) {
      setValidationError('Please enter a valid invitation token.');
      return;
    }

    setIsValidating(true);
    setValidationError('');
    setRegisterError('');

    try {
      const resp = await api.get(`/auth/invitations/validate/?token=${encodeURIComponent(raw)}`);
      if (resp.data.valid) {
        setTokenValidated(true);
        setInvitedEmail(resp.data.email);
        setValidationError('');
      } else {
        setTokenValidated(false);
        setValidationError(resp.data.detail || 'Invitation is invalid or has expired.');
      }
    } catch (err) {
      setTokenValidated(false);
      setInvitedEmail('');
      setValidationError(err.response?.data?.detail || 'Invitation token is invalid, expired, or revoked.');
    } finally {
      setIsValidating(false);
    }
  };

  const handleRegister = async (e) => {
    e.preventDefault();
    setRegisterError('');

    if (!fullName.trim()) {
      setRegisterError('Please enter your full name.');
      return;
    }
    if (!password) {
      setRegisterError('Please enter a password.');
      return;
    }
    if (password !== passwordConfirm) {
      setRegisterError('Passwords do not match.');
      return;
    }

    setSubmitting(true);
    try {
      const resp = await api.post('/auth/register/', {
        token: tokenInput.trim(),
        full_name: fullName.trim(),
        password,
        password_confirm: passwordConfirm,
      });

      setSuccessMessage(resp.data.message || 'Registration successful! Redirecting to login...');
      setTimeout(() => {
        navigate('/login');
      }, 2000);
    } catch (err) {
      if (err.response?.data?.password) {
        const pwErrors = Array.isArray(err.response.data.password)
          ? err.response.data.password.join(' ')
          : err.response.data.password;
        setRegisterError(pwErrors);
      } else if (err.response?.data?.token) {
        setRegisterError(err.response.data.token);
      } else if (err.response?.data?.detail) {
        setRegisterError(err.response.data.detail);
      } else {
        setRegisterError('Registration failed. Please check your inputs or invitation status.');
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      style={{
        display: 'flex',
        minHeight: '100vh',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'radial-gradient(ellipse at top, #1e1b4b 0%, #0a0d14 70%)',
        padding: '24px',
      }}
    >
      <div
        className="glass-panel"
        style={{
          width: '100%',
          maxWidth: '460px',
          padding: '36px',
        }}
      >
        <div style={{ textAlign: 'center', marginBottom: '24px' }}>
          <div
            style={{
              width: '48px',
              height: '48px',
              borderRadius: '12px',
              background: 'linear-gradient(135deg, var(--primary), var(--secondary))',
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#fff',
              boxShadow: 'var(--shadow-glow)',
              marginBottom: '16px',
            }}
          >
            <ShieldCheck size={24} />
          </div>
          <h2 style={{ fontSize: '1.5rem', fontWeight: 800, color: '#fff', letterSpacing: '-0.02em' }}>
            Recruiter Registration
          </h2>
          <p style={{ fontSize: '0.875rem', color: 'var(--text-muted)', marginTop: '4px' }}>
            Join AI Interviewer with an authorized administrator invitation
          </p>
        </div>

        {/* Success Alert */}
        {successMessage && (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
              padding: '12px 14px',
              borderRadius: 'var(--radius-md)',
              background: 'rgba(16, 185, 129, 0.1)',
              border: '1px solid rgba(16, 185, 129, 0.3)',
              color: '#34d399',
              fontSize: '0.875rem',
              marginBottom: '20px',
            }}
          >
            <CheckCircle size={18} style={{ flexShrink: 0 }} />
            <span>{successMessage}</span>
          </div>
        )}

        {/* Validation Error Alert */}
        {validationError && (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
              padding: '12px 14px',
              borderRadius: 'var(--radius-md)',
              background: 'var(--danger-bg)',
              border: '1px solid rgba(239, 68, 68, 0.3)',
              color: '#f87171',
              fontSize: '0.8125rem',
              marginBottom: '20px',
            }}
          >
            <AlertCircle size={18} style={{ flexShrink: 0 }} />
            <span>{validationError}</span>
          </div>
        )}

        {/* Registration Error Alert */}
        {registerError && (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
              padding: '12px 14px',
              borderRadius: 'var(--radius-md)',
              background: 'var(--danger-bg)',
              border: '1px solid rgba(239, 68, 68, 0.3)',
              color: '#f87171',
              fontSize: '0.8125rem',
              marginBottom: '20px',
            }}
          >
            <AlertCircle size={18} style={{ flexShrink: 0 }} />
            <span>{registerError}</span>
          </div>
        )}

        {/* Step 1: Token Input & Validation (if not yet validated) */}
        {!tokenValidated ? (
          <div>
            <div className="form-group">
              <label className="form-label" htmlFor="token">
                Invitation Token
              </label>
              <div style={{ position: 'relative' }}>
                <input
                  id="token"
                  type="text"
                  required
                  className="form-input"
                  placeholder="Paste invitation token from admin"
                  value={tokenInput}
                  onChange={(e) => setTokenInput(e.target.value)}
                />
              </div>
              <p style={{ fontSize: '0.75rem', color: 'var(--text-faint)', marginTop: '6px' }}>
                Registration requires an unexpired invitation issued by an Administrator.
              </p>
            </div>

            <button
              type="button"
              className="btn btn-primary"
              disabled={isValidating || !tokenInput.trim()}
              onClick={() => validateToken(tokenInput)}
              style={{ width: '100%', marginTop: '8px', padding: '12px' }}
            >
              {isValidating ? 'Validating Token...' : 'Verify Invitation'}
              {!isValidating && <ArrowRight size={16} />}
            </button>
          </div>
        ) : (
          /* Step 2: Validated Invitation -> Account Details Form */
          <form onSubmit={handleRegister}>
            {/* Display Verified Email (Read-Only) */}
            <div
              style={{
                padding: '12px 14px',
                borderRadius: 'var(--radius-md)',
                background: 'rgba(99, 102, 241, 0.08)',
                border: '1px solid rgba(99, 102, 241, 0.25)',
                marginBottom: '16px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
              }}
            >
              <div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Authorized Account Email</div>
                <div style={{ fontSize: '0.9375rem', fontWeight: 700, color: '#fff' }}>{invitedEmail}</div>
              </div>
              <span className="badge badge-completed">Verified</span>
            </div>

            <div className="form-group">
              <label className="form-label" htmlFor="fullName">
                Full Name
              </label>
              <input
                id="fullName"
                type="text"
                required
                className="form-input"
                placeholder="Jane Doe"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
              />
            </div>

            <div className="form-group">
              <label className="form-label" htmlFor="password">
                Password
              </label>
              <input
                id="password"
                type="password"
                required
                className="form-input"
                placeholder="Minimum 8 characters"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>

            <div className="form-group">
              <label className="form-label" htmlFor="passwordConfirm">
                Confirm Password
              </label>
              <input
                id="passwordConfirm"
                type="password"
                required
                className="form-input"
                placeholder="Re-enter password"
                value={passwordConfirm}
                onChange={(e) => setPasswordConfirm(e.target.value)}
              />
            </div>

            <button
              type="submit"
              className="btn btn-primary"
              disabled={submitting}
              style={{ width: '100%', marginTop: '12px', padding: '12px' }}
            >
              {submitting ? 'Creating Recruiter Account...' : 'Complete Registration'}
              {!submitting && <ArrowRight size={16} />}
            </button>
          </form>
        )}

        <div style={{ marginTop: '24px', textAlign: 'center' }}>
          <Link
            to="/login"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              fontSize: '0.8125rem',
              color: 'var(--text-muted)',
              textDecoration: 'none',
            }}
          >
            <ArrowLeft size={14} />
            <span>Back to Sign In</span>
          </Link>
        </div>
      </div>
    </div>
  );
}

