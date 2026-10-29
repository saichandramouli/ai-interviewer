import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { api } from '../api/client';
import {
  ArrowLeft,
  Play,
  FastForward,
  XCircle,
  Clock,
  AlertTriangle,
  CheckCircle,
  HelpCircle,
  User,
  Bot,
  RefreshCw,
  Sparkles,
} from 'lucide-react';

export default function MockInterviewSessionPage() {
  const { id } = useParams();
  const navigate = useNavigate();

  const [session, setSession] = useState(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState('');
  const [simulatedResponse, setSimulatedResponse] = useState('');
  const [simulateSilence, setSimulateSilence] = useState(false);

  const fetchSession = async () => {
    try {
      const resp = await api.get(`/interviews/${id}/session/`);
      setSession(resp.data);
      setError('');
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load interview session state.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSession();
    // Poll session updates every 5 seconds if active
    const timer = setInterval(() => {
      if (session?.status === 'in_progress' || session?.status === 'calling') {
        fetchSession();
      }
    }, 5000);
    return () => clearInterval(timer);
  }, [id, session?.status]);

  const handleStart = async () => {
    setActionLoading(true);
    setError('');
    try {
      const resp = await api.post(`/interviews/${id}/start/`);
      setSession(resp.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to start mock session.');
    } finally {
      setActionLoading(false);
    }
  };

  const handleAdvance = async (disconnect = false) => {
    setActionLoading(true);
    setError('');
    try {
      const resp = await api.post(`/interviews/${id}/advance/`, {
        simulated_response: simulatedResponse,
        simulate_silence: simulateSilence,
        simulate_disconnect: disconnect,
      });
      setSession(resp.data);
      setSimulatedResponse('');
      setSimulateSilence(false);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to advance question.');
    } finally {
      setActionLoading(false);
    }
  };

  const handleCancel = async () => {
    if (!window.confirm('Are you sure you want to cancel this mock interview session?')) {
      return;
    }
    setActionLoading(true);
    setError('');
    try {
      const resp = await api.post(`/interviews/${id}/cancel/`, {
        reason: 'Cancelled by recruiter from mock session console.',
      });
      setSession(resp.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to cancel session.');
    } finally {
      setActionLoading(false);
    }
  };

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '60px 0', color: 'var(--text-muted)' }}>
        Loading mock interview session...
      </div>
    );
  }

  const timing = session?.timing || {};
  const currentQ = session?.current_question;
  const progress = session?.progress || {};
  const transcripts = session?.transcripts || [];

  const formatSeconds = (sec = 0) => {
    const mins = Math.floor(sec / 60);
    const s = sec % 60;
    return `${mins}m ${s < 10 ? '0' : ''}${s}s`;
  };

  return (
    <div>
      {/* Top Header & Breadcrumb */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <button
          onClick={() => navigate('/interviews')}
          className="btn btn-secondary"
          style={{ padding: '6px 12px', fontSize: '0.8125rem' }}
        >
          <ArrowLeft size={14} />
          <span>Back to Interviews</span>
        </button>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <span className="badge badge-warning" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Sparkles size={12} />
            <span>MOCK SIMULATION MODE ONLY</span>
          </span>
          <span className={`badge badge-${session?.status}`}>{session?.status}</span>
        </div>
      </div>

      {/* Explicit Mock Disclaimer Banner */}
      <div
        style={{
          background: 'rgba(234, 179, 8, 0.1)',
          border: '1px solid rgba(234, 179, 8, 0.3)',
          borderRadius: 'var(--radius-md)',
          padding: '12px 16px',
          marginBottom: '24px',
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
          color: '#fbbf24',
          fontSize: '0.875rem',
        }}
      >
        <AlertTriangle size={18} style={{ flexShrink: 0 }} />
        <div>
          <strong>Phase 7 Mock Telephony Environment:</strong> No real phone call or live audio is transmitted. This screen operates exclusively with a deterministic mock voice provider for testing interview question progression and candidate responses.
        </div>
      </div>

      {error && (
        <div
          style={{
            padding: '12px 16px',
            borderRadius: 'var(--radius-md)',
            background: 'var(--danger-bg)',
            color: '#f87171',
            marginBottom: '20px',
            fontSize: '0.875rem',
          }}
        >
          {error}
        </div>
      )}

      {/* Main Grid: Details + Timing & Action Controls */}
      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '24px', marginBottom: '24px' }}>
        {/* Left Column: Candidate & Job Details */}
        <div className="glass-panel" style={{ padding: '24px' }}>
          <h2 style={{ fontSize: '1.25rem', fontWeight: 800, color: '#fff', marginBottom: '8px' }}>
            {session?.candidate?.name}
          </h2>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem', marginBottom: '16px' }}>
            Position: <strong style={{ color: '#fff' }}>{session?.job?.title}</strong>
          </p>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', fontSize: '0.8125rem' }}>
            <div>
              <span style={{ color: 'var(--text-faint)' }}>Candidate Email: </span>
              <span style={{ color: '#fff' }}>{session?.candidate?.email}</span>
            </div>
            <div>
              <span style={{ color: 'var(--text-faint)' }}>Consent Verification: </span>
              <span style={{ color: session?.candidate?.consent_status === 'granted' ? '#4ade80' : '#f87171', fontWeight: 600 }}>
                {session?.candidate?.consent_status?.toUpperCase()} ({session?.candidate?.consent_method || 'Unverified'})
              </span>
            </div>
            <div>
              <span style={{ color: 'var(--text-faint)' }}>Provider Session ID: </span>
              <span style={{ color: '#a5b4fc', fontFamily: 'var(--font-mono)' }}>
                {session?.provider_call_id || 'Not initiated'}
              </span>
            </div>
            <div>
              <span style={{ color: 'var(--text-faint)' }}>Progress: </span>
              <span style={{ color: '#fff', fontWeight: 600 }}>
                {progress.questions_asked} of {progress.total_questions} questions completed
              </span>
            </div>
          </div>
        </div>

        {/* Right Column: Time Management */}
        <div className="glass-panel" style={{ padding: '24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
            <Clock size={16} style={{ color: '#818cf8' }} />
            <h3 style={{ fontSize: '1rem', fontWeight: 700, color: '#fff' }}>Time Management</h3>
          </div>

          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px', fontSize: '0.875rem' }}>
            <span style={{ color: 'var(--text-muted)' }}>Elapsed:</span>
            <strong style={{ color: '#fff' }}>{formatSeconds(timing.elapsed_seconds)}</strong>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px', fontSize: '0.875rem' }}>
            <span style={{ color: 'var(--text-muted)' }}>Remaining:</span>
            <strong style={{ color: timing.warning_triggered ? '#f87171' : '#4ade80' }}>
              {formatSeconds(timing.remaining_seconds)}
            </strong>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.875rem' }}>
            <span style={{ color: 'var(--text-muted)' }}>Limit:</span>
            <span style={{ color: 'var(--text-faint)' }}>{formatSeconds(timing.duration_limit_seconds)}</span>
          </div>

          {timing.warning_triggered && !timing.is_expired && (
            <div style={{ marginTop: '12px', fontSize: '0.75rem', color: '#fbbf24', background: 'rgba(234, 179, 8, 0.1)', padding: '6px 10px', borderRadius: '4px' }}>
              Time limit warning threshold reached (&gt;80% elapsed).
            </div>
          )}

          {timing.is_expired && (
            <div style={{ marginTop: '12px', fontSize: '0.75rem', color: '#f87171', background: 'var(--danger-bg)', padding: '6px 10px', borderRadius: '4px' }}>
              Interview time limit expired.
            </div>
          )}
        </div>
      </div>

      {/* Control Console */}
      <div className="glass-panel" style={{ padding: '24px', marginBottom: '24px' }}>
        <h3 style={{ fontSize: '1.125rem', fontWeight: 700, color: '#fff', marginBottom: '16px' }}>
          Session Controls
        </h3>

        {/* State 1: Draft or Scheduled -> Start Button */}
        {['draft', 'scheduled'].includes(session?.status) && (
          <div>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem', marginBottom: '16px' }}>
              The interview is ready to begin. Starting will connect the mock voice provider and deliver the AI introduction.
            </p>
            <button
              onClick={handleStart}
              disabled={actionLoading}
              className="btn btn-primary"
              style={{ padding: '10px 20px', gap: '8px' }}
            >
              <Play size={16} />
              <span>{actionLoading ? 'Connecting Mock Session...' : 'Start Mock Interview'}</span>
            </button>
          </div>
        )}

        {/* State 2: In Progress -> Question Progression & Simulated Candidate Response */}
        {session?.status === 'in_progress' && (
          <div>
            {currentQ && (
              <div
                style={{
                  background: 'rgba(99, 102, 241, 0.08)',
                  border: '1px solid rgba(99, 102, 241, 0.25)',
                  borderRadius: 'var(--radius-md)',
                  padding: '16px',
                  marginBottom: '20px',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                  <span style={{ fontSize: '0.75rem', color: '#818cf8', fontWeight: 700, textTransform: 'uppercase' }}>
                    Current Question #{currentQ.sequence_number} • {currentQ.category}
                  </span>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-faint)' }}>
                    Target: {currentQ.competency}
                  </span>
                </div>
                <div style={{ fontSize: '1rem', fontWeight: 600, color: '#fff', marginBottom: '8px' }}>
                  {currentQ.text}
                </div>
                {currentQ.expected_evidence && (
                  <div style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>
                    <em>Expected Evidence:</em> {currentQ.expected_evidence}
                  </div>
                )}
              </div>
            )}

            {/* Simulated Candidate Response Input */}
            <div style={{ marginBottom: '16px' }}>
              <label className="form-label">Simulate Candidate Answer / Utterance</label>
              <textarea
                className="form-textarea"
                rows={3}
                placeholder="Type simulated candidate response here (or leave blank to use mock default)..."
                value={simulatedResponse}
                onChange={(e) => setSimulatedResponse(e.target.value)}
                disabled={actionLoading || simulateSilence}
              />
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '20px', marginBottom: '20px' }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', fontSize: '0.875rem', color: 'var(--text-muted)' }}>
                <input
                  type="checkbox"
                  checked={simulateSilence}
                  onChange={(e) => setSimulateSilence(e.target.checked)}
                />
                <span>Simulate Candidate Silence (10 seconds)</span>
              </label>
            </div>

            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '12px' }}>
              <button
                onClick={() => handleAdvance(false)}
                disabled={actionLoading}
                className="btn btn-primary"
                style={{ padding: '10px 20px', gap: '8px' }}
              >
                <FastForward size={16} />
                <span>{actionLoading ? 'Processing...' : 'Submit Response & Next Question'}</span>
              </button>

              <button
                onClick={() => handleAdvance(true)}
                disabled={actionLoading}
                className="btn btn-secondary"
                style={{ padding: '10px 16px', gap: '8px', color: '#fbbf24' }}
              >
                <span>Simulate Disconnect</span>
              </button>

              <button
                onClick={handleCancel}
                disabled={actionLoading}
                className="btn btn-secondary"
                style={{ padding: '10px 16px', gap: '8px', color: '#f87171' }}
              >
                <XCircle size={16} />
                <span>End / Cancel Interview</span>
              </button>
            </div>
          </div>
        )}

        {/* State 3: Completed */}
        {session?.status === 'completed' && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', color: '#4ade80' }}>
            <CheckCircle size={24} />
            <div>
              <strong style={{ fontSize: '1rem' }}>Interview Completed Successfully</strong>
              <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem', margin: '4px 0 0 0' }}>
                All scheduled questions were delivered and answered. Transcripts are locked and ready for evaluation.
              </p>
            </div>
          </div>
        )}

        {/* State 4: Cancelled or Failed */}
        {['cancelled', 'failed'].includes(session?.status) && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', color: '#f87171' }}>
            <XCircle size={24} />
            <div>
              <strong style={{ fontSize: '1rem' }}>Interview Session Terminated ({session?.status})</strong>
              <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem', margin: '4px 0 0 0' }}>
                Session is finalized. Further question progression is blocked.
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Live Simulated Transcript Stream */}
      <div className="glass-panel" style={{ padding: '24px' }}>
        <h3 style={{ fontSize: '1.125rem', fontWeight: 700, color: '#fff', marginBottom: '16px' }}>
          Simulated Transcript Feed ({transcripts.length} entries)
        </h3>

        {transcripts.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '30px 0', color: 'var(--text-faint)' }}>
            No transcript entries recorded yet. Utterances will appear here once the session begins.
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {transcripts.map((entry) => {
              const isAI = entry.speaker === 'ai';
              return (
                <div
                  key={entry.id || entry.sequence_number}
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    alignSelf: isAI ? 'flex-start' : 'flex-end',
                    maxWidth: '80%',
                    background: isAI ? 'rgba(99, 102, 241, 0.1)' : 'rgba(255, 255, 255, 0.05)',
                    border: isAI ? '1px solid rgba(99, 102, 241, 0.25)' : '1px solid var(--border-subtle)',
                    borderRadius: 'var(--radius-md)',
                    padding: '12px 16px',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
                    {isAI ? (
                      <Bot size={14} style={{ color: '#818cf8' }} />
                    ) : (
                      <User size={14} style={{ color: '#4ade80' }} />
                    )}
                    <span style={{ fontSize: '0.75rem', fontWeight: 700, color: isAI ? '#818cf8' : '#4ade80' }}>
                      {isAI ? 'AI Interviewer' : 'Candidate'}
                    </span>
                    <span style={{ fontSize: '0.7rem', color: 'var(--text-faint)', marginLeft: 'auto' }}>
                      #{entry.sequence_number} • {new Date(entry.timestamp).toLocaleTimeString()}
                    </span>
                  </div>
                  <div style={{ fontSize: '0.875rem', color: '#fff', whiteSpace: 'pre-wrap', lineHeight: 1.5 }}>
                    {entry.text}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
