import React, { useState } from 'react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip as RechartsTooltip,
  Cell,
} from 'recharts';
import { PieChart as PieChartIcon } from 'lucide-react';
import type { SectorExposureItem, PortfolioAssetRead } from '../../types/api';

interface SectorExposureChartProps {
  sectorExposures: SectorExposureItem[];
  assets: PortfolioAssetRead[];
  totalValue: number;
}

interface ExposureTooltipData {
  name: string;
  value: number;
  weight: number;
  count?: number;
}

interface ExposureTooltipProps {
  active?: boolean;
  payload?: readonly { payload?: unknown }[];
}

const ExposureChartTooltip: React.FC<ExposureTooltipProps> = ({ active, payload }) => {
  if (active && payload && payload.length && payload[0].payload) {
    const data = payload[0].payload as ExposureTooltipData;
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
        <div style={{ color: 'var(--text-primary)', fontSize: '0.85rem', fontWeight: 700 }} className="tabular-nums">
          Carrying Value: ${data.value.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
        </div>
        <div style={{ color: 'var(--accent-primary)', fontSize: '0.75rem', marginTop: '0.2rem' }} className="tabular-nums">
          Portfolio Weight: {(data.weight * 100).toFixed(1)}%
          {data.count !== undefined && ` • ${data.count} holding${data.count > 1 ? 's' : ''}`}
        </div>
      </div>
    );
  }
  return null;
};

const PALETTE = ['#3b82f6', '#06b6d4', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899'];

export const SectorExposureChart: React.FC<SectorExposureChartProps> = ({
  sectorExposures,
  assets,
  totalValue,
}) => {
  const [viewMode, setViewMode] = useState<'sector' | 'asset_class'>('sector');

  // Compute Asset Class Breakdown
  const assetClassTotals: Record<string, { value: number; count: number }> = {};
  for (const a of assets) {
    const rawType = a.asset_type || 'unclassified';
    const cleanType = rawType.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
    const mv = a.market_value || a.shares * a.current_price;
    if (!assetClassTotals[cleanType]) {
      assetClassTotals[cleanType] = { value: 0, count: 0 };
    }
    assetClassTotals[cleanType].value += mv;
    assetClassTotals[cleanType].count += 1;
  }

  const assetClassData: ExposureTooltipData[] = Object.entries(assetClassTotals).map(([name, item]) => ({
    name,
    value: Math.round(item.value),
    weight: totalValue > 0 ? item.value / totalValue : 0,
    count: item.count,
  }));

  const sectorData: ExposureTooltipData[] = sectorExposures.map((item) => ({
    name: item.sector,
    value: Math.round(item.value),
    weight: item.weight,
  }));

  const activeData = viewMode === 'sector' ? sectorData : assetClassData;

  return (
    <div className="card" style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <div className="card-header" style={{ marginBottom: '0.75rem' }}>
        <div>
          <div className="card-title">
            {viewMode === 'sector' ? 'Sector Allocation Breakdown' : 'Asset Class Composition'}
          </div>
          <div className="card-subtitle">
            {viewMode === 'sector'
              ? 'Aggregated carrying value by economic sector'
              : 'Wholesale allocation across credit, rates, equities & hedges'}
          </div>
        </div>

        <div style={{ display: 'flex', gap: '0.25rem', backgroundColor: 'rgba(255, 255, 255, 0.03)', padding: '2px', borderRadius: 'var(--radius-sm)' }}>
          <button
            type="button"
            onClick={() => setViewMode('sector')}
            className={`btn ${viewMode === 'sector' ? 'btn-secondary' : 'btn-outline'}`}
            style={{ fontSize: '0.7rem', padding: '0.25rem 0.5rem' }}
          >
            Sectors
          </button>
          <button
            type="button"
            onClick={() => setViewMode('asset_class')}
            className={`btn ${viewMode === 'asset_class' ? 'btn-secondary' : 'btn-outline'}`}
            style={{ fontSize: '0.7rem', padding: '0.25rem 0.5rem' }}
          >
            Asset Classes
          </button>
        </div>
      </div>

      <div style={{ flex: 1, minHeight: '260px', width: '100%' }}>
        {activeData.length === 0 ? (
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
            <PieChartIcon size={28} />
            <span>No exposure data calculated for this portfolio</span>
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={activeData} margin={{ top: 10, right: 10, left: 10, bottom: 25 }}>
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
              <RechartsTooltip content={(props) => <ExposureChartTooltip {...props} />} />
              <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                {activeData.map((_, index) => (
                  <Cell key={`cell-${index}`} fill={PALETTE[index % PALETTE.length]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>

      <div style={{ marginTop: '0.75rem', borderTop: '1px solid var(--border-subtle)', paddingTop: '0.65rem' }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.75rem', fontSize: '0.75rem' }}>
          {activeData.map((item, idx) => (
            <div key={item.name} style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
              <span style={{ width: 8, height: 8, backgroundColor: PALETTE[idx % PALETTE.length], borderRadius: '50%' }} />
              <span style={{ color: 'var(--text-secondary)' }}>{item.name}:</span>
              <strong className="tabular-nums" style={{ color: 'var(--text-primary)' }}>
                {(item.weight * 100).toFixed(1)}%
              </strong>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
