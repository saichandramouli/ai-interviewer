import React, { useState, useEffect, useMemo } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { Plus, Briefcase, Search, AlertCircle } from 'lucide-react';
import { PageHeader, Card, Button, Badge, DataTable } from '../components/ui';

export default function JobsPage() {
  const navigate = useNavigate();
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all'); // 'all', 'active', 'inactive'

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

  // Combined client-side filtering: search (title & skills) + status (all, active, inactive)
  const filteredJobs = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();

    return jobs.filter((job) => {
      // 1. Status Filter
      if (statusFilter === 'active' && !job.is_active) return false;
      if (statusFilter === 'inactive' && job.is_active) return false;

      // 2. Search Query across title and required_skills array
      if (!q) return true;

      const titleMatch = (job.title || '').toLowerCase().includes(q);
      const skillsMatch = Array.isArray(job.required_skills)
        ? job.required_skills.some((skill) => String(skill).toLowerCase().includes(q))
        : false;

      return titleMatch || skillsMatch;
    });
  }, [jobs, searchQuery, statusFilter]);

  // Column definitions for DataTable
  const columns = [
    {
      header: 'Job Title',
      accessor: 'title',
      render: (row) => (
        <span style={{ fontWeight: 600, color: 'var(--text-main, #111827)' }}>
          {row.title || '—'}
        </span>
      ),
    },
    {
      header: 'Required Skills',
      accessor: 'required_skills',
      render: (row) => {
        const skills = Array.isArray(row.required_skills) ? row.required_skills : [];
        if (skills.length === 0) {
          return <span style={{ color: 'var(--text-faint, #6B7280)' }}>None specified</span>;
        }
        return (
          <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
            {skills.map((skill, i) => (
              <span
                key={i}
                style={{
                  backgroundColor: '#f1f5f9',
                  border: '1px solid #e2e8f0',
                  color: '#374151',
                  fontSize: '0.6875rem',
                  fontWeight: 500,
                  padding: '2px 8px',
                  borderRadius: '4px',
                  lineHeight: 1.25,
                }}
              >
                {skill}
              </span>
            ))}
          </div>
        );
      },
    },
    {
      header: 'Status',
      accessor: 'is_active',
      render: (row) => (
        <Badge variant={row.is_active ? 'success' : 'neutral'} dot>
          {row.is_active ? 'Active' : 'Inactive'}
        </Badge>
      ),
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
          to={`/jobs/${row.id}`}
          style={{
            color: 'var(--primary-accent, #2563eb)',
            fontWeight: 600,
            fontSize: 'var(--text-xs, 0.75rem)',
            textDecoration: 'none',
          }}
          onMouseEnter={(e) => (e.currentTarget.style.textDecoration = 'underline')}
          onMouseLeave={(e) => (e.currentTarget.style.textDecoration = 'none')}
        >
          Edit
        </Link>
      ),
    },
  ];

  return (
    <div>
      {/* Enterprise PageHeader */}
      <PageHeader
        title="Jobs"
        description="Manage job requisitions, required skills, and hiring status."
        actions={
          <Button
            variant="primary"
            size="md"
            icon={Plus}
            onClick={() => navigate('/jobs/new')}
          >
            Create Job
          </Button>
        }
      />

      {/* Error Banner */}
      {error && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '10px 14px',
            borderRadius: 'var(--radius-sm, 6px)',
            backgroundColor: 'var(--danger-bg, #fef2f2)',
            border: '1px solid var(--danger-border, #fecaca)',
            color: 'var(--danger-text, #991b1b)',
            fontSize: 'var(--text-sm, 0.8125rem)',
            marginBottom: '16px',
          }}
        >
          <AlertCircle size={16} style={{ flexShrink: 0 }} />
          <span>{error}</span>
        </div>
      )}

      {/* Main Directory Card */}
      <Card padding="0">
        {/* Search & Status Filter Controls */}
        <div
          style={{
            padding: '16px 20px',
            borderBottom: '1px solid var(--border-subtle, #e2e8f0)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '16px',
            flexWrap: 'wrap',
          }}
        >
          {/* Search Box */}
          <div style={{ position: 'relative', width: '100%', maxWidth: '340px' }}>
            <Search
              size={16}
              style={{
                position: 'absolute',
                left: '12px',
                top: '50%',
                transform: 'translateY(-50%)',
                color: 'var(--text-muted, #737d8c)',
                pointerEvents: 'none',
              }}
            />
            <input
              type="text"
              placeholder="Search by title or required skill..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="form-input"
              style={{
                paddingLeft: '36px',
                fontSize: 'var(--text-sm, 0.8125rem)',
                backgroundColor: '#ffffff',
                border: '1px solid var(--border-subtle, #e2e8f0)',
                borderRadius: 'var(--radius-sm, 6px)',
                width: '100%',
              }}
            />
          </div>

          {/* Status Segmented Buttons */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            {['all', 'active', 'inactive'].map((tab) => {
              const isSelected = statusFilter === tab;
              return (
                <button
                  key={tab}
                  type="button"
                  onClick={() => setStatusFilter(tab)}
                  style={{
                    padding: '6px 12px',
                    borderRadius: 'var(--radius-sm, 6px)',
                    fontSize: 'var(--text-xs, 0.75rem)',
                    fontWeight: 500,
                    cursor: 'pointer',
                    border: '1px solid',
                    borderColor: isSelected ? 'var(--primary, #1e293b)' : 'var(--border-subtle, #e2e8f0)',
                    backgroundColor: isSelected ? 'var(--primary, #1e293b)' : '#ffffff',
                    color: isSelected ? '#ffffff' : 'var(--text-body, #374151)',
                    textTransform: 'capitalize',
                    transition: 'all 0.15s ease',
                  }}
                >
                  {tab}
                </button>
              );
            })}
          </div>
        </div>

        {/* Directory Content */}
        {loading ? (
          <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted, #737d8c)' }}>
            Loading job requisitions...
          </div>
        ) : jobs.length === 0 ? (
          <div style={{ padding: '48px 20px', textAlign: 'center', color: 'var(--text-muted, #737d8c)' }}>
            <Briefcase size={32} style={{ color: 'var(--text-faint, #94a3b8)', margin: '0 auto 12px auto' }} />
            <p style={{ fontSize: 'var(--text-sm, 0.8125rem)', margin: '0 0 16px 0' }}>
              No jobs found. Click "Create Job" above to add your first position.
            </p>
            <Button
              variant="primary"
              size="sm"
              icon={Plus}
              onClick={() => navigate('/jobs/new')}
            >
              Create Job
            </Button>
          </div>
        ) : filteredJobs.length === 0 ? (
          <div style={{ padding: '40px 20px', textAlign: 'center', color: 'var(--text-muted, #737d8c)' }}>
            <p style={{ fontSize: 'var(--text-sm, 0.8125rem)', margin: 0 }}>
              No jobs match your search or filter criteria.
            </p>
            <div style={{ marginTop: '10px', display: 'flex', gap: '8px', justifyContent: 'center' }}>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setSearchQuery('');
                  setStatusFilter('all');
                }}
              >
                Clear filters
              </Button>
            </div>
          </div>
        ) : (
          <DataTable
            columns={columns}
            data={filteredJobs}
            style={{ border: 'none', borderRadius: 0 }}
          />
        )}
      </Card>
    </div>
  );
}
