import React from 'react';
import {
  Globe2,
  TrendingUp,
  AlertTriangle,
  Landmark,
  TrendingDown,
  CheckCircle2,
  Sparkles
} from 'lucide-react';
import { Badge } from '../common/Badge';
import type { StressScenarioDefinition } from '../../types/api';

interface ScenarioSelectorCardProps {
  scenarios: StressScenarioDefinition[];
  selectedScenarioId: string;
  onSelectScenario: (scenarioId: string) => void;
  disabled?: boolean;
}

export const ScenarioSelectorCard: React.FC<ScenarioSelectorCardProps> = ({
  scenarios,
  selectedScenarioId,
  onSelectScenario,
  disabled = false,
}) => {
  const getScenarioIcon = (scenarioId: string) => {
    switch (scenarioId) {
      case 'GEOPOLITICAL_ESCALATION':
        return <Globe2 size={18} color="var(--accent-primary)" />;
      case 'CENTRAL_BANK_RATE_HIKE':
        return <TrendingUp size={18} color="var(--accent-amber)" />;
      case 'CREDIT_EVENT_OR_DEFAULT':
        return <AlertTriangle size={18} color="var(--accent-rose)" />;
      case 'BANKING_SECTOR_CRISIS':
        return <Landmark size={18} color="var(--accent-purple)" />;
      case 'MACROECONOMIC_RECESSION':
      default:
        return <TrendingDown size={18} color="var(--accent-cyan)" />;
    }
  };

  const getCategoryBadgeVariant = (cat: string) => {
    switch (cat) {
      case 'GEOPOLITICAL':
        return 'blue';
      case 'MACROECONOMIC':
        return 'cyan';
      case 'CREDIT_EVENT':
        return 'red';
      case 'REGULATORY_ACTION':
        return 'purple';
      default:
        return 'neutral';
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <div className="card-title" style={{ fontSize: '0.95rem' }}>
            Select Macro / Financial Stress Scenario
          </div>
          <div className="card-subtitle">
            Catalog of canonical historical and hypothetical factor transmission models
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
          <Sparkles size={13} color="var(--accent-primary)" />
          <span>5 Validated Catalogs</span>
        </div>
      </div>

      {/* Scenarios Grid */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
          gap: '0.75rem',
        }}
      >
        {scenarios.map((s) => {
          const isSelected = s.scenario_id === selectedScenarioId;
          const shocks = s.factor_shocks || {};

          return (
            <div
              key={s.scenario_id}
              onClick={() => !disabled && onSelectScenario(s.scenario_id)}
              style={{
                backgroundColor: isSelected ? 'rgba(59, 130, 246, 0.08)' : 'var(--bg-surface)',
                border: `1px solid ${isSelected ? 'var(--accent-primary)' : 'var(--border-subtle)'}`,
                borderRadius: 'var(--radius-lg)',
                padding: '1rem',
                cursor: disabled ? 'not-allowed' : 'pointer',
                transition: 'all 0.15s ease-in-out',
                position: 'relative',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
                boxShadow: isSelected ? '0 0 0 1px var(--accent-primary), var(--shadow-md)' : 'none',
                opacity: disabled ? 0.6 : 1,
              }}
            >
              {/* Header with Title and Selected Check */}
              <div>
                <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '0.5rem', marginBottom: '0.4rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <div
                      style={{
                        padding: '6px',
                        borderRadius: 'var(--radius-md)',
                        backgroundColor: 'rgba(255, 255, 255, 0.03)',
                        display: 'flex',
                      }}
                    >
                      {getScenarioIcon(s.scenario_id)}
                    </div>
                    <div>
                      <div style={{ fontWeight: 600, fontSize: '0.85rem', color: isSelected ? '#ffffff' : 'var(--text-primary)' }}>
                        {s.name}
                      </div>
                      <div className="mono" style={{ fontSize: '0.675rem', color: 'var(--text-muted)' }}>
                        {s.scenario_id}
                      </div>
                    </div>
                  </div>

                  {isSelected && (
                    <CheckCircle2 size={16} color="var(--accent-primary)" style={{ flexShrink: 0, marginTop: '2px' }} />
                  )}
                </div>

                {/* Target Categories */}
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.3rem', margin: '0.5rem 0' }}>
                  {s.target_event_categories.map((cat) => (
                    <Badge key={cat} variant={getCategoryBadgeVariant(cat)}>
                      {cat}
                    </Badge>
                  ))}
                </div>

                {/* Description */}
                <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', margin: '0.4rem 0 0.75rem', lineHeight: 1.4 }}>
                  {s.description}
                </p>
              </div>

              {/* Factor Shock Metrics Preview */}
              <div
                style={{
                  backgroundColor: 'rgba(0, 0, 0, 0.2)',
                  borderRadius: 'var(--radius-sm)',
                  padding: '0.5rem 0.65rem',
                  display: 'grid',
                  gridTemplateColumns: 'repeat(2, 1fr)',
                  gap: '0.35rem 0.5rem',
                  fontSize: '0.7rem',
                  borderTop: '1px solid var(--border-subtle)',
                }}
              >
                <div>
                  <span style={{ color: 'var(--text-muted)' }}>Equity Shock: </span>
                  <strong style={{ color: 'var(--accent-rose)' }}>
                    {shocks.equity_market_shock !== undefined ? `${((shocks.equity_market_shock as number) * 100).toFixed(1)}%` : '—'}
                  </strong>
                </div>
                <div>
                  <span style={{ color: 'var(--text-muted)' }}>Rates Shift: </span>
                  <strong style={{ color: (shocks.rate_shock_bps as number) > 0 ? 'var(--accent-amber)' : 'var(--accent-emerald)' }}>
                    {shocks.rate_shock_bps !== undefined
                      ? `${(shocks.rate_shock_bps as number) > 0 ? '+' : ''}${shocks.rate_shock_bps} bps`
                      : '—'}
                  </strong>
                </div>
                <div>
                  <span style={{ color: 'var(--text-muted)' }}>Credit Spreads: </span>
                  <strong style={{ color: 'var(--accent-amber)' }}>
                    {shocks.credit_spread_bps !== undefined ? `+${shocks.credit_spread_bps} bps` : '—'}
                  </strong>
                </div>
                <div>
                  <span style={{ color: 'var(--text-muted)' }}>Loan PD Mult: </span>
                  <strong style={{ color: 'var(--accent-purple)' }}>
                    {shocks.loan_pd_multiplier !== undefined ? `${shocks.loan_pd_multiplier}x` : '—'}
                  </strong>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
