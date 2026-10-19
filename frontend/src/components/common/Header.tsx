import React from 'react';
import {
  Activity,
  Layers,
  Newspaper,
  PieChart,
  Sliders,
  RefreshCw
} from 'lucide-react';
import type { HealthResponse } from '../../types/api';
import type { ActiveTab } from '../../types/navigation';

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
  const navTabs: { id: ActiveTab; label: string; icon: React.ReactNode }[] = [
    { id: 'dashboard', label: 'Overview Dashboard', icon: <Activity size={16} /> },
    { id: 'intelligence', label: 'Financial Intelligence', icon: <Newspaper size={16} /> },
    { id: 'portfolio', label: 'Portfolio Management', icon: <PieChart size={16} /> },
    { id: 'stress_testing', label: 'Stress Testing', icon: <Sliders size={16} /> },
  ];

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
        <div className="health-indicator">
          <span
            className={`status-dot ${
              healthLoading ? 'degraded' : health?.status === 'healthy' ? 'healthy' : 'offline'
            }`}
          />
          <span style={{ color: 'var(--text-secondary)' }}>
            {healthLoading
              ? 'Probing Backend...'
              : health?.status === 'healthy'
              ? `Backend v${health.version} (${health.inference_mode})`
              : 'Backend Disconnected'}
          </span>
          <button
            onClick={onRefreshHealth}
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
        </div>
      </div>
    </header>
  );
};
