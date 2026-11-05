import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { ArrowLeft, Upload, AlertCircle, FileText } from 'lucide-react';
import { PageHeader, Card, Button, Input } from '../components/ui';

export default function CandidateFormPage() {
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [phoneNumber, setPhoneNumber] = useState('');
  const [consentStatus, setConsentStatus] = useState('pending');
  const [consentMethod, setConsentMethod] = useState('');
  const [resumeFile, setResumeFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const navigate = useNavigate();

  const handleFileChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      const ext = file.name.split('.').pop().toLowerCase();
      if (!['pdf', 'docx'].includes(ext)) {
        setError('Allowed file formats are .pdf and .docx only.');
        setResumeFile(null);
        return;
      }
      if (file.size > 10 * 1024 * 1024) {
        setError('Resume file size cannot exceed 10 MB.');
        setResumeFile(null);
        return;
      }
      setError('');
      setResumeFile(file);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!fullName.trim() || !email.trim()) {
      setError('Name and email are required.');
      return;
    }
    setError('');
    setLoading(true);

    const formData = new FormData();
    formData.append('full_name', fullName);
    formData.append('email', email);
    if (phoneNumber) formData.append('phone_number', phoneNumber);
    formData.append('consent_status', consentStatus);
    if (consentMethod) formData.append('consent_method', consentMethod);
    if (resumeFile) formData.append('resume', resumeFile);

    try {
      await api.post('/candidates/', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      navigate('/candidates');
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create candidate record.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: '640px' }}>
      {/* PageHeader with Back Button */}
      <PageHeader
        title="Add New Candidate"
        description="Create profile and upload candidate CV for AI question generation"
        breadcrumbs={[
          { label: 'Candidates', to: '/candidates' },
          { label: 'New Candidate' },
        ]}
      />

      <Card padding="28px">
        {error && (
          <div
            style={{
              padding: '10px 14px',
              borderRadius: 'var(--radius-sm, 6px)',
              backgroundColor: 'var(--danger-bg, #fef2f2)',
              border: '1px solid var(--danger-border, #fecaca)',
              color: 'var(--danger-text, #991b1b)',
              fontSize: 'var(--text-sm, 0.8125rem)',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              marginBottom: '20px',
            }}
          >
            <AlertCircle size={16} style={{ flexShrink: 0 }} />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div className="form-group" style={{ marginBottom: '16px' }}>
            <label
              className="form-label"
              htmlFor="fullName"
              style={{
                fontSize: 'var(--text-sm, 0.8125rem)',
                fontWeight: 500,
                color: 'var(--text-body, #374151)',
                marginBottom: '4px',
                display: 'block',
              }}
            >
              Full Name *
            </label>
            <input
              id="fullName"
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
                color: 'var(--text-body, #374151)',
                fontSize: 'var(--text-base, 0.875rem)',
              }}
            />
          </div>

          <div className="form-group" style={{ marginBottom: '16px' }}>
            <label
              className="form-label"
              htmlFor="email"
              style={{
                fontSize: 'var(--text-sm, 0.8125rem)',
                fontWeight: 500,
                color: 'var(--text-body, #374151)',
                marginBottom: '4px',
                display: 'block',
              }}
            >
              Email Address *
            </label>
            <input
              id="email"
              type="email"
              required
              className="form-input"
              placeholder="jane.doe@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              style={{
                width: '100%',
                padding: '8px 12px',
                backgroundColor: '#ffffff',
                border: '1px solid var(--border-subtle, #e2e8f0)',
                borderRadius: 'var(--radius-sm, 6px)',
                color: 'var(--text-body, #374151)',
                fontSize: 'var(--text-base, 0.875rem)',
              }}
            />
          </div>

          <div className="form-group" style={{ marginBottom: '16px' }}>
            <label
              className="form-label"
              htmlFor="phone"
              style={{
                fontSize: 'var(--text-sm, 0.8125rem)',
                fontWeight: 500,
                color: 'var(--text-body, #374151)',
                marginBottom: '4px',
                display: 'block',
              }}
            >
              Phone Number
            </label>
            <input
              id="phone"
              className="form-input"
              placeholder="+1 (555) 000-0000"
              value={phoneNumber}
              onChange={(e) => setPhoneNumber(e.target.value)}
              style={{
                width: '100%',
                padding: '8px 12px',
                backgroundColor: '#ffffff',
                border: '1px solid var(--border-subtle, #e2e8f0)',
                borderRadius: 'var(--radius-sm, 6px)',
                color: 'var(--text-body, #374151)',
                fontSize: 'var(--text-base, 0.875rem)',
              }}
            />
          </div>

          <div className="form-group" style={{ marginBottom: '16px' }}>
            <label
              className="form-label"
              htmlFor="consent"
              style={{
                fontSize: 'var(--text-sm, 0.8125rem)',
                fontWeight: 500,
                color: 'var(--text-body, #374151)',
                marginBottom: '4px',
                display: 'block',
              }}
            >
              Candidate Consent Status
            </label>
            <select
              id="consent"
              className="form-select"
              value={consentStatus}
              onChange={(e) => setConsentStatus(e.target.value)}
              style={{
                width: '100%',
                padding: '8px 12px',
                backgroundColor: '#ffffff',
                border: '1px solid var(--border-subtle, #e2e8f0)',
                borderRadius: 'var(--radius-sm, 6px)',
                color: 'var(--text-body, #374151)',
                fontSize: 'var(--text-base, 0.875rem)',
              }}
            >
              <option value="pending">Pending (Not yet granted)</option>
              <option value="granted">Granted (Explicit authorization given)</option>
              <option value="withdrawn">Withdrawn</option>
            </select>
          </div>

          {consentStatus === 'granted' && (
            <div className="form-group" style={{ marginBottom: '16px' }}>
              <label
                className="form-label"
                htmlFor="consentMethod"
                style={{
                  fontSize: 'var(--text-sm, 0.8125rem)',
                  fontWeight: 500,
                  color: 'var(--text-body, #374151)',
                  marginBottom: '4px',
                  display: 'block',
                }}
              >
                Consent Verification Method
              </label>
              <input
                id="consentMethod"
                className="form-input"
                placeholder="e.g. Email consent, Verbal agreement, Application form checkbox"
                value={consentMethod}
                onChange={(e) => setConsentMethod(e.target.value)}
                style={{
                  width: '100%',
                  padding: '8px 12px',
                  backgroundColor: '#ffffff',
                  border: '1px solid var(--border-subtle, #e2e8f0)',
                  borderRadius: 'var(--radius-sm, 6px)',
                  color: 'var(--text-body, #374151)',
                  fontSize: 'var(--text-base, 0.875rem)',
                }}
              />
            </div>
          )}

          <div className="form-group" style={{ marginBottom: '24px' }}>
            <label
              className="form-label"
              style={{
                fontSize: 'var(--text-sm, 0.8125rem)',
                fontWeight: 500,
                color: 'var(--text-body, #374151)',
                marginBottom: '4px',
                display: 'block',
              }}
            >
              Resume Document (.pdf or .docx, max 10MB)
            </label>
            <input
              type="file"
              accept=".pdf,.docx"
              onChange={handleFileChange}
              style={{
                width: '100%',
                padding: '8px 12px',
                backgroundColor: '#ffffff',
                border: '1px solid var(--border-subtle, #e2e8f0)',
                borderRadius: 'var(--radius-sm, 6px)',
                color: 'var(--text-body, #374151)',
                fontSize: 'var(--text-sm, 0.8125rem)',
              }}
            />
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <Button
              type="submit"
              variant="primary"
              disabled={loading}
              loading={loading}
              style={{ padding: '10px 20px' }}
            >
              Create Candidate
            </Button>
            <Button
              type="button"
              variant="secondary"
              onClick={() => navigate('/candidates')}
              style={{ padding: '10px 16px' }}
            >
              Cancel
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
}
