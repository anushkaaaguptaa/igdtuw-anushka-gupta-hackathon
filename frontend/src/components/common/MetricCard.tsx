import React from 'react';
import { Tooltip } from './Tooltip';

interface MetricCardProps {
  title: string;
  value: React.ReactNode;
  subtitle?: React.ReactNode;
  badge?: React.ReactNode;
  icon?: React.ReactNode;
  tooltip?: string;
  tooltipTitle?: string;
  loading?: boolean;
}

export const MetricCard: React.FC<MetricCardProps> = ({
  title,
  value,
  subtitle,
  badge,
  icon,
  tooltip,
  tooltipTitle,
  loading = false,
}) => {
  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
      <div className="card-header" style={{ marginBottom: '0.65rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
          <span className="card-title" style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
            {title}
          </span>
          {tooltip && <Tooltip content={tooltip} title={tooltipTitle || title} />}
        </div>
        {icon && (
          <div
            style={{
              padding: '6px',
              borderRadius: 'var(--radius-md)',
              backgroundColor: 'rgba(255, 255, 255, 0.03)',
              color: 'var(--text-secondary)',
              display: 'flex',
            }}
          >
            {icon}
          </div>
        )}
      </div>

      <div>
        <div style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--text-primary)' }} className="tabular-nums">
          {loading ? (
            <span style={{ color: 'var(--text-muted)', fontSize: '1.2rem' }}>Loading...</span>
          ) : (
            value ?? '—'
          )}
        </div>

        {(subtitle || badge) && (
          <div
            style={{
              marginTop: '0.45rem',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              fontSize: '0.75rem',
              color: 'var(--text-muted)',
              gap: '0.5rem',
            }}
          >
            <div>{subtitle}</div>
            {badge && <div>{badge}</div>}
          </div>
        )}
      </div>
    </div>
  );
};
