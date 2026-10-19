import React, { useState, useEffect } from 'react';
import {
  Sliders,
  Play,
  RotateCcw,
  ShieldAlert,
  TrendingDown,
  Info,
  DollarSign,
  Activity,
  Zap,
  Building2,
  Radio,
  X
} from 'lucide-react';
import { MetricCard } from '../common/MetricCard';
import { Badge, SentimentBadge, ImpactBadge } from '../common/Badge';
import { LoadingSpinner, ErrorBanner } from '../common/StateViews';
import { LossBreakdownChart } from '../dashboard/LossBreakdownChart';
import { ScenarioSelectorCard } from './ScenarioSelectorCard';
import { AssetShockTable } from './AssetShockTable';
import { SimulationHistoryTable } from './SimulationHistoryTable';
import { stressTestService } from '../../services/stressTestService';
import { portfolioService } from '../../services/portfolioService';
import { mapSignalToScenario } from '../../utils/scenarioMapping';
import type {
  StressScenarioDefinition,
  PortfolioRead,
  StressTestSimulationResponse,
  StressTestRunRead,
  AssetShockDetail,
  RiskSignalRead
} from '../../types/api';

interface StressTestingWorkspaceProps {
  triggerSignal?: RiskSignalRead | null;
  onClearTriggerSignal?: () => void;
}

export const StressTestingWorkspace: React.FC<StressTestingWorkspaceProps> = ({
  triggerSignal,
  onClearTriggerSignal,
}) => {
  const [portfolios, setPortfolios] = useState<PortfolioRead[]>([]);
  const [selectedPortfolioId, setSelectedPortfolioId] = useState<string>('port_wholesale_banking');

  const [scenarios, setScenarios] = useState<StressScenarioDefinition[]>([]);
  const [selectedScenarioId, setSelectedScenarioId] = useState<string>('GEOPOLITICAL_ESCALATION');

  // Derive mapped scenario from active trigger signal during render (no setState in effect)
  const mappedScenario = triggerSignal ? mapSignalToScenario(triggerSignal) : null;
  const activeScenarioId = triggerSignal && mappedScenario ? mappedScenario.scenarioId : selectedScenarioId;

  const [severityMultiplier, setSeverityMultiplier] = useState<number>(1.0);
  const [varSimulations, setVarSimulations] = useState<number>(1000);

  const [simulationResult, setSimulationResult] = useState<StressTestSimulationResponse | null>(null);
  const [historicalRuns, setHistoricalRuns] = useState<StressTestRunRead[]>([]);
  const [activeRunId, setActiveRunId] = useState<string | null>(null);

  const [loadingInitial, setLoadingInitial] = useState<boolean>(true);
  const [simulating, setSimulating] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<{ text: string; type: 'success' | 'error' } | null>(null);

  // Initial load of portfolios, scenarios, and historical runs
  useEffect(() => {
    let isMounted = true;

    (async () => {
      try {
        const [ports, scens, runs] = await Promise.all([
          portfolioService.listPortfolios(),
          stressTestService.listScenarios(),
          stressTestService.listRuns(),
        ]);

        if (!isMounted) return;

        setPortfolios(ports);
        setScenarios(scens);
        setHistoricalRuns(runs);

        // Default to wholesale portfolio if available
        if (ports.length > 0) {
          const wholesale = ports.find((p) => p.id === 'port_wholesale_banking');
          setSelectedPortfolioId(wholesale ? wholesale.id : ports[0].id);
        }

        // Default to first scenario
        if (scens.length > 0) {
          setSelectedScenarioId(scens[0].scenario_id);
        }

        // If historical runs exist, load the latest run as initial view
        if (runs.length > 0) {
          const latest = runs[0];
          setActiveRunId(latest.id);
          try {
            const parsedShocks: AssetShockDetail[] = JSON.parse(latest.details_json);
            const parsedAssumptions = latest.assumptions_json ? JSON.parse(latest.assumptions_json) : {};

            // Compute loss by asset type and sector from shocks for chart display
            const lossByAsset: Record<string, number> = {};
            const lossBySec: Record<string, number> = {};
            for (const s of parsedShocks) {
              lossByAsset[s.asset_type] = (lossByAsset[s.asset_type] || 0) + s.asset_loss;
              lossBySec[s.sector] = (lossBySec[s.sector] || 0) + s.asset_loss;
            }

            setSimulationResult({
              simulation_id: latest.id,
              portfolio_id: latest.portfolio_id,
              scenario_id: latest.scenario_id || 'CUSTOM',
              scenario_name: latest.scenario_name,
              scenario_version: latest.scenario_version,
              baseline_value: latest.baseline_value,
              stressed_value: latest.stressed_value,
              total_loss: latest.total_loss,
              loss_percentage: latest.loss_percentage,
              credit_loss: latest.credit_loss,
              market_loss: latest.market_loss,
              loss_by_asset_type: lossByAsset,
              loss_by_sector: lossBySec,
              var_95: latest.var_95,
              var_99: latest.var_99,
              cvar_95: latest.cvar_95,
              cvar_99: latest.cvar_99,
              var_methodology: 'Multi-Factor Monte Carlo (1000 draws, 10-day horizon, illustrative synthetic Cholesky correlation matrix)',
              trigger_signal: null,
              scenario_assumptions: parsedAssumptions,
              asset_shocks: parsedShocks,
              simulated_at: String(latest.simulated_at),
            });
          } catch {
            // If details_json parse fails, leave simulationResult null
          }
        }
      } catch (err) {
        if (!isMounted) return;
        const msg = err instanceof Error ? err.message : 'Failed to load stress testing workspace data.';
        setError(msg);
      } finally {
        if (isMounted) setLoadingInitial(false);
      }
    })();

    return () => {
      isMounted = false;
    };
  }, []);

  // Execute Simulation
  const handleRunSimulation = async () => {
    if (!selectedPortfolioId || !activeScenarioId) return;

    setSimulating(true);
    setError(null);
    setFeedback(null);

    try {
      const response = await stressTestService.simulate({
        portfolio_id: selectedPortfolioId,
        scenario_id: activeScenarioId,
        signal_id: triggerSignal?.id || undefined,
        severity_multiplier: severityMultiplier,
        var_simulations: varSimulations,
        allow_duplicate: true, // Manual execution allows rerun
      });

      setSimulationResult(response);
      setActiveRunId(response.simulation_id);

      // Refresh historical runs
      const updatedRuns = await stressTestService.listRuns();
      setHistoricalRuns(updatedRuns);

      setFeedback({
        text: `Stress simulation '${response.scenario_name}' completed. Simulated loss: $${response.total_loss.toLocaleString()} (${response.loss_percentage.toFixed(2)}%).`,
        type: 'success',
      });
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to execute stress simulation.';
      setError(msg);
    } finally {
      setSimulating(false);
    }
  };

  // Inspect Historical Run
  const handleSelectRun = (run: StressTestRunRead) => {
    setActiveRunId(run.id);
    setSelectedPortfolioId(run.portfolio_id);
    if (run.scenario_id) {
      setSelectedScenarioId(run.scenario_id);
    }

    try {
      const parsedShocks: AssetShockDetail[] = JSON.parse(run.details_json);
      const parsedAssumptions = run.assumptions_json ? JSON.parse(run.assumptions_json) : {};

      // Compute loss by asset type and sector from shocks for chart display
      const lossByAsset: Record<string, number> = {};
      const lossBySec: Record<string, number> = {};
      for (const s of parsedShocks) {
        lossByAsset[s.asset_type] = (lossByAsset[s.asset_type] || 0) + s.asset_loss;
        lossBySec[s.sector] = (lossBySec[s.sector] || 0) + s.asset_loss;
      }

      setSimulationResult({
        simulation_id: run.id,
        portfolio_id: run.portfolio_id,
        scenario_id: run.scenario_id || 'CUSTOM',
        scenario_name: run.scenario_name,
        scenario_version: run.scenario_version,
        baseline_value: run.baseline_value,
        stressed_value: run.stressed_value,
        total_loss: run.total_loss,
        loss_percentage: run.loss_percentage,
        credit_loss: run.credit_loss,
        market_loss: run.market_loss,
        loss_by_asset_type: lossByAsset,
        loss_by_sector: lossBySec,
        var_95: run.var_95,
        var_99: run.var_99,
        cvar_95: run.cvar_95,
        cvar_99: run.cvar_99,
        var_methodology: 'Multi-Factor Monte Carlo (1000 draws, 10-day horizon, illustrative synthetic Cholesky correlation matrix)',
        trigger_signal: null,
        scenario_assumptions: parsedAssumptions,
        asset_shocks: parsedShocks,
        simulated_at: String(run.simulated_at),
      });

      setFeedback({
        text: `Loaded historical run ${run.id} (${run.scenario_name}).`,
        type: 'success',
      });
    } catch {
      setError(`Failed to parse details for run ${run.id}`);
    }
  };

  // Preset Configurations for judges
  const applyPreset = (scenId: string, mult: number) => {
    setSelectedScenarioId(scenId);
    setSeverityMultiplier(mult);
  };

  if (loadingInitial) {
    return <LoadingSpinner message="Initializing Stress-Testing Workspace & Scenario Catalog..." />;
  }

  const selectedPortfolio = portfolios.find((p) => p.id === selectedPortfolioId);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Judge Walkthrough Stepper Banner */}
      <div
        style={{
          padding: '0.85rem 1.25rem',
          backgroundColor: 'rgba(59, 130, 246, 0.08)',
          border: '1px solid rgba(59, 130, 246, 0.25)',
          borderRadius: 'var(--radius-lg)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '0.75rem',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <Zap size={20} color="var(--accent-primary)" />
          <div>
            <div style={{ fontWeight: 600, color: '#93c5fd', fontSize: '0.9rem' }}>
              Screen D: Stress-Testing Workspace & Scenario Simulator
            </div>
            <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: '2px' }}>
              <strong>5-Minute Demo Flow:</strong> 1. Select Portfolio → 2. Choose Scenario → 3. Adjust Severity → 4. Run Monte Carlo Simulation → 5. Inspect Loss Decomposition & Asset Shocks
            </div>
          </div>
        </div>

        {/* Quick Demo Presets */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', flexWrap: 'wrap' }}>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Quick Presets:</span>
          <button
            type="button"
            onClick={() => applyPreset('GEOPOLITICAL_ESCALATION', 1.0)}
            className="btn btn-outline"
            style={{ fontSize: '0.7rem', padding: '0.2rem 0.5rem' }}
          >
            Geopolitical (1.0x)
          </button>
          <button
            type="button"
            onClick={() => applyPreset('CENTRAL_BANK_RATE_HIKE', 1.0)}
            className="btn btn-outline"
            style={{ fontSize: '0.7rem', padding: '0.2rem 0.5rem' }}
          >
            Rate Hike (1.0x)
          </button>
          <button
            type="button"
            onClick={() => applyPreset('MACROECONOMIC_RECESSION', 1.5)}
            className="btn btn-outline"
            style={{ fontSize: '0.7rem', padding: '0.2rem 0.5rem' }}
          >
            Stagflation (1.5x)
          </button>
          <button
            type="button"
            onClick={() => applyPreset('BANKING_SECTOR_CRISIS', 2.0)}
            className="btn btn-outline"
            style={{ fontSize: '0.7rem', padding: '0.2rem 0.5rem' }}
          >
            Liquidity Run (2.0x)
          </button>
        </div>
      </div>

      {/* Global Error Banner */}
      {error && <ErrorBanner message={error} onRetry={() => window.location.reload()} />}

      {/* Action Feedback Banner */}
      {feedback && (
        <div
          style={{
            padding: '0.75rem 1rem',
            borderRadius: 'var(--radius-md)',
            backgroundColor: feedback.type === 'success' ? 'var(--accent-emerald-bg)' : 'var(--accent-rose-bg)',
            border: `1px solid ${feedback.type === 'success' ? 'rgba(16, 185, 129, 0.3)' : 'rgba(244, 63, 94, 0.3)'}`,
            color: feedback.type === 'success' ? '#a7f3d0' : '#fda4af',
            fontSize: '0.85rem',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <span>{feedback.text}</span>
          <button
            type="button"
            onClick={() => setFeedback(null)}
            style={{ background: 'none', border: 'none', color: 'inherit', cursor: 'pointer', fontSize: '0.8rem' }}
          >
            ✕
          </button>
        </div>
      )}

      {/* Signal-to-Scenario Automation Trigger Banner */}
      {triggerSignal && mappedScenario && (
        <div
          style={{
            padding: '1rem 1.25rem',
            backgroundColor: 'rgba(59, 130, 246, 0.08)',
            border: '1px solid var(--accent-primary)',
            borderRadius: 'var(--radius-lg)',
            display: 'flex',
            flexDirection: 'column',
            gap: '0.65rem',
            boxShadow: '0 0 15px rgba(59, 130, 246, 0.1)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.5rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Radio size={18} color="var(--accent-primary)" />
              <span style={{ fontWeight: 700, color: '#93c5fd', fontSize: '0.9rem' }}>
                Signal-to-Scenario Automation Active
              </span>
              <Badge variant="blue">Automated Mapping</Badge>
            </div>
            {onClearTriggerSignal && (
              <button
                type="button"
                onClick={onClearTriggerSignal}
                className="btn btn-outline"
                style={{ fontSize: '0.75rem', padding: '0.25rem 0.5rem', gap: '0.25rem' }}
                title="Dismiss signal trigger and return to manual scenario selection"
              >
                <X size={13} />
                <span>Dismiss Signal Link</span>
              </button>
            )}
          </div>

          <div style={{ fontSize: '0.85rem', color: 'var(--text-primary)', fontWeight: 600 }}>
            Headline: "{triggerSignal.article?.title || 'Triggering Risk Article'}"
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap', fontSize: '0.75rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
              <span style={{ color: 'var(--text-muted)' }}>Event Category:</span>
              <Badge variant="purple">{triggerSignal.event_category.replace(/_/g, ' ')}</Badge>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
              <span style={{ color: 'var(--text-muted)' }}>Sentiment:</span>
              <SentimentBadge sentimentLabel={triggerSignal.sentiment_label} sentimentScore={triggerSignal.sentiment_score} />
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
              <span style={{ color: 'var(--text-muted)' }}>Impact Score:</span>
              <ImpactBadge impactScore={triggerSignal.impact_score} />
            </div>
            {triggerSignal.affected_entities && triggerSignal.affected_entities.length > 0 && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                <span style={{ color: 'var(--text-muted)' }}>Entities:</span>
                {triggerSignal.affected_entities.map((e) => (
                  <Badge key={e.ticker} variant="amber">{e.ticker}</Badge>
                ))}
              </div>
            )}
          </div>

          <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', backgroundColor: 'rgba(0, 0, 0, 0.25)', padding: '0.5rem 0.75rem', borderRadius: 'var(--radius-sm)' }}>
            <strong>Backend Mapping Rationale:</strong> {mappedScenario.mappingReason}
          </div>
        </div>
      )}

      {/* STEP 1 & 2: Controls & Scenario Selector */}
      <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
        {/* Top Controls Row: Target Portfolio + Severity Multiplier + Monte Carlo Draws */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
            gap: '1rem',
            alignItems: 'center',
            borderBottom: '1px solid var(--border-subtle)',
            paddingBottom: '1rem',
          }}
        >
          {/* Portfolio Selector */}
          <div>
            <label className="form-label" style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              <Building2 size={14} color="var(--accent-primary)" />
              <span>Target Portfolio</span>
            </label>
            <select
              value={selectedPortfolioId}
              onChange={(e) => setSelectedPortfolioId(e.target.value)}
              className="form-select"
              disabled={simulating}
              style={{ width: '100%', fontSize: '0.85rem' }}
            >
              {portfolios.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} (${(p.current_total_value / 1_000_000).toFixed(2)}M)
                </option>
              ))}
            </select>
          </div>

          {/* Severity Multiplier */}
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.35rem' }}>
              <label className="form-label" style={{ margin: 0, display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                <Sliders size={14} color="var(--accent-amber)" />
                <span>Severity Multiplier:</span>
              </label>
              <span className="tabular-nums" style={{ fontWeight: 700, color: 'var(--accent-amber)', fontSize: '0.85rem' }}>
                {severityMultiplier.toFixed(1)}x
              </span>
            </div>
            <input
              type="range"
              min="0.5"
              max="3.0"
              step="0.1"
              value={severityMultiplier}
              onChange={(e) => setSeverityMultiplier(parseFloat(e.target.value))}
              disabled={simulating}
              style={{ width: '100%', accentColor: 'var(--accent-amber)', cursor: 'pointer' }}
            />
          </div>

          {/* Monte Carlo Draws */}
          <div>
            <label className="form-label" style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              <Activity size={14} color="var(--accent-purple)" />
              <span>Monte Carlo Draws</span>
            </label>
            <select
              value={varSimulations}
              onChange={(e) => setVarSimulations(parseInt(e.target.value, 10))}
              className="form-select"
              disabled={simulating}
              style={{ width: '100%', fontSize: '0.85rem' }}
            >
              <option value={500}>500 Draws (Fast)</option>
              <option value={1000}>1,000 Draws (Standard Demo)</option>
              <option value={2500}>2,500 Draws (High Precision)</option>
              <option value={5000}>5,000 Draws (Institutional)</option>
            </select>
          </div>

          {/* Primary Action Button */}
          <div style={{ display: 'flex', alignItems: 'flex-end' }}>
            <button
              type="button"
              onClick={handleRunSimulation}
              disabled={simulating}
              className="btn btn-primary"
              style={{
                width: '100%',
                padding: '0.65rem 1rem',
                fontSize: '0.9rem',
                fontWeight: 600,
                boxShadow: 'var(--shadow-md)',
              }}
            >
              {simulating ? (
                <>
                  <RotateCcw size={16} className="spin" />
                  <span>Computing Multi-Factor Transmission...</span>
                </>
              ) : (
                <>
                  <Play size={16} />
                  <span>Execute Stress Simulation</span>
                </>
              )}
            </button>
          </div>
        </div>

        {/* Scenario Cards Grid */}
        <ScenarioSelectorCard
          scenarios={scenarios}
          selectedScenarioId={activeScenarioId}
          onSelectScenario={(scenId) => {
            setSelectedScenarioId(scenId);
            if (onClearTriggerSignal) onClearTriggerSignal();
          }}
          disabled={simulating}
        />
      </div>

      {/* STEP 3 & 4: Active Simulation Results View */}
      {simulationResult && (
        <>
          {/* Results Summary Header */}
          <div
            style={{
              backgroundColor: 'rgba(15, 23, 42, 0.6)',
              border: '1px solid var(--border-default)',
              borderRadius: 'var(--radius-lg)',
              padding: '1.25rem',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              flexWrap: 'wrap',
              gap: '1rem',
            }}
          >
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem', flexWrap: 'wrap' }}>
                <h3 style={{ margin: 0, color: 'var(--text-primary)', fontSize: '1.2rem', fontWeight: 700 }}>
                  {simulationResult.scenario_name}
                </h3>
                <Badge variant={simulationResult.total_loss > 0 ? 'red' : 'green'}>
                  {simulationResult.total_loss > 0 ? 'Capital Loss' : 'Hedge Gain'}
                </Badge>
                <span className="mono" style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                  Run ID: {simulationResult.simulation_id}
                </span>
              </div>
              <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: '0.35rem' }}>
                Target: <strong>{selectedPortfolio?.name || simulationResult.portfolio_id}</strong> • Simulated at: {new Date(simulationResult.simulated_at).toLocaleTimeString()}
              </div>
              {simulationResult.trigger_signal && (
                <div style={{ display: 'inline-flex', alignItems: 'center', gap: '5px', marginTop: '4px', backgroundColor: 'rgba(59, 130, 246, 0.1)', padding: '2px 8px', borderRadius: '4px', fontSize: '0.75rem', color: '#93c5fd' }}>
                  <Radio size={12} color="var(--accent-primary)" />
                  <span>Triggered by Signal: <strong>{simulationResult.trigger_signal.article?.title || simulationResult.trigger_signal.id}</strong></span>
                </div>
              )}
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <div className="tabular-nums" style={{ textAlign: 'right' }}>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Total Simulated Impact</div>
                <div
                  style={{
                    fontSize: '1.4rem',
                    fontWeight: 700,
                    color: simulationResult.total_loss > 0 ? 'var(--accent-rose)' : 'var(--accent-emerald)',
                  }}
                >
                  {simulationResult.total_loss > 0 ? '-' : '+'}${Math.abs(simulationResult.total_loss).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  <span style={{ fontSize: '0.85rem', marginLeft: '0.4rem', opacity: 0.9 }}>
                    ({simulationResult.loss_percentage > 0 ? '-' : '+'}{Math.abs(simulationResult.loss_percentage).toFixed(2)}%)
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* 4 Metric Cards */}
          <div className="grid-metrics">
            {/* KPI 1: Capital Impact */}
            <MetricCard
              title="Net Stressed Loss / Gain"
              value={
                <span style={{ color: simulationResult.total_loss > 0 ? 'var(--accent-rose)' : 'var(--accent-emerald)' }}>
                  {simulationResult.total_loss > 0 ? '-' : '+'}${Math.abs(simulationResult.total_loss).toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
                </span>
              }
              subtitle={
                <span className="tabular-nums" style={{ fontSize: '0.75rem', color: simulationResult.loss_percentage > 0 ? 'var(--accent-rose)' : 'var(--accent-emerald)' }}>
                  {simulationResult.loss_percentage > 0 ? '-' : '+'}{Math.abs(simulationResult.loss_percentage).toFixed(2)}% of carrying baseline
                </span>
              }
              badge={<Badge variant={simulationResult.total_loss > 0 ? 'red' : 'green'}>{simulationResult.total_loss > 0 ? 'Loss' : 'Gain'}</Badge>}
              icon={<TrendingDown size={18} />}
              tooltip="Total change in portfolio carrying value under the applied factor shocks. Reconciles exactly with instrument-level losses and gains."
              tooltipTitle="Net Portfolio Loss"
            />

            {/* KPI 2: Carrying Value Transition */}
            <MetricCard
              title="Carrying Value Transition"
              value={`$${simulationResult.stressed_value.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`}
              subtitle={
                <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                  Baseline: ${simulationResult.baseline_value.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
                </span>
              }
              badge={<Badge variant="blue">Stressed Balance</Badge>}
              icon={<DollarSign size={18} />}
              tooltip="Portfolio post-stress valuation. Commercial loans revalued via IFRS 9 amortized cost; bonds via duration & credit spreads; equities marked to model; put options via delta hedge."
              tooltipTitle="Post-Stress Valuation"
            />

            {/* KPI 3: Credit vs Market Loss */}
            <MetricCard
              title="Loss Decomposition"
              value={`$${simulationResult.credit_loss.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`}
              subtitle={
                <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                  Credit ECL: ${(simulationResult.credit_loss / 1_000).toFixed(0)}k • Market: ${(simulationResult.market_loss / 1_000).toFixed(0)}k
                </span>
              }
              badge={<Badge variant="amber">Credit ECL</Badge>}
              icon={<ShieldAlert size={18} />}
              tooltip="Decomposition into credit losses (increased loan Expected Credit Loss) and market losses (bond duration repricing, credit spread widening, equity beta shocks, net of option hedge offsets)."
              tooltipTitle="Credit vs Market Loss Decomposition"
            />

            {/* KPI 4: Monte Carlo VaR & CVaR */}
            <MetricCard
              title="Illustrative VaR (95% / 10d)"
              value={simulationResult.var_95 ? `$${simulationResult.var_95.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}` : '—'}
              subtitle={
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                  99% VaR: ${simulationResult.var_99 ? Math.round(simulationResult.var_99).toLocaleString() : '—'} • 95% CVaR: ${simulationResult.cvar_95 ? Math.round(simulationResult.cvar_95).toLocaleString() : '—'}
                </span>
              }
              badge={<Badge variant="purple">Monte Carlo</Badge>}
              icon={<Activity size={18} />}
              tooltip="Illustrative 10-day Value-at-Risk and Conditional Value-at-Risk computed via multi-factor Monte Carlo simulation with synthetic Cholesky correlation matrix. Not a live market forecast."
              tooltipTitle="Monte Carlo VaR & CVaR (10-day)"
            />
          </div>

          {/* Statistical Methodology & Disclosure Banner */}
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
                Statistical & Financial Integrity Disclosure
              </div>
              <div>
                <strong>Monte Carlo VaR & CVaR:</strong> Based on a 10-day horizon, {varSimulations.toLocaleString()} draws, and synthetic Cholesky covariance matrix. Estimates represent controlled scenario tail-risk benchmarks, not calibrated live-market forecasts.
              </div>
              <div>
                <strong>Derivative Put Option Hedge Decoupling:</strong> The SPX Protective Put position ($10M underlying notional, $250k contract premium carrying value, $\Delta = -0.35$) offsets simulated market losses as equity indices decline, reflecting genuine downside insurance.
              </div>
            </div>
          </div>

          {/* Recharts Loss Breakdown Visualizations */}
          <div style={{ minHeight: '340px' }}>
            <LossBreakdownChart
              lossByAssetType={simulationResult.loss_by_asset_type}
              lossBySector={simulationResult.loss_by_sector}
            />
          </div>

          {/* Detailed Instrument Factor Shock Table */}
          <AssetShockTable
            shocks={simulationResult.asset_shocks}
            baselineValue={simulationResult.baseline_value}
            stressedValue={simulationResult.stressed_value}
            totalLoss={simulationResult.total_loss}
            creditLoss={simulationResult.credit_loss}
            marketLoss={simulationResult.market_loss}
          />
        </>
      )}

      {/* STEP 5: Simulation History & Audit Log */}
      <SimulationHistoryTable
        runs={historicalRuns}
        activeRunId={activeRunId}
        onSelectRun={handleSelectRun}
        onRefresh={async () => {
          const updated = await stressTestService.listRuns();
          setHistoricalRuns(updated);
        }}
      />
    </div>
  );
};
