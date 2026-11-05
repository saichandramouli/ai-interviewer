import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { ArrowLeft, AlertCircle, Calendar, Clock, Globe } from 'lucide-react';

export default function InterviewFormPage() {
  const [candidates, setCandidates] = useState([]);
  const [jobs, setJobs] = useState([]);
  const [selectedCandidate, setSelectedCandidate] = useState('');
  const [selectedJob, setSelectedJob] = useState('');
  const [initiationType, setInitiationType] = useState('manual');
  const [scheduledDate, setScheduledDate] = useState('');
  const [scheduledTime, setScheduledTime] = useState('');
  const [timeZone, setTimeZone] = useState(() => {
    try {
      return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
    } catch {
      return 'UTC';
    }
  });
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

    let scheduledIso = null;
    if (initiationType === 'scheduled') {
      if (!scheduledDate || !scheduledTime) {
        setError('Please select both an interview date and time for scheduled mode.');
        return;
      }

      // Construct Date object from local date and time inputs
      const scheduledDateTime = new Date(`${scheduledDate}T${scheduledTime}`);
      if (isNaN(scheduledDateTime.getTime())) {
        setError('Invalid date or time value.');
        return;
      }

      // Only future date/time combinations are allowed
      if (scheduledDateTime.getTime() <= Date.now()) {
        setError('Scheduled interview date and time must be in the future.');
        return;
      }

      scheduledIso = scheduledDateTime.toISOString();
    }

    setLoading(true);
    setError('');

    try {
      const payload = {
        candidate: selectedCandidate,
        job: selectedJob,
        initiation_type: initiationType,
        duration_limit_seconds: parseInt(durationLimit, 10),
      };

      if (initiationType === 'scheduled') {
        payload.scheduled_at = scheduledIso;
        payload.timezone = timeZone;
      } else {
        payload.status = 'draft';
      }

      await api.post('/interviews/', payload);
      navigate('/interviews');
    } catch (err) {
      const detail = err.response?.data?.scheduled_at?.[0] ||
        err.response?.data?.timezone?.[0] ||
        err.response?.data?.detail ||
        'Failed to setup interview session.';
      setError(detail);
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
        <h2 style={{ fontSize: '1.5rem', fontWeight: 800, color: 'var(--text-main, #111827)', marginBottom: '8px' }}>
          Setup Interview Session
        </h2>
        <p style={{ color: 'var(--text-muted, #4B5563)', fontSize: '0.875rem', marginBottom: '24px' }}>
          Connect an authorized candidate with a job requisition to generate a tailored interview plan
        </p>

        {error && (
          <div style={{ padding: '12px 14px', borderRadius: 'var(--radius-md)', background: 'var(--danger-bg)', color: '#f87171', marginBottom: '20px' }}>
            <AlertCircle size={16} />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} noValidate>
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

          {initiationType === 'scheduled' && (
            <div
              style={{
                padding: '16px',
                marginBottom: '16px',
                borderRadius: 'var(--radius-sm, 6px)',
                backgroundColor: 'var(--bg-primary, #f8fafc)',
                border: '1px solid var(--border-subtle, #e2e8f0)',
                display: 'flex',
                flexDirection: 'column',
                gap: '14px',
              }}
            >
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <div className="form-group" style={{ marginBottom: 0 }}>
                  <label className="form-label" htmlFor="scheduledDate" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <Calendar size={14} style={{ color: 'var(--primary-accent, #2563eb)' }} />
                    <span>Interview Date *</span>
                  </label>
                  <input
                    id="scheduledDate"
                    type="date"
                    required
                    className="form-input"
                    value={scheduledDate}
                    min={new Date().toISOString().split('T')[0]}
                    onChange={(e) => setScheduledDate(e.target.value)}
                  />
                </div>

                <div className="form-group" style={{ marginBottom: 0 }}>
                  <label className="form-label" htmlFor="scheduledTime" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <Clock size={14} style={{ color: 'var(--primary-accent, #2563eb)' }} />
                    <span>Interview Time *</span>
                  </label>
                  <input
                    id="scheduledTime"
                    type="time"
                    required
                    className="form-input"
                    value={scheduledTime}
                    onChange={(e) => setScheduledTime(e.target.value)}
                  />
                </div>
              </div>

              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  fontSize: 'var(--text-xs, 0.75rem)',
                  color: 'var(--text-muted, #4B5563)',
                  backgroundColor: '#ffffff',
                  padding: '8px 12px',
                  borderRadius: 'var(--radius-xs, 4px)',
                  border: '1px solid var(--border-subtle, #e2e8f0)',
                }}
              >
                <Globe size={14} style={{ color: 'var(--primary-accent, #2563eb)', flexShrink: 0 }} />
                <span>
                  Detected Timezone: <strong>{timeZone}</strong> (Times are scheduled in your local timezone and stored in UTC)
                </span>
              </div>
            </div>
          )}

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
