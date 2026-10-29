import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { ArrowLeft, AlertCircle } from 'lucide-react';

export default function InterviewFormPage() {
  const [candidates, setCandidates] = useState([]);
  const [jobs, setJobs] = useState([]);
  const [selectedCandidate, setSelectedCandidate] = useState('');
  const [selectedJob, setSelectedJob] = useState('');
  const [initiationType, setInitiationType] = useState('manual');
  const [durationLimit, setDurationLimit] = useState(1800);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const navigate = useNavigate();

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [cResp, jResp] = await Promise.all([
          api.get('/candidates/'),
          api.get('/jobs/'),
        ]);
        const cList = cResp.data.results || (Array.isArray(cResp.data) ? cResp.data : []);
        const jList = jResp.data.results || (Array.isArray(jResp.data) ? jResp.data : []);
        setCandidates(cList);
        setJobs(jList);
        if (cList.length > 0) setSelectedCandidate(cList[0].id);
        if (jList.length > 0) setSelectedJob(jList[0].id);
      } catch {
        setError('Failed to fetch candidate and job options.');
      }
    };
    fetchData();
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!selectedCandidate || !selectedJob) {
      setError('Please select both a candidate and a job requisition.');
      return;
    }

    setLoading(true);
    setError('');

    try {
      await api.post('/interviews/', {
        candidate: selectedCandidate,
        job: selectedJob,
        initiation_type: initiationType,
        duration_limit_seconds: parseInt(durationLimit, 10),
        status: 'draft',
      });
      navigate('/interviews');
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to setup interview session.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: '640px' }}>
      <button
        onClick={() => navigate('/interviews')}
        className="btn btn-secondary"
        style={{ marginBottom: '20px', padding: '6px 12px', fontSize: '0.8125rem' }}
      >
        <ArrowLeft size={14} />
        <span>Back to Interviews</span>
      </button>

      <div className="glass-panel" style={{ padding: '32px' }}>
        <h2 style={{ fontSize: '1.5rem', fontWeight: 800, color: '#fff', marginBottom: '8px' }}>
          Setup Interview Session
        </h2>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem', marginBottom: '24px' }}>
          Connect an authorized candidate with a job requisition to generate a tailored interview plan
        </p>

        {error && (
          <div style={{ padding: '12px 14px', borderRadius: 'var(--radius-md)', background: 'var(--danger-bg)', color: '#f87171', marginBottom: '20px' }}>
            <AlertCircle size={16} />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label" htmlFor="candidate">Select Candidate *</label>
            <select
              id="candidate"
              required
              className="form-select"
              value={selectedCandidate}
              onChange={(e) => setSelectedCandidate(e.target.value)}
            >
              {candidates.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.full_name} ({c.email}) - Consent: {c.consent_status}
                </option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="job">Select Job Position *</label>
            <select
              id="job"
              required
              className="form-select"
              value={selectedJob}
              onChange={(e) => setSelectedJob(e.target.value)}
            >
              {jobs.map((j) => (
                <option key={j.id} value={j.id}>
                  {j.title} {j.is_active ? '(Active)' : '(Inactive)'}
                </option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="initiation">Call Initiation Mode</label>
            <select
              id="initiation"
              className="form-select"
              value={initiationType}
              onChange={(e) => setInitiationType(e.target.value)}
            >
              <option value="manual">Manual (Recruiter Initiated)</option>
              <option value="scheduled">Scheduled (Preset Time Window)</option>
            </select>
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="duration">Target Duration Limit (Seconds)</label>
            <input
              id="duration"
              type="number"
              className="form-input"
              value={durationLimit}
              onChange={(e) => setDurationLimit(e.target.value)}
            />
          </div>

          <div style={{ marginTop: '28px', display: 'flex', gap: '12px' }}>
            <button type="submit" disabled={loading} className="btn btn-primary" style={{ padding: '12px 24px' }}>
              {loading ? 'Creating Interview...' : 'Create Interview Session'}
            </button>
            <button
              type="button"
              onClick={() => navigate('/interviews')}
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
