import React from 'react';
import { Loader2 } from 'lucide-react';

/**
 * Enterprise Slate Button component.
 * Supports primary, secondary, danger, outline, and ghost variants,
 * along with sm, md, and lg sizes, loading states, and icon slots.
 */
export default function Button({
  children,
  variant = 'primary',
  size = 'md',
  type = 'button',
  disabled = false,
  loading = false,
  onClick,
  className = '',
  style = {},
  icon: Icon,
  ...rest
}) {
  const baseStyle = {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 'var(--space-2, 8px)',
    fontFamily: 'inherit',
    fontWeight: 500,
    lineHeight: 1.25,
    borderRadius: 'var(--radius-sm, 6px)',
    border: '1px solid transparent',
    cursor: disabled || loading ? 'not-allowed' : 'pointer',
    opacity: disabled || loading ? 0.6 : 1,
    whiteSpace: 'nowrap',
    userSelect: 'none',
    transition: 'background-color 0.15s ease, border-color 0.15s ease, box-shadow 0.15s ease',
    ...style,
  };

  const sizeStyles = {
    sm: {
      padding: '4px 10px',
      fontSize: 'var(--text-xs, 0.75rem)',
      minHeight: '28px',
    },
    md: {
      padding: '8px 14px',
      fontSize: 'var(--text-sm, 0.8125rem)',
      minHeight: '36px',
    },
    lg: {
      padding: '10px 18px',
      fontSize: 'var(--text-base, 0.875rem)',
      minHeight: '42px',
    },
  };

  const variantStyles = {
    primary: {
      backgroundColor: 'var(--primary, #1e293b)',
      borderColor: 'var(--primary, #1e293b)',
      color: '#ffffff',
      boxShadow: 'var(--shadow-sm)',
    },
    secondary: {
      backgroundColor: '#ffffff',
      borderColor: 'var(--border-subtle, #e2e8f0)',
      color: 'var(--text-main, #202733)',
      boxShadow: 'var(--shadow-sm)',
    },
    outline: {
      backgroundColor: 'transparent',
      borderColor: 'var(--border-strong, #cbd5e1)',
      color: 'var(--text-main, #202733)',
    },
    danger: {
      backgroundColor: 'var(--danger-bg, #fef2f2)',
      borderColor: 'var(--danger-border, #fecaca)',
      color: 'var(--danger-text, #991b1b)',
    },
    ghost: {
      backgroundColor: 'transparent',
      borderColor: 'transparent',
      color: 'var(--text-muted, #737d8c)',
      boxShadow: 'none',
    },
    accent: {
      backgroundColor: 'var(--primary-accent, #2563eb)',
      borderColor: 'var(--primary-accent, #2563eb)',
      color: '#ffffff',
      boxShadow: 'var(--shadow-sm)',
    },
  };

  const selectedSize = sizeStyles[size] || sizeStyles.md;
  const selectedVariant = variantStyles[variant] || variantStyles.primary;

  const combinedStyle = {
    ...baseStyle,
    ...selectedSize,
    ...selectedVariant,
    ...style,
  };

  const handleMouseEnter = (e) => {
    if (disabled || loading) return;
    if (variant === 'primary') {
      e.currentTarget.style.backgroundColor = 'var(--primary-hover, #0f172a)';
      e.currentTarget.style.borderColor = 'var(--primary-hover, #0f172a)';
    } else if (variant === 'secondary') {
      e.currentTarget.style.backgroundColor = 'var(--bg-elevated, #f1f5f9)';
      e.currentTarget.style.borderColor = 'var(--border-strong, #cbd5e1)';
    } else if (variant === 'outline') {
      e.currentTarget.style.backgroundColor = 'var(--bg-elevated, #f1f5f9)';
    } else if (variant === 'danger') {
      e.currentTarget.style.backgroundColor = 'var(--danger, #dc2626)';
      e.currentTarget.style.borderColor = 'var(--danger, #dc2626)';
      e.currentTarget.style.color = '#ffffff';
    } else if (variant === 'ghost') {
      e.currentTarget.style.backgroundColor = 'var(--bg-elevated, #f1f5f9)';
      e.currentTarget.style.color = 'var(--text-main, #202733)';
    } else if (variant === 'accent') {
      e.currentTarget.style.backgroundColor = 'var(--primary-accent-hover, #1d4ed8)';
      e.currentTarget.style.borderColor = 'var(--primary-accent-hover, #1d4ed8)';
    }
  };

  const handleMouseLeave = (e) => {
    if (disabled || loading) return;
    Object.assign(e.currentTarget.style, selectedVariant, style);
  };

  return (
    <button
      type={type}
      disabled={disabled || loading}
      onClick={onClick}
      className={`btn ${className}`.trim()}
      style={combinedStyle}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      {...rest}
    >
      {loading ? (
        <>
          <Loader2
            size={size === 'sm' ? 14 : 16}
            className="animate-spin"
            style={{ animation: 'spin 1s linear infinite' }}
          />
          <span>{children}</span>
        </>
      ) : (
        <>
          {Icon && <Icon size={size === 'sm' ? 14 : 16} />}
          {children}
        </>
      )}
    </button>
  );
}
