import React from 'react';

/**
 * Enterprise Slate Badge component.
 * Supports status variants: success, warning, danger, info, and neutral,
 * with optional dot indicator and custom icons.
 */
export default function Badge({
  children,
  variant = 'neutral',
  status, // optional status string for automatic mapping
  dot = false,
  icon: Icon,
  className = '',
  style = {},
  ...rest
}) {
  // Resolve variant from status string if provided
  let resolvedVariant = variant;
  if (status) {
    const s = String(status).toLowerCase();
    if (['completed', 'succeeded', 'active', 'granted', 'hire', 'strong_hire'].includes(s)) {
      resolvedVariant = 'success';
    } else if (['scheduled', 'running', 'in_progress', 'info'].includes(s)) {
      resolvedVariant = 'info';
    } else if (['calling', 'pending', 'hold', 'paused', 'warning'].includes(s)) {
      resolvedVariant = 'warning';
    } else if (['failed', 'cancelled', 'rejected', 'no_hire', 'revoked', 'expired', 'danger'].includes(s)) {
      resolvedVariant = 'danger';
    } else {
      resolvedVariant = 'neutral';
    }
  }

  const variantStyles = {
    neutral: {
      backgroundColor: '#f1f5f9',
      borderColor: '#e2e8f0',
      color: '#475569',
      dotColor: '#64748b',
    },
    success: {
      backgroundColor: 'var(--success-bg, #ecfdf5)',
      borderColor: 'var(--success-border, #bbf7d0)',
      color: 'var(--success-text, #166534)',
      dotColor: 'var(--success, #16a34a)',
    },
    warning: {
      backgroundColor: 'var(--warning-bg, #fffbeb)',
      borderColor: 'var(--warning-border, #fde68a)',
      color: 'var(--warning-text, #92400e)',
      dotColor: 'var(--warning, #d97706)',
    },
    danger: {
      backgroundColor: 'var(--danger-bg, #fef2f2)',
      borderColor: 'var(--danger-border, #fecaca)',
      color: 'var(--danger-text, #991b1b)',
      dotColor: 'var(--danger, #dc2626)',
    },
    info: {
      backgroundColor: 'var(--info-bg, #eff6ff)',
      borderColor: 'var(--info-border, #bfdbfe)',
      color: 'var(--info-text, #1e40af)',
      dotColor: 'var(--info, #2563eb)',
    },
  };

  const selected = variantStyles[resolvedVariant] || variantStyles.neutral;

  const badgeStyle = {
    display: 'inline-flex',
    alignItems: 'center',
    gap: '5px',
    padding: '2px 8px',
    borderRadius: 'var(--radius-sm, 6px)',
    fontSize: 'var(--text-xs, 0.75rem)',
    fontWeight: 500,
    lineHeight: 1.25,
    border: '1px solid',
    backgroundColor: selected.backgroundColor,
    borderColor: selected.borderColor,
    color: selected.color,
    whiteSpace: 'nowrap',
    textTransform: 'capitalize',
    letterSpacing: '0.01em',
    ...style,
  };

  return (
    <span className={`badge ${className}`.trim()} style={badgeStyle} {...rest}>
      {dot && (
        <span
          style={{
            width: '6px',
            height: '6px',
            borderRadius: '50%',
            backgroundColor: selected.dotColor,
            flexShrink: 0,
          }}
        />
      )}
      {Icon && <Icon size={12} style={{ flexShrink: 0 }} />}
      <span>{children || status}</span>
    </span>
  );
}
