import React from 'react';
import { Loader2 } from 'lucide-react';

/**
 * Enterprise Slate DataTable component.
 * Supports column definitions, row keys, custom renderers, loading skeletons,
 * empty state messaging, and responsive horizontal scrolling.
 */
export default function DataTable({
  columns = [],
  data = [],
  rowKey = 'id',
  loading = false,
  emptyMessage = 'No records found.',
  className = '',
  style = {},
}) {
  return (
    <div
      className={`data-table-container ${className}`.trim()}
      style={{
        width: '100%',
        overflowX: 'auto',
        border: '1px solid var(--border-subtle, #e2e8f0)',
        borderRadius: 'var(--radius-md, 8px)',
        backgroundColor: '#ffffff',
        ...style,
      }}
    >
      <table
        className="data-table"
        style={{
          width: '100%',
          borderCollapse: 'collapse',
          textAlign: 'left',
          fontSize: 'var(--text-sm, 0.8125rem)',
        }}
      >
        <thead>
          <tr>
            {columns.map((col, idx) => (
              <th
                key={col.key || col.accessor || idx}
                style={{
                  padding: '10px 16px',
                  backgroundColor: 'var(--bg-primary, #f8fafc)',
                  color: 'var(--text-body, #374151)',
                  fontSize: 'var(--text-xs, 0.75rem)',
                  fontWeight: 600,
                  textTransform: 'uppercase',
                  letterSpacing: '0.04em',
                  borderBottom: '1px solid var(--border-subtle, #e2e8f0)',
                  whiteSpace: 'nowrap',
                  width: col.width || 'auto',
                  textAlign: col.align || 'left',
                  ...col.headerStyle,
                }}
              >
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {loading ? (
            <tr>
              <td
                colSpan={columns.length}
                style={{
                  padding: '36px 16px',
                  textAlign: 'center',
                  color: 'var(--text-muted, #4B5563)',
                  backgroundColor: '#ffffff',
                }}
              >
                <div style={{ display: 'inline-flex', alignItems: 'center', gap: '8px' }}>
                  <Loader2 size={18} style={{ animation: 'spin 1s linear infinite' }} />
                  <span>Loading records...</span>
                </div>
              </td>
            </tr>
          ) : data.length === 0 ? (
            <tr>
              <td
                colSpan={columns.length}
                style={{
                  padding: '40px 16px',
                  textAlign: 'center',
                  color: 'var(--text-muted, #4B5563)',
                  backgroundColor: '#ffffff',
                }}
              >
                {emptyMessage}
              </td>
            </tr>
          ) : (
            data.map((row, rowIdx) => {
              const keyVal = typeof rowKey === 'function' ? rowKey(row, rowIdx) : row[rowKey] || rowIdx;
              return (
                <tr
                  key={keyVal}
                  style={{
                    borderBottom: rowIdx === data.length - 1 ? 'none' : '1px solid var(--border-subtle, #e2e8f0)',
                    transition: 'background-color 0.15s ease',
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = 'var(--bg-primary, #f8fafc)')}
                  onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = '#ffffff')}
                >
                  {columns.map((col, colIdx) => {
                    const cellVal = col.accessor ? row[col.accessor] : undefined;
                    return (
                      <td
                        key={col.key || col.accessor || colIdx}
                        style={{
                          padding: '12px 16px',
                          color: 'var(--text-body, #374151)',
                          verticalAlign: 'middle',
                          textAlign: col.align || 'left',
                          ...col.cellStyle,
                        }}
                      >
                        {col.render ? col.render(row, rowIdx) : (cellVal !== undefined ? cellVal : '—')}
                      </td>
                    );
                  })}
                </tr>
              );
            })
          )}
        </tbody>
      </table>
    </div>
  );
}
