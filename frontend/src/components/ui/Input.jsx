import React from 'react';
import { AlertCircle } from 'lucide-react';

/**
 * Enterprise Slate Input component.
 * Supports labels, helper text, inline validation errors,
 * required asterisks, and controlled value bindings.
 */
export default function Input({
  label,
  id,
  type = 'text',
  placeholder,
  value,
  onChange,
  required = false,
  disabled = false,
  error,
  helperText,
  className = '',
  style = {},
  inputStyle = {},
  ...rest
}) {
  const inputId = id || (label ? `input-${label.toLowerCase().replace(/\s+/g, '-')}` : undefined);

  return (
    <div
      className={`form-group ${className}`.trim()}
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 'var(--space-1, 4px)',
        marginBottom: 'var(--space-4, 16px)',
        ...style,
      }}
    >
      {label && (
        <label
          htmlFor={inputId}
          className="form-label"
          style={{
            fontSize: 'var(--text-sm, 0.8125rem)',
            fontWeight: 500,
            color: 'var(--text-body, #374151)',
            display: 'flex',
            alignItems: 'center',
            gap: '4px',
          }}
        >
          <span>{label}</span>
          {required && <span style={{ color: 'var(--danger, #dc2626)' }}>*</span>}
        </label>
      )}

      <input
        id={inputId}
        type={type}
        placeholder={placeholder}
        value={value}
        onChange={onChange}
        required={required}
        disabled={disabled}
        className="form-input"
        style={{
          width: '100%',
          padding: '8px 12px',
          backgroundColor: '#ffffff',
          border: error ? '1px solid var(--danger, #dc2626)' : '1px solid var(--border-subtle, #e2e8f0)',
          borderRadius: 'var(--radius-sm, 6px)',
          color: 'var(--text-body, #374151)',
          fontFamily: 'inherit',
          fontSize: 'var(--text-base, 0.875rem)',
          lineHeight: 1.4,
          boxShadow: 'var(--shadow-sm, 0 1px 2px 0 rgba(0, 0, 0, 0.05))',
          outline: 'none',
          opacity: disabled ? 0.6 : 1,
          cursor: disabled ? 'not-allowed' : 'text',
          transition: 'border-color 0.15s ease, box-shadow 0.15s ease',
          ...inputStyle,
        }}
        onFocus={(e) => {
          if (!error) {
            e.currentTarget.style.borderColor = 'var(--border-focus, #2563eb)';
            e.currentTarget.style.boxShadow = '0 0 0 3px rgba(37, 99, 235, 0.12)';
          }
        }}
        onBlur={(e) => {
          if (!error) {
            e.currentTarget.style.borderColor = 'var(--border-subtle, #e2e8f0)';
            e.currentTarget.style.boxShadow = 'var(--shadow-sm, 0 1px 2px 0 rgba(0, 0, 0, 0.05))';
          }
        }}
        {...rest}
      />

      {error ? (
        <span
          style={{
            fontSize: 'var(--text-xs, 0.75rem)',
            color: 'var(--danger, #dc2626)',
            display: 'flex',
            alignItems: 'center',
            gap: '4px',
            marginTop: '2px',
          }}
        >
          <AlertCircle size={12} style={{ flexShrink: 0 }} />
          <span>{error}</span>
        </span>
      ) : helperText ? (
        <span
          style={{
            fontSize: 'var(--text-xs, 0.75rem)',
            color: 'var(--text-muted, #737d8c)',
            marginTop: '2px',
          }}
        >
          {helperText}
        </span>
      ) : null}
    </div>
  );
}
