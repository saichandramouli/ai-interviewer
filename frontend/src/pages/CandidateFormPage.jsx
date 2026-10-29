import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { ArrowLeft, Upload, AlertCircle } from 'lucide-react';

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
      <button
        onClick={() => navigate('/candidates')}
        className="btn btn-secondary"
        style={{ marginBottom: '20px', padding: '6px 12px', fontSize: '0.8125rem' }}
      >
        <ArrowLeft size={14} />
        <span>Back to Candidates</span>
      </button>

      <div className="glass-panel" style={{ padding: '32px' }}>
        <h2 style={{ fontSize: '1.5rem', fontWeight: 800, color: '#fff', marginBottom: '8px' }}>
          Add New Candidate
        </h2>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem', marginBottom: '24px' }}>
          Create profile and upload candidate CV for AI question generation
        </p>

        {error && (
          <div
            style={{
              padding: '12px 14px',
              borderRadius: 'var(--radius-md)',
              background: 'var(--danger-bg)',
              color: '#f87171',
              fontSize: '0.8125rem',
              display: 'flex',
              gap: '8px',
              marginBottom: '20px',
            }}
          >
            <AlertCircle size={16} />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label" htmlFor="fullName">Full Name *</label>
            <input
              id="fullName"
              required
              className="form-input"
              placeholder="e.g. Jane Doe"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
            />
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="email">Email Address *</label>
            <input
              id="email"
              type="email"
              required
              className="form-input"
              placeholder="jane.doe@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="phone">Phone Number</label>
            <input
              id="phone"
              className="form-input"
              placeholder="+1 (555) 000-0000"
              value={phoneNumber}
              onChange={(e) => setPhoneNumber(e.target.value)}
            />
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="consent">Candidate Consent Status</label>
            <select
              id="consent"
              className="form-select"
              value={consentStatus}
              onChange={(e) => setConsentStatus(e.target.value)}
            >
              <option value="pending">Pending (Not yet granted)</option>
              <option value="granted">Granted (Explicit authorization given)</option>
              <option value="withdrawn">Withdrawn</option>
            </select>
          </div>

          {consentStatus === 'granted' && (
            <div className="form-group">
              <label className="form-label" htmlFor="consentMethod">Consent Verification Method</label>
              <input
                id="consentMethod"
                className="form-input"
                placeholder="e.g. Email consent, Verbal agreement, Application form checkbox"
                value={consentMethod}
                onChange={(e) => setConsentMethod(e.target.value)}
              />
            </div>
          )}

          <div className="form-group">
            <label className="form-label">Resume Document (.pdf or .docx, max 10MB)</label>
            <input
              type="file"
              accept=".pdf,.docx"
              onChange={handleFileChange}
              style={{
                width: '100%',
                padding: '10px',
                background: 'rgba(10, 13, 20, 0.8)',
                border: '1px solid var(--border-subtle)',
                borderRadius: 'var(--radius-md)',
                color: 'var(--text-muted)',
                fontSize: '0.875rem',
              }}
            />
          </div>

          <div style={{ marginTop: '28px', display: 'flex', gap: '12px' }}>
            <button type="submit" disabled={loading} className="btn btn-primary" style={{ padding: '12px 24px' }}>
              {loading ? 'Saving Candidate...' : 'Create Candidate'}
            </button>
            <button
              type="button"
              onClick={() => navigate('/candidates')}
              className="btn btn-secondary"
            >
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
