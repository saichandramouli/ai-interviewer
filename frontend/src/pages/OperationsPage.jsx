import React, { useState, useEffect } from 'react';
import { api } from '../api/client';
import { Activity, Clock, CheckCircle2, AlertCircle, RefreshCw } from 'lucide-react';

export default function OperationsPage() {
  const [operations, setOperations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const fetchOperations = async () => {
    setLoading(true);
    try {
      const resp = await api.get('/operations/');
      const data = resp.data.results || (Array.isArray(resp.data) ? resp.data : []);
      setOperations(data);
    } catch {
      setError('Failed to fetch operations log.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchOperations();
    const interval = setInterval(fetchOperations, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <div>
          <h2 style={{ fontSize: '1.75rem', fontWeight: 800, color: '#fff' }}>Asynchronous Operations</h2>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>
            Live status of Celery background jobs (resume parsing & question generation)
          </p>
        </div>
        <button onClick={fetchOperations} className="btn btn-secondary">
          <RefreshCw size={14} />
          <span>Refresh</span>
        </button>
      </div>

      {error && (
        <div style={{ padding: '12px 16px', borderRadius: 'var(--radius-md)', background: 'var(--danger-bg)', color: '#f87171', marginBottom: '16px' }}>
          {error}
        </div>
      )}

      <div className="glass-panel" style={{ padding: '20px' }}>
        {loading && operations.length === 0 ? (
          <div style={{ padding: '30px', textAlign: 'center', color: 'var(--text-muted)' }}>Loading operations...</div>
        ) : operations.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '40px 0', color: 'var(--text-faint)' }}>
            No operations recorded yet. Background jobs triggered from candidates or interviews will appear here.
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Operation ID</th>
                  <th>Type</th>
                  <th>Status</th>
                  <th>Message / Error</th>
                  <th>Attempts</th>
                  <th>Created</th>
                  <th>Completed</th>
                </tr>
              </thead>
              <tbody>
                {operations.map((op) => (
                  <tr key={op.id}>
                    <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem', color: '#a5b4fc' }}>
                      {op.id.substring(0, 8)}...
                    </td>
                    <td style={{ fontWeight: 600, color: '#fff', textTransform: 'capitalize' }}>
                      {op.operation_type.replace('_', ' ')}
                    </td>
                    <td>
                      <span className={`badge badge-${op.status}`}>{op.status}</span>
                    </td>
                    <td style={{ color: op.status === 'failed' ? '#f87171' : 'var(--text-muted)' }}>
                      {op.status_message || op.error_code || '—'}
                    </td>
                    <td style={{ color: 'var(--text-faint)' }}>{op.attempt_count}</td>
                    <td style={{ color: 'var(--text-faint)', fontSize: '0.8125rem' }}>
                      {new Date(op.created_at).toLocaleTimeString()}
                    </td>
                    <td style={{ color: 'var(--text-faint)', fontSize: '0.8125rem' }}>
                      {op.completed_at ? new Date(op.completed_at).toLocaleTimeString() : 'In flight'}
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
