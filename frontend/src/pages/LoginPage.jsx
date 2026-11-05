import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Lock, Mail, AlertCircle, ArrowRight, UserPlus, Eye, EyeOff } from 'lucide-react';
import { Button, Card } from '../components/ui';

export default function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!email.trim() || !password.trim()) {
      setError('Please enter both email and password.');
      return;
    }
    setError('');
    setLoading(true);

    try {
      const authData = await login(email, password);
      if (authData?.role === 'admin') {
        navigate('/admin/dashboard');
      } else {
        navigate('/dashboard');
      }
    } catch (err) {
      if (err.response?.data?.detail) {
        setError(err.response.data.detail);
      } else if (err.response?.status === 401) {
        setError('Invalid email or password. Please verify credentials.');
      } else {
        setError('Unable to authenticate with backend. Please ensure the Django API is running.');
      }
    } finally {
      setLoading(false);
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
      <div style={{ width: '100%', maxWidth: '400px' }}>
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
            Recruiter Login
          </h2>
          <p
            style={{
              fontSize: 'var(--text-sm, 0.8125rem)',
              color: 'var(--text-muted, #737d8c)',
              marginTop: '4px',
            }}
          >
            Sign in to manage candidates and AI interview plans
          </p>
        </div>

        {/* Card Form */}
        <Card padding="28px">
          {error && (
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
                lineHeight: 1.4,
              }}
            >
              <AlertCircle size={16} style={{ flexShrink: 0, marginTop: '2px' }} />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit}>
            <div className="form-group" style={{ marginBottom: '16px' }}>
              <label
                className="form-label"
                htmlFor="email"
                style={{
                  fontSize: 'var(--text-sm, 0.8125rem)',
                  fontWeight: 500,
                  color: 'var(--text-main, #202733)',
                  marginBottom: '4px',
                  display: 'block',
                }}
              >
                Email Address
              </label>
              <input
                id="email"
                type="email"
                required
                className="form-input"
                placeholder="recruiter@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
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

            <div className="form-group" style={{ marginBottom: '20px' }}>
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
                  placeholder="••••••••••••"
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

            <Button
              type="submit"
              variant="primary"
              disabled={loading}
              loading={loading}
              style={{ width: '100%', padding: '10px 14px' }}
            >
              Sign In
            </Button>
          </form>

          {/* Invitation Registration Link */}
          <div
            style={{
              marginTop: '20px',
              paddingTop: '16px',
              borderTop: '1px solid var(--border-subtle, #e2e8f0)',
              textAlign: 'center',
            }}
          >
            <div style={{ fontSize: 'var(--text-xs, 0.75rem)', color: 'var(--text-muted, #737d8c)' }}>
              Have an invitation token?
            </div>
            <Link
              to="/register"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                marginTop: '6px',
                color: 'var(--primary-accent, #2563eb)',
                fontWeight: 600,
                fontSize: 'var(--text-sm, 0.8125rem)',
                textDecoration: 'none',
                transition: 'color 0.15s ease',
              }}
            >
              <UserPlus size={14} />
              <span>Register with Invitation</span>
            </Link>
          </div>
        </Card>
      </div>
    </div>
  );
}
