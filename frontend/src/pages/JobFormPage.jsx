import React, { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { api } from '../api/client';
import { AlertCircle } from 'lucide-react';
import { PageHeader, Card, Button } from '../components/ui';

export default function JobFormPage() {
  const { id } = useParams();
  const isEditMode = Boolean(id);
  const navigate = useNavigate();

  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [skillsInput, setSkillsInput] = useState('');
  const [experience, setExperience] = useState('');
  const [isActive, setIsActive] = useState(true);
  const [loading, setLoading] = useState(false);
  const [fetching, setFetching] = useState(isEditMode);
  const [error, setError] = useState('');

  // Fetch existing job details if in edit mode (/jobs/:id)
  useEffect(() => {
    if (isEditMode) {
      const fetchJobDetails = async () => {
        setFetching(true);
        try {
          const resp = await api.get(`/jobs/${id}/`);
          const job = resp.data;
          setTitle(job.title || '');
          setDescription(job.description || '');
          setSkillsInput(Array.isArray(job.required_skills) ? job.required_skills.join(', ') : '');
          setExperience(job.experience_requirements || '');
          setIsActive(job.is_active !== undefined ? job.is_active : true);
        } catch (err) {
          setError(err.response?.data?.detail || 'Failed to load existing job details.');
        } finally {
          setFetching(false);
        }
      };
      fetchJobDetails();
    }
  }, [id, isEditMode]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    const skillsArray = skillsInput
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean);

    const payload = {
      title,
      description,
      required_skills: skillsArray,
      experience_requirements: experience,
      is_active: isActive,
    };

    try {
      if (isEditMode) {
        await api.patch(`/jobs/${id}/`, payload);
      } else {
        await api.post('/jobs/', payload);
      }
      navigate('/jobs');
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to save job position.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: '680px' }}>
      {/* PageHeader with breadcrumb trail */}
      <PageHeader
        title={isEditMode ? 'Edit Job Position' : 'Create Job Position'}
        description="Define expectations and competencies to guide AI interview questioning"
        breadcrumbs={[
          { label: 'Jobs', to: '/jobs' },
          { label: isEditMode ? 'Edit Position' : 'New Position' },
        ]}
      />

      <Card padding="28px">
        {error && (
          <div
            style={{
              padding: '10px 14px',
              borderRadius: 'var(--radius-sm, 6px)',
              backgroundColor: 'var(--danger-bg, #fef2f2)',
              border: '1px solid var(--danger-border, #fecaca)',
              color: 'var(--danger-text, #991b1b)',
              fontSize: 'var(--text-sm, 0.8125rem)',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              marginBottom: '20px',
            }}
          >
            <AlertCircle size={16} style={{ flexShrink: 0 }} />
            <span>{error}</span>
          </div>
        )}

        {fetching ? (
          <div style={{ padding: '30px', textAlign: 'center', color: 'var(--text-muted, #737d8c)' }}>
            Loading job requisition details...
          </div>
        ) : (
          <form onSubmit={handleSubmit}>
            <div className="form-group" style={{ marginBottom: '16px' }}>
              <label
                className="form-label"
                htmlFor="title"
                style={{
                  fontSize: 'var(--text-sm, 0.8125rem)',
                  fontWeight: 500,
                  color: 'var(--text-body, #374151)',
                  marginBottom: '4px',
                  display: 'block',
                }}
              >
                Job Title *
              </label>
              <input
                id="title"
                required
                className="form-input"
                placeholder="e.g. Senior Backend Engineer"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                style={{
                  width: '100%',
                  padding: '8px 12px',
                  backgroundColor: '#ffffff',
                  border: '1px solid var(--border-subtle, #e2e8f0)',
                  borderRadius: 'var(--radius-sm, 6px)',
                  color: 'var(--text-body, #374151)',
                  fontSize: 'var(--text-base, 0.875rem)',
                }}
              />
            </div>

            <div className="form-group" style={{ marginBottom: '16px' }}>
              <label
                className="form-label"
                htmlFor="description"
                style={{
                  fontSize: 'var(--text-sm, 0.8125rem)',
                  fontWeight: 500,
                  color: 'var(--text-body, #374151)',
                  marginBottom: '4px',
                  display: 'block',
                }}
              >
                Job Description *
              </label>
              <textarea
                id="description"
                required
                className="form-textarea"
                placeholder="Describe core responsibilities, architecture challenges, and expectations..."
                rows={5}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                style={{
                  width: '100%',
                  padding: '8px 12px',
                  backgroundColor: '#ffffff',
                  border: '1px solid var(--border-subtle, #e2e8f0)',
                  borderRadius: 'var(--radius-sm, 6px)',
                  color: 'var(--text-body, #374151)',
                  fontSize: 'var(--text-base, 0.875rem)',
                  minHeight: '110px',
                  resize: 'vertical',
                }}
              />
            </div>

            <div className="form-group" style={{ marginBottom: '16px' }}>
              <label
                className="form-label"
                htmlFor="skills"
                style={{
                  fontSize: 'var(--text-sm, 0.8125rem)',
                  fontWeight: 500,
                  color: 'var(--text-body, #374151)',
                  marginBottom: '4px',
                  display: 'block',
                }}
              >
                Required Skills (Comma separated)
              </label>
              <input
                id="skills"
                className="form-input"
                placeholder="e.g. Python, Django, PostgreSQL, Distributed Systems"
                value={skillsInput}
                onChange={(e) => setSkillsInput(e.target.value)}
                style={{
                  width: '100%',
                  padding: '8px 12px',
                  backgroundColor: '#ffffff',
                  border: '1px solid var(--border-subtle, #e2e8f0)',
                  borderRadius: 'var(--radius-sm, 6px)',
                  color: 'var(--text-body, #374151)',
                  fontSize: 'var(--text-base, 0.875rem)',
                }}
              />
            </div>

            <div className="form-group" style={{ marginBottom: '20px' }}>
              <label
                className="form-label"
                htmlFor="experience"
                style={{
                  fontSize: 'var(--text-sm, 0.8125rem)',
                  fontWeight: 500,
                  color: 'var(--text-body, #374151)',
                  marginBottom: '4px',
                  display: 'block',
                }}
              >
                Experience Requirements
              </label>
              <input
                id="experience"
                className="form-input"
                placeholder="e.g. 5+ years experience building APIs"
                value={experience}
                onChange={(e) => setExperience(e.target.value)}
                style={{
                  width: '100%',
                  padding: '8px 12px',
                  backgroundColor: '#ffffff',
                  border: '1px solid var(--border-subtle, #e2e8f0)',
                  borderRadius: 'var(--radius-sm, 6px)',
                  color: 'var(--text-body, #374151)',
                  fontSize: 'var(--text-base, 0.875rem)',
                }}
              />
            </div>

            <div
              style={{
                marginBottom: '24px',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '10px 12px',
                backgroundColor: 'var(--bg-primary, #f8fafc)',
                border: '1px solid var(--border-subtle, #e2e8f0)',
                borderRadius: 'var(--radius-sm, 6px)',
              }}
            >
              <input
                type="checkbox"
                id="isActive"
                checked={isActive}
                onChange={(e) => setIsActive(e.target.checked)}
                style={{
                  width: '16px',
                  height: '16px',
                  accentColor: 'var(--primary-accent, #2563eb)',
                  cursor: 'pointer',
                }}
              />
              <label
                htmlFor="isActive"
                style={{
                  fontSize: 'var(--text-sm, 0.8125rem)',
                  color: 'var(--text-body, #374151)',
                  cursor: 'pointer',
                  userSelect: 'none',
                }}
              >
                Mark requisition as active (available for scheduling candidate interviews)
              </label>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <Button
                type="submit"
                variant="primary"
                disabled={loading}
                loading={loading}
                style={{ padding: '10px 20px' }}
              >
                {isEditMode
                  ? loading
                    ? 'Saving Changes...'
                    : 'Save Changes'
                  : loading
                    ? 'Creating Job...'
                    : 'Create Job Requisition'}
              </Button>
              <Button
                type="button"
                variant="secondary"
                onClick={() => navigate('/jobs')}
                style={{ padding: '10px 16px' }}
              >
                Cancel
              </Button>
            </div>
          </form>
        )}
      </Card>
    </div>
  );
}
