import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api/client';
import { Plus, Sparkles, RefreshCw, Eye, Play, Award, Send, Calendar, Clock } from 'lucide-react';
import CandidateInviteModal from '../components/CandidateInviteModal';

export default function InterviewsPage() {
  const [interviews, setInterviews] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [generatingId, setGeneratingId] = useState(null);
  const [operationMsg, setOperationMsg] = useState('');
  const [selectedInviteInterview, setSelectedInviteInterview] = useState(null);

  const fetchInterviews = async () => {
    setLoading(true);
    try {
      const resp = await api.get('/interviews/');
      const data = resp.data.results || (Array.isArray(resp.data) ? resp.data : []);
      setInterviews(data);
    } catch {
      setError('Failed to fetch interviews.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchInterviews();
  }, []);

  const handleGeneratePlan = async (interviewId) => {
    setGeneratingId(interviewId);
    setOperationMsg('');
    setError('');

    try {
      const resp = await api.post(`/interviews/${interviewId}/generate-plan/`);
      const { operation_id } = resp.data;
      setOperationMsg(`AI plan generation enqueued. Operation ID: ${operation_id}`);

      // Poll operation status
      const pollInterval = setInterval(async () => {
        try {
          const opResp = await api.get(`/operations/${operation_id}/`);
          const opStatus = opResp.data.status;
          if (opStatus === 'succeeded') {
            clearInterval(pollInterval);
            setGeneratingId(null);
            setOperationMsg('AI interview plan generated successfully!');
            fetchInterviews();
          } else if (opStatus === 'failed') {
            clearInterval(pollInterval);
            setGeneratingId(null);
            setError(`Plan generation failed: ${opResp.data.status_message || opResp.data.error_code}`);
          }
        } catch {
          clearInterval(pollInterval);
          setGeneratingId(null);
        }
      }, 2000);
    } catch (err) {
      setGeneratingId(null);
      setError(err.response?.data?.detail || 'Failed to dispatch plan generation task.');
    }
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <div>
          <h2 style={{ fontSize: '1.75rem', fontWeight: 800, color: 'var(--text-main, #111827)' }}>Interview Sessions</h2>
          <p style={{ color: 'var(--text-muted, #4B5563)', fontSize: '0.875rem' }}>
            Schedule sessions, generate AI plans, and view transcripts
          </p>
        </div>
        <Link to="/interviews/new" className="btn btn-primary">
          <Plus size={16} />
          <span>Setup Interview</span>
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
          <div style={{ padding: '30px', textAlign: 'center', color: 'var(--text-muted)' }}>Loading sessions...</div>
        ) : interviews.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '40px 0', color: 'var(--text-faint)' }}>
            No interviews scheduled. Click "Setup Interview" above to link a candidate with a job requisition.
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Candidate</th>
                  <th>Job Title</th>
                  <th>Status</th>
                  <th>Scheduled Time</th>
                  <th>Plan & Questions</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {interviews.map((intv) => {
                  let formattedScheduled = null;
                  if (intv.scheduled_at) {
                    try {
                      const dt = new Date(intv.scheduled_at);
                      formattedScheduled = dt.toLocaleString(undefined, {
                        timeZone: intv.timezone || undefined,
                        dateStyle: 'medium',
                        timeStyle: 'short',
                      });
                    } catch {
                      formattedScheduled = new Date(intv.scheduled_at).toLocaleString();
                    }
                  }

                  return (
                    <tr key={intv.id}>
                      <td style={{ fontWeight: 600, color: 'var(--text-main, #111827)' }}>{intv.candidate_name || intv.candidate}</td>
                      <td style={{ color: 'var(--text-muted, #4B5563)' }}>{intv.job_title || intv.job}</td>
                      <td>
                        <span className={`badge badge-${intv.status}`}>{intv.status}</span>
                      </td>
                      <td>
                        {formattedScheduled ? (
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.8125rem', color: 'var(--text-main, #111827)', fontWeight: 500 }}>
                              <Clock size={13} style={{ color: 'var(--primary-accent, #2563eb)' }} />
                              <span>{formattedScheduled}</span>
                            </div>
                            {intv.timezone && (
                              <span style={{ fontSize: '0.6875rem', color: 'var(--text-faint, #6B7280)', paddingLeft: '19px' }}>
                                {intv.timezone}
                              </span>
                            )}
                          </div>
                        ) : (
                          <span style={{ fontSize: '0.75rem', color: 'var(--text-faint, #6B7280)' }}>
                            {intv.initiation_type === 'manual' ? 'Manual Initiation' : '—'}
                          </span>
                        )}
                      </td>
                      <td>
                      <button
                        onClick={() => handleGeneratePlan(intv.id)}
                        disabled={generatingId === intv.id}
                        className="btn btn-secondary"
                        style={{ padding: '6px 12px', fontSize: '0.75rem', gap: '6px' }}
                      >
                        {generatingId === intv.id ? (
                          <>
                            <RefreshCw size={12} className="spin" />
                            <span>Generating...</span>
                          </>
                        ) : (
                          <>
                            <Sparkles size={12} style={{ color: '#818cf8' }} />
                            <span>Generate AI Plan</span>
                          </>
                        )}
                      </button>
                    </td>
                    <td style={{ display: 'flex', gap: '8px' }}>
                      <Link
                        to={`/interviews/${intv.id}/plan`}
                        className="btn btn-secondary"
                        style={{ padding: '6px 12px', fontSize: '0.75rem' }}
                      >
                        <Eye size={12} />
                        <span>Plan</span>
                      </Link>
                      {intv.status !== 'completed' && intv.status !== 'cancelled' && (
                        <button
                          onClick={() => setSelectedInviteInterview(intv)}
                          className="btn btn-secondary"
                          style={{ padding: '6px 12px', fontSize: '0.75rem', borderColor: '#34d399', color: '#6ee7b7', gap: '6px' }}
                          title="Generate candidate link and send invitation email"
                        >
                          <Send size={12} />
                          <span>Invite</span>
                        </button>
                      )}
                      {intv.status === 'completed' && (
                        <Link
                          to={`/interviews/${intv.id}/report`}
                          className="btn btn-secondary"
                          style={{ padding: '6px 12px', fontSize: '0.75rem', borderColor: '#818cf8', color: '#a5b4fc' }}
                        >
                          <Award size={12} />
                          <span>Evaluation</span>
                        </Link>
                      )}
                      <Link
                        to={`/interviews/${intv.id}/session`}
                        className="btn btn-primary"
                        style={{ padding: '6px 12px', fontSize: '0.75rem' }}
                      >
                        <Play size={12} />
                        <span>Mock Session</span>
                      </Link>
                    </td>
                  </tr>
                );
              })}
            </tbody>
            </table>
          </div>
        )}
      </div>

      <CandidateInviteModal
        interview={selectedInviteInterview}
        isOpen={!!selectedInviteInterview}
        onClose={() => setSelectedInviteInterview(null)}
      />
    </div>
  );
}
