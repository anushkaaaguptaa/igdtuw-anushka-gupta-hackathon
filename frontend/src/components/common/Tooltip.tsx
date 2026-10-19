import React, { useState } from 'react';
import { Info } from 'lucide-react';

interface TooltipProps {
  content: string | React.ReactNode;
  title?: string;
  children?: React.ReactNode;
}

export const Tooltip: React.FC<TooltipProps> = ({ content, title, children }) => {
  const [visible, setVisible] = useState(false);

  return (
    <span
      style={{ position: 'relative', display: 'inline-flex', alignItems: 'center', cursor: 'help' }}
      onMouseEnter={() => setVisible(true)}
      onMouseLeave={() => setVisible(false)}
      onFocus={() => setVisible(true)}
      onBlur={() => setVisible(false)}
      tabIndex={0}
      aria-label={typeof content === 'string' ? content : title || 'Info tooltip'}
    >
      {children ? (
        children
      ) : (
        <Info
          size={14}
          style={{ color: 'var(--text-muted)', marginLeft: '4px', verticalAlign: 'middle' }}
        />
      )}

      {visible && (
        <span
          style={{
            position: 'absolute',
            bottom: 'calc(100% + 8px)',
            left: '50%',
            transform: 'translateX(-50%)',
            backgroundColor: '#0f172a',
            color: '#f8fafc',
            border: '1px solid var(--border-default)',
            borderRadius: 'var(--radius-md)',
            padding: '0.65rem 0.85rem',
            fontSize: '0.75rem',
            lineHeight: 1.4,
            width: 'max-content',
            maxWidth: '280px',
            boxShadow: 'var(--shadow-lg)',
            zIndex: 100,
            pointerEvents: 'none',
            textAlign: 'left',
          }}
        >
          {title && (
            <span style={{ display: 'block', fontWeight: 600, marginBottom: '0.25rem', color: '#93c5fd' }}>
              {title}
            </span>
          )}
          <span style={{ color: 'var(--text-secondary)' }}>{content}</span>
        </span>
      )}
    </span>
  );
};
