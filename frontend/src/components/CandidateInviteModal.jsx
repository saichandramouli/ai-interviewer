import React, { useState, useEffect } from 'react';
import { api } from '../api/client';
import { Mail, Send, Copy, Check, AlertCircle, Clock, X, CheckCircle, RefreshCw, AlertTriangle } from 'lucide-react';

export default function CandidateInviteModal({ interview, isOpen, onClose }) {
  const [loading, setLoading] = useState(false);
  const [resending, setResending] = useState(false);
  const [replacing, setReplacing] = useState(false);
  const [confirmReplace, setConfirmReplace] = useState(false);
  const [statusData, setStatusData] = useState(null);
  const [copied, setCopied] = useState(false);
  const [generatedLink, setGeneratedLink] = useState('');
  const [feedback, setFeedback] = useState(null);

  useEffect(() => {
    if (isOpen && interview?.id) {
      fetchStatus();
      setCopied(false);
      setFeedback(null);
      setGeneratedLink('');
      setConfirmReplace(false);
    }
  }, [isOpen, interview?.id]);

  const fetchStatus = async () => {
    try {
      setLoading(true);
      const res = await api.get(`/interviews/${interview.id}/candidate-link-status/`);
      setStatusData(res.data);
    } catch (err) {
      console.error('Failed to load candidate link status', err);
    } finally {
      setLoading(false);
    }
  };

  const handleGenerateLink = async () => {
    try {
      setLoading(true);
      setFeedback(null);
      const res = await api.post(`/interviews/${interview.id}/generate-candidate-link/`, { valid_hours: 72 });
      setGeneratedLink(res.data.candidate_url);
      setFeedback({
        type: 'success',
        message: res.data.email_enqueued
          ? 'Interview link created and invitation email queued successfully!'
          : 'Interview link created. Note: Candidate has no registered email, so invitation was not sent.',
      });
      fetchStatus();
    } catch (err) {
      setFeedback({
        type: 'error',
        message: err.response?.data?.detail || 'Failed to generate candidate interview link.',
      });
    } finally {
      setLoading(false);
    }
  };

  const handleResendInvitation = async () => {
    try {
      setResending(true);
      setFeedback(null);
      const res = await api.post(`/interviews/${interview.id}/resend-candidate-link/`, { valid_hours: 72 });
      if (res.data.candidate_url) {
        setGeneratedLink(res.data.candidate_url);
      }
      setFeedback({
        type: 'success',
        message: 'Existing invitation email enqueued successfully. Prior candidate link remains valid.',
      });
      fetchStatus();
    } catch (err) {
      setFeedback({
        type: 'error',
        message: err.response?.data?.detail || 'Failed to resend interview invitation.',
      });
    } finally {
      setResending(false);
    }
  };

  const handleReplaceLink = async () => {
    try {
      setReplacing(true);
      setFeedback(null);
      const res = await api.post(`/interviews/${interview.id}/replace-candidate-link/`, { valid_hours: 72 });
      setGeneratedLink(res.data.candidate_url);
      setConfirmReplace(false);
      setFeedback({
        type: 'success',
        message: 'Prior links revoked. Fresh replacement link generated and emailed to candidate.',
      });
      fetchStatus();
    } catch (err) {
      setFeedback({
        type: 'error',
        message: err.response?.data?.detail || 'Failed to generate replacement link.',
      });
    } finally {
      setReplacing(false);
    }
  };

  const handleCopyLink = () => {
    if (!generatedLink) return;
    navigator.clipboard.writeText(generatedLink);
    setCopied(true);
    setTimeout(() => setCopied(false), 3000);
  };

  if (!isOpen) return null;

  const isEmailSending = statusData?.delivery_status === 'sending';
  const isEmailSent = statusData?.delivery_status === 'sent';
  const isEmailFailed = statusData?.delivery_status === 'failed';
  const isTokenExpired = statusData?.is_expired;
  const isTokenRevoked = statusData?.is_revoked;
  const canResend = statusData?.has_token && statusData?.is_valid && !isTokenExpired && !isTokenRevoked;

  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: 'rgba(0, 0, 0, 0.7)',
        backdropFilter: 'blur(4px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 9999,
        padding: '16px',
      }}
    >
      <div
        className="glass-panel"
        style={{
          width: '100%',
          maxWidth: '580px',
          background: '#111827',
          border: '1px solid rgba(255, 255, 255, 0.12)',
          borderRadius: '16px',
          padding: '24px',
          boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.5), 0 8px 10px -6px rgba(0, 0, 0, 0.5)',
          color: '#f9fafb',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div
              style={{
                width: '36px',
                height: '36px',
                borderRadius: '8px',
                background: 'rgba(99, 102, 241, 0.2)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#818cf8',
              }}
            >
              <Mail size={20} />
            </div>
            <div>
              <h3 style={{ fontSize: '1.125rem', fontWeight: 700, margin: 0, color: '#fff' }}>
                Candidate Interview Invitation
              </h3>
              <p style={{ fontSize: '0.8125rem', color: '#9ca3af', margin: '2px 0 0 0' }}>
                {interview?.candidate_name || interview?.candidate} · {interview?.job_title || interview?.job}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            style={{
              background: 'transparent',
              border: 'none',
              color: '#9ca3af',
              cursor: 'pointer',
              padding: '6px',
            }}
          >
            <X size={20} />
          </button>
        </div>

        {feedback && (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
              padding: '12px 14px',
              borderRadius: '8px',
              marginBottom: '18px',
              fontSize: '0.875rem',
              background: feedback.type === 'success' ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.15)',
              border: `1px solid ${feedback.type === 'success' ? '#10b981' : '#ef4444'}`,
              color: feedback.type === 'success' ? '#34d399' : '#f87171',
            }}
          >
            {feedback.type === 'success' ? <CheckCircle size={18} /> : <AlertCircle size={18} />}
            <span>{feedback.message}</span>
          </div>
        )}

        {/* Link and Delivery Status Card */}
        <div
          style={{
            background: 'rgba(255, 255, 255, 0.03)',
            border: '1px solid rgba(255, 255, 255, 0.08)',
            borderRadius: '12px',
            padding: '16px',
            marginBottom: '20px',
          }}
        >
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px', fontSize: '0.875rem' }}>
            <div>
              <span style={{ color: '#9ca3af', fontSize: '0.75rem', textTransform: 'uppercase', fontWeight: 600 }}>
                Candidate Email
              </span>
              <p style={{ margin: '4px 0 0 0', fontWeight: 500, color: '#f3f4f6' }}>
                {statusData?.recipient_email || statusData?.candidate_email || 'Not registered'}
              </p>
            </div>

            <div>
              <span style={{ color: '#9ca3af', fontSize: '0.75rem', textTransform: 'uppercase', fontWeight: 600 }}>
                Email Delivery Status
              </span>
              <div style={{ margin: '4px 0 0 0' }}>
                {statusData?.has_token ? (
                  <span
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '6px',
                      padding: '2px 8px',
                      borderRadius: '9999px',
                      fontSize: '0.75rem',
                      fontWeight: 600,
                      background:
                        isEmailSent
                          ? 'rgba(16, 185, 129, 0.2)'
                          : isEmailSending
                          ? 'rgba(99, 102, 241, 0.2)'
                          : isEmailFailed
                          ? 'rgba(239, 68, 68, 0.2)'
                          : 'rgba(245, 158, 11, 0.2)',
                      color:
                        isEmailSent
                          ? '#34d399'
                          : isEmailSending
                          ? '#818cf8'
                          : isEmailFailed
                          ? '#f87171'
                          : '#fbbf24',
                    }}
                  >
                    {isEmailSending && <RefreshCw size={12} className="spin" />}
                    {statusData.delivery_status?.toUpperCase() || 'UNKNOWN'}
                  </span>
                ) : (
                  <span style={{ color: '#6b7280', fontSize: '0.8125rem' }}>No link generated</span>
                )}
              </div>
            </div>

            {statusData?.has_token && (
              <>
                <div>
                  <span style={{ color: '#9ca3af', fontSize: '0.75rem', textTransform: 'uppercase', fontWeight: 600 }}>
                    Token Status
                  </span>
                  <p
                    style={{
                      margin: '4px 0 0 0',
                      fontWeight: 600,
                      color: isTokenRevoked ? '#f87171' : isTokenExpired ? '#f59e0b' : '#34d399',
                    }}
                  >
                    {isTokenRevoked ? 'Revoked' : isTokenExpired ? 'Expired' : 'Active & Valid'}
                  </p>
                </div>

                <div>
                  <span style={{ color: '#9ca3af', fontSize: '0.75rem', textTransform: 'uppercase', fontWeight: 600 }}>
                    Expires At
                  </span>
                  <p style={{ margin: '4px 0 0 0', fontWeight: 500, color: '#f3f4f6', fontSize: '0.8125rem' }}>
                    {statusData.expires_at ? new Date(statusData.expires_at).toLocaleString() : 'N/A'}
                  </p>
                </div>
              </>
            )}
          </div>

          {statusData?.delivery_error && (
            <div style={{ marginTop: '12px', fontSize: '0.8125rem', color: '#f87171' }}>
              <strong>Delivery Error:</strong> {statusData.delivery_error}
            </div>
          )}
        </div>

        {/* Copy Link fallback section */}
        {generatedLink && (
          <div style={{ marginBottom: '20px' }}>
            <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, color: '#9ca3af', marginBottom: '6px' }}>
              SECURE CANDIDATE INTERVIEW LINK
            </label>
            <div style={{ display: 'flex', gap: '8px' }}>
              <input
                type="text"
                readOnly
                value={generatedLink}
                style={{
                  flex: 1,
                  background: 'rgba(0, 0, 0, 0.4)',
                  border: '1px solid rgba(255, 255, 255, 0.15)',
                  borderRadius: '8px',
                  padding: '8px 12px',
                  color: '#e5e7eb',
                  fontSize: '0.8125rem',
                }}
              />
              <button
                onClick={handleCopyLink}
                className="btn btn-secondary"
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  padding: '8px 14px',
                  fontSize: '0.8125rem',
                  fontWeight: 600,
                }}
              >
                {copied ? <Check size={16} style={{ color: '#10b981' }} /> : <Copy size={16} />}
                <span>{copied ? 'Copied' : 'Copy'}</span>
              </button>
            </div>
          </div>
        )}

        {/* Confirmation dialogue for generating replacement link */}
        {confirmReplace && (
          <div
            style={{
              padding: '14px',
              borderRadius: '8px',
              background: 'rgba(239, 68, 68, 0.1)',
              border: '1px solid rgba(239, 68, 68, 0.3)',
              marginBottom: '16px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: '10px' }}>
              <AlertTriangle size={20} style={{ color: '#f87171', flexShrink: 0, marginTop: '2px' }} />
              <div>
                <h4 style={{ fontSize: '0.875rem', fontWeight: 700, margin: 0, color: '#f87171' }}>
                  Generate Replacement Link?
                </h4>
                <p style={{ fontSize: '0.8125rem', color: '#d1d5db', margin: '4px 0 10px 0', lineHeight: 1.5 }}>
                  This will <strong>revoke and invalidate all previously issued candidate links</strong>. The candidate will not be able to use older links.
                </p>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <button
                    onClick={handleReplaceLink}
                    disabled={replacing}
                    className="btn btn-danger"
                    style={{ padding: '6px 14px', fontSize: '0.75rem', fontWeight: 600 }}
                  >
                    {replacing ? 'Revoking & Generating...' : 'Confirm Revoke & Replace'}
                  </button>
                  <button
                    onClick={() => setConfirmReplace(false)}
                    className="btn btn-secondary"
                    style={{ padding: '6px 14px', fontSize: '0.75rem' }}
                  >
                    Cancel
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Action Buttons */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '24px' }}>
          <button
            onClick={onClose}
            className="btn btn-secondary"
            style={{ padding: '8px 16px', fontSize: '0.875rem' }}
          >
            Close
          </button>

          {!statusData?.has_token ? (
            <button
              onClick={handleGenerateLink}
              disabled={loading}
              className="btn btn-primary"
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '8px 18px',
                fontSize: '0.875rem',
                fontWeight: 600,
              }}
            >
              {loading ? (
                <>
                  <RefreshCw size={16} className="spin" />
                  <span>Generating...</span>
                </>
              ) : (
                <>
                  <Send size={16} />
                  <span>Generate & Send Invite</span>
                </>
              )}
            </button>
          ) : (
            <>
              {/* Replace link button */}
              <button
                onClick={() => setConfirmReplace(true)}
                disabled={replacing || interview?.status === 'completed' || interview?.status === 'cancelled'}
                className="btn btn-secondary"
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  padding: '8px 14px',
                  fontSize: '0.875rem',
                  borderColor: '#ef4444',
                  color: '#f87171',
                }}
                title="Revoke prior links and create a fresh replacement token"
              >
                <span>Replace Link</span>
              </button>

              {/* Resend existing invitation button */}
              <button
                onClick={handleResendInvitation}
                disabled={
                  !canResend ||
                  resending ||
                  isEmailSending ||
                  interview?.status === 'completed' ||
                  interview?.status === 'cancelled'
                }
                className="btn btn-primary"
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  padding: '8px 18px',
                  fontSize: '0.875rem',
                  fontWeight: 600,
                }}
                title={
                  !canResend
                    ? 'Cannot resend expired or revoked link. Use Replace Link.'
                    : 'Resend invitation email without changing existing link'
                }
              >
                {resending ? (
                  <>
                    <RefreshCw size={16} className="spin" />
                    <span>Resending...</span>
                  </>
                ) : (
                  <>
                    <Send size={16} />
                    <span>Resend Existing Link</span>
                  </>
                )}
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
