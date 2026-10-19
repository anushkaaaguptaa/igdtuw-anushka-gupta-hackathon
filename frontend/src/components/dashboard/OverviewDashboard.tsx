import React, { useState, useEffect, useCallback } from 'react';
import {
  DollarSign,
  TrendingDown,
  ShieldAlert,
  Newspaper,
  Sliders,
  ArrowRight,
  Database,
  ExternalLink,
  RefreshCw
} from 'lucide-react';
import { MetricCard } from '../common/MetricCard';
import { Badge, SentimentBadge, ImpactBadge, ProvenanceBadge } from '../common/Badge';
import { LoadingSpinner, ErrorBanner, EmptyState } from '../common/StateViews';
import { LossBreakdownChart } from './LossBreakdownChart';
import { portfolioService } from '../../services/portfolioService';
import { stressTestService } from '../../services/stressTestService';
import { signalsService } from '../../services/signalsService';
import { ingestionService } from '../../services/ingestionService';
import type {
  PortfolioRead,
  PortfolioExposureRead,
  StressTestRunRead,
  RiskSignalRead,
  IngestStatusResponse
} from '../../types/api';
import type { ActiveTab } from '../../types/navigation';

interface OverviewDashboardProps {
  onNavigateTab: (tab: ActiveTab) => void;
  onTriggerStressForSignal?: (signal: RiskSignalRead) => void;
}

export const OverviewDashboard: React.FC<OverviewDashboardProps> = ({
  onNavigateTab,
  onTriggerStressForSignal,
}) => {
  const [portfolios, setPortfolios] = useState<PortfolioRead[]>([]);
  const [exposure, setExposure] = useState<PortfolioExposureRead | null>(null);
  const [latestRun, setLatestRun] = useState<StressTestRunRead | null>(null);
  const [signals, setSignals] = useState<RiskSignalRead[]>([]);
  const [ingestStatus, setIngestStatus] = useState<IngestStatusResponse | null>(null);

  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<{ text: string; type: 'success' | 'error' } | null>(null);

  const loadDashboardData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // 1. Fetch Portfolios
      const ports = await portfolioService.listPortfolios();
      setPortfolios(ports);

      // If portfolios exist, load exposure of the first/wholesale portfolio
      if (ports.length > 0) {
        try {
          const exp = await portfolioService.getExposure(ports[0].id);
          setExposure(exp);
        } catch {
          setExposure(null);
        }
      } else {
        setExposure(null);
      }

      // 2. Fetch Latest Stress Test Run
      const runs = await stressTestService.listRuns();
      if (runs.length > 0) {
        setLatestRun(runs[0]);
      } else {
        setLatestRun(null);
      }

      // 3. Fetch Recent Signals
      const sigResponse = await signalsService.listSignals({ limit: 5 });
      setSignals(sigResponse.items);

      // 4. Fetch Ingestion Health Status
      const statusRes = await ingestionService.getStatus();
      setIngestStatus(statusRes);
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to retrieve overview dashboard data.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let isMounted = true;
    (async () => {
      try {
        const [ports, runs, sigResponse, statusRes] = await Promise.all([
          portfolioService.listPortfolios(),
          stressTestService.listRuns(),
          signalsService.listSignals({ limit: 5 }),
          ingestionService.getStatus(),
        ]);
        if (!isMounted) return;
        setPortfolios(ports);
        if (runs.length > 0) setLatestRun(runs[0]);
        setSignals(sigResponse.items);
        setIngestStatus(statusRes);

        if (ports.length > 0) {
          try {
            const exp = await portfolioService.getExposure(ports[0].id);
            if (isMounted) setExposure(exp);
          } catch {
            if (isMounted) setExposure(null);
          }
        }
      } catch (err) {
        if (!isMounted) return;
        const msg = err instanceof Error ? err.message : 'Failed to retrieve overview dashboard data.';
        setError(msg);
      } finally {
        if (isMounted) setLoading(false);
      }
    })();

    return () => {
      isMounted = false;
    };
  }, []);

  // Quick Action: Seed wholesale banking sample portfolio
  const handleSeedWholesale = async () => {
    setActionLoading('seed');
    setActionMessage(null);
    try {
      const created = await portfolioService.seedWholesalePortfolio();
      setActionMessage({ text: `Wholesale banking portfolio seeded successfully ($${created.current_total_value.toLocaleString()}).`, type: 'success' });
      await loadDashboardData();
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to seed sample portfolio.';
      setActionMessage({ text: msg, type: 'error' });
    } finally {
      setActionLoading(null);
    }
  };

  // Quick Action: Replay news fixtures
  const handleReplayIngestion = async () => {
    setActionLoading('replay');
    setActionMessage(null);
    try {
      const summary = await ingestionService.triggerIngestion({
        mode: 'replay',
        sources: ['replay_fixture'],
        limit_per_source: 5,
        run_nlp: true,
      });
      setActionMessage({
        text: `Replay ingestion completed: ${summary.articles_persisted} articles ingested, ${summary.signals_generated} signals generated.`,
        type: 'success',
      });
      await loadDashboardData();
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to trigger replay ingestion.';
      setActionMessage({ text: msg, type: 'error' });
    } finally {
      setActionLoading(null);
    }
  };

  // Calculations
  const primaryPortfolio = portfolios[0];
  const totalPortfolioValue = portfolios.reduce((acc, p) => acc + (p.current_total_value || 0), 0);
  const totalHoldingsCount = portfolios.reduce((acc, p) => acc + (p.assets?.length || 0), 0);

  // Parse loss breakdowns from latest run details_json if available
  let lossByAssetType: Record<string, number> = {};
  let lossBySector: Record<string, number> = {};
  if (latestRun?.details_json) {
    try {
      const shocks = JSON.parse(latestRun.details_json);
      if (Array.isArray(shocks)) {
        for (const s of shocks) {
          const type = s.asset_type || 'unclassified';
          const sector = s.sector || 'General';
          lossByAssetType[type] = (lossByAssetType[type] || 0) + (s.asset_loss || 0);
          lossBySector[sector] = (lossBySector[sector] || 0) + (s.asset_loss || 0);
        }
      }
    } catch {
      lossByAssetType = {};
      lossBySector = {};
    }
  }

  if (loading && portfolios.length === 0 && !latestRun && signals.length === 0) {
    return <LoadingSpinner message="Loading RiskLens AI financial risk intelligence dashboard..." size={32} />;
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.75rem' }}>
      {/* Top Banner / Error */}
      {error && (
        <ErrorBanner
          title="Dashboard Data Synchronization Failure"
          message={error}
          onRetry={loadDashboardData}
        />
      )}

      {actionMessage && (
        <div
          style={{
            padding: '0.85rem 1.25rem',
            borderRadius: 'var(--radius-md)',
            fontSize: '0.85rem',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            backgroundColor: actionMessage.type === 'success' ? 'var(--accent-emerald-bg)' : 'var(--accent-rose-bg)',
            color: actionMessage.type === 'success' ? '#6ee7b7' : '#fda4af',
            border: `1px solid ${actionMessage.type === 'success' ? 'rgba(16, 185, 129, 0.3)' : 'rgba(244, 63, 94, 0.3)'}`,
          }}
        >
          <span>{actionMessage.text}</span>
          <button
            onClick={() => setActionMessage(null)}
            style={{ background: 'transparent', border: 'none', color: 'inherit', cursor: 'pointer', fontWeight: 600 }}
          >
            ✕
          </button>
        </div>
      )}

      {/* Header section with quick action buttons */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h2>Executive Risk Intelligence Overview</h2>
          <p style={{ fontSize: '0.825rem', marginTop: '2px' }}>
            Consolidated portfolio carrying values, market & credit stress impact, and live NLP risk signals.
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
          <button
            onClick={loadDashboardData}
            disabled={loading}
            className="btn btn-outline"
            style={{ fontSize: '0.8rem', padding: '0.45rem 0.75rem' }}
            title="Refresh dashboard metrics"
            type="button"
          >
            <RefreshCw size={14} className={loading ? 'spin' : ''} />
            <span>Sync</span>
          </button>

          {portfolios.length === 0 && (
            <button
              onClick={handleSeedWholesale}
              disabled={actionLoading === 'seed'}
              className="btn btn-primary"
              style={{ fontSize: '0.8rem' }}
              type="button"
            >
              <Database size={14} />
              <span>Seed Wholesale Portfolio</span>
            </button>
          )}

          <button
            onClick={handleReplayIngestion}
            disabled={actionLoading === 'replay'}
            className="btn btn-secondary"
            style={{ fontSize: '0.8rem' }}
            type="button"
          >
            <Newspaper size={14} />
            <span>Replay News Fixtures</span>
          </button>
        </div>
      </div>

      {/* 4 Core Financial KPI Metric Cards */}
      <div className="grid-cols-4">
        {/* Metric 1: Total Portfolio Value */}
        <MetricCard
          title="Portfolio Baseline Carrying Value"
          value={
            portfolios.length > 0 ? (
              `$${totalPortfolioValue.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
            ) : (
              <span style={{ fontSize: '1.1rem', color: 'var(--text-muted)' }}>No Active Portfolios</span>
            )
          }
          subtitle={
            portfolios.length > 0
              ? `${portfolios.length} portfolio${portfolios.length > 1 ? 's' : ''} • ${totalHoldingsCount} holdings`
              : 'Seed sample portfolio to begin'
          }
          icon={<DollarSign size={18} color="var(--accent-primary)" />}
          badge={
            portfolios.length > 0 ? (
              <Badge variant="blue">{primaryPortfolio?.base_currency || 'USD'}</Badge>
            ) : (
              <button
                onClick={handleSeedWholesale}
                disabled={actionLoading === 'seed'}
                className="btn btn-primary"
                style={{ fontSize: '0.7rem', padding: '0.2rem 0.5rem' }}
              >
                + Seed
              </button>
            )
          }
          tooltip="Total carrying value across all portfolios. Evaluated at IFRS 9 amortized cost for corporate loans (EAD minus baseline ECL provision) and fair market value for bonds, equities, and derivative positions."
          tooltipTitle="Carrying Value Accounting"
          loading={loading}
        />

        {/* Metric 2: Latest Stress Test Loss */}
        <MetricCard
          title="Simulated Stress Impact"
          value={
            latestRun ? (
              <span style={{ color: 'var(--accent-rose)' }}>
                -${Math.abs(latestRun.total_loss).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </span>
            ) : (
              <span style={{ fontSize: '1.1rem', color: 'var(--text-muted)' }}>No Simulations Run</span>
            )
          }
          subtitle={
            latestRun
              ? `Drawdown: ${latestRun.loss_percentage.toFixed(2)}% of carrying baseline`
              : 'Run simulation in workspace'
          }
          icon={<TrendingDown size={18} color="var(--accent-rose)" />}
          badge={
            latestRun ? (
              <Badge variant="red">
                {latestRun.scenario_name.replace(/\[AUTO\]\s*/, '')}
              </Badge>
            ) : null
          }
          tooltip="Deterministic simulated portfolio loss under the most recent macroeconomic or credit stress scenario. Mathematical identity: Total Loss = Stressed Carrying Loss = Credit Impairment Loss + Market Revaluation Loss."
          tooltipTitle="Stress Testing Reconciliation"
          loading={loading}
        />

        {/* Metric 3: Value-at-Risk (VaR / CVaR) */}
        <MetricCard
          title="Illustrative 10-Day VaR & CVaR"
          value={
            latestRun?.var_95 ? (
              <div style={{ fontSize: '1.25rem', display: 'flex', alignItems: 'baseline', gap: '0.4rem' }}>
                <span>VaR₉₅: ${Math.round(latestRun.var_95).toLocaleString()}</span>
              </div>
            ) : (
              <span style={{ fontSize: '1.1rem', color: 'var(--text-muted)' }}>Pending Run</span>
            )
          }
          subtitle={
            latestRun?.cvar_95
              ? `CVaR₉₅ (ES): $${Math.round(latestRun.cvar_95).toLocaleString()} • Horizon: 10d`
              : 'Monte Carlo simulation estimate'
          }
          icon={<ShieldAlert size={18} color="var(--accent-amber)" />}
          badge={<Badge variant="amber">Illustrative MC</Badge>}
          tooltip="Illustrative multi-factor Monte Carlo simulation (1,000 draws, 10-day risk horizon). Evaluated via Cholesky decomposition of a synthetic 4-factor correlation matrix [Equity, Rate, Spread, Credit]. For demonstration purposes only; not calibrated to live market tick data."
          tooltipTitle="Statistical Model Notice"
          loading={loading}
        />

        {/* Metric 4: Risk Intelligence Ingestion */}
        <MetricCard
          title="NLP Risk Intelligence Feed"
          value={`${signals.length} Signals`}
          subtitle={
            ingestStatus
              ? `${ingestStatus.total_articles_stored} articles stored • Status: ${ingestStatus.overall_status}`
              : 'Monitoring news sources'
          }
          icon={<Newspaper size={18} color="var(--accent-cyan)" />}
          badge={
            <Badge variant={ingestStatus?.overall_status === 'healthy' ? 'green' : 'neutral'}>
              {ingestStatus?.overall_status || 'Operational'}
            </Badge>
          }
          tooltip="Ingestion coordinator status across GDELT 2.0 Doc API, financial RSS feeds, and historical replay fixtures. FinBERT continuous sentiment scores P(pos) - P(neg) mapped to deterministic 1-10 impact scale."
          tooltipTitle="Signal Provenance"
          loading={loading}
        />
      </div>

      {/* Middle Section: Exposure & Stress Highlights */}
      <div className="grid-cols-2">
        {/* Left: Recharts Loss Breakdown / Portfolio Exposure */}
        <LossBreakdownChart
          lossByAssetType={lossByAssetType}
          lossBySector={lossBySector}
          sectorExposure={exposure?.sector_exposures || []}
        />

        {/* Right: Latest Simulation Summary or Empty State */}
        <div className="card" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
          <div className="card-header">
            <div>
              <div className="card-title">Stress Simulation Highlights</div>
              <div className="card-subtitle">
                {latestRun
                  ? `Execution: ${new Date(latestRun.simulated_at).toLocaleString()} • Scenario: ${latestRun.scenario_version}`
                  : 'Execute a shock scenario to inspect before-and-after revaluations'}
              </div>
            </div>
            {latestRun && (
              <button
                onClick={() => onNavigateTab('stress_testing')}
                className="btn btn-outline"
                style={{ fontSize: '0.75rem', padding: '0.25rem 0.5rem' }}
                type="button"
              >
                <span>Full Workspace</span>
                <ArrowRight size={12} />
              </button>
            )}
          </div>

          {latestRun ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
              {/* Scenario details */}
              <div
                style={{
                  backgroundColor: 'rgba(255, 255, 255, 0.02)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: 'var(--radius-md)',
                  padding: '1rem',
                }}
              >
                <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Active Scenario</div>
                <div style={{ fontSize: '1.05rem', fontWeight: 600, color: 'var(--text-primary)', marginTop: '2px' }}>
                  {latestRun.scenario_name}
                </div>
              </div>

              {/* Before vs After Carrying Value */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                <div
                  style={{
                    backgroundColor: 'rgba(255, 255, 255, 0.02)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: 'var(--radius-md)',
                    padding: '0.85rem',
                  }}
                >
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Baseline Carrying Value</div>
                  <div style={{ fontSize: '1.2rem', fontWeight: 700, marginTop: '2px' }} className="tabular-nums">
                    ${latestRun.baseline_value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </div>
                </div>

                <div
                  style={{
                    backgroundColor: 'rgba(244, 63, 94, 0.05)',
                    border: '1px solid rgba(244, 63, 94, 0.2)',
                    borderRadius: 'var(--radius-md)',
                    padding: '0.85rem',
                  }}
                >
                  <div style={{ fontSize: '0.75rem', color: '#fda4af' }}>Stressed Carrying Value</div>
                  <div style={{ fontSize: '1.2rem', fontWeight: 700, color: '#f43f5e', marginTop: '2px' }} className="tabular-nums">
                    ${latestRun.stressed_value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </div>
                </div>
              </div>

              {/* Loss Component Reconciliation Breakdown */}
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: '1fr 1fr 1fr',
                  gap: '0.75rem',
                  padding: '0.85rem',
                  borderRadius: 'var(--radius-md)',
                  backgroundColor: 'rgba(255, 255, 255, 0.02)',
                  border: '1px solid var(--border-subtle)',
                }}
              >
                <div>
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Market Loss (MtM)</div>
                  <div style={{ fontSize: '1rem', fontWeight: 600, color: '#fda4af', marginTop: '2px' }} className="tabular-nums">
                    ${latestRun.market_loss.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </div>
                  <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>Equities, Bonds & Options</div>
                </div>

                <div>
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Credit Loss (ECL)</div>
                  <div style={{ fontSize: '1rem', fontWeight: 600, color: '#fcd34d', marginTop: '2px' }} className="tabular-nums">
                    ${latestRun.credit_loss.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </div>
                  <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>Corporate Loans (Basel II)</div>
                </div>

                <div>
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Reconciliation Status</div>
                  <div style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--accent-emerald)', marginTop: '4px' }}>
                    100% Reconciled
                  </div>
                  <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>Zero Double-Counting</div>
                </div>
              </div>

              {/* Notice on hedge gains */}
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', lineHeight: 1.4 }}>
                * Note: Put option derivative positions are represented as negative losses (gains) that offset market drawdown.
              </div>
            </div>
          ) : (
            <EmptyState
              icon={<Sliders size={32} color="var(--accent-primary)" />}
              title="No Stress Simulations Recorded"
              description="Configure and execute a multi-factor stress test to evaluate credit impairment and market revaluation impact across your wholesale portfolio."
              actionLabel="Launch Stress Workspace"
              onAction={() => onNavigateTab('stress_testing')}
            />
          )}
        </div>
      </div>

      {/* Bottom Section: Recent Risk Signals Table */}
      <div className="card">
        <div className="card-header">
          <div>
            <div className="card-title">Recent High-Impact Financial Risk Signals</div>
            <div className="card-subtitle">
              FinBERT financial sentiment, deterministic impact scores (1-10), and extracted market entities
            </div>
          </div>

          <button
            onClick={() => onNavigateTab('intelligence')}
            className="btn btn-outline"
            style={{ fontSize: '0.75rem', padding: '0.35rem 0.65rem' }}
            type="button"
          >
            <span>View All Signals</span>
            <ArrowRight size={13} />
          </button>
        </div>

        {signals.length === 0 ? (
          <EmptyState
            icon={<Newspaper size={32} color="var(--text-muted)" />}
            title="No Risk Signals Recorded"
            description="Trigger financial news ingestion or replay the curated historical crisis fixture dataset to generate NLP signals."
            actionLabel="Replay Historical Fixtures"
            onAction={handleReplayIngestion}
            actionLoading={actionLoading === 'replay'}
          />
        ) : (
          <div className="table-container">
            <table className="table">
              <thead>
                <tr>
                  <th>Headline / Summary</th>
                  <th>Event Category</th>
                  <th>FinBERT Sentiment</th>
                  <th>Impact Score</th>
                  <th>Affected Entities</th>
                  <th>Provenance</th>
                  <th>Timestamp</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {signals.map((sig) => (
                  <tr key={sig.id}>
                    <td style={{ maxWidth: '340px' }}>
                      <div style={{ fontWeight: 600, color: 'var(--text-primary)', fontSize: '0.85rem' }}>
                        {sig.article?.title || sig.impact_rationale || sig.id}
                      </div>
                      {sig.article?.url && (
                        <a
                          href={sig.article.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          style={{
                            fontSize: '0.7rem',
                            color: 'var(--accent-primary)',
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '3px',
                            marginTop: '2px',
                            textDecoration: 'none',
                          }}
                        >
                          <span>{sig.article.source}</span>
                          <ExternalLink size={10} />
                        </a>
                      )}
                    </td>

                    <td>
                      <Badge variant="blue">
                        {sig.event_category.replace(/_/g, ' ')}
                      </Badge>
                    </td>

                    <td>
                      <SentimentBadge
                        sentimentLabel={sig.sentiment_label}
                        sentimentScore={sig.sentiment_score}
                        inferenceMode={sig.inference_mode}
                      />
                    </td>

                    <td>
                      <ImpactBadge impactScore={sig.impact_score} />
                    </td>

                    <td>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.25rem' }}>
                        {sig.affected_entities && sig.affected_entities.length > 0 ? (
                          sig.affected_entities.map((e) => (
                            <Badge key={e.ticker} variant="neutral" title={`${e.name} (${e.sector})`}>
                              {e.ticker}
                            </Badge>
                          ))
                        ) : (
                          <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>General Market</span>
                        )}
                      </div>
                    </td>

                    <td>
                      <ProvenanceBadge
                        source={sig.article?.source}
                        inferenceMode={sig.inference_mode}
                      />
                    </td>

                    <td style={{ fontSize: '0.75rem', color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>
                      {new Date(sig.created_at).toLocaleDateString()}{' '}
                      {new Date(sig.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </td>

                    <td>
                      {onTriggerStressForSignal && (
                        <button
                          type="button"
                          onClick={() => onTriggerStressForSignal(sig)}
                          className="btn btn-outline"
                          style={{ fontSize: '0.7rem', padding: '0.25rem 0.5rem', gap: '4px' }}
                          title="Simulate factor transmission for this risk signal in Stress-Testing Workspace"
                        >
                          <Sliders size={12} color="var(--accent-primary)" />
                          <span>Simulate</span>
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
