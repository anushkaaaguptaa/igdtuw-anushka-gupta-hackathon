import React, { useState } from 'react';
import {
  Sparkles,
  Send,
  Loader2,
  CheckCircle2,
  AlertCircle,
  Clock,
  Cpu,
  BookmarkCheck,
  Tag
} from 'lucide-react';
import { Badge, SentimentBadge, ImpactBadge } from '../common/Badge';
import { signalsService } from '../../services/signalsService';
import type { TextAnalysisResponse } from '../../types/api';

interface TextAnalysisCardProps {
  onSignalCreated?: () => void;
}

const SAMPLE_HEADLINES = [
  {
    label: 'Regulatory Antitrust',
    title: 'FTC Launches Antitrust Investigation into Microsoft and Alphabet Cloud AI Alliances',
    content: 'The Federal Trade Commission issued inquiry orders examining cloud market power and exclusive compute agreements.',
  },
  {
    label: 'Fed Rate Tightening',
    title: 'Federal Reserve Signals Aggressive 50 bps Policy Rate Hike as Core Inflation Accelerates',
    content: 'Chairman Powell indicated borrowing costs will remain elevated to bring consumer prices back to the 2% target.',
  },
  {
    label: 'Corporate Credit Default',
    title: 'Acme Industrial Enters Debt Restructuring After Defaulting on $500M Senior Secured Notes',
    content: 'Credit rating agencies downgraded the issuer to selective default following missed coupon obligations.',
  },
  {
    label: 'Wholesale Bank Liquidity',
    title: 'Regional Bank Liquidity Run Triggers Emergency Discount Window Borrowing and Deposit Flights',
    content: 'Uninsured corporate deposit outflows pressured capital ratios, forcing asset fire sales.',
  },
  {
    label: 'Earnings Surge',
    title: 'NVIDIA Reports Record Q4 Revenue Surging 265% on Data Center AI Accelerator Demand',
    content: 'Enterprise demand for Hopper GPUs propelled revenue to $22.1 billion, crushing consensus estimates.',
  },
];

export const TextAnalysisCard: React.FC<TextAnalysisCardProps> = ({ onSignalCreated }) => {
  const [title, setTitle] = useState('');
  const [content, setContent] = useState('');
  const [saveToDb, setSaveToDb] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<TextAnalysisResponse | null>(null);

  const handleSelectSample = (sample: typeof SAMPLE_HEADLINES[0]) => {
    setTitle(sample.title);
    setContent(sample.content);
    setError(null);
  };

  const handleAnalyze = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) {
      setError('Please provide a financial headline or article title.');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const res = await signalsService.analyzeText({
        title: title.trim(),
        content: content.trim() || undefined,
        save_to_db: saveToDb,
        source: 'interactive_analyzer',
      });
      setResult(res);
      if (saveToDb && onSignalCreated) {
        onSignalCreated();
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Text analysis request failed.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div className="card-header" style={{ marginBottom: '1rem' }}>
        <div>
          <div className="card-title" style={{ display: 'flex', alignItems: 'center', gap: '0.45rem' }}>
            <Sparkles size={16} color="var(--accent-primary)" />
            <span>Interactive NLP Risk Analyzer</span>
          </div>
          <div className="card-subtitle">
            Evaluate text through FinBERT financial sentiment, event categorization, and impact scoring
          </div>
        </div>
        {result && (
          <span className="badge badge-green">
            <CheckCircle2 size={12} /> {result.processing_status}
          </span>
        )}
      </div>

      {/* Preset sample buttons */}
      <div style={{ marginBottom: '1rem' }}>
        <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.4rem' }}>
          Test with standard event presets:
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.35rem' }}>
          {SAMPLE_HEADLINES.map((s) => (
            <button
              key={s.label}
              onClick={() => handleSelectSample(s)}
              className="btn btn-outline"
              style={{ fontSize: '0.7rem', padding: '0.2rem 0.5rem' }}
              type="button"
            >
              {s.label}
            </button>
          ))}
        </div>
      </div>

      {/* Input form */}
      <form onSubmit={handleAnalyze} style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
        <div className="form-group" style={{ marginBottom: 0 }}>
          <label className="form-label" htmlFor="nlp-headline">
            Headline / Event Description <span style={{ color: 'var(--accent-rose)' }}>*</span>
          </label>
          <input
            id="nlp-headline"
            type="text"
            className="form-input"
            placeholder="e.g. FTC launches antitrust inquiry into Big Tech cloud partnerships..."
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            disabled={loading}
          />
        </div>

        <div className="form-group" style={{ marginBottom: 0 }}>
          <label className="form-label" htmlFor="nlp-content">
            Article Body / Context Snippet <span style={{ color: 'var(--text-muted)', fontWeight: 400 }}>(Optional)</span>
          </label>
          <textarea
            id="nlp-content"
            className="form-textarea"
            rows={2}
            placeholder="Provide surrounding article sentences to improve entity resolution and impact evidence..."
            value={content}
            onChange={(e) => setContent(e.target.value)}
            disabled={loading}
          />
        </div>

        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: '0.25rem' }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
            <input
              type="checkbox"
              className="form-checkbox"
              checked={saveToDb}
              onChange={(e) => setSaveToDb(e.target.checked)}
              disabled={loading}
            />
            <span>Persist to Database (creates Article & Signal records)</span>
          </label>

          <button
            type="submit"
            disabled={loading || !title.trim()}
            className="btn btn-primary"
            style={{ fontSize: '0.8rem', padding: '0.45rem 1rem' }}
          >
            {loading ? <Loader2 size={14} className="spin" /> : <Send size={14} />}
            <span>{loading ? 'Analyzing...' : 'Run Analysis'}</span>
          </button>
        </div>
      </form>

      {/* Error alert */}
      {error && (
        <div
          style={{
            marginTop: '1rem',
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

      {/* Analysis Results Display */}
      {result && (
        <div
          style={{
            marginTop: '1.25rem',
            padding: '1.15rem',
            backgroundColor: 'rgba(255, 255, 255, 0.02)',
            border: '1px solid var(--border-default)',
            borderRadius: 'var(--radius-md)',
            display: 'flex',
            flexDirection: 'column',
            gap: '0.85rem',
          }}
        >
          {/* Header row: Event category & Sentiment */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.5rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Category:</span>
              <Badge variant="blue">{result.signal.event_category.replace(/_/g, ' ')}</Badge>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                ({(result.signal.event_confidence * 100).toFixed(0)}% conf)
              </span>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                {result.signal.inference_mode === 'neural_live' ? 'FinBERT:' : 'Lexicon:'}
              </span>
              <SentimentBadge
                sentimentLabel={result.signal.sentiment_label}
                sentimentScore={result.signal.sentiment_score}
                inferenceMode={result.signal.inference_mode}
              />
            </div>
          </div>

          {/* Probability distribution if returned */}
          {result.signal.sentiment_probabilities && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.3rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                <span>Class Probabilities:</span>
                <span>
                  Pos: {((result.signal.sentiment_probabilities.positive || 0) * 100).toFixed(1)}% •
                  Neu: {((result.signal.sentiment_probabilities.neutral || 0) * 100).toFixed(1)}% •
                  Neg: {((result.signal.sentiment_probabilities.negative || 0) * 100).toFixed(1)}%
                </span>
              </div>
              <div style={{ height: '6px', borderRadius: '3px', display: 'flex', overflow: 'hidden', backgroundColor: 'var(--bg-surface)' }}>
                <div style={{ width: `${(result.signal.sentiment_probabilities.positive || 0) * 100}%`, backgroundColor: 'var(--accent-emerald)' }} title="Positive" />
                <div style={{ width: `${(result.signal.sentiment_probabilities.neutral || 0) * 100}%`, backgroundColor: '#64748b' }} title="Neutral" />
                <div style={{ width: `${(result.signal.sentiment_probabilities.negative || 0) * 100}%`, backgroundColor: 'var(--accent-rose)' }} title="Negative" />
              </div>
            </div>
          )}

          {/* Impact Score and Rationale */}
          <div
            style={{
              padding: '0.75rem',
              backgroundColor: 'rgba(255, 255, 255, 0.02)',
              borderRadius: 'var(--radius-sm)',
              border: '1px solid var(--border-subtle)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.35rem' }}>
              <span style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-secondary)' }}>Impact Calibration:</span>
              <ImpactBadge impactScore={result.signal.impact_score} />
            </div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', lineHeight: 1.4 }}>
              {result.signal.impact_rationale}
            </div>
          </div>

          {/* Resolved Entities */}
          <div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.35rem', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <Tag size={12} />
              <span>Resolved Market Entities:</span>
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.35rem' }}>
              {result.signal.affected_entities && result.signal.affected_entities.length > 0 ? (
                result.signal.affected_entities.map((ent) => (
                  <Badge
                    key={ent.ticker}
                    variant={ent.is_primary_target ? 'amber' : 'neutral'}
                    title={`${ent.name} • ${ent.sector} (Relevance: ${(ent.relevance_score * 100).toFixed(0)}%)`}
                  >
                    {ent.ticker}: {ent.name} {ent.is_primary_target && '★'}
                  </Badge>
                ))
              ) : (
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                  No single entity identified (Systemic / Macro factor scope)
                </span>
              )}
            </div>
          </div>

          {/* Model Provenance & Execution Telemetry */}
          <div
            style={{
              borderTop: '1px solid var(--border-subtle)',
              paddingTop: '0.5rem',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              fontSize: '0.7rem',
              color: 'var(--text-muted)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: '3px' }}>
                <Cpu size={12} /> Mode: <strong style={{ color: 'var(--text-secondary)' }}>{result.signal.inference_mode}</strong>
              </span>
              <span>Model: <strong style={{ color: 'var(--text-secondary)' }}>{result.signal.model_version}</strong></span>
            </div>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: '3px' }}>
              <Clock size={12} /> {result.execution_time_ms.toFixed(1)}ms
            </span>
          </div>

          {saveToDb && result.signal.id && (
            <div style={{ fontSize: '0.7rem', color: 'var(--accent-emerald)', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <BookmarkCheck size={12} /> Persisted as Signal ID: <span className="mono">{result.signal.id}</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
