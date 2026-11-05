import React from 'react';

/**
 * Enterprise Slate Card component.
 * Features a solid white surface, hairline border (#e2e8f0),
 * clean 8px radius, and optional header, title, description, and footer.
 */
export default function Card({
  children,
  title,
  description,
  headerAction,
  footer,
  padding = '20px',
  className = '',
  style = {},
  ...rest
}) {
  const cardStyle = {
    backgroundColor: 'var(--bg-card, #ffffff)',
    border: '1px solid var(--border-subtle, #e2e8f0)',
    borderRadius: 'var(--radius-md, 8px)',
    boxShadow: 'var(--shadow-sm, 0 1px 2px 0 rgba(0, 0, 0, 0.05))',
    overflow: 'hidden',
    ...style,
  };

  const hasHeader = Boolean(title || description || headerAction);

  return (
    <div className={`card-panel ${className}`.trim()} style={cardStyle} {...rest}>
      {hasHeader && (
        <div
          style={{
            padding: '16px 20px',
            borderBottom: '1px solid var(--border-subtle, #e2e8f0)',
            display: 'flex',
            alignItems: 'flex-start',
            justifyContent: 'space-between',
            gap: '12px',
          }}
        >
          <div>
            {title && (
              <h3
                style={{
                  fontSize: 'var(--text-md, 1rem)',
                  fontWeight: 600,
                  color: 'var(--text-heading, #1F2937)',
                  margin: 0,
                  lineHeight: 1.3,
                }}
              >
                {title}
              </h3>
            )}
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
          {headerAction && <div>{headerAction}</div>}
        </div>
      )}

      <div style={{ padding }}>{children}</div>

      {footer && (
        <div
          style={{
            padding: '12px 20px',
            backgroundColor: 'var(--bg-primary, #f8fafc)',
            borderTop: '1px solid var(--border-subtle, #e2e8f0)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'flex-end',
            gap: '8px',
          }}
        >
          {footer}
        </div>
      )}
    </div>
  );
}
