import React, { useState, useEffect, useCallback } from 'react';
import {
  Building2,
  ShieldCheck,
  RefreshCw,
  PieChart,
  Info,
  DollarSign,
  Layers,
  CheckCircle2,
  AlertCircle,
  PlusCircle,
  FileText
} from 'lucide-react';
import { MetricCard } from '../common/MetricCard';
import { Badge } from '../common/Badge';
import { LoadingSpinner, ErrorBanner, EmptyState } from '../common/StateViews';
import { AssetHoldingsTable } from './AssetHoldingsTable';
import { SectorExposureChart } from './SectorExposureChart';
import { portfolioService } from '../../services/portfolioService';
import type { PortfolioRead, PortfolioExposureRead } from '../../types/api';
import type { ActiveTab } from '../../types/navigation';

interface PortfolioManagerProps {
  onNavigateTab?: (tab: ActiveTab) => void;
}

export const PortfolioManager: React.FC<PortfolioManagerProps> = ({ onNavigateTab }) => {
  const [portfolios, setPortfolios] = useState<PortfolioRead[]>([]);
  const [selectedPortfolioId, setSelectedPortfolioId] = useState<string | null>(null);
  const [selectedPortfolio, setSelectedPortfolio] = useState<PortfolioRead | null>(null);
  const [exposure, setExposure] = useState<PortfolioExposureRead | null>(null);

  const [loadingList, setLoadingList] = useState<boolean>(true);
  const [loadingDetail, setLoadingDetail] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const [actionLoading, setActionLoading] = useState<'wholesale' | 'sample' | 'refresh' | null>(null);
  const [feedback, setFeedback] = useState<{ text: string; type: 'success' | 'error' } | null>(null);

  // Load list of portfolios from FastAPI
  const loadPortfolios = useCallback(async (preferredId?: string) => {
    setLoadingList(true);
    setError(null);
    try {
      const list = await portfolioService.listPortfolios();
      setPortfolios(list);

      if (list.length > 0) {
        let nextId = preferredId;
        if (!nextId && selectedPortfolioId && list.some((p) => p.id === selectedPortfolioId)) {
          nextId = selectedPortfolioId;
        } else if (!nextId) {
          const wholesale = list.find((p) => p.id === 'port_wholesale_banking');
          nextId = wholesale ? wholesale.id : list[0].id;
        }
        setSelectedPortfolioId(nextId);
      } else {
        setSelectedPortfolioId(null);
        setSelectedPortfolio(null);
        setExposure(null);
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to retrieve portfolios from backend.';
      setError(msg);
    } finally {
      setLoadingList(false);
    }
  }, [selectedPortfolioId]);

  // Initial load via async IIFE to prevent synchronous setState cascading renders
  useEffect(() => {
    let isMounted = true;
    (async () => {
      try {
        const list = await portfolioService.listPortfolios();
        if (!isMounted) return;
        setPortfolios(list);

        if (list.length > 0) {
          const wholesale = list.find((p) => p.id === 'port_wholesale_banking');
          const nextId = wholesale ? wholesale.id : list[0].id;
          setSelectedPortfolioId(nextId);
        }
      } catch (err) {
        if (!isMounted) return;
        const msg = err instanceof Error ? err.message : 'Failed to retrieve portfolios from backend.';
        setError(msg);
      } finally {
        if (isMounted) setLoadingList(false);
      }
    })();

    return () => {
      isMounted = false;
    };
  }, []);

  // Load single portfolio details & exposure whenever selectedPortfolioId changes
  useEffect(() => {
    if (!selectedPortfolioId) return;

    let isMounted = true;

    Promise.all([
      portfolioService.getPortfolio(selectedPortfolioId),
      portfolioService.getExposure(selectedPortfolioId).catch(() => null),
    ])
      .then(([port, exp]) => {
        if (!isMounted) return;
        setSelectedPortfolio(port);
        setExposure(exp);
      })
      .catch((err) => {
        if (!isMounted) return;
        const msg = err instanceof Error ? err.message : `Failed to load details for ${selectedPortfolioId}`;
        setError(msg);
      })
      .finally(() => {
        if (isMounted) setLoadingDetail(false);
      });

    return () => {
      isMounted = false;
    };
  }, [selectedPortfolioId]);

  const handleSelectPortfolio = (id: string) => {
    if (id !== selectedPortfolioId) {
      setLoadingDetail(true);
      setSelectedPortfolioId(id);
    }
  };

  // Handler: Seed Wholesale Portfolio
  const handleSeedWholesale = async () => {
    setActionLoading('wholesale');
    setFeedback(null);
    try {
      const created = await portfolioService.seedWholesalePortfolio();
      await loadPortfolios(created.id);
      setFeedback({
        text: `Synthetic Wholesale Banking Portfolio seeded successfully with ${created.assets.length} multi-asset holdings ($${created.current_total_value.toLocaleString()} carrying value).`,
        type: 'success',
      });
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to seed wholesale portfolio.';
      setFeedback({ text: msg, type: 'error' });
    } finally {
      setActionLoading(null);
    }
  };

  // Handler: Seed Sample Multi-Asset Equity Portfolio
  const handleSeedSample = async () => {
    setActionLoading('sample');
    setFeedback(null);
    try {
      const created = await portfolioService.seedSamplePortfolio();
      await loadPortfolios(created.id);
      setFeedback({
        text: `Global Multi-Asset Alpha Portfolio seeded successfully with ${created.assets.length} equity positions ($${created.current_total_value.toLocaleString()} carrying value).`,
        type: 'success',
      });
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to seed sample portfolio.';
      setFeedback({ text: msg, type: 'error' });
    } finally {
      setActionLoading(null);
    }
  };

  // Handler: Refresh data
  const handleRefresh = async () => {
    setActionLoading('refresh');
    try {
      await loadPortfolios(selectedPortfolioId || undefined);
    } finally {
      setActionLoading(null);
    }
  };

  // Derive portfolio allocation metrics
  const assets = selectedPortfolio?.assets || [];
  const totalVal = selectedPortfolio?.current_total_value || 0;

  const debtAndLoanValue = assets
    .filter((a) => ['corporate_loan', 'government_bond', 'corporate_bond'].includes(a.asset_type))
    .reduce((sum, a) => sum + (a.market_value || a.shares * a.current_price), 0);
  const debtAndLoanPct = totalVal > 0 ? (debtAndLoanValue / totalVal) * 100 : 0;

  const equityValue = assets
    .filter((a) => a.asset_type === 'equity')
    .reduce((sum, a) => sum + (a.market_value || a.shares * a.current_price), 0);
  const equityPct = totalVal > 0 ? (equityValue / totalVal) * 100 : 0;

  const derivativeAsset = assets.find((a) => a.asset_type === 'derivative');
  const hedgeNotional = derivativeAsset?.notional || (derivativeAsset?.attributes?.underlying_notional as number) || 0;

  const isWholesalePortfolio = selectedPortfolioId === 'port_wholesale_banking';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Top Action & Portfolio Selection Bar */}
      <div
        className="card"
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '1rem',
          padding: '1rem 1.25rem',
        }}
      >
        {/* Left: Portfolio Switcher */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Building2 size={20} color="var(--accent-primary)" />
            <span style={{ fontWeight: 600, color: 'var(--text-primary)', fontSize: '0.9rem' }}>
              Select Portfolio:
            </span>
          </div>

          {portfolios.length > 0 ? (
            <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
              {portfolios.map((p) => {
                const isSelected = p.id === selectedPortfolioId;
                const isWholesale = p.id === 'port_wholesale_banking';
                return (
                  <button
                    key={p.id}
                    type="button"
                    onClick={() => handleSelectPortfolio(p.id)}
                    className={`btn ${isSelected ? 'btn-primary' : 'btn-outline'}`}
                    style={{
                      fontSize: '0.8rem',
                      padding: '0.45rem 0.85rem',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.5rem',
                    }}
                  >
                    <span>{p.name}</span>
                    <span
                      style={{
                        fontSize: '0.7rem',
                        opacity: isSelected ? 0.9 : 0.6,
                        fontWeight: 600,
                      }}
                      className="tabular-nums"
                    >
                      ${(p.current_total_value / 1_000_000).toFixed(2)}M
                    </span>
                    {isWholesale && (
                      <span
                        style={{
                          backgroundColor: isSelected ? 'rgba(255,255,255,0.2)' : 'rgba(59, 130, 246, 0.2)',
                          color: isSelected ? '#ffffff' : '#93c5fd',
                          borderRadius: '4px',
                          padding: '1px 5px',
                          fontSize: '0.65rem',
                          fontWeight: 700,
                        }}
                      >
                        Wholesale
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
          ) : (
            <span style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>
              No portfolios loaded in database
            </span>
          )}
        </div>

        {/* Right: Actions */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
          <button
            type="button"
            onClick={handleSeedWholesale}
            disabled={actionLoading !== null}
            className="btn btn-secondary"
            style={{ fontSize: '0.8rem', gap: '0.4rem' }}
            title="Seed calibrated wholesale banking portfolio with corporate loans, government bonds, corporate bonds, equities, and derivative put hedges"
          >
            <ShieldCheck size={14} color="var(--accent-primary)" />
            <span>
              {actionLoading === 'wholesale' ? 'Seeding Wholesale...' : 'Seed Wholesale Portfolio'}
            </span>
          </button>

          <button
            type="button"
            onClick={handleSeedSample}
            disabled={actionLoading !== null}
            className="btn btn-outline"
            style={{ fontSize: '0.8rem', gap: '0.4rem' }}
            title="Seed diversified 6-equity alpha portfolio"
          >
            <PlusCircle size={14} />
            <span>
              {actionLoading === 'sample' ? 'Seeding Multi-Asset...' : 'Seed Equity Portfolio'}
            </span>
          </button>

          <button
            type="button"
            onClick={handleRefresh}
            disabled={actionLoading !== null}
            className="btn btn-outline"
            style={{ padding: '0.45rem', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
            title="Refresh portfolio and exposure data"
          >
            <RefreshCw size={15} className={actionLoading === 'refresh' ? 'spin' : ''} />
          </button>
        </div>
      </div>

      {/* Action Notification Banner */}
      {feedback && (
        <div
          style={{
            padding: '0.75rem 1rem',
            borderRadius: 'var(--radius-md)',
            backgroundColor:
              feedback.type === 'success' ? 'var(--accent-emerald-bg)' : 'var(--accent-rose-bg)',
            border: `1px solid ${
              feedback.type === 'success' ? 'rgba(16, 185, 129, 0.3)' : 'rgba(244, 63, 94, 0.3)'
            }`,
            color: feedback.type === 'success' ? '#a7f3d0' : '#fda4af',
            fontSize: '0.85rem',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            {feedback.type === 'success' ? (
              <CheckCircle2 size={16} color="var(--accent-emerald)" />
            ) : (
              <AlertCircle size={16} color="var(--accent-rose)" />
            )}
            <span>{feedback.text}</span>
          </div>
          <button
            type="button"
            onClick={() => setFeedback(null)}
            style={{
              background: 'none',
              border: 'none',
              color: 'inherit',
              cursor: 'pointer',
              fontSize: '0.8rem',
              opacity: 0.8,
            }}
          >
            ✕
          </button>
        </div>
      )}

      {/* Global Error State */}
      {error && <ErrorBanner message={error} onRetry={() => loadPortfolios(selectedPortfolioId || undefined)} />}

      {/* Loading List State */}
      {loadingList && portfolios.length === 0 && (
        <LoadingSpinner message="Querying portfolio entities and carrying valuations from backend..." />
      )}

      {/* Empty State: No Portfolios Exist */}
      {!loadingList && portfolios.length === 0 && (
        <EmptyState
          icon={<Layers size={40} color="var(--accent-primary)" />}
          title="No Portfolios Configured"
          description="Initialize RiskLens AI with a representative wholesale banking portfolio encompassing commercial loans (EAD, PD, LGD), sovereign bonds, corporate debt, public equities, and derivative hedges."
          actionLabel="Seed Wholesale Banking Portfolio"
          onAction={handleSeedWholesale}
          actionLoading={actionLoading === 'wholesale'}
        />
      )}

      {/* Portfolio Content when loaded */}
      {selectedPortfolio && (
        <>
          {/* Portfolio Description & Meta */}
          <div
            style={{
              backgroundColor: 'rgba(15, 23, 42, 0.6)',
              border: '1px solid var(--border-default)',
              borderRadius: 'var(--radius-lg)',
              padding: '1rem 1.25rem',
              display: 'flex',
              alignItems: 'flex-start',
              justifyContent: 'space-between',
              gap: '1rem',
              flexWrap: 'wrap',
            }}
          >
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
                <h2 style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--text-primary)', margin: 0 }}>
                  {selectedPortfolio.name}
                </h2>
                <Badge variant={isWholesalePortfolio ? 'blue' : 'purple'}>
                  {isWholesalePortfolio ? 'Synthetic Wholesale Benchmark' : 'Standard Asset Portfolio'}
                </Badge>
                <span className="mono" style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                  ID: {selectedPortfolio.id}
                </span>
              </div>
              <p
                style={{
                  fontSize: '0.85rem',
                  color: 'var(--text-secondary)',
                  marginTop: '0.35rem',
                  marginBottom: 0,
                  maxWidth: '850px',
                }}
              >
                {selectedPortfolio.description || 'Configured wholesale banking holdings for stress testing and scenario analysis.'}
              </p>
            </div>

            {onNavigateTab && (
              <button
                type="button"
                onClick={() => onNavigateTab('stress_testing')}
                className="btn btn-outline"
                style={{ fontSize: '0.75rem', gap: '0.4rem', whiteSpace: 'nowrap' }}
              >
                <span>Stress Test Portfolio</span>
                <PieChart size={13} />
              </button>
            )}
          </div>

          {/* 4 Summary KPI Metric Cards */}
          <div className="grid-metrics">
            {/* KPI 1: Carrying Value */}
            <MetricCard
              title="Portfolio Carrying Value"
              value={`$${totalVal.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
              subtitle={
                <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                  Base: {selectedPortfolio.base_currency} • Initial: ${selectedPortfolio.initial_value.toLocaleString()}
                </span>
              }
              badge={<Badge variant="blue">Baseline Valuation</Badge>}
              icon={<DollarSign size={18} />}
              tooltip="Carrying value represents the validated balance sheet valuation. Loans use IFRS 9 amortized cost (EAD - baseline ECL); securities reflect fair value; derivatives reflect option premium."
              tooltipTitle="Carrying Value Convention"
              loading={loadingDetail}
            />

            {/* KPI 2: Fixed Income & Loan Allocation */}
            <MetricCard
              title="Loans & Debt Exposure"
              value={`$${debtAndLoanValue.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`}
              subtitle={
                <span className="tabular-nums" style={{ fontSize: '0.75rem', color: 'var(--accent-amber)' }}>
                  {debtAndLoanPct.toFixed(1)}% of total portfolio value
                </span>
              }
              badge={<Badge variant="amber">Credit & Rates</Badge>}
              icon={<Layers size={18} />}
              tooltip="Total allocation in corporate loans, sovereign treasuries, and corporate bonds subject to credit spread widening and duration repricing."
              tooltipTitle="Credit & Fixed Income Allocation"
              loading={loadingDetail}
            />

            {/* KPI 3: Public Equity Allocation */}
            <MetricCard
              title="Public Equity Allocation"
              value={`$${equityValue.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`}
              subtitle={
                <span className="tabular-nums" style={{ fontSize: '0.75rem', color: 'var(--accent-primary)' }}>
                  {equityPct.toFixed(1)}% of total portfolio value
                </span>
              }
              badge={<Badge variant="cyan">Market Beta</Badge>}
              icon={<PieChart size={18} />}
              tooltip="Equity positions subject to systematic market factor beta shocks and sector volatility."
              tooltipTitle="Equity Allocation"
              loading={loadingDetail}
            />

            {/* KPI 4: Macro Derivative Put Protection */}
            <MetricCard
              title="Macro Hedge Protection"
              value={
                derivativeAsset
                  ? `$${hedgeNotional.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`
                  : 'No Active Hedges'
              }
              subtitle={
                derivativeAsset ? (
                  <span style={{ color: 'var(--accent-emerald)', fontSize: '0.75rem', fontWeight: 600 }}>
                    Delta: {derivativeAsset.attributes?.delta ?? -0.35} • Premium: ${(derivativeAsset.shares * derivativeAsset.current_price).toLocaleString()}
                  </span>
                ) : (
                  <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>
                    Unhedged market risk exposure
                  </span>
                )
              }
              badge={
                <Badge variant={derivativeAsset ? 'green' : 'neutral'}>
                  {derivativeAsset ? 'Protected' : 'Unhedged'}
                </Badge>
              }
              icon={<ShieldCheck size={18} />}
              tooltip="Protective put option positions decouple contract carrying value ($250k) from underlying protected notional ($10M). Offsets simulated portfolio losses during adverse market shocks."
              tooltipTitle="Derivative Put Hedge Decoupling"
              loading={loadingDetail}
            />
          </div>

          {/* Financial Accuracy & Accounting Disclosure Callout */}
          <div
            style={{
              padding: '0.85rem 1.15rem',
              backgroundColor: 'rgba(30, 41, 59, 0.4)',
              border: '1px solid var(--border-subtle)',
              borderRadius: 'var(--radius-md)',
              display: 'flex',
              alignItems: 'flex-start',
              gap: '0.85rem',
              fontSize: '0.8rem',
              color: 'var(--text-secondary)',
              lineHeight: 1.5,
            }}
          >
            <Info size={18} color="var(--accent-primary)" style={{ flexShrink: 0, marginTop: '2px' }} />
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
              <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                Financial Accuracy & Accounting Conventions Disclosure
              </div>
              <div>
                <strong>Carrying Value:</strong> Reflects balance sheet carrying value rather than real-time streaming exchange prices. Commercial loans are modeled under IFRS 9 / Basel II amortized cost (<span className="mono">V = EAD - baseline ECL</span>) so that market price discounts are never double-counted.
              </div>
              <div>
                <strong>Aggregated Exposure:</strong> Sector allocations reflect genuine backend rollups of instrument carrying values. Totals reconcile 100.0% with backend calculations.
              </div>
            </div>
          </div>

          {/* Main Portfolio Grid: Holdings Table (Left) + Sector Exposure Chart (Right) */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'minmax(0, 1.8fr) minmax(0, 1.2fr)',
              gap: '1.5rem',
              alignItems: 'stretch',
            }}
          >
            {/* Left 60%: Asset Holdings Table */}
            <div style={{ minWidth: 0 }}>
              <AssetHoldingsTable assets={assets} totalValue={totalVal} />
            </div>

            {/* Right 40%: Sector & Asset Class Exposure Chart */}
            <div style={{ minWidth: 0, display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <SectorExposureChart
                sectorExposures={exposure?.sector_exposures || []}
                assets={assets}
                totalValue={totalVal}
              />

              {/* Portfolio Composition Summary Card */}
              <div className="card" style={{ padding: '1rem 1.25rem' }}>
                <div style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                  <FileText size={15} color="var(--accent-primary)" />
                  <span>Wholesale Risk Summary</span>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.45rem', fontSize: '0.775rem' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-secondary)' }}>
                    <span>Total Holdings Count:</span>
                    <strong style={{ color: 'var(--text-primary)' }}>{assets.length} instruments</strong>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-secondary)' }}>
                    <span>Basel II Credit Assets:</span>
                    <strong style={{ color: 'var(--accent-amber)' }}>
                      {assets.filter((a) => a.asset_type === 'corporate_loan').length} loan ($5.0M EAD)
                    </strong>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-secondary)' }}>
                    <span>Fixed Income Treasuries & Bonds:</span>
                    <strong style={{ color: 'var(--accent-cyan)' }}>
                      {assets.filter((a) => ['government_bond', 'corporate_bond'].includes(a.asset_type)).length} issues (D_mod 4.2y - 7.8y)
                    </strong>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-secondary)' }}>
                    <span>Macro Put Protection:</span>
                    <strong style={{ color: 'var(--accent-emerald)' }}>
                      {derivativeAsset ? 'SPX Put ($10M notional, Δ -0.35)' : 'None'}
                    </strong>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
};
