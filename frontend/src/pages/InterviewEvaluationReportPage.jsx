import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { api } from '../api/client';
import {
  ArrowLeft,
  CheckCircle,
  AlertCircle,
  Clock,
  RefreshCw,
  Award,
  TrendingUp,
  AlertTriangle,
  FileText,
  UserCheck,
  ChevronDown,
  ChevronUp,
  MessageSquare,
  Sparkles,
} from 'lucide-react';
import InterviewTranscriptViewer from '../components/InterviewTranscriptViewer';

export default function InterviewEvaluationReportPage() {
  const { id } = useParams();
  const navigate = useNavigate();

  // Data states
  const [interview, setInterview] = useState(null);
  const [evaluation, setEvaluation] = useState(null);
  const [transcripts, setTranscripts] = useState([]);
  const [questions, setQuestions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Review form states
  const [recruiterNotes, setRecruiterNotes] = useState('');
  const [finalDecision, setFinalDecision] = useState('');
  const [submittingReview, setSubmittingReview] = useState(false);
  const [reviewSuccessMsg, setReviewSuccessMsg] = useState('');

  // Retry state
  const [retrying, setRetrying] = useState(false);
  const [retryMsg, setRetryMsg] = useState('');

  // UI accordion state for question-wise evaluation
  const [expandedQuestions, setExpandedQuestions] = useState({});

  const pollTimerRef = useRef(null);

  const fetchAllData = async (isPolling = false) => {
    if (!isPolling) setLoading(true);
    try {
      const [intvResp, evalResp, transResp, qResp] = await Promise.all([
        api.get(`/interviews/${id}/`),
        api.get(`/interviews/${id}/evaluation/`).catch((err) => {
          if (err.response?.status === 404) {
            return { data: { evaluation_status: 'not_generated', message: 'No evaluation generated yet.' } };
          }
          throw err;
        }),
        api.get(`/interviews/${id}/transcript/`),
        api.get(`/interviews/${id}/questions/`),
      ]);

      setInterview(intvResp.data);
      const evalData = evalResp.data;
      setEvaluation(evalData);
      setTranscripts(transResp.data || []);
      setQuestions(qResp.data || []);

      if (evalData?.recruiter_notes && !recruiterNotes) {
        setRecruiterNotes(evalData.recruiter_notes);
      }
      if (evalData?.final_decision && !finalDecision) {
        setFinalDecision(evalData.final_decision);
      }

      // Check polling terminal condition
      const evalStatus = evalData?.evaluation_status;
      if (evalStatus === 'pending' || evalStatus === 'processing') {
        if (!pollTimerRef.current) {
          pollTimerRef.current = setTimeout(() => {
            pollTimerRef.current = null;
            fetchAllData(true);
          }, 5000);
        }
      } else {
        if (pollTimerRef.current) {
          clearTimeout(pollTimerRef.current);
          pollTimerRef.current = null;
        }
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load evaluation report data.');
    } finally {
      if (!isPolling) setLoading(false);
    }
  };

  useEffect(() => {
    fetchAllData();
    return () => {
      if (pollTimerRef.current) {
        clearTimeout(pollTimerRef.current);
      }
    };
  }, [id]);

  const toggleQuestion = (qId) => {
    setExpandedQuestions((prev) => ({ ...prev, [qId]: !prev[qId] }));
  };

  const handleReviewSubmit = async (e) => {
    e.preventDefault();
    if (!finalDecision) {
      alert('Please select a hiring decision (Hire, Hold, or Reject).');
      return;
    }

    setSubmittingReview(true);
    setReviewSuccessMsg('');
    setError('');

    try {
      const resp = await api.patch(`/interviews/${id}/evaluation/review/`, {
        final_decision: finalDecision,
        recruiter_notes: recruiterNotes,
      });
      setEvaluation(resp.data);
      setReviewSuccessMsg('Recruiter review successfully saved!');
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to save recruiter review.');
    } finally {
      setSubmittingReview(false);
    }
  };

  const handleRetryEvaluation = async () => {
    setRetrying(true);
    setRetryMsg('');
    setError('');

    try {
      await api.post(`/interviews/${id}/evaluation/retry/`);
      setRetryMsg('Evaluation generation enqueued. Polling status...');
      // Start polling
      setTimeout(() => fetchAllData(true), 2000);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to dispatch evaluation retry task.');
    } finally {
      setRetrying(false);
    }
  };

  if (loading) {
    return (
      <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)' }}>
        <RefreshCw size={24} className="spin" style={{ margin: '0 auto 12px auto' }} />
        <p>Loading candidate evaluation report...</p>
      </div>
    );
  }

  if (error && !interview) {
    return (
      <div style={{ maxWidth: '800px', margin: '0 auto' }}>
        <Link to="/interviews" className="btn btn-secondary" style={{ marginBottom: '20px' }}>
          <ArrowLeft size={16} /> Back to Interviews
        </Link>
        <div style={{ padding: '20px', borderRadius: 'var(--radius-md)', background: 'var(--danger-bg)', color: '#f87171' }}>
          {error}
        </div>
      </div>
    );
  }

  const evalStatus = evaluation?.evaluation_status || 'not_generated';
  const isReviewed = evaluation?.review_status === 'reviewed';
  const overallScore = evaluation?.overall_score;
  const compScores = evaluation?.competency_scores || {};
  const strengths = evaluation?.strengths || [];
  const improvementAreas = evaluation?.improvement_areas || [];

  return (
    <div style={{ maxWidth: '1100px', margin: '0 auto', paddingBottom: '60px' }}>
      {/* Navigation & Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <Link to="/interviews" className="btn btn-secondary" style={{ padding: '6px 14px', fontSize: '0.8125rem' }}>
          <ArrowLeft size={14} /> Back to Interviews
        </Link>
        <div style={{ display: 'flex', gap: '8px' }}>
          {(evalStatus === 'failed' || evalStatus === 'not_generated' || evalStatus === 'insufficient_data') && !isReviewed && (
            <button
              onClick={handleRetryEvaluation}
              disabled={retrying}
              className="btn btn-secondary"
              style={{ padding: '6px 14px', fontSize: '0.8125rem', gap: '6px' }}
            >
              <RefreshCw size={14} className={retrying ? 'spin' : ''} />
              <span>{retrying ? 'Retrying...' : 'Retry Evaluation'}</span>
            </button>
          )}
        </div>
      </div>

      {error && (
        <div style={{ padding: '14px 18px', borderRadius: 'var(--radius-md)', background: 'var(--danger-bg)', color: '#f87171', marginBottom: '20px' }}>
          {error}
        </div>
      )}

      {retryMsg && (
        <div style={{ padding: '14px 18px', borderRadius: 'var(--radius-md)', background: 'rgba(99, 102, 241, 0.15)', color: '#a5b4fc', marginBottom: '20px' }}>
          {retryMsg}
        </div>
      )}

      {reviewSuccessMsg && (
        <div style={{ padding: '14px 18px', borderRadius: 'var(--radius-md)', background: 'var(--success-bg)', color: '#34d399', marginBottom: '20px' }}>
          {reviewSuccessMsg}
        </div>
      )}

      {/* 1. Candidate & Interview Overview Header */}
      <div className="glass-panel" style={{ padding: '28px', marginBottom: '28px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '16px' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
              <span className={`badge badge-${interview?.status}`}>{interview?.status}</span>
              <span className="badge badge-completed" style={{ textTransform: 'capitalize' }}>
                Eval: {evalStatus.replace('_', ' ')}
              </span>
              {isReviewed && (
                <span className="badge badge-reviewed" style={{ background: '#059669', color: '#fff' }}>
                  Reviewed
                </span>
              )}
            </div>
            <h1 style={{ fontSize: '1.875rem', fontWeight: 800, color: '#fff', margin: '4px 0' }}>
              {interview?.candidate_name || 'Candidate Evaluation Report'}
            </h1>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.9375rem', margin: 0 }}>
              Position: <strong style={{ color: '#fff' }}>{interview?.job_title || 'Software Role'}</strong>
              {interview?.candidate_email && ` • ${interview.candidate_email}`}
            </p>
          </div>

          {/* Timestamp details */}
          <div style={{ textAlign: 'right', fontSize: '0.8125rem', color: 'var(--text-faint)' }}>
            <div>Started: {interview?.started_at ? new Date(interview.started_at).toLocaleString() : 'N/A'}</div>
            {interview?.ended_at && (
              <div>Concluded: {new Date(interview.ended_at).toLocaleString()}</div>
            )}
            <div style={{ marginTop: '6px', color: '#fbbf24', fontWeight: 600 }}>
              AI Advisory Report (Human Decision Required)
            </div>
          </div>
        </div>
      </div>

      {/* Asynchronous Processing or Pending State */}
      {(evalStatus === 'pending' || evalStatus === 'processing') && (
        <div className="glass-panel" style={{ padding: '40px', textAlign: 'center', marginBottom: '28px' }}>
          <RefreshCw size={36} className="spin" style={{ color: 'var(--primary)', margin: '0 auto 16px auto' }} />
          <h3 style={{ fontSize: '1.25rem', fontWeight: 700, color: '#fff' }}>Evaluation in Progress</h3>
          <p style={{ color: 'var(--text-muted)', maxWidth: '500px', margin: '8px auto 0 auto' }}>
            NVIDIA Nemotron is analyzing the interview transcript against competencies and formulating evidence. This screen polls automatically.
          </p>
        </div>
      )}

      {/* Insufficient Evidence State */}
      {evalStatus === 'insufficient_data' && (
        <div className="glass-panel" style={{ padding: '30px', borderLeft: '4px solid #fbbf24', marginBottom: '28px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', color: '#fbbf24', marginBottom: '8px' }}>
            <AlertTriangle size={20} />
            <h3 style={{ margin: 0, fontWeight: 700 }}>Insufficient Evidence</h3>
          </div>
          <p style={{ color: 'var(--text-muted)', margin: 0, lineHeight: 1.6 }}>
            {evaluation?.evidence_summary || 'The interview session concluded without recording sufficient candidate responses to calculate a reliable score.'}
          </p>
        </div>
      )}

      {/* Main Evaluation Content (Rendered when completed or reviewed) */}
      {(evalStatus === 'completed' || evalStatus === 'insufficient_data') && (
        <>
          {/* 2. Overall Score Card */}
          <div className="glass-panel" style={{ padding: '28px', marginBottom: '28px', display: 'flex', alignItems: 'center', gap: '32px', flexWrap: 'wrap' }}>
            <div
              style={{
                width: '120px',
                height: '120px',
                borderRadius: '50%',
                background: overallScore !== null ? 'rgba(99, 102, 241, 0.15)' : 'rgba(255, 255, 255, 0.05)',
                border: overallScore !== null ? '4px solid var(--primary)' : '4px solid var(--border-color)',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <span style={{ fontSize: '2rem', fontWeight: 800, color: overallScore !== null ? '#fff' : 'var(--text-faint)' }}>
                {overallScore !== null && overallScore !== undefined ? overallScore : 'N/A'}
              </span>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 600 }}>/ 100</span>
            </div>

            <div style={{ flex: 1, minWidth: '240px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--primary)', marginBottom: '6px' }}>
                <Award size={18} />
                <span style={{ fontWeight: 700, fontSize: '0.875rem', textTransform: 'uppercase' }}>Overall Assessment Score</span>
              </div>
              <p style={{ margin: '0 0 10px 0', fontSize: '0.9375rem', color: '#fff', lineHeight: 1.5 }}>
                {overallScore !== null
                  ? `Demonstrated technical aptitude of ${overallScore}% across planned interview questions and competency areas.`
                  : 'Insufficient evidence to calculate a reliable score. Candidate answers were missing or silent.'}
              </p>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-faint)' }}>
                Scores are evidence-based observations. They are advisory and never constitute an automated hiring decision.
              </span>
            </div>
          </div>

          {/* 3. Competency-wise Evaluation */}
          {Object.keys(compScores).length > 0 && (
            <div className="glass-panel" style={{ padding: '28px', marginBottom: '28px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '20px' }}>
                <TrendingUp size={18} style={{ color: 'var(--primary)' }} />
                <h3 style={{ margin: 0, fontSize: '1.25rem', fontWeight: 700, color: '#fff' }}>
                  Competency Breakdown
                </h3>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
                {Object.entries(compScores).map(([compName, score]) => (
                  <div key={compName}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px', fontSize: '0.875rem' }}>
                      <span style={{ fontWeight: 600, color: '#fff' }}>{compName}</span>
                      <span style={{ fontWeight: 700, color: score >= 70 ? '#34d399' : score >= 50 ? '#fbbf24' : '#f87171' }}>
                        {score} / 100
                      </span>
                    </div>
                    <div style={{ height: '8px', background: 'rgba(255,255,255,0.06)', borderRadius: '4px', overflow: 'hidden' }}>
                      <div
                        style={{
                          height: '100%',
                          width: `${Math.min(100, Math.max(0, score))}%`,
                          background: score >= 70 ? '#10b981' : score >= 50 ? '#f59e0b' : '#ef4444',
                          borderRadius: '4px',
                          transition: 'width 0.4s ease',
                        }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 4 & 5: Strengths & Improvement Areas Grid */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '24px', marginBottom: '28px' }}>
            {/* Strengths */}
            <div className="glass-panel" style={{ padding: '24px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#34d399', marginBottom: '16px' }}>
                <CheckCircle size={18} />
                <h4 style={{ margin: 0, fontSize: '1.125rem', fontWeight: 700 }}>Demonstrated Strengths</h4>
              </div>
              {strengths.length === 0 ? (
                <p style={{ color: 'var(--text-faint)', fontSize: '0.875rem' }}>No specific strengths highlighted.</p>
              ) : (
                <ul style={{ margin: 0, paddingLeft: '20px', color: 'var(--text-main)', fontSize: '0.875rem', lineHeight: 1.6 }}>
                  {strengths.map((str, idx) => (
                    <li key={idx} style={{ marginBottom: '8px' }}>{str}</li>
                  ))}
                </ul>
              )}
            </div>

            {/* Improvement Areas */}
            <div className="glass-panel" style={{ padding: '24px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#f87171', marginBottom: '16px' }}>
                <AlertCircle size={18} />
                <h4 style={{ margin: 0, fontSize: '1.125rem', fontWeight: 700 }}>Areas for Growth</h4>
              </div>
              {improvementAreas.length === 0 ? (
                <p style={{ color: 'var(--text-faint)', fontSize: '0.875rem' }}>No significant gaps identified.</p>
              ) : (
                <ul style={{ margin: 0, paddingLeft: '20px', color: 'var(--text-main)', fontSize: '0.875rem', lineHeight: 1.6 }}>
                  {improvementAreas.map((area, idx) => (
                    <li key={idx} style={{ marginBottom: '8px' }}>{area}</li>
                  ))}
                </ul>
              )}
            </div>
          </div>

          {/* 6. Evidence Summary */}
          {evaluation?.evidence_summary && (
            <div className="glass-panel" style={{ padding: '24px', marginBottom: '28px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px', color: 'var(--primary)' }}>
                <FileText size={18} />
                <h4 style={{ margin: 0, fontSize: '1.125rem', fontWeight: 700, color: '#fff' }}>Evidence Synthesis</h4>
              </div>
              <p style={{ color: 'var(--text-main)', fontSize: '0.9375rem', lineHeight: 1.6, margin: 0 }}>
                {evaluation.evidence_summary}
              </p>
            </div>
          )}

          {/* 7. Question-wise Breakdown */}
          {questions.length > 0 && (
            <div className="glass-panel" style={{ padding: '28px', marginBottom: '28px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '18px' }}>
                <Sparkles size={18} style={{ color: 'var(--primary)' }} />
                <h3 style={{ margin: 0, fontSize: '1.25rem', fontWeight: 700, color: '#fff' }}>
                  Interview Question Breakdown ({questions.length})
                </h3>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                {questions.map((q) => {
                  const isExpanded = !!expandedQuestions[q.id];
                  return (
                    <div
                      key={q.id}
                      style={{
                        borderRadius: 'var(--radius-md)',
                        background: 'rgba(255, 255, 255, 0.02)',
                        border: '1px solid var(--border-color)',
                        overflow: 'hidden',
                      }}
                    >
                      <button
                        onClick={() => toggleQuestion(q.id)}
                        style={{
                          width: '100%',
                          padding: '16px 20px',
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center',
                          background: 'none',
                          border: 'none',
                          cursor: 'pointer',
                          color: '#fff',
                          textAlign: 'left',
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                          <span
                            style={{
                              width: '26px',
                              height: '26px',
                              borderRadius: '50%',
                              background: 'var(--bg-elevated)',
                              fontSize: '0.75rem',
                              fontWeight: 700,
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                            }}
                          >
                            {q.sequence_number}
                          </span>
                          <span style={{ fontWeight: 600, fontSize: '0.9375rem' }}>{q.question_text}</span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                          <span className="badge badge-scheduled" style={{ fontSize: '0.75rem' }}>
                            {q.competency}
                          </span>
                          {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                        </div>
                      </button>

                      {isExpanded && (
                        <div style={{ padding: '0 20px 20px 20px', borderTop: '1px solid rgba(255,255,255,0.04)', fontSize: '0.875rem' }}>
                          <div style={{ marginTop: '12px', color: 'var(--text-muted)' }}>
                            <strong style={{ color: '#a5b4fc' }}>Expected Evidence: </strong>
                            {q.expected_evidence || 'Core competency demonstration.'}
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </>
      )}

      {/* Complete Interview Transcript Viewer */}
      <div style={{ marginBottom: '32px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
          <MessageSquare size={18} style={{ color: 'var(--primary)' }} />
          <h3 style={{ margin: 0, fontSize: '1.25rem', fontWeight: 700, color: '#fff' }}>
            Full Chronological Transcript ({transcripts.length} turns)
          </h3>
        </div>
        <InterviewTranscriptViewer transcripts={transcripts} />
      </div>

      {/* Recruiter Review & Final Decision Form */}
      <div className="glass-panel" style={{ padding: '32px', border: '1px solid var(--primary)', background: 'rgba(99, 102, 241, 0.04)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '18px' }}>
          <UserCheck size={22} style={{ color: 'var(--primary)' }} />
          <h3 style={{ margin: 0, fontSize: '1.375rem', fontWeight: 800, color: '#fff' }}>
            Recruiter Assessment & Hiring Decision
          </h3>
        </div>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem', marginTop: 0, marginBottom: '24px' }}>
          Record your human hiring decision and feedback notes. AI findings are advisory only.
        </p>

        <form onSubmit={handleReviewSubmit}>
          {/* Decision Radio / Buttons */}
          <div style={{ marginBottom: '24px' }}>
            <label style={{ display: 'block', fontWeight: 700, color: '#fff', marginBottom: '12px', fontSize: '0.875rem' }}>
              Final Hiring Decision *
            </label>
            <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap' }}>
              {[
                { val: 'hire', label: 'Hire Candidate', color: '#10b981', border: '#059669' },
                { val: 'hold', label: 'Hold / Follow-up', color: '#f59e0b', border: '#d97706' },
                { val: 'reject', label: 'Reject', color: '#ef4444', border: '#dc2626' },
              ].map((opt) => (
                <button
                  type="button"
                  key={opt.val}
                  onClick={() => setFinalDecision(opt.val)}
                  style={{
                    flex: '1 1 180px',
                    padding: '14px 18px',
                    borderRadius: 'var(--radius-md)',
                    border: finalDecision === opt.val ? `2px solid ${opt.color}` : '1px solid var(--border-color)',
                    background: finalDecision === opt.val ? `${opt.color}25` : 'rgba(255, 255, 255, 0.02)',
                    color: finalDecision === opt.val ? '#fff' : 'var(--text-muted)',
                    fontWeight: 700,
                    cursor: 'pointer',
                    textAlign: 'center',
                    transition: 'all 0.2s ease',
                  }}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          {/* Recruiter Notes */}
          <div style={{ marginBottom: '24px' }}>
            <label style={{ display: 'block', fontWeight: 700, color: '#fff', marginBottom: '8px', fontSize: '0.875rem' }}>
              Recruiter Evaluation Notes
            </label>
            <textarea
              value={recruiterNotes}
              onChange={(e) => setRecruiterNotes(e.target.value)}
              placeholder="Add your interview observations, reasoning for final decision, or follow-up feedback..."
              rows={4}
              maxLength={5000}
              className="form-input"
              style={{
                width: '100%',
                padding: '12px 16px',
                borderRadius: 'var(--radius-md)',
                background: 'rgba(0, 0, 0, 0.2)',
                color: '#fff',
                border: '1px solid var(--border-color)',
                resize: 'vertical',
                fontSize: '0.875rem',
              }}
            />
          </div>

          {/* Submitter & Review Details */}
          {evaluation?.reviewed_by_email && (
            <div style={{ marginBottom: '20px', fontSize: '0.8125rem', color: 'var(--text-faint)' }}>
              Last reviewed by <strong>{evaluation.reviewed_by_name || evaluation.reviewed_by_email}</strong> on{' '}
              {new Date(evaluation.reviewed_at).toLocaleString()}
            </div>
          )}

          <button
            type="submit"
            disabled={submittingReview}
            className="btn btn-primary"
            style={{ padding: '12px 28px', fontSize: '0.9375rem', fontWeight: 700 }}
          >
            {submittingReview ? 'Saving Review...' : isReviewed ? 'Update Hiring Decision' : 'Submit Hiring Decision'}
          </button>
        </form>
      </div>
    </div>
  );
}

