import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api/client';
import { Users, Briefcase, FileQuestion, Activity, ArrowUpRight, Clock, Plus } from 'lucide-react';

export default function DashboardPage() {
  const [stats, setStats] = useState({
    candidatesCount: 0,
    jobsCount: 0,
    interviewsCount: 0,
    recentInterviews: [],
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const fetchDashboardData = async () => {
      try {
        const [candResp, jobResp, intResp] = await Promise.all([
          api.get('/candidates/'),
          api.get('/jobs/'),
          api.get('/interviews/'),
        ]);

        const cCount = candResp.data.count !== undefined ? candResp.data.count : (candResp.data.results?.length || candResp.data.length || 0);
        const jCount = jobResp.data.count !== undefined ? jobResp.data.count : (jobResp.data.results?.length || jobResp.data.length || 0);
        const iCount = intResp.data.count !== undefined ? intResp.data.count : (intResp.data.results?.length || intResp.data.length || 0);
        const recent = intResp.data.results || (Array.isArray(intResp.data) ? intResp.data : []);

        setStats({
          candidatesCount: cCount,
          jobsCount: jCount,
          interviewsCount: iCount,
          recentInterviews: recent.slice(0, 5),
        });
      } catch (err) {
        setError('Failed to load dashboard metrics from backend.');
      } finally {
        setLoading(false);
      }
    };

    fetchDashboardData();
  }, []);

  if (loading) {
    return <div style={{ color: 'var(--text-muted)' }}>Loading dashboard metrics...</div>;
  }

  const statCards = [
    { label: 'Total Candidates', value: stats.candidatesCount, icon: Users, path: '/candidates', color: '#6366f1' },
    { label: 'Active Jobs', value: stats.jobsCount, icon: Briefcase, path: '/jobs', color: '#06b6d4' },
    { label: 'Scheduled / Draft Interviews', value: stats.interviewsCount, icon: FileQuestion, path: '/interviews', color: '#10b981' },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '28px' }}>
        <div>
          <h2 style={{ fontSize: '1.75rem', fontWeight: 800, color: '#fff', letterSpacing: '-0.02em' }}>
            Recruiter Overview
          </h2>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem', marginTop: '4px' }}>
            Real-time pipeline metrics and AI plan statuses
          </p>
        </div>
        <div style={{ display: 'flex', gap: '12px' }}>
          <Link to="/candidates/new" className="btn btn-primary">
            <Plus size={16} />
            <span>Add Candidate</span>
          </Link>
          <Link to="/jobs/new" className="btn btn-secondary">
            <Plus size={16} />
            <span>Create Job</span>
          </Link>
        </div>
      </div>

      {error && (
        <div style={{ padding: '14px', borderRadius: 'var(--radius-md)', background: 'var(--danger-bg)', color: '#f87171', marginBottom: '20px' }}>
          {error}
        </div>
      )}

      {/* Metric Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '20px', marginBottom: '32px' }}>
        {statCards.map((card) => {
          const Icon = card.icon;
          return (
            <Link key={card.label} to={card.path} className="glass-panel" style={{ padding: '24px', display: 'block' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div
                  style={{
                    width: '42px',
                    height: '42px',
                    borderRadius: '10px',
                    background: `${card.color}20`,
                    color: card.color,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  <Icon size={22} />
                </div>
                <ArrowUpRight size={18} style={{ color: 'var(--text-faint)' }} />
              </div>
              <div style={{ marginTop: '18px' }}>
                <span style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', fontWeight: 600 }}>{card.label}</span>
                <div style={{ fontSize: '2rem', fontWeight: 800, color: '#fff', marginTop: '4px' }}>{card.value}</div>
              </div>
            </Link>
          );
        })}
      </div>

      {/* Recent Interviews Table */}
      <div className="glass-panel" style={{ padding: '24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
          <h3 style={{ fontSize: '1.125rem', fontWeight: 700, color: '#fff' }}>Recent Interviews</h3>
          <Link to="/interviews" style={{ fontSize: '0.8125rem', color: 'var(--primary)', fontWeight: 600 }}>
            View all
          </Link>
        </div>

        {stats.recentInterviews.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '40px 0', color: 'var(--text-faint)' }}>
            No interview sessions created yet. Click "Add Candidate" and "Create Job" to get started.
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Candidate</th>
                  <th>Job Title</th>
                  <th>Status</th>
                  <th>Created</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {stats.recentInterviews.map((intv) => (
                  <tr key={intv.id}>
                    <td style={{ fontWeight: 600, color: '#fff' }}>{intv.candidate_name || intv.candidate}</td>
                    <td style={{ color: 'var(--text-muted)' }}>{intv.job_title || intv.job}</td>
                    <td>
                      <span className={`badge badge-${intv.status}`}>{intv.status}</span>
                    </td>
                    <td style={{ color: 'var(--text-faint)', fontSize: '0.8125rem' }}>
                      {new Date(intv.created_at).toLocaleDateString()}
                    </td>
                    <td>
                      <Link
                        to={`/interviews/${intv.id}/plan`}
                        className="btn btn-secondary"
                        style={{ padding: '6px 12px', fontSize: '0.75rem' }}
                      >
                        Review Plan
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
