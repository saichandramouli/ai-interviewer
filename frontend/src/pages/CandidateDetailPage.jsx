import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { api } from '../api/client';
import {
  User,
  Mail,
  Phone,
  Calendar,
  FileText,
  AlertCircle,
  Loader2,
  ArrowLeft,
  CheckCircle,
  Clock,
  Shield,
  FileCheck,
} from 'lucide-react';
import { PageHeader, Card, Button, Badge } from '../components/ui';

export default function CandidateDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();

  const [candidate, setCandidate] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const fetchCandidate = async () => {
      setLoading(true);
      setError('');
      try {
        const resp = await api.get(`/candidates/${id}/`);
        setCandidate(resp.data);
      } catch (err) {
        setError(err.response?.data?.detail || 'Failed to load candidate details.');
      } finally {
        setLoading(false);
      }
    };

    if (id) {
      fetchCandidate();
    }
  }, [id]);

  if (loading) {
    return (
      <div>
        <PageHeader
          title="Candidate Profile"
          description="Loading candidate information..."
          breadcrumbs={[
            { label: 'Candidates', to: '/candidates' },
            { label: 'Profile' },
          ]}
        />
        <Card padding="40px" style={{ textAlign: 'center' }}>
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '10px',
              color: 'var(--text-muted, #737d8c)',
              fontSize: 'var(--text-sm, 0.8125rem)',
            }}
          >
            <Loader2 size={20} style={{ animation: 'spin 1s linear infinite' }} />
            <span>Loading candidate profile...</span>
          </div>
        </Card>
      </div>
    );
  }

  if (error || !candidate) {
    return (
      <div>
        <PageHeader
          title="Candidate Profile"
          description="Error loading candidate profile"
          breadcrumbs={[
            { label: 'Candidates', to: '/candidates' },
            { label: 'Profile' },
          ]}
        />
        <Card padding="32px">
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '12px',
              padding: '14px 18px',
              borderRadius: 'var(--radius-sm, 6px)',
              backgroundColor: 'var(--danger-bg, #fef2f2)',
              border: '1px solid var(--danger-border, #fecaca)',
              color: 'var(--danger-text, #991b1b)',
              fontSize: 'var(--text-sm, 0.8125rem)',
              marginBottom: '20px',
            }}
          >
            <AlertCircle size={20} style={{ flexShrink: 0 }} />
            <div>
              <div style={{ fontWeight: 600 }}>Unable to load candidate</div>
              <div>{error || 'Candidate record not found.'}</div>
            </div>
          </div>
          <Button
            variant="secondary"
            icon={ArrowLeft}
            onClick={() => navigate('/candidates')}
          >
            Back to Candidates
          </Button>
        </Card>
      </div>
    );
  }

  return (
    <div>
      {/* Enterprise Slate PageHeader with Breadcrumbs and Back Action */}
      <PageHeader
        title={candidate.full_name || 'Candidate Profile'}
        description={`Registered on ${candidate.created_at ? new Date(candidate.created_at).toLocaleDateString() : '—'}`}
        breadcrumbs={[
          { label: 'Candidates', to: '/candidates' },
          { label: candidate.full_name || 'Profile' },
        ]}
        actions={
          <Button
            variant="secondary"
            size="md"
            icon={ArrowLeft}
            onClick={() => navigate('/candidates')}
          >
            Back to Candidates
          </Button>
        }
      />

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '20px' }}>
        {/* Contact & Personal Information Card */}
        <Card
          title="Candidate Information"
          description="Contact details and identification"
          padding="24px"
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div>
              <div style={{ fontSize: 'var(--text-xs, 0.75rem)', color: 'var(--text-muted, #4B5563)', fontWeight: 500 }}>
                Full Name
              </div>
              <div style={{ fontSize: 'var(--text-base, 0.875rem)', fontWeight: 600, color: 'var(--text-main, #111827)', marginTop: '2px' }}>
                {candidate.full_name || '—'}
              </div>
            </div>

            <div>
              <div style={{ fontSize: 'var(--text-xs, 0.75rem)', color: 'var(--text-muted, #4B5563)', fontWeight: 500 }}>
                Email Address
              </div>
              <div style={{ fontSize: 'var(--text-sm, 0.8125rem)', color: 'var(--text-body, #374151)', marginTop: '2px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Mail size={14} style={{ color: 'var(--text-muted, #4B5563)' }} />
                <span>{candidate.email || '—'}</span>
              </div>
            </div>

            <div>
              <div style={{ fontSize: 'var(--text-xs, 0.75rem)', color: 'var(--text-muted, #4B5563)', fontWeight: 500 }}>
                Phone Number
              </div>
              <div style={{ fontSize: 'var(--text-sm, 0.8125rem)', color: 'var(--text-body, #374151)', marginTop: '2px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Phone size={14} style={{ color: 'var(--text-muted, #4B5563)' }} />
                <span>{candidate.phone_number || <span style={{ color: 'var(--text-faint, #6B7280)' }}>Not provided</span>}</span>
              </div>
            </div>

            <div style={{ borderTop: '1px solid var(--border-subtle, #e2e8f0)', paddingTop: '16px' }}>
              <div style={{ fontSize: 'var(--text-xs, 0.75rem)', color: 'var(--text-muted, #4B5563)', fontWeight: 500 }}>
                Record Created
              </div>
              <div style={{ fontSize: 'var(--text-sm, 0.8125rem)', color: 'var(--text-body, #374151)', marginTop: '2px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Calendar size={14} style={{ color: 'var(--text-muted, #4B5563)' }} />
                <span>{candidate.created_at ? new Date(candidate.created_at).toLocaleString() : '—'}</span>
              </div>
            </div>
          </div>
        </Card>

        {/* Consent & Compliance Card */}
        <Card
          title="Consent & Privacy"
          description="Candidate authorization status for AI interviews"
          padding="24px"
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div>
              <div style={{ fontSize: 'var(--text-xs, 0.75rem)', color: 'var(--text-muted, #4B5563)', fontWeight: 500 }}>
                Consent Status
              </div>
              <div style={{ marginTop: '6px' }}>
                <Badge status={candidate.consent_status}>
                  {candidate.consent_status}
                </Badge>
              </div>
            </div>

            <div>
              <div style={{ fontSize: 'var(--text-xs, 0.75rem)', color: 'var(--text-muted, #4B5563)', fontWeight: 500 }}>
                Consent Method
              </div>
              <div style={{ fontSize: 'var(--text-sm, 0.8125rem)', color: 'var(--text-body, #374151)', marginTop: '2px' }}>
                {candidate.consent_method || <span style={{ color: 'var(--text-faint, #6B7280)' }}>Not specified</span>}
              </div>
            </div>

            <div>
              <div style={{ fontSize: 'var(--text-xs, 0.75rem)', color: 'var(--text-muted, #4B5563)', fontWeight: 500 }}>
                Consent Recorded At
              </div>
              <div style={{ fontSize: 'var(--text-sm, 0.8125rem)', color: 'var(--text-body, #374151)', marginTop: '2px' }}>
                {candidate.consent_recorded_at
                  ? new Date(candidate.consent_recorded_at).toLocaleString()
                  : <span style={{ color: 'var(--text-faint, #6B7280)' }}>Pending authorization</span>}
              </div>
            </div>

            <div style={{ borderTop: '1px solid var(--border-subtle, #e2e8f0)', paddingTop: '16px' }}>
              <div style={{ fontSize: 'var(--text-xs, 0.75rem)', color: 'var(--text-muted, #4B5563)', fontWeight: 500 }}>
                Candidate ID
              </div>
              <div style={{ fontSize: '0.75rem', fontFamily: 'monospace', color: 'var(--text-muted, #4B5563)', marginTop: '2px', wordBreak: 'break-all' }}>
                {candidate.id}
              </div>
            </div>
          </div>
        </Card>
      </div>

      {/* Resume Document & Extracted Content Card */}
      <div style={{ marginTop: '20px' }}>
        <Card
          title="Resume & Extracted Content"
          description="Uploaded CV document and parsed text for interview question generation"
          padding="24px"
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            {/* Uploaded File Link */}
            <div>
              <div style={{ fontSize: 'var(--text-xs, 0.75rem)', color: 'var(--text-muted, #4B5563)', fontWeight: 500, marginBottom: '6px' }}>
                Uploaded File
              </div>
              {candidate.resume ? (
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '10px',
                    padding: '12px 16px',
                    borderRadius: 'var(--radius-sm, 6px)',
                    backgroundColor: 'var(--bg-primary, #f8fafc)',
                    border: '1px solid var(--border-subtle, #e2e8f0)',
                  }}
                >
                  <FileText size={20} style={{ color: 'var(--primary-accent, #2563eb)' }} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 'var(--text-sm, 0.8125rem)', fontWeight: 600, color: 'var(--text-main, #111827)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {candidate.resume.split('/').pop()}
                    </div>
                  </div>
                  <a
                    href={candidate.resume}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="btn btn-secondary"
                    style={{ fontSize: 'var(--text-xs, 0.75rem)', padding: '6px 12px' }}
                  >
                    Download File
                  </a>
                </div>
              ) : (
                <div
                  style={{
                    padding: '16px',
                    borderRadius: 'var(--radius-sm, 6px)',
                    backgroundColor: 'var(--bg-primary, #f8fafc)',
                    border: '1px dashed var(--border-subtle, #e2e8f0)',
                    color: 'var(--text-muted, #4B5563)',
                    fontSize: 'var(--text-sm, 0.8125rem)',
                  }}
                >
                  No resume document uploaded for this candidate.
                </div>
              )}
            </div>

            {/* Extracted Text */}
            <div>
              <div style={{ fontSize: 'var(--text-xs, 0.75rem)', color: 'var(--text-muted, #4B5563)', fontWeight: 500, marginBottom: '6px' }}>
                Extracted Resume Text
              </div>
              {candidate.extracted_resume_text ? (
                <div
                  style={{
                    padding: '14px 16px',
                    borderRadius: 'var(--radius-sm, 6px)',
                    backgroundColor: '#ffffff',
                    border: '1px solid var(--border-subtle, #e2e8f0)',
                    fontSize: 'var(--text-sm, 0.8125rem)',
                    color: 'var(--text-body, #374151)',
                    lineHeight: 1.6,
                    maxHeight: '320px',
                    overflowY: 'auto',
                    whiteSpace: 'pre-wrap',
                    fontFamily: 'inherit',
                  }}
                >
                  {candidate.extracted_resume_text}
                </div>
              ) : (
                <div
                  style={{
                    padding: '16px',
                    borderRadius: 'var(--radius-sm, 6px)',
                    backgroundColor: 'var(--bg-primary, #f8fafc)',
                    border: '1px dashed var(--border-subtle, #e2e8f0)',
                    color: 'var(--text-muted, #4B5563)',
                    fontSize: 'var(--text-sm, 0.8125rem)',
                  }}
                >
                  No extracted text available yet. Return to the Candidates directory and click "Extract Resume" to extract text using the AI parser.
                </div>
              )}
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}

