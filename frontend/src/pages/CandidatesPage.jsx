import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api/client';
import { Plus, FileText, CheckCircle, Clock, AlertTriangle, RefreshCw } from 'lucide-react';

export default function CandidatesPage() {
  const [candidates, setCandidates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [extractingId, setExtractingId] = useState(null);
  const [operationMsg, setOperationMsg] = useState('');

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
  }, []);

  const handleExtractResume = async (candidateId) => {
    setExtractingId(candidateId);
    setOperationMsg('');
    setError('');

    try {
      const resp = await api.post(`/candidates/${candidateId}/extract-resume/`);
      const { operation_id, status_url } = resp.data;
      setOperationMsg(`Resume extraction enqueued. Operation ID: ${operation_id}`);

      // Poll operation status until succeeded or failed
      const pollInterval = setInterval(async () => {
        try {
          const opResp = await api.get(`/operations/${operation_id}/`);
          const opStatus = opResp.data.status;
          if (opStatus === 'succeeded') {
            clearInterval(pollInterval);
            setExtractingId(null);
            setOperationMsg('Resume extracted successfully! Candidate updated.');
            fetchCandidates();
          } else if (opStatus === 'failed') {
            clearInterval(pollInterval);
            setExtractingId(null);
            setError(`Resume extraction failed: ${opResp.data.status_message || opResp.data.error_code}`);
          }
        } catch {
          clearInterval(pollInterval);
          setExtractingId(null);
        }
      }, 2000);
    } catch (err) {
      setExtractingId(null);
      setError(err.response?.data?.detail || 'Failed to dispatch extraction task.');
    }
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <div>
          <h2 style={{ fontSize: '1.75rem', fontWeight: 800, color: '#fff' }}>Candidate Directory</h2>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>
            Manage candidate profiles, resumes, and consent records
          </p>
        </div>
        <Link to="/candidates/new" className="btn btn-primary">
          <Plus size={16} />
          <span>Add Candidate</span>
        </Link>
      </div>

      {operationMsg && (
        <div style={{ padding: '12px 16px', borderRadius: 'var(--radius-md)', background: 'var(--success-bg)', color: '#34d399', marginBottom: '16px' }}>
          {operationMsg}
        </div>
      )}

      {error && (
        <div style={{ padding: '12px 16px', borderRadius: 'var(--radius-md)', background: 'var(--danger-bg)', color: '#f87171', marginBottom: '16px' }}>
          {error}
        </div>
      )}

      <div className="glass-panel" style={{ padding: '20px' }}>
        {loading ? (
          <div style={{ padding: '30px', textAlign: 'center', color: 'var(--text-muted)' }}>Loading candidates...</div>
        ) : candidates.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '40px 0', color: 'var(--text-faint)' }}>
            No candidates registered yet. Click "Add Candidate" above to create your first candidate.
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Email</th>
                  <th>Phone</th>
                  <th>Consent Status</th>
                  <th>Resume Status</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {candidates.map((c) => (
                  <tr key={c.id}>
                    <td style={{ fontWeight: 600, color: '#fff' }}>{c.full_name}</td>
                    <td style={{ color: 'var(--text-muted)' }}>{c.email}</td>
                    <td style={{ color: 'var(--text-faint)' }}>{c.phone_number || '—'}</td>
                    <td>
                      <span className={`badge badge-${c.consent_status}`}>{c.consent_status}</span>
                    </td>
                    <td>
                      <button
                        onClick={() => handleExtractResume(c.id)}
                        disabled={extractingId === c.id}
                        className="btn btn-secondary"
                        style={{ padding: '6px 12px', fontSize: '0.75rem' }}
                      >
                        {extractingId === c.id ? (
                          <>
                            <RefreshCw size={12} className="spin" />
                            <span>Extracting...</span>
                          </>
                        ) : (
                          <>
                            <FileText size={12} />
                            <span>Extract Resume</span>
                          </>
                        )}
                      </button>
                    </td>
                    <td>
                      <Link
                        to={`/candidates/${c.id}`}
                        style={{ color: 'var(--primary)', fontWeight: 600, fontSize: '0.8125rem' }}
                      >
                        View Details
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
