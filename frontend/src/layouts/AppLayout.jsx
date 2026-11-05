import React, { useState } from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import {
  LayoutDashboard,
  Users,
  Briefcase,
  FileQuestion,
  LogOut,
  ShieldCheck,
  Menu,
  X,
  User,
} from 'lucide-react';
import { Badge } from '../components/ui';

export default function AppLayout() {
  const { userEmail, userRole, isAdmin, logout } = useAuth();
  const navigate = useNavigate();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  // Strictly separated role-based navigation menus
  const navItems = isAdmin
    ? [
        { label: 'Dashboard', path: '/admin/dashboard', icon: LayoutDashboard },
        { label: 'User Management', path: '/admin/users', icon: ShieldCheck },
      ]
    : [
        { label: 'Dashboard', path: '/dashboard', icon: LayoutDashboard },
        { label: 'Candidates', path: '/candidates', icon: Users },
        { label: 'Jobs', path: '/jobs', icon: Briefcase },
        { label: 'Interviews', path: '/interviews', icon: FileQuestion },
      ];

  const closeMobileMenu = () => setMobileMenuOpen(false);

  return (
    <div style={{ display: 'flex', minHeight: '100vh', backgroundColor: 'var(--bg-primary, #f8fafc)' }}>
      {/* Mobile Backdrop */}
      {mobileMenuOpen && (
        <div
          onClick={closeMobileMenu}
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(15, 23, 42, 0.5)',
            zIndex: 45,
            transition: 'opacity 0.2s ease',
          }}
        />
      )}

      {/* Sidebar Navigation */}
      <aside
        style={{
          width: '260px',
          backgroundColor: 'var(--bg-secondary, #0f172a)',
          borderRight: '1px solid #1e293b',
          display: 'flex',
          flexDirection: 'column',
          padding: '24px 16px',
          position: 'sticky',
          top: 0,
          height: '100vh',
          zIndex: 50,
          boxShadow: '1px 0 3px 0 rgba(0, 0, 0, 0.1)',
          flexShrink: 0,
        }}
        className={mobileMenuOpen ? 'sidebar-open' : ''}
      >
        {/* Brand / Logo Header */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '0 8px 24px 8px',
            borderBottom: '1px solid #1e293b',
            marginBottom: '16px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div
              style={{
                width: '32px',
                height: '32px',
                borderRadius: '6px',
                backgroundColor: 'var(--primary-accent, #2563eb)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#ffffff',
                fontWeight: 700,
                fontSize: '0.875rem',
                letterSpacing: '-0.02em',
              }}
            >
              AI
            </div>
            <div>
              <h1
                style={{
                  fontSize: '0.9375rem',
                  fontWeight: 700,
                  letterSpacing: '-0.015em',
                  color: '#ffffff',
                  margin: 0,
                  lineHeight: 1.2,
                }}
              >
                AI Interviewer
              </h1>
              <span
                style={{
                  fontSize: '0.6875rem',
                  color: '#94a3b8',
                  textTransform: 'uppercase',
                  letterSpacing: '0.04em',
                  fontWeight: 500,
                }}
              >
                {isAdmin ? 'Admin Console' : 'Recruiter Console'}
              </span>
            </div>
          </div>

          {/* Mobile Close Button */}
          <button
            onClick={closeMobileMenu}
            style={{
              color: '#94a3b8',
              background: 'transparent',
              border: 'none',
              cursor: 'pointer',
              padding: '4px',
              display: 'none',
            }}
            className="mobile-close-btn"
            aria-label="Close menu"
          >
            <X size={20} />
          </button>
        </div>

        {/* Navigation Items */}
        <nav style={{ display: 'flex', flexDirection: 'column', gap: '4px', flex: 1 }}>
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.path}
                to={item.path}
                onClick={closeMobileMenu}
                style={({ isActive }) => ({
                  display: 'flex',
                  alignItems: 'center',
                  gap: '12px',
                  padding: '9px 12px',
                  borderRadius: 'var(--radius-sm, 6px)',
                  fontSize: 'var(--text-sm, 0.8125rem)',
                  fontWeight: isActive ? 600 : 500,
                  color: isActive ? '#ffffff' : '#94a3b8',
                  backgroundColor: isActive ? 'rgba(37, 99, 235, 0.15)' : 'transparent',
                  borderLeft: isActive ? '3px solid var(--primary-accent, #2563eb)' : '3px solid transparent',
                  transition: 'background-color 0.15s ease, color 0.15s ease',
                  textDecoration: 'none',
                })}
              >
                <Icon size={18} />
                <span>{item.label}</span>
              </NavLink>
            );
          })}
        </nav>

        {/* User Card & Logout in Sidebar Footer */}
        <div
          style={{
            padding: '12px',
            borderRadius: 'var(--radius-sm, 6px)',
            backgroundColor: '#1e293b',
            border: '1px solid #334155',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div
              style={{
                fontSize: '0.8125rem',
                fontWeight: 600,
                color: '#ffffff',
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                maxWidth: '140px',
              }}
              title={userEmail || 'User'}
            >
              {userEmail || 'User'}
            </div>
            <span
              className={`badge ${isAdmin ? 'badge-completed' : 'badge-draft'}`}
              style={{ fontSize: '0.625rem', padding: '2px 6px' }}
            >
              {userRole}
            </span>
          </div>
          <button
            onClick={handleLogout}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              fontSize: '0.75rem',
              color: '#94a3b8',
              marginTop: '8px',
              cursor: 'pointer',
              transition: 'color 0.15s ease',
              background: 'none',
              border: 'none',
              padding: 0,
            }}
            onMouseEnter={(e) => (e.currentTarget.style.color = '#ef4444')}
            onMouseLeave={(e) => (e.currentTarget.style.color = '#94a3b8')}
          >
            <LogOut size={13} />
            <span>Sign out</span>
          </button>
        </div>
      </aside>

      {/* Main Content Area */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        {/* Clean Enterprise Top Header */}
        <header
          style={{
            height: '56px',
            borderBottom: '1px solid var(--border-subtle, #e2e8f0)',
            backgroundColor: '#ffffff',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '0 24px',
            position: 'sticky',
            top: 0,
            zIndex: 30,
            boxShadow: 'var(--shadow-sm, 0 1px 2px 0 rgba(0, 0, 0, 0.05))',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <button
              onClick={() => setMobileMenuOpen(true)}
              style={{
                display: 'none',
                background: 'transparent',
                border: 'none',
                color: 'var(--text-main, #202733)',
                cursor: 'pointer',
                padding: '4px',
              }}
              className="mobile-menu-toggle"
              aria-label="Open menu"
            >
              <Menu size={20} />
            </button>
            <div style={{ fontSize: 'var(--text-sm, 0.8125rem)', color: 'var(--text-muted, #737d8c)' }}>
              Console:{' '}
              <strong style={{ color: 'var(--text-main, #202733)' }}>
                {isAdmin ? 'Administrator Access' : 'Recruiter Access'}
              </strong>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <Badge variant="success" dot>
              {isAdmin ? 'Admin Mode' : 'Recruiter Mode'}
            </Badge>
          </div>
        </header>

        {/* Main Body Viewport */}
        <main
          style={{
            padding: '24px',
            flex: 1,
            minWidth: 0,
            backgroundColor: 'var(--bg-primary, #f8fafc)',
          }}
        >
          <Outlet />
        </main>
      </div>
    </div>
  );
}
