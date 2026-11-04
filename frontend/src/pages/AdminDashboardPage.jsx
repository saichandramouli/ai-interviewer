import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api/client';
import {
  Users,
  UserCheck,
  Mail,
  UserPlus,
  Clock,
  Ban,
  Check,
  Copy,
  RefreshCw,
  ArrowUpRight,
  ShieldCheck,
  CheckCircle,
} from 'lucide-react';

export default function AdminDashboardPage() {
  const [metrics, setMetrics] = useState({
    totalRecruiters: 0,
    activeRecruiters: 0,
    pendingInvitations: 0,
    usedInvitations: 0,
    expiredInvitations: 0,
    revokedInvitations: 0,
  });
  const [recentUsers, setRecentUsers] = useState([]);
  const [recentInvitations, setRecentInvitations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  // Quick Invite State
  const [inviteEmail, setInviteEmail] = useState('');
  const [generatedLink, setGeneratedLink] = useState('');
  const [copiedLink, setCopiedLink] = useState(false);

  const fetchAdminData = async () => {
    setLoading(true);
    setError('');
    try {
      const [usersResp, invResp] = await Promise.all([
        api.get('/admin/users/'),
        api.get('/admin/invitations/'),
      ]);

      const users = usersResp.data.results || (Array.isArray(usersResp.data) ? usersResp.data : []);
      const invs = invResp.data.results || (Array.isArray(invResp.data) ? invResp.data : []);

      // Calculate recruiter metrics
      const recruiters = users.filter((u) => u.role === 'recruiter');
      const activeRecruiters = recruiters.filter((u) => u.is_active || u.status === 'active');

      const pendingInvs = invs.filter((i) => i.status === 'pending');
      const usedInvs = invs.filter((i) => i.status === 'used');
      const expiredInvs = invs.filter((i) => i.status === 'expired');
      const revokedInvs = invs.filter((i) => i.status === 'revoked');

      setMetrics({
        totalRecruiters: recruiters.length,
        activeRecruiters: activeRecruiters.length,
        pendingInvitations: pendingInvs.length,
        usedInvitations: usedInvs.length,
        expiredInvitations: expiredInvs.length,
        revokedInvitations: revokedInvs.length,
      });

      setRecentUsers(recruiters.slice(0, 5));
      setRecentInvitations(invs.slice(0, 5));
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load administrator metrics.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAdminData();
  }, []);

  const handleQuickInvite = async (e) => {
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
      fetchAdminData();
    } catch (err) {
      const errMsg = err.response?.data?.email?.[0] || err.response?.data?.detail || 'Failed to create invitation.';
      setError(errMsg);
    } finally {
      setActionLoading(false);
    }
  };

  const handleRevoke = async (invId) => {
    if (!window.confirm('Are you sure you want to revoke this invitation?')) return;
    setActionLoading(true);
    try {
      await api.post(`/admin/invitations/${invId}/revoke/`);
      setSuccess('Invitation revoked successfully.');
      fetchAdminData();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to revoke invitation.');
    } finally {
      setActionLoading(false);
    }
  };

  const handleToggleUserActive = async (userId, currentActive) => {
    const actionText = currentActive ? 'deactivate' : 'activate';
    if (!window.confirm(`Are you sure you want to ${actionText} this recruiter account?`)) return;

    setActionLoading(true);
    try {
      await api.post(`/admin/users/${userId}/toggle-active/`);
      setSuccess(`Recruiter account ${actionText}d successfully.`);
      fetchAdminData();
    } catch (err) {
      setError(err.response?.data?.detail || `Failed to ${actionText} recruiter.`);
    } finally {
      setActionLoading(false);
    }
  };

  const handleCopy = (text) => {
    navigator.clipboard.writeText(text);
    setCopiedLink(true);
    setTimeout(() => setCopiedLink(false), 2500);
  };

  if (loading) {
    return <div style={{ color: 'var(--text-muted)' }}>Loading administrator overview...</div>;
  }

  const statCards = [
    { label: 'Total Registered Recruiters', value: metrics.totalRecruiters, icon: Users, color: '#6366f1' },
    { label: 'Active Recruiters', value: metrics.activeRecruiters, icon: UserCheck, color: '#10b981' },
    { label: 'Pending Invitations', value: metrics.pendingInvitations, icon: Mail, color: '#06b6d4' },
    { label: 'Used / Expired Invitations', value: `${metrics.usedInvitations} / ${metrics.expiredInvitations}`, icon: Clock, color: '#f59e0b' },
  ];

  return (
    <div>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '28px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <h2 style={{ fontSize: '1.75rem', fontWeight: 800, color: '#fff', letterSpacing: '-0.02em' }}>
              Admin Dashboard
            </h2>
            <span className="badge badge-completed" style={{ fontSize: '0.7rem' }}>Administrator</span>
          </div>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem', marginTop: '4px' }}>
            User and recruiter account management console
          </p>
        </div>
        <div style={{ display: 'flex', gap: '12px' }}>
          <button className="btn btn-secondary" onClick={fetchAdminData} disabled={loading}>
            <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
            <span>Refresh</span>
          </button>
          <Link to="/admin/users" className="btn btn-primary">
            <ShieldCheck size={16} />
            <span>Manage All Users</span>
          </Link>
        </div>
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

      {/* Prominent Create Recruiter / Invite Recruiter Action */}
      <div className="glass-panel" style={{ padding: '24px', marginBottom: '28px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
          <div
            style={{
              width: '36px',
              height: '36px',
              borderRadius: '8px',
              background: 'linear-gradient(135deg, var(--primary), var(--secondary))',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#fff',
            }}
          >
            <UserPlus size={18} />
          </div>
          <div>
            <h3 style={{ fontSize: '1.125rem', fontWeight: 700, color: '#fff' }}>
              Create Recruiter Account (Send Invitation)
            </h3>
            <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>
              Issue a secure, single-use 48-hour registration invitation token for a new recruiter.
            </p>
          </div>
        </div>

        <form onSubmit={handleQuickInvite} style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', marginTop: '16px' }}>
          <div style={{ flex: '1 1 320px' }}>
            <input
              type="email"
              required
              className="form-input"
              placeholder="recruiter.name@company.com"
              value={inviteEmail}
              onChange={(e) => setInviteEmail(e.target.value)}
            />
          </div>
          <button type="submit" className="btn btn-primary" disabled={actionLoading || !inviteEmail.trim()}>
            <UserPlus size={16} />
            <span>{actionLoading ? 'Generating...' : 'Invite Recruiter'}</span>
          </button>
        </form>

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
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 600 }}>
                INVITATION LINK:
              </div>
              <div style={{ fontSize: '0.875rem', color: '#fff', wordBreak: 'break-all', fontFamily: 'monospace', marginTop: '2px' }}>
                {generatedLink}
              </div>
            </div>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => handleCopy(generatedLink)}
              style={{ flexShrink: 0 }}
            >
              {copiedLink ? <Check size={16} color="#34d399" /> : <Copy size={16} />}
              <span>{copiedLink ? 'Copied!' : 'Copy Link'}</span>
            </button>
          </div>
        )}
      </div>

      {/* Metrics Row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '20px', marginBottom: '32px' }}>
        {statCards.map((card) => {
          const Icon = card.icon;
          return (
            <div key={card.label} className="glass-panel" style={{ padding: '24px' }}>
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
              </div>
              <div style={{ marginTop: '18px' }}>
                <span style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', fontWeight: 600 }}>{card.label}</span>
                <div style={{ fontSize: '1.875rem', fontWeight: 800, color: '#fff', marginTop: '4px' }}>{card.value}</div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Two-column layout: Recruiters and Invitations */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(450px, 1fr))', gap: '24px' }}>
        {/* Recruiter Accounts List */}
        <div className="glass-panel" style={{ padding: '24px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <h3 style={{ fontSize: '1.125rem', fontWeight: 700, color: '#fff' }}>Recruiter Accounts</h3>
            <Link to="/admin/users" style={{ fontSize: '0.8125rem', color: 'var(--primary)', fontWeight: 600 }}>
              View all
            </Link>
          </div>

          {recentUsers.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '30px 0', color: 'var(--text-faint)' }}>
              No recruiters registered yet. Issue an invitation to onboard a recruiter.
            </div>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Email</th>
                    <th>Status</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {recentUsers.map((u) => (
                    <tr key={u.id}>
                      <td style={{ fontWeight: 600, color: '#fff' }}>
                        <div>{u.email}</div>
                        <div style={{ fontSize: '0.75rem', color: 'var(--text-faint)' }}>
                          {[u.first_name, u.last_name].filter(Boolean).join(' ') || 'Recruiter'}
                        </div>
                      </td>
                      <td>
                        <span className={`badge ${u.status === 'active' || u.is_active ? 'badge-completed' : 'badge-failed'}`}>
                          {u.status === 'active' || u.is_active ? 'active' : 'inactive'}
                        </span>
                      </td>
                      <td>
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
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Recent Invitations */}
        <div className="glass-panel" style={{ padding: '24px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <h3 style={{ fontSize: '1.125rem', fontWeight: 700, color: '#fff' }}>Recent Invitations</h3>
            <Link to="/admin/users" style={{ fontSize: '0.8125rem', color: 'var(--primary)', fontWeight: 600 }}>
              Manage all
            </Link>
          </div>

          {recentInvitations.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '30px 0', color: 'var(--text-faint)' }}>
              No invitations issued yet.
            </div>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Invited Email</th>
                    <th>Status</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {recentInvitations.map((inv) => (
                    <tr key={inv.id}>
                      <td style={{ fontWeight: 600, color: '#fff' }}>
                        <div>{inv.email}</div>
                        <div style={{ fontSize: '0.75rem', color: 'var(--text-faint)' }}>
                          Expires: {new Date(inv.expires_at).toLocaleDateString()}
                        </div>
                      </td>
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
                      <td>
                        {inv.status === 'pending' ? (
                          <button
                            type="button"
                            className="btn btn-secondary"
                            style={{ padding: '4px 10px', fontSize: '0.75rem', color: '#ef4444' }}
                            disabled={actionLoading}
                            onClick={() => handleRevoke(inv.id)}
                          >
                            <Ban size={12} />
                            <span>Revoke</span>
                          </button>
                        ) : (
                          <span style={{ fontSize: '0.75rem', color: 'var(--text-faint)' }}>
                            {inv.status}
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

