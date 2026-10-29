import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api/client';
import { Plus, Briefcase, Check, X } from 'lucide-react';

export default function JobsPage() {
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const fetchJobs = async () => {
    setLoading(true);
    try {
      const resp = await api.get('/jobs/');
      const data = resp.data.results || (Array.isArray(resp.data) ? resp.data : []);
      setJobs(data);
    } catch {
      setError('Failed to fetch jobs.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchJobs();
  }, []);

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <div>
          <h2 style={{ fontSize: '1.75rem', fontWeight: 800, color: '#fff' }}>Job Requisitions</h2>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>
            Job descriptions and competency frameworks for interview generation
          </p>
        </div>
        <Link to="/jobs/new" className="btn btn-primary">
          <Plus size={16} />
          <span>Create Job</span>
        </Link>
      </div>

      {error && (
        <div style={{ padding: '12px 16px', borderRadius: 'var(--radius-md)', background: 'var(--danger-bg)', color: '#f87171', marginBottom: '16px' }}>
          {error}
        </div>
      )}

      <div className="glass-panel" style={{ padding: '20px' }}>
        {loading ? (
          <div style={{ padding: '30px', textAlign: 'center', color: 'var(--text-muted)' }}>Loading jobs...</div>
        ) : jobs.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '40px 0', color: 'var(--text-faint)' }}>
            No jobs found. Click "Create Job" above to add your first position.
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Job Title</th>
                  <th>Required Skills</th>
                  <th>Status</th>
                  <th>Created</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {jobs.map((j) => (
                  <tr key={j.id}>
                    <td style={{ fontWeight: 600, color: '#fff' }}>{j.title}</td>
                    <td>
                      <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                        {(j.required_skills || []).map((skill, i) => (
                          <span
                            key={i}
                            style={{
                              background: 'rgba(99, 102, 241, 0.15)',
                              color: '#a5b4fc',
                              fontSize: '0.75rem',
                              padding: '2px 8px',
                              borderRadius: '4px',
                            }}
                          >
                            {skill}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td>
                      <span className={`badge ${j.is_active ? 'badge-completed' : 'badge-draft'}`}>
                        {j.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </td>
                    <td style={{ color: 'var(--text-faint)', fontSize: '0.8125rem' }}>
                      {new Date(j.created_at).toLocaleDateString()}
                    </td>
                    <td>
                      <Link
                        to={`/jobs/${j.id}`}
                        style={{ color: 'var(--primary)', fontWeight: 600, fontSize: '0.8125rem' }}
                      >
                        Edit
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
