import React from 'react';
import { MessageSquare, Bot, User, Clock } from 'lucide-react';

export default function InterviewTranscriptViewer({ transcripts = [], loading = false }) {
  if (loading) {
    return (
      <div className="glass-panel" style={{ padding: '32px', textAlign: 'center', color: 'var(--text-muted)' }}>
        Loading interview transcript...
      </div>
    );
  }

  if (!transcripts || transcripts.length === 0) {
    return (
      <div className="glass-panel" style={{ padding: '32px', textAlign: 'center', color: 'var(--text-faint)' }}>
        <MessageSquare size={32} style={{ margin: '0 auto 12px auto', opacity: 0.5 }} />
        <p>No spoken transcript entries recorded for this interview session.</p>
      </div>
    );
  }

  const formatTimestamp = (isoString) => {
    if (!isoString) return '';
    try {
      const d = new Date(isoString);
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    } catch {
      return '';
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      {transcripts.map((entry) => {
        const isAI = entry.speaker === 'ai';
        return (
          <div
            key={entry.id || entry.sequence_number}
            className="glass-panel"
            style={{
              padding: '18px 22px',
              borderLeft: isAI ? '4px solid var(--primary)' : '4px solid #10b981',
              background: isAI ? 'rgba(99, 102, 241, 0.04)' : 'rgba(16, 185, 129, 0.04)',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                {isAI ? (
                  <div
                    style={{
                      width: '26px',
                      height: '26px',
                      borderRadius: '50%',
                      background: 'rgba(99, 102, 241, 0.2)',
                      color: 'var(--primary)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}
                  >
                    <Bot size={15} />
                  </div>
                ) : (
                  <div
                    style={{
                      width: '26px',
                      height: '26px',
                      borderRadius: '50%',
                      background: 'rgba(16, 185, 129, 0.2)',
                      color: '#10b981',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}
                  >
                    <User size={15} />
                  </div>
                )}
                <span style={{ fontWeight: 700, fontSize: '0.875rem', color: isAI ? '#a5b4fc' : '#6ee7b7' }}>
                  {isAI ? 'AI Interviewer' : 'Candidate'}
                </span>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-faint)' }}>
                  (Turn #{entry.sequence_number})
                </span>
              </div>
              {entry.timestamp && (
                <div style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.75rem', color: 'var(--text-faint)' }}>
                  <Clock size={12} />
                  <span>{formatTimestamp(entry.timestamp)}</span>
                </div>
              )}
            </div>

            <p style={{ margin: 0, fontSize: '0.9375rem', color: '#fff', lineHeight: 1.6, whiteSpace: 'pre-wrap' }}>
              {entry.text}
            </p>
          </div>
        );
      })}
    </div>
  );
}

