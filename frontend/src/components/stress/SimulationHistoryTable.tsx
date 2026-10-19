import React from 'react';
import { History, Eye, RefreshCw, Calendar, TrendingDown } from 'lucide-react';
import { Badge } from '../common/Badge';
import type { StressTestRunRead } from '../../types/api';

interface SimulationHistoryTableProps {
  runs: StressTestRunRead[];
  activeRunId?: string | null;
  onSelectRun: (run: StressTestRunRead) => void;
  loading?: boolean;
  onRefresh?: () => void;
}

export const SimulationHistoryTable: React.FC<SimulationHistoryTableProps> = ({
  runs,
  activeRunId,
  onSelectRun,
  loading = false,
  onRefresh,
}) => {
  const formatTimestamp = (iso: string) => {
    try {
      const d = new Date(iso);
      return d.toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      });
    } catch {
      return iso;
    }
  };

  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <History size={18} color="var(--accent-primary)" />
          <div>
            <div className="card-title">Stress Simulation Run History</div>
            <div className="card-subtitle">
              Audit trail of persistent historical runs with parameter snapshots and loss breakdowns
            </div>
          </div>
        </div>

        {onRefresh && (
          <button
            type="button"
            onClick={onRefresh}
            disabled={loading}
            className="btn btn-outline"
            style={{ fontSize: '0.75rem', padding: '0.35rem 0.65rem', gap: '0.35rem' }}
          >
            <RefreshCw size={13} className={loading ? 'spin' : ''} />
            <span>Refresh Runs</span>
          </button>
        )}
      </div>

      {/* Table of Runs */}
      {runs.length === 0 ? (
        <div
          style={{
            textAlign: 'center',
            padding: '2.5rem',
            color: 'var(--text-muted)',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: '0.5rem',
          }}
        >
          <History size={28} />
          <span>No historical stress simulations recorded yet. Run a scenario above to record a new run.</span>
        </div>
      ) : (
        <div className="table-container">
          <table className="table">
            <thead>
              <tr>
                <th>Execution Time</th>
                <th>Scenario Name</th>
                <th>Target Portfolio</th>
                <th>Total Loss ($)</th>
                <th>Impact (%)</th>
                <th>95% VaR (10d)</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((r) => {
                const isActive = r.id === activeRunId;

                return (
                  <tr
                    key={r.id}
                    style={{
                      backgroundColor: isActive ? 'rgba(59, 130, 246, 0.08)' : undefined,
                    }}
                  >
                    {/* Timestamp */}
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', color: 'var(--text-primary)', fontSize: '0.8rem' }}>
                        <Calendar size={13} color="var(--text-muted)" />
                        <span>{formatTimestamp(r.simulated_at)}</span>
                      </div>
                      <div className="mono" style={{ fontSize: '0.675rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                        {r.id}
                      </div>
                    </td>

                    {/* Scenario */}
                    <td>
                      <div style={{ fontWeight: 600, color: 'var(--text-primary)', fontSize: '0.85rem' }}>
                        {r.scenario_name}
                      </div>
                      <div style={{ display: 'flex', gap: '0.3rem', marginTop: '2px' }}>
                        <Badge variant="blue">{r.scenario_id || 'CUSTOM'}</Badge>
                        <span className="mono" style={{ fontSize: '0.675rem', color: 'var(--text-muted)' }}>
                          {r.scenario_version}
                        </span>
                      </div>
                    </td>

                    {/* Portfolio */}
                    <td>
                      <span className="mono" style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                        {r.portfolio_id}
                      </span>
                    </td>

                    {/* Total Loss */}
                    <td className="tabular-nums">
                      <span
                        style={{
                          fontWeight: 700,
                          color: r.total_loss > 0 ? 'var(--accent-rose)' : 'var(--accent-emerald)',
                        }}
                      >
                        {r.total_loss > 0 ? '+' : '-'}${Math.abs(r.total_loss).toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
                      </span>
                    </td>

                    {/* Loss Percentage */}
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                        <TrendingDown size={13} color={r.loss_percentage > 0 ? 'var(--accent-rose)' : 'var(--accent-emerald)'} />
                        <span
                          className="tabular-nums"
                          style={{
                            fontWeight: 700,
                            color: r.loss_percentage > 0 ? 'var(--accent-rose)' : 'var(--accent-emerald)',
                          }}
                        >
                          {r.loss_percentage.toFixed(2)}%
                        </span>
                      </div>
                    </td>

                    {/* VaR */}
                    <td className="tabular-nums" style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>
                      {r.var_95 !== null && r.var_95 !== undefined ? `$${Math.round(r.var_95).toLocaleString()}` : '—'}
                    </td>

                    {/* Inspect Button */}
                    <td>
                      <button
                        type="button"
                        onClick={() => onSelectRun(r)}
                        className={`btn ${isActive ? 'btn-primary' : 'btn-outline'}`}
                        style={{ fontSize: '0.75rem', padding: '0.3rem 0.65rem', gap: '0.35rem' }}
                      >
                        <Eye size={13} />
                        <span>{isActive ? 'Active' : 'Inspect Run'}</span>
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
