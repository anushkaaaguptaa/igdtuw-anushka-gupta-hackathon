import React, { useState } from 'react';
import { Search, Tag, CheckCircle2 } from 'lucide-react';
import { Badge } from '../common/Badge';
import { Tooltip } from '../common/Tooltip';
import type { AssetShockDetail } from '../../types/api';

interface AssetShockTableProps {
  shocks: AssetShockDetail[];
  baselineValue: number;
  stressedValue: number;
  totalLoss: number;
  creditLoss?: number;
  marketLoss?: number;
}

export const AssetShockTable: React.FC<AssetShockTableProps> = ({
  shocks,
  baselineValue,
  stressedValue,
  totalLoss,
  creditLoss = 0,
  marketLoss = 0,
}) => {
  const [selectedType, setSelectedType] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');

  const filteredShocks = shocks.filter((s) => {
    const matchesType = selectedType === 'all' || s.asset_type === selectedType;
    if (!matchesType) return false;

    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    return (
      s.ticker.toLowerCase().includes(q) ||
      s.name.toLowerCase().includes(q) ||
      s.sector.toLowerCase().includes(q) ||
      s.valuation_methodology.toLowerCase().includes(q)
    );
  });

  const getAssetTypeBadgeVariant = (type: string) => {
    switch (type) {
      case 'corporate_loan':
        return 'amber';
      case 'government_bond':
        return 'cyan';
      case 'corporate_bond':
        return 'purple';
      case 'equity':
        return 'blue';
      case 'derivative':
        return 'green';
      default:
        return 'neutral';
    }
  };

  const formatAssetTypeName = (type: string) => {
    switch (type) {
      case 'corporate_loan':
        return 'Commercial Loan';
      case 'government_bond':
        return 'Sovereign Treasury';
      case 'corporate_bond':
        return 'Corporate Bond';
      case 'equity':
        return 'Public Equity';
      case 'derivative':
        return 'Put Option Hedge';
      default:
        return type;
    }
  };

  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      {/* Table Header & Search */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem' }}>
        <div>
          <div className="card-title">Simulated Factor Transmission by Instrument</div>
          <div className="card-subtitle">
            Before-and-after carrying values, percentage repricing, and mathematical factor breakdown
          </div>
        </div>

        {/* Search Input */}
        <div style={{ position: 'relative', width: '220px' }}>
          <Search size={14} style={{ position: 'absolute', left: '8px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
          <input
            type="text"
            placeholder="Search instrument..."
            className="form-input"
            style={{ paddingLeft: '28px', fontSize: '0.8rem', height: '32px' }}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>
      </div>

      {/* Asset Class Filter Pills */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.35rem', backgroundColor: 'rgba(255, 255, 255, 0.02)', padding: '0.35rem', borderRadius: 'var(--radius-md)' }}>
        {[
          { id: 'all', label: `All Positions (${shocks.length})` },
          { id: 'corporate_loan', label: 'Commercial Loans' },
          { id: 'government_bond', label: 'Sovereign Treasuries' },
          { id: 'corporate_bond', label: 'Corporate Bonds' },
          { id: 'equity', label: 'Public Equities' },
          { id: 'derivative', label: 'Put Option Hedges' },
        ].map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => setSelectedType(tab.id)}
            className={`btn ${selectedType === tab.id ? 'btn-secondary' : 'btn-outline'}`}
            style={{ fontSize: '0.75rem', padding: '0.3rem 0.65rem' }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Shock Table */}
      <div className="table-container">
        <table className="table">
          <thead>
            <tr>
              <th>Instrument / Sector</th>
              <th>Asset Class</th>
              <th>Baseline Value</th>
              <th>Stressed Value</th>
              <th>Price Impact</th>
              <th>Simulated Loss / Gain</th>
              <th>Valuation Model & Factor Shocks</th>
            </tr>
          </thead>
          <tbody>
            {filteredShocks.length === 0 ? (
              <tr>
                <td colSpan={7} style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>
                  No instruments match the selected filter or search criteria.
                </td>
              </tr>
            ) : (
              filteredShocks.map((s) => {
                const isGain = s.asset_loss < 0;
                const isDerivative = s.asset_type === 'derivative';
                const isLoan = s.asset_type === 'corporate_loan';

                return (
                  <tr key={s.ticker}>
                    {/* Ticker & Sector */}
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem' }}>
                        <span style={{ fontWeight: 700, color: 'var(--text-primary)', fontSize: '0.9rem' }}>
                          {s.ticker}
                        </span>
                        <span className="badge badge-neutral" style={{ fontSize: '0.7rem' }}>
                          {s.sector}
                        </span>
                      </div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                        {s.name}
                      </div>
                    </td>

                    {/* Asset Type */}
                    <td>
                      <Badge variant={getAssetTypeBadgeVariant(s.asset_type)}>
                        {formatAssetTypeName(s.asset_type)}
                      </Badge>
                    </td>

                    {/* Baseline Value */}
                    <td className="tabular-nums" style={{ color: 'var(--text-secondary)' }}>
                      ${s.baseline_value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </td>

                    {/* Stressed Value */}
                    <td className="tabular-nums" style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                      ${s.stressed_value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </td>

                    {/* Percentage Repricing */}
                    <td>
                      <span
                        className="tabular-nums"
                        style={{
                          fontWeight: 700,
                          fontSize: '0.85rem',
                          color: s.pct_change < 0 ? 'var(--accent-rose)' : 'var(--accent-emerald)',
                        }}
                      >
                        {s.pct_change > 0 ? '+' : ''}{s.pct_change.toFixed(2)}%
                      </span>
                    </td>

                    {/* Net Simulated Loss / Gain */}
                    <td>
                      <div
                        className="tabular-nums"
                        style={{
                          fontWeight: 700,
                          fontSize: '0.9rem',
                          color: isGain ? 'var(--accent-emerald)' : 'var(--accent-rose)',
                        }}
                      >
                        {isGain ? '-' : '+'}${Math.abs(s.asset_loss).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      </div>
                      <div style={{ fontSize: '0.7rem', color: isGain ? 'var(--accent-emerald)' : 'var(--text-muted)' }}>
                        {isDerivative ? (
                          'Hedge Gain Offset'
                        ) : isGain ? (
                          'Flight-to-Safety Yield Gain'
                        ) : isLoan ? (
                          'Credit ECL Surge'
                        ) : (
                          'Market Haircut'
                        )}
                      </div>
                    </td>

                    {/* Valuation Model & Shock Applied */}
                    <td style={{ fontSize: '0.75rem' }}>
                      <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                        {s.shock_applied}
                      </div>
                      <div className="mono" style={{ fontSize: '0.675rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                        {s.valuation_methodology}
                      </div>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>

          {/* Table Footer: Total Portfolio Reconciliation */}
          <tfoot>
            <tr style={{ backgroundColor: 'rgba(255, 255, 255, 0.02)', fontWeight: 700, borderTop: '2px solid var(--border-default)' }}>
              <td>
                <span style={{ color: 'var(--text-primary)' }}>Total Portfolio Balance</span>
              </td>
              <td>
                <Badge variant="blue">{shocks.length} Positions</Badge>
              </td>
              <td className="tabular-nums" style={{ color: 'var(--text-secondary)' }}>
                ${baselineValue.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </td>
              <td className="tabular-nums" style={{ color: 'var(--text-primary)' }}>
                ${stressedValue.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </td>
              <td className="tabular-nums" style={{ color: totalLoss > 0 ? 'var(--accent-rose)' : 'var(--accent-emerald)' }}>
                {baselineValue > 0 ? `${((-totalLoss / baselineValue) * 100).toFixed(2)}%` : '0.00%'}
              </td>
              <td>
                <div className="tabular-nums" style={{ color: totalLoss > 0 ? 'var(--accent-rose)' : 'var(--accent-emerald)', fontSize: '0.95rem' }}>
                  {totalLoss > 0 ? '+' : '-'}${Math.abs(totalLoss).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </div>
              </td>
              <td>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: 'var(--accent-emerald)', fontSize: '0.75rem' }}>
                  <CheckCircle2 size={13} />
                  <span>
                    Credit: ${creditLoss.toLocaleString()} • Market: ${marketLoss.toLocaleString()}
                  </span>
                </div>
              </td>
            </tr>
          </tfoot>
        </table>
      </div>

      {/* Accounting Footnote */}
      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', borderTop: '1px solid var(--border-subtle)', paddingTop: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
        <Tag size={13} color="var(--accent-primary)" />
        <span>
          <strong>Sign Convention:</strong> Positive values indicate portfolio capital loss. Negative values indicate hedging or flight-to-safety portfolio gains. Mathematical balance: Credit Loss + Market Loss = Total Loss exactly.
          <Tooltip content="Signage convention: Loss = Baseline Value - Stressed Value. A negative loss represents an asset value increase (e.g., protective put gains or treasury price increases from lower yields)." title="Sign Convention Guarantee" />
        </span>
      </div>
    </div>
  );
};
