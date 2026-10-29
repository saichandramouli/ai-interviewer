import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { ArrowLeft, Sparkles, Clock, Target, FileText, CheckCircle, HelpCircle } from 'lucide-react';

export default function InterviewPlanReviewPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [interview, setInterview] = useState(null);
  const [questions, setQuestions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const fetchPlanData = async () => {
      setLoading(true);
      try {
        const [intvResp, qResp] = await Promise.all([
          api.get(`/interviews/${id}/`),
          api.get(`/interviews/${id}/questions/`),
        ]);
        setInterview(intvResp.data);
        setQuestions(qResp.data || []);
      } catch (err) {
        setError('Failed to load interview plan and questions.');
      } finally {
        setLoading(false);
      }
    };
    fetchPlanData();
  }, [id]);

  if (loading) {
    return <div style={{ color: 'var(--text-muted)' }}>Loading structured interview plan...</div>;
  }

  if (error || !interview) {
    return (
      <div>
        <button onClick={() => navigate('/interviews')} className="btn btn-secondary" style={{ marginBottom: '20px' }}>
          <ArrowLeft size={14} /> Back
        </button>
        <div style={{ padding: '16px', background: 'var(--danger-bg)', color: '#f87171', borderRadius: 'var(--radius-md)' }}>
          {error || 'Interview session not found.'}
        </div>
      </div>
    );
  }

  const planData = interview.plan_data || {};

  return (
    <div style={{ maxWidth: '900px' }}>
      <button
        onClick={() => navigate('/interviews')}
        className="btn btn-secondary"
        style={{ marginBottom: '20px', padding: '6px 12px', fontSize: '0.8125rem' }}
      >
        <ArrowLeft size={14} />
        <span>Back to Interviews</span>
      </button>

      {/* Header Summary */}
      <div className="glass-panel" style={{ padding: '28px', marginBottom: '24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
              <span className="badge badge-completed">AI Generated Plan</span>
              <span className={`badge badge-${interview.status}`}>{interview.status}</span>
            </div>
            <h2 style={{ fontSize: '1.75rem', fontWeight: 800, color: '#fff' }}>
              Interview Plan: {interview.candidate_name || interview.candidate}
            </h2>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.9375rem', marginTop: '4px' }}>
              Role: <strong style={{ color: '#fff' }}>{interview.job_title || interview.job}</strong>
            </p>
          </div>
          {planData.total_estimated_minutes && (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '8px 14px',
                borderRadius: 'var(--radius-md)',
                background: 'rgba(99, 102, 241, 0.15)',
                color: '#a5b4fc',
                fontWeight: 600,
                fontSize: '0.875rem',
              }}
            >
              <Clock size={16} />
              <span>~{planData.total_estimated_minutes} min total duration</span>
            </div>
          )}
        </div>

        {/* Intro Statement */}
        {planData.introduction && (
          <div
            style={{
              marginTop: '20px',
              padding: '16px',
              borderRadius: 'var(--radius-md)',
              background: 'rgba(255, 255, 255, 0.02)',
              borderLeft: '4px solid var(--primary)',
            }}
          >
            <span style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: 'var(--text-faint)', fontWeight: 700 }}>
              AI Welcome & Context
            </span>
            <p style={{ fontSize: '0.875rem', color: 'var(--text-main)', marginTop: '4px', lineHeight: 1.6 }}>
              {planData.introduction}
            </p>
          </div>
        )}
      </div>

      {/* Questions List */}
      <div style={{ marginBottom: '24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
          <h3 style={{ fontSize: '1.25rem', fontWeight: 700, color: '#fff' }}>
            Interview Questions ({questions.length})
          </h3>
        </div>

        {questions.length === 0 ? (
          <div className="glass-panel" style={{ padding: '36px', textAlign: 'center', color: 'var(--text-faint)' }}>
            No questions generated for this interview yet. Click "Generate AI Plan" on the Interviews page to formulate questions.
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {questions.map((q) => (
              <div key={q.id} className="glass-panel" style={{ padding: '24px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '10px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <span
                      style={{
                        width: '28px',
                        height: '28px',
                        borderRadius: 'var(--radius-full)',
                        background: 'var(--bg-elevated)',
                        color: '#fff',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        fontSize: '0.8125rem',
                        fontWeight: 700,
                      }}
                    >
                      {q.sequence_number}
                    </span>
                    <span className="badge badge-scheduled" style={{ textTransform: 'capitalize' }}>
                      {q.category}
                    </span>
                    <span style={{ fontSize: '0.8125rem', fontWeight: 600, color: '#a5b4fc' }}>
                      {q.competency}
                    </span>
                  </div>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-faint)' }}>
                    Est: {q.estimated_minutes || 3} mins
                  </span>
                </div>

                <p style={{ fontSize: '1rem', fontWeight: 600, color: '#fff', margin: '12px 0 16px 0', lineHeight: 1.5 }}>
                  {q.question_text}
                </p>

                {q.expected_evidence && (
                  <div style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', marginBottom: '8px' }}>
                    <strong style={{ color: '#34d399' }}>Expected Evidence: </strong>
                    {q.expected_evidence}
                  </div>
                )}

                {q.suggested_follow_up && (
                  <div style={{ fontSize: '0.8125rem', color: 'var(--text-faint)' }}>
                    <strong style={{ color: '#fbbf24' }}>Follow-up Probe: </strong>
                    {q.suggested_follow_up}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Closing Statement */}
      {planData.closing_statement && (
        <div className="glass-panel" style={{ padding: '20px', borderLeft: '4px solid var(--secondary)' }}>
          <span style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: 'var(--text-faint)', fontWeight: 700 }}>
            Closing Statement
          </span>
          <p style={{ fontSize: '0.875rem', color: 'var(--text-main)', marginTop: '4px', lineHeight: 1.6 }}>
            {planData.closing_statement}
          </p>
        </div>
      )}
    </div>
  );
}
