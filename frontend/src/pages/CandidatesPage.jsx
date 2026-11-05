import React, { useState, useEffect, useMemo, useRef } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import {
  Plus,
  FileText,
  RefreshCw,
  Search,
  Users,
  AlertCircle,
  CheckCircle,
  Clock,
  UserCheck,
} from 'lucide-react';
import { PageHeader, Card, Button, Badge, DataTable, Input } from '../components/ui';

export default function CandidatesPage() {
  const navigate = useNavigate();
  const [candidates, setCandidates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [extractingId, setExtractingId] = useState(null);
  const [operationMsg, setOperationMsg] = useState('');

  // Ref to hold active interval timer for safe cleanup on unmount
  const pollIntervalRef = useRef(null);

  const fetchCandidates = async () => {
    setLoading(true);
    try {
      const resp = await api.get('/candidates/');
      const data = resp.data.results || (Array.isArray(resp.data) ? resp.data : []);
      setCandidates(data);
    } catch (err) {
      setError('Failed to fetch candidates list.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCandidates();
    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
    };
  }, []);

  const handleExtractResume = async (candidateId) => {
    if (extractingId) return; // Prevent concurrent extractions
    setExtractingId(candidateId);
    setOperationMsg('');
    setError('');

    try {
      const resp = await api.post(`/candidates/${candidateId}/extract-resume/`);
      const { operation_id } = resp.data;
      setOperationMsg(`Resume extraction enqueued. Operation ID: ${operation_id}`);

      // Poll operation status until succeeded or failed every 2,000 ms
      pollIntervalRef.current = setInterval(async () => {
        try {
          const opResp = await api.get(`/operations/${operation_id}/`);
          const opStatus = opResp.data.status;
          if (opStatus === 'succeeded') {
            clearInterval(pollIntervalRef.current);
            pollIntervalRef.current = null;
            setExtractingId(null);
            setOperationMsg('Resume extracted successfully! Candidate updated.');
            fetchCandidates();
          } else if (opStatus === 'failed') {
            clearInterval(pollIntervalRef.current);
            pollIntervalRef.current = null;
            setExtractingId(null);
            setError(
              `Resume extraction failed: ${opResp.data.status_message || opResp.data.error_code || 'Unknown error'}`
            );
          }
        } catch {
          clearInterval(pollIntervalRef.current);
          pollIntervalRef.current = null;
          setExtractingId(null);
          setError('Connection lost while checking resume extraction status. Please refresh and try again.');
        }
      }, 2000);
    } catch (err) {
      setExtractingId(null);
      setError(err.response?.data?.detail || 'Failed to dispatch extraction task.');
    }
  };

  // Client-side search filtering across Name, Email, and Phone
  const filteredCandidates = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return candidates;
    return candidates.filter((c) => {
      const name = (c.full_name || '').toLowerCase();
      const email = (c.email || '').toLowerCase();
      const phone = (c.phone_number || '').toLowerCase();
      return name.includes(q) || email.includes(q) || phone.includes(q);
    });
  }, [candidates, searchQuery]);

  // Column definitions for DataTable
  const columns = [
    {
      header: 'Name',
      accessor: 'full_name',
      render: (row) => (
        <span style={{ fontWeight: 600, color: 'var(--text-main, #111827)' }}>
          {row.full_name || '—'}
        </span>
      ),
    },
    {
      header: 'Email',
      accessor: 'email',
      render: (row) => (
        <span style={{ color: 'var(--text-muted, #4B5563)' }}>
          {row.email || '—'}
        </span>
      ),
    },
    {
      header: 'Phone',
      accessor: 'phone_number',
      render: (row) => (
        <span style={{ color: 'var(--text-muted, #4B5563)' }}>
          {row.phone_number || '—'}
        </span>
      ),
    },
    {
      header: 'Consent Status',
      accessor: 'consent_status',
      render: (row) => (
        <Badge status={row.consent_status}>
          {row.consent_status}
        </Badge>
      ),
    },
    {
      header: 'Resume Status',
      render: (row) => (
        <Button
          variant="secondary"
          size="sm"
          onClick={() => handleExtractResume(row.id)}
          disabled={extractingId === row.id}
          icon={extractingId === row.id ? RefreshCw : FileText}
        >
          {extractingId === row.id ? 'Extracting...' : 'Extract Resume'}
        </Button>
      ),
    },
    {
      header: 'Action',
      render: (row) => (
        <Link
          to={`/candidates/${row.id}`}
          style={{
            color: 'var(--primary-accent, #2563eb)',
            fontWeight: 600,
            fontSize: 'var(--text-xs, 0.75rem)',
            textDecoration: 'none',
          }}
          onMouseEnter={(e) => (e.currentTarget.style.textDecoration = 'underline')}
          onMouseLeave={(e) => (e.currentTarget.style.textDecoration = 'none')}
        >
          View Details
        </Link>
      ),
    },
  ];

  return (
    <div>
      {/* PageHeader with Action Button */}
      <PageHeader
        title="Candidates"
        description="Manage candidate profiles, resumes, and consent records"
        actions={
          <Button
            variant="primary"
            size="md"
            icon={Plus}
            onClick={() => navigate('/candidates/new')}
          >
            Add Candidate
          </Button>
        }
      />

      {/* Operation Feedback Alert */}
      {operationMsg && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '10px 14px',
            borderRadius: 'var(--radius-sm, 6px)',
            backgroundColor: 'var(--success-bg, #ecfdf5)',
            border: '1px solid var(--success-border, #bbf7d0)',
            color: 'var(--success-text, #166534)',
            fontSize: 'var(--text-sm, 0.8125rem)',
            marginBottom: '16px',
          }}
        >
          <CheckCircle size={16} style={{ flexShrink: 0 }} />
          <span>{operationMsg}</span>
        </div>
      )}

      {/* Error Feedback Alert */}
      {error && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '10px 14px',
            borderRadius: 'var(--radius-sm, 6px)',
            backgroundColor: 'var(--danger-bg, #fef2f2)',
            border: '1px solid var(--danger-border, #fecaca)',
            color: 'var(--danger-text, #991b1b)',
            fontSize: 'var(--text-sm, 0.8125rem)',
            marginBottom: '16px',
          }}
        >
          <AlertCircle size={16} style={{ flexShrink: 0 }} />
          <span>{error}</span>
        </div>
      )}

      {/* Main Directory Card */}
      <Card padding="0">
        {/* Search & Filter Bar */}
        <div
          style={{
            padding: '16px 20px',
            borderBottom: '1px solid var(--border-subtle, #e2e8f0)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '16px',
            flexWrap: 'wrap',
          }}
        >
          <div style={{ position: 'relative', width: '100%', maxWidth: '360px' }}>
            <Search
              size={16}
              style={{
                position: 'absolute',
                left: '12px',
                top: '50%',
                transform: 'translateY(-50%)',
                color: 'var(--text-muted, #737d8c)',
                pointerEvents: 'none',
              }}
            />
            <input
              type="text"
              placeholder="Search by name, email, or phone..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="form-input"
              style={{
                paddingLeft: '36px',
                fontSize: 'var(--text-sm, 0.8125rem)',
                backgroundColor: '#ffffff',
                border: '1px solid var(--border-subtle, #e2e8f0)',
                borderRadius: 'var(--radius-sm, 6px)',
                width: '100%',
              }}
            />
          </div>

          <div style={{ fontSize: 'var(--text-xs, 0.75rem)', color: 'var(--text-muted, #737d8c)' }}>
            Showing <strong>{filteredCandidates.length}</strong> of <strong>{candidates.length}</strong> candidates
          </div>
        </div>

        {/* Candidate DataTable */}
        {loading ? (
          <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted, #737d8c)' }}>
            Loading candidate directory...
          </div>
        ) : candidates.length === 0 ? (
          <div style={{ padding: '48px 20px', textAlign: 'center', color: 'var(--text-muted, #737d8c)' }}>
            <Users size={32} style={{ color: 'var(--text-faint, #94a3b8)', margin: '0 auto 12px auto' }} />
            <p style={{ fontSize: 'var(--text-sm, 0.8125rem)', margin: '0 0 16px 0' }}>
              No candidates registered yet. Click "Add Candidate" above to create your first candidate.
            </p>
            <Button
              variant="primary"
              size="sm"
              icon={Plus}
              onClick={() => navigate('/candidates/new')}
            >
              Add Candidate
            </Button>
          </div>
        ) : filteredCandidates.length === 0 ? (
          <div style={{ padding: '40px 20px', textAlign: 'center', color: 'var(--text-muted, #737d8c)' }}>
            <p style={{ fontSize: 'var(--text-sm, 0.8125rem)', margin: 0 }}>
              No candidates match your search query: "<strong>{searchQuery}</strong>"
            </p>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setSearchQuery('')}
              style={{ marginTop: '10px' }}
            >
              Clear search filter
            </Button>
          </div>
        ) : (
          <DataTable
            columns={columns}
            data={filteredCandidates}
            style={{ border: 'none', borderRadius: 0 }}
          />
        )}
      </Card>
    </div>
  );
}
