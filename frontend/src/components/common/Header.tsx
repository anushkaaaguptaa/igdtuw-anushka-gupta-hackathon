import React, { useState } from 'react';
import {
  Activity,
  Layers,
  Newspaper,
  PieChart,
  Sliders,
  RefreshCw,
  Settings,
  Check,
  Globe,
  X,
  Server
} from 'lucide-react';
import type { HealthResponse } from '../../types/api';
import type { ActiveTab } from '../../types/navigation';
import {
  getBaseUrl,
  setBaseUrlOverride,
  DEFAULT_RENDER_URL,
  DEFAULT_TUNNEL_URL
} from '../../services/apiClient';

interface HeaderProps {
  activeTab: ActiveTab;
  onTabChange: (tab: ActiveTab) => void;
  health: HealthResponse | null;
  healthLoading: boolean;
  onRefreshHealth: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  activeTab,
  onTabChange,
  health,
  healthLoading,
  onRefreshHealth,
}) => {
  const [isConfigOpen, setIsConfigOpen] = useState(false);
  const [currentUrl, setCurrentUrl] = useState(() => getBaseUrl());
  const [customInput, setCustomInput] = useState('');

  const navTabs: { id: ActiveTab; label: string; icon: React.ReactNode }[] = [
    { id: 'dashboard', label: 'Overview Dashboard', icon: <Activity size={16} /> },
    { id: 'intelligence', label: 'Financial Intelligence', icon: <Newspaper size={16} /> },
    { id: 'portfolio', label: 'Portfolio Management', icon: <PieChart size={16} /> },
    { id: 'stress_testing', label: 'Stress Testing', icon: <Sliders size={16} /> },
  ];

  const handleSelectEndpoint = (targetUrl: string | null) => {
    setBaseUrlOverride(targetUrl);
    const updated = getBaseUrl();
    setCurrentUrl(updated);
    setIsConfigOpen(false);
    onRefreshHealth();
  };

  const handleCustomSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (customInput.trim()) {
      handleSelectEndpoint(customInput.trim());
      setCustomInput('');
    }
  };

  // Human-readable status label
  const getStatusLabel = () => {
    if (health?.status === 'healthy') {
      return `Backend v${health.version} (${health.inference_mode})`;
    }
    if (healthLoading) {
      return health ? 'Syncing...' : 'Waking backend (~30s)...';
    }
    return 'Backend Offline (auto-retrying)';
  };

  return (
    <header className="app-header">
      <div className="brand-section">
        <div className="brand-logo-icon">
          <Layers size={18} />
        </div>
        <div>
          <div className="brand-title">RiskLens AI</div>
          <div className="brand-tagline">Financial Risk Intelligence Platform</div>
        </div>
      </div>

      <nav className="nav-tabs" aria-label="Main Navigation">
        {navTabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => onTabChange(tab.id)}
            className={`nav-tab-btn ${activeTab === tab.id ? 'active' : ''}`}
            type="button"
          >
            {tab.icon}
            <span>{tab.label}</span>
          </button>
        ))}
      </nav>

      <div className="header-actions">
        <div
          className="health-indicator"
          style={{ cursor: 'pointer' }}
          onClick={() => setIsConfigOpen(true)}
          title="Click to view or switch backend endpoint"
        >
          <span
            className={`status-dot ${
              health?.status === 'healthy'
                ? 'healthy'
                : healthLoading
                ? 'degraded'
                : 'offline'
            }`}
          />
          <span style={{ color: 'var(--text-secondary)' }}>
            {getStatusLabel()}
          </span>
          <button
            onClick={(e) => {
              e.stopPropagation();
              onRefreshHealth();
            }}
            disabled={healthLoading}
            title="Refresh System Health"
            type="button"
            style={{
              background: 'transparent',
              border: 'none',
              color: 'var(--text-muted)',
              cursor: 'pointer',
              display: 'inline-flex',
              padding: '2px',
            }}
          >
            <RefreshCw size={13} className={healthLoading ? 'spin' : ''} />
          </button>
          <button
            onClick={(e) => {
              e.stopPropagation();
              setIsConfigOpen(true);
            }}
            title="Configure Backend Connection"
            type="button"
            style={{
              background: 'transparent',
              border: 'none',
              color: 'var(--text-muted)',
              cursor: 'pointer',
              display: 'inline-flex',
              padding: '2px',
            }}
          >
            <Settings size={13} />
          </button>
        </div>
      </div>

      {/* Endpoint Configuration Modal */}
      {isConfigOpen && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.75)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 9999,
            padding: '1rem',
          }}
          onClick={() => setIsConfigOpen(false)}
        >
          <div
            style={{
              backgroundColor: 'var(--bg-surface, #1e222d)',
              border: '1px solid var(--border-subtle, #2e3440)',
              borderRadius: '12px',
              padding: '1.5rem',
              width: '100%',
              maxWidth: '520px',
              boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.5)',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: 600, fontSize: '1rem' }}>
                <Server size={18} style={{ color: 'var(--accent-blue, #3b82f6)' }} />
                <span>Backend Connection Manager</span>
              </div>
              <button
                onClick={() => setIsConfigOpen(false)}
                style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}
              >
                <X size={18} />
              </button>
            </div>

            <div style={{ fontSize: '0.825rem', color: 'var(--text-secondary)', marginBottom: '1.25rem', lineHeight: 1.5 }}>
              Choose which backend service RiskLens AI connects to. Both cloud hosting and live neural tunnels are supported.
            </div>

            {/* Presets */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', marginBottom: '1.25rem' }}>
              {/* Preset 1: Render Cloud */}
              <div
                onClick={() => handleSelectEndpoint(DEFAULT_RENDER_URL)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '0.75rem 1rem',
                  borderRadius: '8px',
                  border: `1px solid ${currentUrl === DEFAULT_RENDER_URL ? 'var(--accent-blue, #3b82f6)' : 'var(--border-subtle, #2e3440)'}`,
                  backgroundColor: currentUrl === DEFAULT_RENDER_URL ? 'rgba(59, 130, 246, 0.1)' : 'rgba(255, 255, 255, 0.02)',
                  cursor: 'pointer',
                }}
              >
                <div>
                  <div style={{ fontWeight: 500, fontSize: '0.875rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <Globe size={14} style={{ color: '#10b981' }} />
                    <span>Render Cloud (24/7 Deployed API)</span>
                  </div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.2rem', fontFamily: 'monospace' }}>
                    {DEFAULT_RENDER_URL}
                  </div>
                </div>
                {currentUrl === DEFAULT_RENDER_URL && <Check size={16} style={{ color: 'var(--accent-blue, #3b82f6)' }} />}
              </div>

              {/* Preset 2: Cloudflare Tunnel */}
              <div
                onClick={() => handleSelectEndpoint(DEFAULT_TUNNEL_URL)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '0.75rem 1rem',
                  borderRadius: '8px',
                  border: `1px solid ${currentUrl === DEFAULT_TUNNEL_URL ? 'var(--accent-blue, #3b82f6)' : 'var(--border-subtle, #2e3440)'}`,
                  backgroundColor: currentUrl === DEFAULT_TUNNEL_URL ? 'rgba(59, 130, 246, 0.1)' : 'rgba(255, 255, 255, 0.02)',
                  cursor: 'pointer',
                }}
              >
                <div>
                  <div style={{ fontWeight: 500, fontSize: '0.875rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <Activity size={14} style={{ color: '#f59e0b' }} />
                    <span>Live Mac Tunnel (Apple Silicon / GPU FinBERT)</span>
                  </div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.2rem', fontFamily: 'monospace' }}>
                    {DEFAULT_TUNNEL_URL}
                  </div>
                </div>
                {currentUrl === DEFAULT_TUNNEL_URL && <Check size={16} style={{ color: 'var(--accent-blue, #3b82f6)' }} />}
              </div>

              {/* Preset 3: Localhost */}
              <div
                onClick={() => handleSelectEndpoint('http://localhost:8000')}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '0.75rem 1rem',
                  borderRadius: '8px',
                  border: `1px solid ${currentUrl === 'http://localhost:8000' ? 'var(--accent-blue, #3b82f6)' : 'var(--border-subtle, #2e3440)'}`,
                  backgroundColor: currentUrl === 'http://localhost:8000' ? 'rgba(59, 130, 246, 0.1)' : 'rgba(255, 255, 255, 0.02)',
                  cursor: 'pointer',
                }}
              >
                <div>
                  <div style={{ fontWeight: 500, fontSize: '0.875rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <Server size={14} style={{ color: '#8b5cf6' }} />
                    <span>Localhost Development</span>
                  </div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.2rem', fontFamily: 'monospace' }}>
                    http://localhost:8000
                  </div>
                </div>
                {currentUrl === 'http://localhost:8000' && <Check size={16} style={{ color: 'var(--accent-blue, #3b82f6)' }} />}
              </div>
            </div>

            {/* Custom URL Input */}
            <form onSubmit={handleCustomSubmit} style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem' }}>
              <input
                type="url"
                placeholder="https://your-custom-backend.com"
                value={customInput}
                onChange={(e) => setCustomInput(e.target.value)}
                style={{
                  flex: 1,
                  padding: '0.5rem 0.75rem',
                  borderRadius: '6px',
                  border: '1px solid var(--border-subtle, #2e3440)',
                  backgroundColor: 'rgba(0,0,0,0.2)',
                  color: 'white',
                  fontSize: '0.825rem',
                }}
              />
              <button
                type="submit"
                style={{
                  padding: '0.5rem 1rem',
                  borderRadius: '6px',
                  backgroundColor: 'var(--accent-blue, #3b82f6)',
                  color: 'white',
                  border: 'none',
                  fontSize: '0.825rem',
                  fontWeight: 500,
                  cursor: 'pointer',
                }}
              >
                Connect
              </button>
            </form>

            <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
              <button
                type="button"
                onClick={() => handleSelectEndpoint(null)}
                style={{
                  background: 'transparent',
                  border: 'none',
                  color: 'var(--text-muted)',
                  fontSize: '0.75rem',
                  cursor: 'pointer',
                  textDecoration: 'underline',
                }}
              >
                Reset to default environment URL
              </button>
            </div>
          </div>
        </div>
      )}
    </header>
  );
};
