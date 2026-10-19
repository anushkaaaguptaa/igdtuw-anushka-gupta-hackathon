import React from 'react';
import { Loader2, AlertCircle, Inbox } from 'lucide-react';

export const LoadingSpinner: React.FC<{ message?: string; size?: number }> = ({
  message = 'Loading data...',
  size = 24,
}) => (
  <div
    style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '2.5rem 1rem',
      gap: '0.75rem',
      color: 'var(--text-secondary)',
    }}
  >
    <Loader2 size={size} className="spin" style={{ color: 'var(--accent-primary)' }} />
    <span style={{ fontSize: '0.85rem' }}>{message}</span>
  </div>
);

export const ErrorBanner: React.FC<{
  title?: string;
  message: string;
  onRetry?: () => void;
}> = ({ title = 'Failed to load data', message, onRetry }) => (
  <div
    style={{
      padding: '1rem 1.25rem',
      backgroundColor: 'var(--accent-rose-bg)',
      border: '1px solid rgba(244, 63, 94, 0.25)',
      borderRadius: 'var(--radius-lg)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      gap: '1rem',
    }}
  >
    <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
      <AlertCircle size={20} color="var(--accent-rose)" style={{ flexShrink: 0 }} />
      <div>
        <div style={{ fontWeight: 600, color: '#fda4af', fontSize: '0.9rem' }}>{title}</div>
        <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: '2px' }}>
          {message}
        </div>
      </div>
    </div>
    {onRetry && (
      <button onClick={onRetry} className="btn btn-outline" style={{ fontSize: '0.75rem' }}>
        Retry
      </button>
    )}
  </div>
);

export const EmptyState: React.FC<{
  icon?: React.ReactNode;
  title: string;
  description: string;
  actionLabel?: string;
  onAction?: () => void;
  actionLoading?: boolean;
}> = ({
  icon = <Inbox size={32} color="var(--text-muted)" />,
  title,
  description,
  actionLabel,
  onAction,
  actionLoading = false,
}) => (
  <div
    style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '3rem 1.5rem',
      textAlign: 'center',
      backgroundColor: 'var(--bg-card)',
      border: '1px dashed var(--border-default)',
      borderRadius: 'var(--radius-lg)',
    }}
  >
    <div style={{ marginBottom: '0.85rem' }}>{icon}</div>
    <div style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '0.35rem' }}>
      {title}
    </div>
    <div style={{ fontSize: '0.825rem', color: 'var(--text-muted)', maxWidth: '420px', marginBottom: actionLabel ? '1.25rem' : 0 }}>
      {description}
    </div>
    {actionLabel && onAction && (
      <button
        onClick={onAction}
        disabled={actionLoading}
        className="btn btn-primary"
        style={{ fontSize: '0.825rem' }}
      >
        {actionLoading ? <Loader2 size={14} className="spin" /> : null}
        {actionLabel}
      </button>
    )}
  </div>
);
