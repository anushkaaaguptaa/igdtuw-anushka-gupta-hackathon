import React, { useState } from 'react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip as RechartsTooltip,
  Cell,
  ReferenceLine,
} from 'recharts';
import { Layers } from 'lucide-react';
import type { SectorExposureItem } from '../../types/api';

interface LossBreakdownChartProps {
  lossByAssetType?: Record<string, number>;
  lossBySector?: Record<string, number>;
  sectorExposure?: SectorExposureItem[];
}

interface TooltipData {
  name: string;
  formattedValue: string;
  value: number;
  isGain: boolean;
}

interface LossChartTooltipProps {
  active?: boolean;
  payload?: readonly { payload?: unknown }[];
  viewMode: 'asset_type' | 'sector' | 'exposure';
}

const LossChartTooltip: React.FC<LossChartTooltipProps> = ({ active, payload, viewMode }) => {
  if (active && payload && payload.length && payload[0].payload) {
    const data = payload[0].payload as TooltipData;
    return (
      <div
        style={{
          backgroundColor: '#0f172a',
          border: '1px solid var(--border-default)',
          borderRadius: 'var(--radius-md)',
          padding: '0.65rem 0.85rem',
          boxShadow: 'var(--shadow-md)',
        }}
      >
        <div style={{ color: '#93c5fd', fontWeight: 600, fontSize: '0.8rem', marginBottom: '0.2rem' }}>
          {data.name}
        </div>
        <div style={{ color: data.isGain ? 'var(--accent-emerald)' : 'var(--text-primary)', fontSize: '0.85rem', fontWeight: 700 }} className="tabular-nums">
          {viewMode === 'exposure' ? 'Exposure: ' : data.isGain ? 'Hedge Gain: ' : 'Simulated Loss: '}
          {data.formattedValue}
        </div>
        {data.isGain && (
          <div style={{ fontSize: '0.7rem', color: 'var(--accent-emerald)', marginTop: '0.25rem' }}>
            Derivative protective position offset
          </div>
        )}
      </div>
    );
  }
  return null;
};

export const LossBreakdownChart: React.FC<LossBreakdownChartProps> = ({
  lossByAssetType = {},
  lossBySector = {},
  sectorExposure = [],
}) => {
  const hasStressLosses = Object.keys(lossByAssetType).length > 0 || Object.keys(lossBySector).length > 0;
  const [viewMode, setViewMode] = useState<'asset_type' | 'sector' | 'exposure'>(
    hasStressLosses ? 'asset_type' : 'exposure'
  );

  let chartData: { name: string; value: number; formattedValue: string; isGain: boolean }[] = [];

  if (viewMode === 'asset_type' && Object.keys(lossByAssetType).length > 0) {
    chartData = Object.entries(lossByAssetType).map(([key, val]) => {
      const cleanName = key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
      return {
        name: cleanName,
        value: val,
        formattedValue: `${val < 0 ? '-' : ''}$${Math.abs(val).toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`,
        isGain: val < 0,
      };
    });
  } else if (viewMode === 'sector' && Object.keys(lossBySector).length > 0) {
    chartData = Object.entries(lossBySector).map(([key, val]) => ({
      name: key,
      value: val,
      formattedValue: `${val < 0 ? '-' : ''}$${Math.abs(val).toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`,
      isGain: val < 0,
    }));
  } else if (sectorExposure.length > 0) {
    chartData = sectorExposure.map((item) => ({
      name: item.sector,
      value: item.value,
      formattedValue: `$${item.value.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })} (${(item.weight * 100).toFixed(1)}%)`,
      isGain: false,
    }));
  }

  return (
    <div className="card" style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <div className="card-header" style={{ marginBottom: '0.75rem' }}>
        <div>
          <div className="card-title">
            {viewMode === 'exposure' ? 'Portfolio Sector Exposure' : 'Loss Contribution Breakdown'}
          </div>
          <div className="card-subtitle">
            {viewMode === 'exposure'
              ? 'Carrying value distribution across economic sectors'
              : 'Deterministic factor impact across asset classes (hedge gains reflected as negative losses)'}
          </div>
        </div>

        {/* View mode toggle */}
        <div style={{ display: 'flex', gap: '0.25rem', backgroundColor: 'rgba(255, 255, 255, 0.03)', padding: '2px', borderRadius: 'var(--radius-sm)' }}>
          {Object.keys(lossByAssetType).length > 0 && (
            <button
              onClick={() => setViewMode('asset_type')}
              className={`btn ${viewMode === 'asset_type' ? 'btn-secondary' : 'btn-outline'}`}
              style={{ fontSize: '0.7rem', padding: '0.25rem 0.5rem' }}
              type="button"
            >
              Asset Classes
            </button>
          )}
          {Object.keys(lossBySector).length > 0 && (
            <button
              onClick={() => setViewMode('sector')}
              className={`btn ${viewMode === 'sector' ? 'btn-secondary' : 'btn-outline'}`}
              style={{ fontSize: '0.7rem', padding: '0.25rem 0.5rem' }}
              type="button"
            >
              Stress Sectors
            </button>
          )}
          {sectorExposure.length > 0 && (
            <button
              onClick={() => setViewMode('exposure')}
              className={`btn ${viewMode === 'exposure' ? 'btn-secondary' : 'btn-outline'}`}
              style={{ fontSize: '0.7rem', padding: '0.25rem 0.5rem' }}
              type="button"
            >
              Baseline Exposure
            </button>
          )}
        </div>
      </div>

      <div style={{ flex: 1, minHeight: '260px', width: '100%' }}>
        {chartData.length === 0 ? (
          <div
            style={{
              height: '100%',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--text-muted)',
              fontSize: '0.85rem',
              gap: '0.5rem',
            }}
          >
            <Layers size={28} />
            <span>No simulation runs or portfolio allocations recorded yet</span>
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} margin={{ top: 10, right: 10, left: 10, bottom: 25 }}>
              <XAxis
                dataKey="name"
                stroke="#64748b"
                fontSize={11}
                tickLine={false}
                interval={0}
                angle={-15}
                textAnchor="end"
              />
              <YAxis
                stroke="#64748b"
                fontSize={11}
                tickLine={false}
                tickFormatter={(val) => {
                  if (Math.abs(val) >= 1_000_000) return `$${(val / 1_000_000).toFixed(1)}M`;
                  if (Math.abs(val) >= 1_000) return `$${(val / 1_000).toFixed(0)}k`;
                  return `$${val}`;
                }}
              />
              <ReferenceLine y={0} stroke="rgba(255, 255, 255, 0.15)" />
              <RechartsTooltip content={(props) => <LossChartTooltip {...props} viewMode={viewMode} />} />
              <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                {chartData.map((entry, index) => {
                  let fillColor = '#3b82f6';
                  if (viewMode === 'exposure') {
                    fillColor = '#3b82f6';
                  } else if (entry.isGain) {
                    fillColor = '#10b981'; // Green for hedge gain
                  } else {
                    fillColor = '#f43f5e'; // Rose for loss
                  }
                  return <Cell key={`cell-${index}`} fill={fillColor} />;
                })}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>

      {hasStressLosses && viewMode !== 'exposure' && (
        <div style={{ display: 'flex', gap: '1rem', justifyContent: 'center', fontSize: '0.75rem', marginTop: '0.5rem', color: 'var(--text-muted)' }}>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
            <span style={{ width: 10, height: 10, backgroundColor: '#f43f5e', borderRadius: 2 }} /> Net Market/Credit Loss
          </span>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
            <span style={{ width: 10, height: 10, backgroundColor: '#10b981', borderRadius: 2 }} /> Derivative Hedge Gain (Negative Loss)
          </span>
        </div>
      )}
    </div>
  );
};
