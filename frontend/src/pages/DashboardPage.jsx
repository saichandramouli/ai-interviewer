import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import {
  Users,
  Briefcase,
  CalendarCheck,
  Plus,
  ArrowUpRight,
  AlertCircle,
  Loader2,
  FileQuestion,
} from 'lucide-react';
import { PageHeader, Card, Button, Badge, DataTable } from '../components/ui';

export default function DashboardPage() {
  const navigate = useNavigate();
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

        const cCount =
          candResp.data.count !== undefined
            ? candResp.data.count
            : candResp.data.results?.length || candResp.data.length || 0;
        const jCount =
          jobResp.data.count !== undefined
            ? jobResp.data.count
            : jobResp.data.results?.length || jobResp.data.length || 0;
        const iCount =
          intResp.data.count !== undefined
            ? intResp.data.count
            : intResp.data.results?.length || intResp.data.length || 0;
        const recent =
          intResp.data.results || (Array.isArray(intResp.data) ? intResp.data : []);

        setStats({
          candidatesCount: cCount,
          jobsCount: jCount,
          interviewsCount: iCount,
          recentInterviews: recent.slice(0, 5),
        });
      } catch (err) {
        setError('Failed to load recruiter metrics from backend.');
      } finally {
        setLoading(false);
      }
    };

    fetchDashboardData();
  }, []);

  const statCards = [
    {
      label: 'My Candidates',
      value: stats.candidatesCount,
      icon: Users,
      path: '/candidates',
      color: '#2563eb',
      bgColor: '#eff6ff',
    },
    {
      label: 'My Active Jobs',
      value: stats.jobsCount,
      icon: Briefcase,
      path: '/jobs',
      color: '#0891b2',
      bgColor: '#ecfeff',
    },
    {
      label: 'Scheduled / In-Progress Interviews',
      value: stats.interviewsCount,
      icon: CalendarCheck,
      path: '/interviews',
      color: '#16a34a',
      bgColor: '#f0fdf4',
    },
  ];

  // Define columns for Recent Interviews DataTable
  const interviewColumns = [
    {
      header: 'Candidate',
      accessor: 'candidate_name',
      render: (row) => (
        <span style={{ fontWeight: 600, color: 'var(--text-main, #111827)' }}>
          {row.candidate_name || row.candidate || '—'}
        </span>
      ),
    },
    {
      header: 'Job Title',
      accessor: 'job_title',
      render: (row) => (
        <span style={{ color: 'var(--text-muted, #4B5563)' }}>
          {row.job_title || row.job || '—'}
        </span>
      ),
    },
    {
      header: 'Status',
      accessor: 'status',
      render: (row) => <Badge status={row.status}>{row.status}</Badge>,
    },
    {
      header: 'Created',
      accessor: 'created_at',
      render: (row) => (
        <span style={{ color: 'var(--text-muted, #4B5563)', fontSize: 'var(--text-xs, 0.75rem)' }}>
          {row.created_at ? new Date(row.created_at).toLocaleDateString() : '—'}
        </span>
      ),
    },
    {
      header: 'Action',
      render: (row) => (
        <Link
          to={`/interviews/${row.id}/plan`}
          className="btn btn-secondary"
          style={{ padding: '4px 10px', fontSize: 'var(--text-xs, 0.75rem)' }}
        >
          Review Plan
        </Link>
      ),
    },
  ];

  return (
    <div>
      {/* Reusable Enterprise PageHeader */}
      <PageHeader
        title="Recruiter Overview"
        description="Manage candidates, jobs, interview plans, and AI evaluations"
        actions={
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Button
              variant="primary"
              size="md"
              icon={Plus}
              onClick={() => navigate('/candidates/new')}
            >
              Add Candidate
            </Button>
            <Button
              variant="secondary"
              size="md"
              icon={Plus}
              onClick={() => navigate('/jobs/new')}
            >
              Create Job
            </Button>
          </div>
        }
      />

      {/* Error State Banner */}
      {error && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '12px 16px',
            borderRadius: 'var(--radius-sm, 6px)',
            backgroundColor: 'var(--danger-bg, #fef2f2)',
            border: '1px solid var(--danger-border, #fecaca)',
            color: 'var(--danger-text, #991b1b)',
            fontSize: 'var(--text-sm, 0.8125rem)',
            marginBottom: '20px',
          }}
        >
          <AlertCircle size={16} style={{ flexShrink: 0 }} />
          <span>{error}</span>
        </div>
      )}

      {/* Loading Presentation */}
      {loading ? (
        <Card padding="40px" style={{ textAlign: 'center', marginBottom: '24px' }}>
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '10px',
              color: 'var(--text-muted, #737d8c)',
              fontSize: 'var(--text-sm, 0.8125rem)',
            }}
          >
            <Loader2 size={20} style={{ animation: 'spin 1s linear infinite' }} />
            <span>Loading recruiter overview metrics...</span>
          </div>
        </Card>
      ) : (
        <>
          {/* KPI Cards Grid */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
              gap: '16px',
              marginBottom: '24px',
            }}
          >
            {statCards.map((card) => {
              const Icon = card.icon;
              return (
                <Link
                  key={card.label}
                  to={card.path}
                  style={{ textDecoration: 'none', color: 'inherit' }}
                >
                  <Card
                    padding="20px"
                    style={{
                      cursor: 'pointer',
                      transition: 'border-color 0.15s ease, box-shadow 0.15s ease',
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.borderColor = 'var(--border-strong, #cbd5e1)';
                      e.currentTarget.style.boxShadow = 'var(--shadow-md)';
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.borderColor = 'var(--border-subtle, #e2e8f0)';
                      e.currentTarget.style.boxShadow = 'var(--shadow-sm)';
                    }}
                  >
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                      }}
                    >
                      <div
                        style={{
                          width: '38px',
                          height: '38px',
                          borderRadius: '8px',
                          backgroundColor: card.bgColor,
                          color: card.color,
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                        }}
                      >
                        <Icon size={20} />
                      </div>
                      <ArrowUpRight size={16} style={{ color: 'var(--text-faint, #94a3b8)' }} />
                    </div>
                    <div style={{ marginTop: '16px' }}>
                      <span
                        style={{
                          fontSize: 'var(--text-xs, 0.75rem)',
                          color: 'var(--text-muted, #4B5563)',
                          fontWeight: 600,
                          textTransform: 'uppercase',
                          letterSpacing: '0.03em',
                        }}
                      >
                        {card.label}
                      </span>
                      <div
                        style={{
                          fontSize: '1.75rem',
                          fontWeight: 700,
                          color: 'var(--text-main, #111827)',
                          letterSpacing: '-0.02em',
                          marginTop: '4px',
                          lineHeight: 1.2,
                        }}
                      >
                        {card.value}
                      </div>
                    </div>
                  </Card>
                </Link>
              );
            })}
          </div>

          {/* Recent Interviews Section */}
          <Card
            title="My Recent Interviews"
            description="Active candidate sessions and evaluation status"
            headerAction={
              <Link
                to="/interviews"
                style={{
                  fontSize: 'var(--text-xs, 0.75rem)',
                  color: 'var(--primary-accent, #2563eb)',
                  fontWeight: 600,
                  textDecoration: 'none',
                }}
              >
                View all interviews →
              </Link>
            }
            padding="0"
          >
            {stats.recentInterviews.length === 0 ? (
              <div
                style={{
                  textAlign: 'center',
                  padding: '40px 20px',
                  color: 'var(--text-muted, #737d8c)',
                }}
              >
                <FileQuestion
                  size={32}
                  style={{
                    color: 'var(--text-faint, #94a3b8)',
                    margin: '0 auto 12px auto',
                    display: 'block',
                  }}
                />
                <p style={{ fontSize: 'var(--text-sm, 0.8125rem)', margin: 0 }}>
                  No interview sessions created yet. Click "Add Candidate" and "Create Job" to get started.
                </p>
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '12px',
                    marginTop: '16px',
                  }}
                >
                  <Button
                    variant="primary"
                    size="sm"
                    icon={Plus}
                    onClick={() => navigate('/candidates/new')}
                  >
                    Add Candidate
                  </Button>
                  <Button
                    variant="secondary"
                    size="sm"
                    icon={Plus}
                    onClick={() => navigate('/jobs/new')}
                  >
                    Create Job
                  </Button>
                </div>
              </div>
            ) : (
              <DataTable
                columns={interviewColumns}
                data={stats.recentInterviews}
                style={{ border: 'none', borderRadius: 0 }}
              />
            )}
          </Card>
        </>
      )}
    </div>
  );
}
