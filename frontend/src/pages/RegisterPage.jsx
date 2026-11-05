import React, { useState, useEffect } from 'react';
import { useNavigate, useSearchParams, Link } from 'react-router-dom';
import { api } from '../api/client';
import { CheckCircle, AlertCircle, ArrowRight, ArrowLeft, Key, Eye, EyeOff } from 'lucide-react';
import { Button, Card, Input } from '../components/ui';

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
  const [showPassword, setShowPassword] = useState(false);
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
        backgroundColor: 'var(--bg-primary, #f8fafc)',
        padding: '24px',
      }}
    >
      <div style={{ width: '100%', maxWidth: '440px' }}>
        {/* Brand Header */}
        <div style={{ textAlign: 'center', marginBottom: '24px' }}>
          <div
            style={{
              width: '40px',
              height: '40px',
              borderRadius: '8px',
              backgroundColor: 'var(--primary, #1e293b)',
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#ffffff',
              fontWeight: 700,
              fontSize: '1.125rem',
              letterSpacing: '-0.02em',
              marginBottom: '12px',
              boxShadow: 'var(--shadow-sm)',
            }}
          >
            AI
          </div>
          <h2
            style={{
              fontSize: 'var(--text-xl, 1.25rem)',
              fontWeight: 700,
              color: 'var(--text-main, #202733)',
              letterSpacing: '-0.015em',
              margin: 0,
            }}
          >
            Recruiter Registration
          </h2>
          <p
            style={{
              fontSize: 'var(--text-sm, 0.8125rem)',
              color: 'var(--text-muted, #737d8c)',
              marginTop: '4px',
            }}
          >
            Join AI Interviewer with an authorized administrator invitation
          </p>
        </div>

        {/* Card Body */}
        <Card padding="28px">
          {/* Success Alert */}
          {successMessage && (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '10px 12px',
                borderRadius: 'var(--radius-sm, 6px)',
                backgroundColor: 'var(--success-bg, #ecfdf5)',
                border: '1px solid var(--success-border, #bbf7d0)',
                color: 'var(--success-text, #166534)',
                fontSize: 'var(--text-sm, 0.8125rem)',
                marginBottom: '16px',
              }}
            >
              <CheckCircle size={16} style={{ flexShrink: 0 }} />
              <span>{successMessage}</span>
            </div>
          )}

          {/* Registration Error */}
          {registerError && (
            <div
              style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: '8px',
                padding: '10px 12px',
                borderRadius: 'var(--radius-sm, 6px)',
                backgroundColor: 'var(--danger-bg, #fef2f2)',
                border: '1px solid var(--danger-border, #fecaca)',
                color: 'var(--danger-text, #991b1b)',
                fontSize: 'var(--text-sm, 0.8125rem)',
                marginBottom: '16px',
              }}
            >
              <AlertCircle size={16} style={{ flexShrink: 0, marginTop: '2px' }} />
              <span>{registerError}</span>
            </div>
          )}

          {/* Step 1: Token Input / Validation */}
          {!tokenValidated ? (
            <div>
              <div className="form-group" style={{ marginBottom: '16px' }}>
                <label
                  className="form-label"
                  htmlFor="tokenInput"
                  style={{
                    fontSize: 'var(--text-sm, 0.8125rem)',
                    fontWeight: 500,
                    color: 'var(--text-main, #202733)',
                    marginBottom: '4px',
                    display: 'block',
                  }}
                >
                  Invitation Token
                </label>
                <input
                  id="tokenInput"
                  type="text"
                  required
                  className="form-input"
                  placeholder="Paste invitation token here"
                  value={tokenInput}
                  onChange={(e) => {
                    setTokenInput(e.target.value);
                    setValidationError('');
                  }}
                  style={{
                    width: '100%',
                    padding: '8px 12px',
                    backgroundColor: '#ffffff',
                    border: '1px solid var(--border-subtle, #e2e8f0)',
                    borderRadius: 'var(--radius-sm, 6px)',
                    color: 'var(--text-main, #202733)',
                    fontSize: 'var(--text-base, 0.875rem)',
                  }}
                />
              </div>

              {validationError && (
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: '8px',
                    padding: '10px 12px',
                    borderRadius: 'var(--radius-sm, 6px)',
                    backgroundColor: 'var(--danger-bg, #fef2f2)',
                    border: '1px solid var(--danger-border, #fecaca)',
                    color: 'var(--danger-text, #991b1b)',
                    fontSize: 'var(--text-sm, 0.8125rem)',
                    marginBottom: '16px',
                  }}
                >
                  <AlertCircle size={16} style={{ flexShrink: 0, marginTop: '2px' }} />
                  <span>{validationError}</span>
                </div>
              )}

              <Button
                variant="primary"
                onClick={() => validateToken(tokenInput)}
                disabled={!tokenInput.trim() || isValidating}
                loading={isValidating}
                style={{ width: '100%', padding: '10px 14px' }}
              >
                {isValidating ? 'Validating Token...' : 'Verify Invitation'}
              </Button>
            </div>
          ) : (
            /* Step 2: Validated Invitation Form */
            <form onSubmit={handleRegister}>
              <div
                style={{
                  padding: '10px 12px',
                  borderRadius: 'var(--radius-sm, 6px)',
                  backgroundColor: 'var(--bg-primary, #f8fafc)',
                  border: '1px solid var(--border-subtle, #e2e8f0)',
                  marginBottom: '16px',
                  fontSize: 'var(--text-sm, 0.8125rem)',
                }}
              >
                <div style={{ color: 'var(--text-muted, #737d8c)', fontSize: 'var(--text-xs, 0.75rem)' }}>
                  Verified Recruiter Email:
                </div>
                <div style={{ fontWeight: 600, color: 'var(--text-main, #202733)', marginTop: '2px' }}>
                  {invitedEmail}
                </div>
              </div>

              <div className="form-group" style={{ marginBottom: '14px' }}>
                <label
                  className="form-label"
                  htmlFor="fullName"
                  style={{
                    fontSize: 'var(--text-sm, 0.8125rem)',
                    fontWeight: 500,
                    color: 'var(--text-main, #202733)',
                    marginBottom: '4px',
                    display: 'block',
                  }}
                >
                  Full Name
                </label>
                <input
                  id="fullName"
                  type="text"
                  required
                  className="form-input"
                  placeholder="e.g. Jane Doe"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '8px 12px',
                    backgroundColor: '#ffffff',
                    border: '1px solid var(--border-subtle, #e2e8f0)',
                    borderRadius: 'var(--radius-sm, 6px)',
                    color: 'var(--text-main, #202733)',
                    fontSize: 'var(--text-base, 0.875rem)',
                  }}
                />
              </div>

              <div className="form-group" style={{ marginBottom: '14px' }}>
                <label
                  className="form-label"
                  htmlFor="password"
                  style={{
                    fontSize: 'var(--text-sm, 0.8125rem)',
                    fontWeight: 500,
                    color: 'var(--text-main, #202733)',
                    marginBottom: '4px',
                    display: 'block',
                  }}
                >
                  Password
                </label>
                <div style={{ position: 'relative' }}>
                  <input
                    id="password"
                    type={showPassword ? 'text' : 'password'}
                    required
                    className="form-input"
                    placeholder="Minimum 8 characters"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    style={{
                      width: '100%',
                      padding: '8px 36px 8px 12px',
                      backgroundColor: '#ffffff',
                      border: '1px solid var(--border-subtle, #e2e8f0)',
                      borderRadius: 'var(--radius-sm, 6px)',
                      color: 'var(--text-main, #202733)',
                      fontSize: 'var(--text-base, 0.875rem)',
                    }}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    aria-label={showPassword ? 'Hide' : 'Show'}
                    title={showPassword ? 'Hide password' : 'Show password'}
                    style={{
                      position: 'absolute',
                      right: '10px',
                      top: '50%',
                      transform: 'translateY(-50%)',
                      background: 'none',
                      border: 'none',
                      color: 'var(--text-muted, #737d8c)',
                      cursor: 'pointer',
                      padding: '2px',
                      display: 'flex',
                      alignItems: 'center',
                    }}
                  >
                    {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
              </div>

              <div className="form-group" style={{ marginBottom: '20px' }}>
                <label
                  className="form-label"
                  htmlFor="passwordConfirm"
                  style={{
                    fontSize: 'var(--text-sm, 0.8125rem)',
                    fontWeight: 500,
                    color: 'var(--text-main, #202733)',
                    marginBottom: '4px',
                    display: 'block',
                  }}
                >
                  Confirm Password
                </label>
                <input
                  id="passwordConfirm"
                  type={showPassword ? 'text' : 'password'}
                  required
                  className="form-input"
                  placeholder="Repeat password"
                  value={passwordConfirm}
                  onChange={(e) => setPasswordConfirm(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '8px 12px',
                    backgroundColor: '#ffffff',
                    border: '1px solid var(--border-subtle, #e2e8f0)',
                    borderRadius: 'var(--radius-sm, 6px)',
                    color: 'var(--text-main, #202733)',
                    fontSize: 'var(--text-base, 0.875rem)',
                  }}
                />
              </div>

              <Button
                type="submit"
                variant="primary"
                disabled={submitting}
                loading={submitting}
                style={{ width: '100%', padding: '10px 14px' }}
              >
                Complete Registration
              </Button>
            </form>
          )}

          {/* Back to Login */}
          <div
            style={{
              marginTop: '20px',
              paddingTop: '16px',
              borderTop: '1px solid var(--border-subtle, #e2e8f0)',
              textAlign: 'center',
            }}
          >
            <Link
              to="/login"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                color: 'var(--text-muted, #737d8c)',
                fontSize: 'var(--text-sm, 0.8125rem)',
                textDecoration: 'none',
                fontWeight: 500,
                transition: 'color 0.15s ease',
              }}
              onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--text-main, #202733)')}
              onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--text-muted, #737d8c)')}
            >
              <ArrowLeft size={14} />
              <span>Back to Login</span>
            </Link>
          </div>
        </Card>
      </div>
    </div>
  );
}
