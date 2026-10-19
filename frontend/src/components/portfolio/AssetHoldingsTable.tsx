import React, { useState } from 'react';
import { Search, Tag } from 'lucide-react';
import { Badge } from '../common/Badge';
import { Tooltip } from '../common/Tooltip';
import type { PortfolioAssetRead } from '../../types/api';

interface AssetHoldingsTableProps {
  assets: PortfolioAssetRead[];
  totalValue: number;
}

export const AssetHoldingsTable: React.FC<AssetHoldingsTableProps> = ({ assets }) => {
  const [selectedType, setSelectedType] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');

  const filteredAssets = assets.filter((a) => {
    const matchesType = selectedType === 'all' || a.asset_type === selectedType;
    if (!matchesType) return false;

    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    const tickerMatch = a.ticker.toLowerCase().includes(q);
    const issuerMatch = a.issuer?.toLowerCase().includes(q) || false;
    const sectorMatch = a.entity?.sector.toLowerCase().includes(q) || false;
    return tickerMatch || issuerMatch || sectorMatch;
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
        return 'Macro Put Hedge';
      default:
        return type;
    }
  };

  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      {/* Table Header & Filter Bar */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem' }}>
        <div>
          <div className="card-title">Portfolio Holdings & Risk Sensitivities</div>
          <div className="card-subtitle">
            Asset-level carrying values, accounting classifications, and duration / credit spread / ECL parameters
          </div>
        </div>

        {/* Search Bar */}
        <div style={{ position: 'relative', width: '220px' }}>
          <Search size={14} style={{ position: 'absolute', left: '8px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
          <input
            type="text"
            placeholder="Search ticker, issuer..."
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
          { id: 'all', label: `All Holdings (${assets.length})` },
          { id: 'corporate_loan', label: 'Commercial Loans' },
          { id: 'government_bond', label: 'Sovereign Treasuries' },
          { id: 'corporate_bond', label: 'Corporate Bonds' },
          { id: 'equity', label: 'Public Equities' },
          { id: 'derivative', label: 'Derivative Hedges' },
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

      {/* Holdings Table */}
      <div className="table-container">
        <table className="table">
          <thead>
            <tr>
              <th>Instrument / Issuer</th>
              <th>Asset Class</th>
              <th>Carrying Value</th>
              <th>Weight</th>
              <th>Unit Price / Base</th>
              <th>Quantity / Units</th>
              <th>Financial & Risk Parameters</th>
            </tr>
          </thead>
          <tbody>
            {filteredAssets.length === 0 ? (
              <tr>
                <td colSpan={7} style={{ textAlign: 'center', padding: '2.5rem', color: 'var(--text-muted)' }}>
                  No holdings match the selected asset class or search query.
                </td>
              </tr>
            ) : (
              filteredAssets.map((asset) => {
                const attrs = asset.attributes || {};
                const mv = asset.market_value || asset.shares * asset.current_price;
                const isLoan = asset.asset_type === 'corporate_loan';
                const isGovtBond = asset.asset_type === 'government_bond';
                const isCorpBond = asset.asset_type === 'corporate_bond';
                const isEquity = asset.asset_type === 'equity';
                const isDeriv = asset.asset_type === 'derivative';

                return (
                  <tr key={asset.id}>
                    {/* Ticker & Issuer */}
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem' }}>
                        <span style={{ fontWeight: 700, color: 'var(--text-primary)', fontSize: '0.9rem' }}>
                          {asset.ticker}
                        </span>
                        <span className="badge badge-neutral" style={{ fontSize: '0.7rem' }}>
                          {asset.entity?.sector || 'General'}
                        </span>
                      </div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                        {asset.issuer || asset.entity?.name || asset.ticker}
                      </div>
                    </td>

                    {/* Asset Type */}
                    <td>
                      <Badge variant={getAssetTypeBadgeVariant(asset.asset_type)}>
                        {formatAssetTypeName(asset.asset_type)}
                      </Badge>
                    </td>

                    {/* Carrying Value */}
                    <td>
                      <div style={{ fontWeight: 700, color: 'var(--text-primary)' }} className="tabular-nums">
                        ${mv.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      </div>
                      <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                        {isLoan ? (
                          <span style={{ color: 'var(--accent-amber)' }}>Amortized Cost (IFRS 9)</span>
                        ) : (
                          'Fair Value (MtM)'
                        )}
                      </div>
                    </td>

                    {/* Weight % */}
                    <td className="tabular-nums" style={{ fontWeight: 600, color: 'var(--text-secondary)' }}>
                      {(asset.weight * 100).toFixed(2)}%
                    </td>

                    {/* Unit Price */}
                    <td className="tabular-nums">
                      ${asset.current_price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </td>

                    {/* Shares / Quantity */}
                    <td className="tabular-nums">
                      {asset.shares.toLocaleString()}
                    </td>

                    {/* Financial Risk Parameters */}
                    <td style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                      {isLoan && (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                          <span>
                            <strong>EAD:</strong> ${(attrs.ead || asset.notional || 5000000).toLocaleString()}
                            <Tooltip content="Exposure at Default under Basel II: Total facility balance subject to credit loss provisions." title="Exposure at Default (EAD)" />
                          </span>
                          <span>
                            <strong>PD:</strong> {((attrs.pd || 0.025) * 100).toFixed(1)}% • <strong>LGD:</strong> {((attrs.lgd || 0.45) * 100).toFixed(1)}%
                            <Tooltip content="Basel II / IFRS 9 Expected Credit Loss model: ECL = EAD * PD * LGD." title="ECL Model" />
                          </span>
                        </div>
                      )}

                      {isGovtBond && (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                          <span>
                            <strong>D_mod:</strong> {attrs.modified_duration || 7.8}y • <strong>Convexity:</strong> {attrs.convexity || 65.0}
                            <Tooltip content="Modified Duration & Convexity repricing: dP/P ≈ -D_mod * dy + 0.5 * C * (dy)^2." title="Bond Convexity" />
                          </span>
                          <span style={{ color: 'var(--text-muted)' }}>
                            Coupon: {((attrs.coupon || 0.0425) * 100).toFixed(2)}% • Rating: {attrs.rating || 'AAA'}
                          </span>
                        </div>
                      )}

                      {isCorpBond && (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                          <span>
                            <strong>D_mod:</strong> {attrs.modified_duration || 4.2}y • <strong>Spread:</strong> +{attrs.credit_spread_bps || 120} bps
                            <Tooltip content="Corporate bond credit spread widening duration: dP/P ≈ -D_mod * (dy + ds)." title="Spread Sensitivity" />
                          </span>
                          <span style={{ color: 'var(--text-muted)' }}>
                            Rating: {attrs.rating || 'A'} • Beta: {asset.sector_beta}
                          </span>
                        </div>
                      )}

                      {isEquity && (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                          <span>
                            <strong>Sector Beta:</strong> {asset.sector_beta}
                            <Tooltip content="Beta sensitivity to broad market factor: dP/P = Market Shock * Beta." title="Market Beta" />
                          </span>
                          <span style={{ color: 'var(--text-muted)' }}>
                            Cap: {attrs.market_cap ? String(attrs.market_cap).replace('_', ' ') : 'Large Cap'}
                          </span>
                        </div>
                      )}

                      {isDeriv && (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                          <span style={{ color: 'var(--accent-emerald)', fontWeight: 600 }}>
                            <strong>Delta:</strong> {attrs.delta || asset.sector_beta} • Protective Put
                            <Tooltip content="First-order delta approximation: dV ≈ delta * (dS/S) * Notional. Negative loss represents hedging gain." title="Put Option Delta Hedge" />
                          </span>
                          <span>
                            <strong>Underlying Notional:</strong> ${(attrs.underlying_notional || asset.notional || 10000000).toLocaleString()}
                          </span>
                        </div>
                      )}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Accounting Conventions Footnote */}
      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', borderTop: '1px solid var(--border-subtle)', paddingTop: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
        <Tag size={13} color="var(--accent-primary)" />
        <span>
          <strong>Accounting Convention Guarantee:</strong> Commercial loans are accounted for at amortized cost (carrying value = EAD - baseline ECL). No market price haircut is double-counted on loans.
        </span>
      </div>
    </div>
  );
};
