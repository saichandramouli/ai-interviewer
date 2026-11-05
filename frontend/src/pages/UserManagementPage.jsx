import React, { useState, useEffect } from 'react';
import { api } from '../api/client';
import {
  Users,
  UserPlus,
  Mail,
  Copy,
  Check,
  Ban,
  Clock,
  Shield,
  AlertCircle,
  RefreshCw,
  Search,
  UserCheck,
} from 'lucide-react';

export default function UserManagementPage() {
  const [users, setUsers] = useState([]);
  const [invitations, setInvitations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  // Create Invitation Form State
  const [inviteEmail, setInviteEmail] = useState('');
  const [generatedLink, setGeneratedLink] = useState('');
  const [copiedLink, setCopiedLink] = useState(false);

  // Tab: 'users' or 'invitations'
  const [activeTab, setActiveTab] = useState('invitations');

  const fetchData = async () => {
    setLoading(true);
    setError('');
    try {
      const [usersResp, invResp] = await Promise.all([
        api.get('/admin/users/'),
        api.get('/admin/invitations/'),
      ]);
      setUsers(usersResp.data.results || (Array.isArray(usersResp.data) ? usersResp.data : []));
      setInvitations(invResp.data.results || (Array.isArray(invResp.data) ? invResp.data : []));
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load user management records. Ensure you are signed in as an Admin.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleCreateInvitation = async (e) => {
    e.preventDefault();
    if (!inviteEmail.trim()) return;

    setActionLoading(true);
    setError('');
    setSuccess('');
    setGeneratedLink('');

    try {
      const resp = await api.post('/admin/invitations/', { email: inviteEmail.trim() });
      const rawToken = resp.data.raw_token;
      const fullUrl = `${window.location.origin}/register?token=${rawToken}`;
      setGeneratedLink(fullUrl);
      setSuccess(`Invitation successfully created for ${inviteEmail.trim()}`);
      setInviteEmail('');
      fetchData();
    } catch (err) {
      const errMsg = err.response?.data?.email?.[0] || err.response?.data?.detail || 'Failed to generate invitation.';
      setError(errMsg);
    } finally {
      setActionLoading(false);
    }
  };

  const handleRevokeInvitation = async (invId) => {
    if (!window.confirm('Are you sure you want to revoke this invitation? The token will become immediately invalid.')) {
      return;
    }

    setActionLoading(true);
    setError('');
    try {
      await api.post(`/admin/invitations/${invId}/revoke/`);
      setSuccess('Invitation revoked successfully.');
      fetchData();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to revoke invitation.');
    } finally {
      setActionLoading(false);
    }
  };

  const handleToggleUserActive = async (userId, currentActive) => {
    const actionText = currentActive ? 'deactivate' : 'activate';
    if (!window.confirm(`Are you sure you want to ${actionText} this recruiter account?`)) {
      return;
    }

    setActionLoading(true);
    setError('');
    try {
      await api.post(`/admin/users/${userId}/toggle-active/`);
      setSuccess(`User account ${actionText}d successfully.`);
      fetchData();
    } catch (err) {
      setError(err.response?.data?.detail || `Failed to ${actionText} user.`);
    } finally {
      setActionLoading(false);
    }
  };

  const handleCopyLink = (linkToCopy) => {
    navigator.clipboard.writeText(linkToCopy);
    setCopiedLink(true);
    setTimeout(() => setCopiedLink(false), 2500);
  };

  return (
    <div>
      {/* Page Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '28px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <h2 style={{ fontSize: '1.75rem', fontWeight: 800, color: 'var(--text-main, #111827)', letterSpacing: '-0.02em' }}>
              User Management
            </h2>
            <span className="badge badge-completed" style={{ textTransform: 'uppercase', fontSize: '0.7rem' }}>
              Admin Console
            </span>
          </div>
          <p style={{ color: 'var(--text-muted, #4B5563)', fontSize: '0.875rem', marginTop: '4px' }}>
            Manage registered users and control recruiter invitation onboarding
          </p>
        </div>
        <button className="btn btn-secondary" onClick={fetchData} disabled={loading}>
          <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
          <span>Refresh</span>
        </button>
      </div>

      {error && (
        <div style={{ padding: '14px', borderRadius: 'var(--radius-md)', background: 'var(--danger-bg)', color: '#f87171', marginBottom: '20px' }}>
          {error}
        </div>
      )}

      {success && (
        <div style={{ padding: '14px', borderRadius: 'var(--radius-md)', background: 'rgba(16, 185, 129, 0.1)', border: '1px solid rgba(16, 185, 129, 0.3)', color: '#34d399', marginBottom: '20px' }}>
          {success}
        </div>
      )}

      {/* Invitation Generation Card */}
      <div className="glass-panel" style={{ padding: '24px', marginBottom: '28px' }}>
        <h3 style={{ fontSize: '1.125rem', fontWeight: 700, color: 'var(--text-heading, #1F2937)', marginBottom: '6px' }}>
          Invite New Recruiter
        </h3>
        <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted, #4B5563)', marginBottom: '16px' }}>
          Generate a single-use, 48-hour onboarding invitation link. Only the token hash is stored in the database.
        </p>

        <form onSubmit={handleCreateInvitation} style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', alignItems: 'flex-start' }}>
          <div style={{ flex: '1 1 300px' }}>
            <input
              type="email"
              required
              className="form-input"
              placeholder="recruiter.candidate@company.com"
              value={inviteEmail}
              onChange={(e) => setInviteEmail(e.target.value)}
            />
          </div>
          <button type="submit" className="btn btn-primary" disabled={actionLoading || !inviteEmail.trim()}>
            <UserPlus size={16} />
            <span>{actionLoading ? 'Creating...' : 'Create Recruiter Invitation'}</span>
          </button>
        </form>

        {/* Display freshly generated copyable link */}
        {generatedLink && (
          <div
            style={{
              marginTop: '16px',
              padding: '14px',
              borderRadius: 'var(--radius-md)',
              background: 'rgba(99, 102, 241, 0.1)',
              border: '1px solid rgba(99, 102, 241, 0.3)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: '12px',
            }}
          >
            <div style={{ minWidth: 0, flex: 1 }}>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted, #4B5563)', fontWeight: 600 }}>
                INVITATION REGISTRATION LINK (Share this securely with the invitee):
              </div>
              <div style={{ fontSize: '0.875rem', color: '#111827', wordBreak: 'break-all', fontFamily: 'monospace', marginTop: '2px' }}>
                {generatedLink}
              </div>
            </div>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => handleCopyLink(generatedLink)}
              style={{ flexShrink: 0 }}
            >
              {copiedLink ? <Check size={16} color="#34d399" /> : <Copy size={16} />}
              <span>{copiedLink ? 'Copied!' : 'Copy Link'}</span>
            </button>
          </div>
        )}
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: '12px', marginBottom: '20px', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '8px' }}>
        <button
          onClick={() => setActiveTab('invitations')}
          style={{
            background: 'none',
            border: 'none',
            padding: '8px 16px',
            cursor: 'pointer',
            fontSize: '0.9375rem',
            fontWeight: 700,
            color: '#111827',
            borderBottom: activeTab === 'invitations' ? '2px solid var(--primary, #1e293b)' : '2px solid transparent',
          }}
        >
          Invitations ({invitations.length})
        </button>
        <button
          onClick={() => setActiveTab('users')}
          style={{
            background: 'none',
            border: 'none',
            padding: '8px 16px',
            cursor: 'pointer',
            fontSize: '0.9375rem',
            fontWeight: 700,
            color: '#111827',
            borderBottom: activeTab === 'users' ? '2px solid var(--primary, #1e293b)' : '2px solid transparent',
          }}
        >
          Registered Users ({users.length})
        </button>
      </div>

      {/* Tab 1: Invitations List */}
      {activeTab === 'invitations' && (
        <div className="glass-panel" style={{ padding: '24px' }}>
          <h3 style={{ fontSize: '1.125rem', fontWeight: 700, color: 'var(--text-heading, #1F2937)', marginBottom: '16px' }}>
            Recruiter Invitations
          </h3>

          {invitations.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '40px 0', color: 'var(--text-faint, #6B7280)' }}>
              No invitations created yet. Use the form above to invite a recruiter.
            </div>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table className="data-table">
                <thead>
                  <tr>
                    <th style={{ color: '#111827' }}>Invited Email</th>
                    <th style={{ color: '#111827' }}>Status</th>
                    <th style={{ color: '#111827' }}>Created</th>
                    <th style={{ color: '#111827' }}>Expires</th>
                    <th style={{ color: '#111827' }}>Created By</th>
                    <th style={{ color: '#111827' }}>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {invitations.map((inv) => (
                    <tr key={inv.id}>
                      <td style={{ fontWeight: 600, color: '#111827' }}>{inv.email}</td>
                      <td>
                        <span
                          className={`badge ${
                            inv.status === 'pending'
                              ? 'badge-calling'
                              : inv.status === 'used'
                              ? 'badge-completed'
                              : 'badge-failed'
                          }`}
                        >
                          {inv.status}
                        </span>
                      </td>
                      <td style={{ color: '#111827', fontSize: '0.8125rem' }}>
                        {new Date(inv.created_at).toLocaleDateString()}
                      </td>
                      <td style={{ color: '#111827', fontSize: '0.8125rem' }}>
                        {new Date(inv.expires_at).toLocaleDateString()}
                      </td>
                      <td style={{ color: '#111827', fontSize: '0.8125rem' }}>
                        {inv.created_by_email || 'Admin'}
                      </td>
                      <td>
                        {inv.status === 'pending' && (
                          <button
                            type="button"
                            onClick={() => handleRevokeInvitation(inv.id)}
                            className="btn btn-secondary"
                            style={{ padding: '6px 12px', fontSize: '0.75rem', color: '#ef4444' }}
                            disabled={actionLoading}
                          >
                            <Ban size={14} />
                            <span>Revoke</span>
                          </button>
                        )}
                        {inv.status === 'used' && (
                          <span style={{ fontSize: '0.75rem', color: '#111827', fontWeight: 500 }}>Registered</span>
                        )}
                        {(inv.status === 'revoked' || inv.status === 'expired') && (
                          <span style={{ fontSize: '0.75rem', color: '#111827', fontWeight: 500 }}>Inactive</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Tab 2: Users List */}
      {activeTab === 'users' && (
        <div className="glass-panel" style={{ padding: '24px' }}>
          <h3 style={{ fontSize: '1.125rem', fontWeight: 700, color: 'var(--text-heading, #1F2937)', marginBottom: '16px' }}>
            Registered System Users
          </h3>

          {users.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '40px 0', color: 'var(--text-faint, #6B7280)' }}>
              No registered users found.
            </div>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table className="data-table">
                <thead>
                  <tr>
                    <th style={{ color: '#111827' }}>Email Address</th>
                    <th style={{ color: '#111827' }}>Name</th>
                    <th style={{ color: '#111827' }}>Role</th>
                    <th style={{ color: '#111827' }}>Account Status</th>
                    <th style={{ color: '#111827' }}>Joined</th>
                    <th style={{ color: '#111827' }}>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((u) => (
                    <tr key={u.id}>
                      <td style={{ fontWeight: 600, color: '#111827' }}>{u.email}</td>
                      <td style={{ color: '#111827' }}>
                        {[u.first_name, u.last_name].filter(Boolean).join(' ') || '—'}
                      </td>
                      <td>
                        <span className={`badge ${u.role === 'admin' ? 'badge-completed' : 'badge-draft'}`}>
                          {u.role}
                        </span>
                      </td>
                      <td>
                        <span className={`badge ${u.is_active || u.status === 'active' ? 'badge-completed' : 'badge-failed'}`}>
                          {u.is_active || u.status === 'active' ? 'active' : 'inactive'}
                        </span>
                      </td>
                      <td style={{ color: '#111827', fontSize: '0.8125rem' }}>
                        {new Date(u.date_joined).toLocaleDateString()}
                      </td>
                      <td>
                        {u.role === 'recruiter' ? (
                          <button
                            type="button"
                            className="btn btn-secondary"
                            style={{
                              padding: '4px 10px',
                              fontSize: '0.75rem',
                              color: u.is_active ? '#ef4444' : '#10b981',
                            }}
                            disabled={actionLoading}
                            onClick={() => handleToggleUserActive(u.id, u.is_active)}
                          >
                            {u.is_active ? 'Deactivate' : 'Activate'}
                          </button>
                        ) : (
                          <span style={{ fontSize: '0.75rem', color: '#111827', fontWeight: 500 }}>System Admin</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
