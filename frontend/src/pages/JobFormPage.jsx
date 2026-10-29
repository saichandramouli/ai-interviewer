import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { ArrowLeft, AlertCircle } from 'lucide-react';

export default function JobFormPage() {
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [skillsInput, setSkillsInput] = useState('');
  const [experience, setExperience] = useState('');
  const [isActive, setIsActive] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    const skillsArray = skillsInput
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean);

    try {
      await api.post('/jobs/', {
        title,
        description,
        required_skills: skillsArray,
        experience_requirements: experience,
        is_active: isActive,
      });
      navigate('/jobs');
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to save job position.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: '680px' }}>
      <button
        onClick={() => navigate('/jobs')}
        className="btn btn-secondary"
        style={{ marginBottom: '20px', padding: '6px 12px', fontSize: '0.8125rem' }}
      >
        <ArrowLeft size={14} />
        <span>Back to Jobs</span>
      </button>

      <div className="glass-panel" style={{ padding: '32px' }}>
        <h2 style={{ fontSize: '1.5rem', fontWeight: 800, color: '#fff', marginBottom: '8px' }}>
          Create Job Position
        </h2>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem', marginBottom: '24px' }}>
          Define expectations and competencies to guide AI interview questioning
        </p>

        {error && (
          <div style={{ padding: '12px 14px', borderRadius: 'var(--radius-md)', background: 'var(--danger-bg)', color: '#f87171', marginBottom: '20px' }}>
            <AlertCircle size={16} />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label" htmlFor="title">Job Title *</label>
            <input
              id="title"
              required
              className="form-input"
              placeholder="e.g. Senior Backend Engineer"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
            />
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="description">Job Description *</label>
            <textarea
              id="description"
              required
              className="form-textarea"
              placeholder="Describe core responsibilities, architecture challenges, and expectations..."
              rows={5}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="skills">Required Skills (Comma separated)</label>
            <input
              id="skills"
              className="form-input"
              placeholder="e.g. Python, Django, PostgreSQL, Distributed Systems"
              value={skillsInput}
              onChange={(e) => setSkillsInput(e.target.value)}
            />
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="experience">Experience Requirements</label>
            <input
              id="experience"
              className="form-input"
              placeholder="e.g. 5+ years experience building APIs"
              value={experience}
              onChange={(e) => setExperience(e.target.value)}
            />
          </div>

          <div style={{ marginTop: '24px', display: 'flex', alignItems: 'center', gap: '10px' }}>
            <input
              type="checkbox"
              id="isActive"
              checked={isActive}
              onChange={(e) => setIsActive(e.target.checked)}
              style={{ width: '16px', height: '16px', accentColor: 'var(--primary)' }}
            />
            <label htmlFor="isActive" style={{ fontSize: '0.875rem', color: '#fff', cursor: 'pointer' }}>
              Mark requisition as active
            </label>
          </div>

          <div style={{ marginTop: '28px', display: 'flex', gap: '12px' }}>
            <button type="submit" disabled={loading} className="btn btn-primary" style={{ padding: '12px 24px' }}>
              {loading ? 'Creating Job...' : 'Create Job Requisition'}
            </button>
            <button
              type="button"
              onClick={() => navigate('/jobs')}
              className="btn btn-secondary"
            >
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
