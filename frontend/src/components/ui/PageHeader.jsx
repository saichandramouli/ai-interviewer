import React from 'react';
import { ChevronRight } from 'lucide-react';
import { Link } from 'react-router-dom';

/**
 * Enterprise Slate PageHeader component.
 * Provides unified page title, description, optional breadcrumb trail,
 * and primary/secondary action button slots.
 */
export default function PageHeader({
  title,
  description,
  breadcrumbs = [],
  actions,
  className = '',
  style = {},
}) {
  return (
    <div
      className={`page-header ${className}`.trim()}
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 'var(--space-2, 8px)',
        marginBottom: 'var(--space-6, 24px)',
        ...style,
      }}
    >
      {/* Optional Breadcrumb Trail */}
      {breadcrumbs && breadcrumbs.length > 0 && (
        <nav
          aria-label="Breadcrumbs"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            fontSize: 'var(--text-xs, 0.75rem)',
            color: 'var(--text-muted, #4B5563)',
            marginBottom: '4px',
          }}
        >
          {breadcrumbs.map((crumb, idx) => {
            const isLast = idx === breadcrumbs.length - 1;
            return (
              <React.Fragment key={crumb.label || idx}>
                {crumb.to && !isLast ? (
                  <Link
                    to={crumb.to}
                    style={{
                      color: 'var(--text-muted, #4B5563)',
                      textDecoration: 'none',
                      transition: 'color 0.15s ease',
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--primary-accent, #2563eb)')}
                    onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--text-muted, #4B5563)')}
                  >
                    {crumb.label}
                  </Link>
                ) : (
                  <span
                    style={{
                      color: isLast ? 'var(--text-main, #111827)' : 'var(--text-muted, #4B5563)',
                      fontWeight: isLast ? 600 : 400,
                    }}
                  >
                    {crumb.label}
                  </span>
                )}
                {!isLast && <ChevronRight size={12} style={{ color: 'var(--text-faint, #6B7280)' }} />}
              </React.Fragment>
            );
          })}
        </nav>
      )}

      {/* Main Title and Action Row */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '16px',
        }}
      >
        <div>
          <h1
            style={{
              fontSize: 'var(--text-xl, 1.25rem)',
              fontWeight: 700,
              color: 'var(--text-main, #111827)',
              letterSpacing: '-0.015em',
              margin: 0,
              lineHeight: 1.25,
            }}
          >
            {title}
          </h1>
          {description && (
            <p
              style={{
                fontSize: 'var(--text-sm, 0.8125rem)',
                color: 'var(--text-muted, #4B5563)',
                margin: '4px 0 0 0',
                lineHeight: 1.4,
              }}
            >
              {description}
            </p>
          )}
        </div>

        {actions && (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 'var(--space-3, 12px)',
              flexWrap: 'wrap',
            }}
          >
            {actions}
          </div>
        )}
      </div>
    </div>
  );
}
