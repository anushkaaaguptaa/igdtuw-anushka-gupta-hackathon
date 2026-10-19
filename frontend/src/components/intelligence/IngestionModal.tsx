import React, { useState } from 'react';
import {
  X,
  Play,
  Loader2,
  CheckCircle2,
  AlertCircle,
  Database,
  Globe,
  Rss,
  History,
  Clock
} from 'lucide-react';
import { ingestionService } from '../../services/ingestionService';
import type { IngestSummaryResponse } from '../../types/api';

interface IngestionModalProps {
  isOpen: boolean;
  onClose: () => void;
  onIngestComplete: () => void;
}

export const IngestionModal: React.FC<IngestionModalProps> = ({
  isOpen,
  onClose,
  onIngestComplete,
}) => {
  const [mode, setMode] = useState<'live' | 'replay'>('live');
  const [useGdelt, setUseGdelt] = useState(true);
  const [useRss, setUseRss] = useState(true);
  const [limit, setLimit] = useState(10);
  const [keywords, setKeywords] = useState('');
  const [runNlp, setRunNlp] = useState(true);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [summary, setSummary] = useState<IngestSummaryResponse | null>(null);

  if (!isOpen) return null;

  const handleRun = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setSummary(null);

    const sources: string[] = [];
    if (mode === 'live') {
      if (useGdelt) sources.push('gdelt');
      if (useRss) sources.push('financial_rss');
      if (sources.length === 0) {
        setError('Please select at least one live source (GDELT or Financial RSS).');
        setLoading(false);
        return;
      }
    } else {
      sources.push('replay_fixture');
    }

    const keywordList = keywords
      .split(',')
      .map((k) => k.trim())
      .filter(Boolean);

    try {
      const res = await ingestionService.triggerIngestion({
        mode,
        sources,
        keywords: keywordList.length > 0 ? keywordList : undefined,
        limit_per_source: limit,
        run_nlp: runNlp,
      });
      setSummary(res);
      onIngestComplete();
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Ingestion batch execution failed.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-dialog" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Database size={18} color="var(--accent-primary)" />
            <h3 style={{ margin: 0, fontSize: '1.05rem' }}>Trigger Financial News Ingestion Batch</h3>
          </div>
          <button
            onClick={onClose}
            className="btn btn-outline"
            style={{ padding: '4px', border: 'none', background: 'transparent' }}
            type="button"
          >
            <X size={18} />
          </button>
        </div>

        <form onSubmit={handleRun}>
          <div className="modal-body" style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            {/* Mode selection */}
            <div>
              <label className="form-label" style={{ marginBottom: '0.4rem', display: 'block' }}>
                Ingestion Source Mode
              </label>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                <button
                  type="button"
                  onClick={() => setMode('live')}
                  className={`btn ${mode === 'live' ? 'btn-primary' : 'btn-outline'}`}
                  style={{ justifyContent: 'flex-start', padding: '0.75rem' }}
                >
                  <Globe size={16} />
                  <div style={{ textAlign: 'left' }}>
                    <div style={{ fontWeight: 600 }}>Live External Feeds</div>
                    <div style={{ fontSize: '0.7rem', opacity: 0.8 }}>GDELT 2.0 & Financial RSS</div>
                  </div>
                </button>

                <button
                  type="button"
                  onClick={() => setMode('replay')}
                  className={`btn ${mode === 'replay' ? 'btn-primary' : 'btn-outline'}`}
                  style={{ justifyContent: 'flex-start', padding: '0.75rem' }}
                >
                  <History size={16} />
                  <div style={{ textAlign: 'left' }}>
                    <div style={{ fontWeight: 600 }}>Curated Replay Dataset</div>
                    <div style={{ fontSize: '0.7rem', opacity: 0.8 }}>Deterministic Crisis Fixtures</div>
                  </div>
                </button>
              </div>
            </div>

            {/* Sources selection (if live) */}
            {mode === 'live' && (
              <div
                style={{
                  padding: '0.85rem',
                  backgroundColor: 'rgba(255, 255, 255, 0.02)',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--border-subtle)',
                }}
              >
                <div style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
                  Select Live Source Adapters:
                </div>
                <div style={{ display: 'flex', gap: '1.25rem' }}>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.825rem', cursor: 'pointer' }}>
                    <input
                      type="checkbox"
                      className="form-checkbox"
                      checked={useGdelt}
                      onChange={(e) => setUseGdelt(e.target.checked)}
                    />
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '3px' }}>
                      <Globe size={13} color="var(--accent-primary)" /> GDELT 2.0 Doc API
                    </span>
                  </label>

                  <label style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.825rem', cursor: 'pointer' }}>
                    <input
                      type="checkbox"
                      className="form-checkbox"
                      checked={useRss}
                      onChange={(e) => setUseRss(e.target.checked)}
                    />
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '3px' }}>
                      <Rss size={13} color="var(--accent-amber)" /> Yahoo / Dow Jones RSS
                    </span>
                  </label>
                </div>
              </div>
            )}

            {/* Limit and keywords */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '0.85rem' }}>
              <div className="form-group" style={{ marginBottom: 0 }}>
                <label className="form-label" htmlFor="ingest-limit">
                  Limit per Source
                </label>
                <input
                  id="ingest-limit"
                  type="number"
                  min={1}
                  max={50}
                  className="form-input"
                  value={limit}
                  onChange={(e) => setLimit(Math.max(1, Math.min(50, parseInt(e.target.value) || 10)))}
                />
              </div>

              <div className="form-group" style={{ marginBottom: 0 }}>
                <label className="form-label" htmlFor="ingest-keywords">
                  Keyword Filter <span style={{ color: 'var(--text-muted)', fontWeight: 400 }}>(Optional, comma-separated)</span>
                </label>
                <input
                  id="ingest-keywords"
                  type="text"
                  className="form-input"
                  placeholder="e.g. sanctions, antitrust, default, rate"
                  value={keywords}
                  onChange={(e) => setKeywords(e.target.value)}
                />
              </div>
            </div>

            {/* NLP Pipeline checkbox */}
            <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer', fontSize: '0.825rem', color: 'var(--text-secondary)' }}>
              <input
                type="checkbox"
                className="form-checkbox"
                checked={runNlp}
                onChange={(e) => setRunNlp(e.target.checked)}
              />
              <span>Automatically generate FinBERT sentiment and impact signals for ingested items</span>
            </label>

            {/* Error display */}
            {error && (
              <div
                style={{
                  padding: '0.75rem 1rem',
                  borderRadius: 'var(--radius-md)',
                  backgroundColor: 'var(--accent-rose-bg)',
                  border: '1px solid rgba(244, 63, 94, 0.3)',
                  color: '#fda4af',
                  fontSize: '0.8rem',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                }}
              >
                <AlertCircle size={16} />
                <span>{error}</span>
              </div>
            )}

            {/* Ingestion Summary Results */}
            {summary && (
              <div
                style={{
                  padding: '1rem',
                  borderRadius: 'var(--radius-md)',
                  backgroundColor: 'var(--accent-emerald-bg)',
                  border: '1px solid rgba(16, 185, 129, 0.3)',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '0.65rem',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', color: '#6ee7b7', fontWeight: 600, fontSize: '0.9rem' }}>
                  <CheckCircle2 size={16} />
                  <span>Ingestion Batch Completed</span>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '0.5rem', textAlign: 'center' }}>
                  <div style={{ backgroundColor: 'rgba(0, 0, 0, 0.2)', padding: '0.5rem', borderRadius: 'var(--radius-sm)' }}>
                    <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Fetched</div>
                    <div style={{ fontSize: '1.1rem', fontWeight: 700 }} className="tabular-nums">{summary.articles_fetched}</div>
                  </div>
                  <div style={{ backgroundColor: 'rgba(0, 0, 0, 0.2)', padding: '0.5rem', borderRadius: 'var(--radius-sm)' }}>
                    <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Persisted</div>
                    <div style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--accent-emerald)' }} className="tabular-nums">{summary.articles_persisted}</div>
                  </div>
                  <div style={{ backgroundColor: 'rgba(0, 0, 0, 0.2)', padding: '0.5rem', borderRadius: 'var(--radius-sm)' }}>
                    <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Duplicates</div>
                    <div style={{ fontSize: '1.1rem', fontWeight: 700 }} className="tabular-nums">{summary.duplicates_skipped}</div>
                  </div>
                  <div style={{ backgroundColor: 'rgba(0, 0, 0, 0.2)', padding: '0.5rem', borderRadius: 'var(--radius-sm)' }}>
                    <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Signals</div>
                    <div style={{ fontSize: '1.1rem', fontWeight: 700, color: '#93c5fd' }} className="tabular-nums">{summary.signals_generated}</div>
                  </div>
                </div>

                <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <Clock size={11} /> Batch Execution Time: {summary.duration_ms.toFixed(0)}ms
                </div>
              </div>
            )}
          </div>

          <div className="modal-footer">
            <button type="button" onClick={onClose} className="btn btn-outline" style={{ fontSize: '0.8rem' }}>
              Close
            </button>
            <button
              type="submit"
              disabled={loading}
              className="btn btn-primary"
              style={{ fontSize: '0.8rem' }}
            >
              {loading ? <Loader2 size={14} className="spin" /> : <Play size={14} />}
              <span>{loading ? 'Ingesting Feeds...' : 'Trigger Ingestion Batch'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
