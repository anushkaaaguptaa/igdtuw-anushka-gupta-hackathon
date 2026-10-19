import React, { useState, useEffect, useCallback } from 'react';
import {
  Newspaper,
  Globe,
  Rss,
  History,
  ExternalLink,
  ChevronDown,
  ChevronUp,
  Search,
  RefreshCw,
  Plus,
  FileText,
  Sliders
} from 'lucide-react';
import { Badge, SentimentBadge, ImpactBadge, ProvenanceBadge } from '../common/Badge';
import { LoadingSpinner, ErrorBanner, EmptyState } from '../common/StateViews';
import { TextAnalysisCard } from './TextAnalysisCard';
import { IngestionModal } from './IngestionModal';
import { signalsService } from '../../services/signalsService';
import { ingestionService } from '../../services/ingestionService';
import type {
  RiskSignalRead,
  IngestStatusResponse,
  ArticleRead
} from '../../types/api';

interface IntelligenceFeedProps {
  onTriggerStressForSignal?: (signal: RiskSignalRead) => void;
}

export const IntelligenceFeed: React.FC<IntelligenceFeedProps> = ({ onTriggerStressForSignal }) => {
  const [signals, setSignals] = useState<RiskSignalRead[]>([]);
  const [articles, setArticles] = useState<ArticleRead[]>([]);
  const [ingestStatus, setIngestStatus] = useState<IngestStatusResponse | null>(null);

  const [activeView, setActiveView] = useState<'signals' | 'articles'>('signals');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [expandedSignalId, setExpandedSignalId] = useState<string | null>(null);

  // Filters
  const [searchQuery, setSearchQuery] = useState('');
  const [minImpact, setMinImpact] = useState<number | undefined>(undefined);
  const [selectedCategory, setSelectedCategory] = useState<string>('');
  const [tickerFilter, setTickerFilter] = useState<string>('');
  const [modeFilter, setModeFilter] = useState<string>('');

  const [actionLoading, setActionLoading] = useState(false);

  const loadFeedData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [sigRes, artRes, statusRes] = await Promise.all([
        signalsService.listSignals({
          limit: 50,
          min_impact: minImpact,
          category: selectedCategory || undefined,
          ticker: tickerFilter.trim() || undefined,
          inference_mode: modeFilter || undefined,
        }),
        ingestionService.listArticles({ limit: 50 }),
        ingestionService.getStatus(),
      ]);

      setSignals(sigRes.items);
      setArticles(artRes.items);
      setIngestStatus(statusRes);
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to retrieve financial intelligence feed.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [minImpact, selectedCategory, tickerFilter, modeFilter]);

  useEffect(() => {
    let isMounted = true;
    (async () => {
      try {
        const [sigRes, artRes, statusRes] = await Promise.all([
          signalsService.listSignals({ limit: 50 }),
          ingestionService.listArticles({ limit: 50 }),
          ingestionService.getStatus(),
        ]);
        if (!isMounted) return;
        setSignals(sigRes.items);
        setArticles(artRes.items);
        setIngestStatus(statusRes);
      } catch (err) {
        if (!isMounted) return;
        const msg = err instanceof Error ? err.message : 'Failed to retrieve financial intelligence feed.';
        setError(msg);
      } finally {
        if (isMounted) setLoading(false);
      }
    })();

    return () => {
      isMounted = false;
    };
  }, []);

  const handleQuickReplay = async () => {
    setActionLoading(true);
    try {
      await ingestionService.triggerIngestion({
        mode: 'replay',
        sources: ['replay_fixture'],
        limit_per_source: 10,
        run_nlp: true,
      });
      await loadFeedData();
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to execute quick replay.';
      setError(msg);
    } finally {
      setActionLoading(false);
    }
  };

  // Client-side text search on title or evidence
  const filteredSignals = signals.filter((s) => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    const titleMatch = s.article?.title?.toLowerCase().includes(q) || false;
    const rationaleMatch = s.impact_rationale?.toLowerCase().includes(q) || false;
    const evidenceMatch = s.evidence?.toLowerCase().includes(q) || false;
    const entityMatch = s.affected_entities?.some((e) => e.ticker.toLowerCase().includes(q) || e.name.toLowerCase().includes(q)) || false;
    return titleMatch || rationaleMatch || evidenceMatch || entityMatch;
  });

  const filteredArticles = articles.filter((a) => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    return a.title.toLowerCase().includes(q) || a.raw_content.toLowerCase().includes(q);
  });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Top Header & Telemetry Bar */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h2>Financial Intelligence Feed & Ingestion Telemetry</h2>
          <p style={{ fontSize: '0.825rem', marginTop: '2px' }}>
            Multi-source financial news ingestion, FinBERT continuous sentiment analysis, and deterministic event classification.
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
          <button
            onClick={loadFeedData}
            disabled={loading}
            className="btn btn-outline"
            style={{ fontSize: '0.8rem', padding: '0.45rem 0.75rem' }}
            title="Refresh feeds"
            type="button"
          >
            <RefreshCw size={14} className={loading ? 'spin' : ''} />
            <span>Sync</span>
          </button>

          <button
            onClick={handleQuickReplay}
            disabled={actionLoading}
            className="btn btn-secondary"
            style={{ fontSize: '0.8rem' }}
            type="button"
          >
            <History size={14} />
            <span>Quick Crisis Replay</span>
          </button>

          <button
            onClick={() => setIsModalOpen(true)}
            className="btn btn-primary"
            style={{ fontSize: '0.8rem' }}
            type="button"
          >
            <Plus size={14} />
            <span>Trigger Ingestion Batch</span>
          </button>
        </div>
      </div>

      {/* Error banner */}
      {error && (
        <ErrorBanner
          title="Intelligence Feed Error"
          message={error}
          onRetry={loadFeedData}
        />
      )}

      {/* Ingestion Source Health Status Telemetry Grid */}
      <div className="grid-cols-4">
        {/* Source 1: GDELT */}
        <div className="card" style={{ padding: '1rem' }}>
          <div className="card-header" style={{ marginBottom: '0.35rem' }}>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <Globe size={13} color="var(--accent-primary)" /> GDELT 2.0 Doc API
            </span>
            <span className="badge badge-blue">
              {ingestStatus?.sources.find((s) => s.source === 'gdelt')?.status || 'Initialized'}
            </span>
          </div>
          <div style={{ fontSize: '1.2rem', fontWeight: 700 }} className="tabular-nums">
            {ingestStatus?.sources.find((s) => s.source === 'gdelt')?.articles_fetched_count || 0}
            <span style={{ fontSize: '0.75rem', fontWeight: 400, color: 'var(--text-muted)', marginLeft: '4px' }}>articles</span>
          </div>
          <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '2px' }}>
            Global geopolitical & macro events
          </div>
        </div>

        {/* Source 2: Financial RSS */}
        <div className="card" style={{ padding: '1rem' }}>
          <div className="card-header" style={{ marginBottom: '0.35rem' }}>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <Rss size={13} color="var(--accent-amber)" /> Financial RSS
            </span>
            <span className="badge badge-amber">
              {ingestStatus?.sources.find((s) => s.source === 'financial_rss')?.status || 'Initialized'}
            </span>
          </div>
          <div style={{ fontSize: '1.2rem', fontWeight: 700 }} className="tabular-nums">
            {ingestStatus?.sources.find((s) => s.source === 'financial_rss')?.articles_fetched_count || 0}
            <span style={{ fontSize: '0.75rem', fontWeight: 400, color: 'var(--text-muted)', marginLeft: '4px' }}>articles</span>
          </div>
          <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '2px' }}>
            Dow Jones & Yahoo Finance headlines
          </div>
        </div>

        {/* Source 3: Replay Fixture */}
        <div className="card" style={{ padding: '1rem' }}>
          <div className="card-header" style={{ marginBottom: '0.35rem' }}>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <History size={13} color="var(--accent-purple)" /> Replay Dataset
            </span>
            <span className="badge badge-purple">
              {ingestStatus?.sources.find((s) => s.source === 'replay_fixture')?.status || 'Ready'}
            </span>
          </div>
          <div style={{ fontSize: '1.2rem', fontWeight: 700 }} className="tabular-nums">
            Curated
          </div>
          <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '2px' }}>
            SVB, Credit Suisse & rate shock testbed
          </div>
        </div>

        {/* Total Persisted */}
        <div className="card" style={{ padding: '1rem' }}>
          <div className="card-header" style={{ marginBottom: '0.35rem' }}>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <FileText size={13} color="var(--accent-emerald)" /> Persisted Records
            </span>
            <span className="badge badge-green">SQLite</span>
          </div>
          <div style={{ fontSize: '1.2rem', fontWeight: 700 }} className="tabular-nums">
            {ingestStatus?.total_signals_stored || signals.length}
            <span style={{ fontSize: '0.75rem', fontWeight: 400, color: 'var(--text-muted)', marginLeft: '4px' }}>signals</span>
          </div>
          <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '2px' }}>
            {ingestStatus?.total_articles_stored || articles.length} raw articles stored
          </div>
        </div>
      </div>

      {/* Main Two-Column Layout: Left Feed (60%), Right NLP Analyzer (40%) */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.5fr 1fr', gap: '1.5rem', alignItems: 'start' }}>
        {/* Left Column: Feed & Filter Bar */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {/* Feed Filter & View Selector Card */}
          <div className="card" style={{ padding: '1rem' }}>
            {/* View Mode Toggle & Search */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.75rem', flexWrap: 'wrap', marginBottom: '0.85rem' }}>
              <div style={{ display: 'flex', gap: '0.25rem', backgroundColor: 'rgba(255, 255, 255, 0.03)', padding: '2px', borderRadius: 'var(--radius-sm)' }}>
                <button
                  type="button"
                  onClick={() => setActiveView('signals')}
                  className={`btn ${activeView === 'signals' ? 'btn-secondary' : 'btn-outline'}`}
                  style={{ fontSize: '0.75rem', padding: '0.3rem 0.65rem' }}
                >
                  <Newspaper size={13} />
                  <span>Risk Signals ({filteredSignals.length})</span>
                </button>
                <button
                  type="button"
                  onClick={() => setActiveView('articles')}
                  className={`btn ${activeView === 'articles' ? 'btn-secondary' : 'btn-outline'}`}
                  style={{ fontSize: '0.75rem', padding: '0.3rem 0.65rem' }}
                >
                  <FileText size={13} />
                  <span>Raw Articles ({filteredArticles.length})</span>
                </button>
              </div>

              {/* Text search */}
              <div style={{ position: 'relative', width: '220px' }}>
                <Search size={14} style={{ position: 'absolute', left: '8px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
                <input
                  type="text"
                  placeholder="Search headlines, tickers..."
                  className="form-input"
                  style={{ paddingLeft: '28px', fontSize: '0.8rem', height: '32px' }}
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
              </div>
            </div>

            {/* Server-Side Filter Selectors */}
            {activeView === 'signals' && (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '0.5rem', paddingTop: '0.75rem', borderTop: '1px solid var(--border-subtle)' }}>
                <div>
                  <label className="form-label" style={{ fontSize: '0.7rem' }}>Impact Severity</label>
                  <select
                    className="form-select"
                    style={{ fontSize: '0.75rem', padding: '0.35rem 0.6rem' }}
                    value={minImpact !== undefined ? String(minImpact) : ''}
                    onChange={(e) => {
                      const val = e.target.value ? parseInt(e.target.value) : undefined;
                      setMinImpact(val);
                    }}
                  >
                    <option value="">All Impact Scores</option>
                    <option value="8">High Impact (8-10)</option>
                    <option value="5">Medium+ Impact (5-10)</option>
                    <option value="1">All Scores (1-10)</option>
                  </select>
                </div>

                <div>
                  <label className="form-label" style={{ fontSize: '0.7rem' }}>Event Category</label>
                  <select
                    className="form-select"
                    style={{ fontSize: '0.75rem', padding: '0.35rem 0.6rem' }}
                    value={selectedCategory}
                    onChange={(e) => setSelectedCategory(e.target.value)}
                  >
                    <option value="">All Categories</option>
                    <option value="GEOPOLITICAL">Geopolitical</option>
                    <option value="MACROECONOMIC">Macroeconomic</option>
                    <option value="CREDIT_EVENT">Credit Event / Default</option>
                    <option value="REGULATORY_ACTION">Regulatory Action</option>
                    <option value="EARNINGS_FINANCIAL_RESULTS">Earnings & Results</option>
                  </select>
                </div>

                <div>
                  <label className="form-label" style={{ fontSize: '0.7rem' }}>Target Ticker</label>
                  <input
                    type="text"
                    placeholder="e.g. NVDA, MSFT"
                    className="form-input"
                    style={{ fontSize: '0.75rem', padding: '0.35rem 0.6rem' }}
                    value={tickerFilter}
                    onChange={(e) => setTickerFilter(e.target.value)}
                    onBlur={loadFeedData}
                  />
                </div>

                <div>
                  <label className="form-label" style={{ fontSize: '0.7rem' }}>Inference Mode</label>
                  <select
                    className="form-select"
                    style={{ fontSize: '0.75rem', padding: '0.35rem 0.6rem' }}
                    value={modeFilter}
                    onChange={(e) => setModeFilter(e.target.value)}
                  >
                    <option value="">All Modes</option>
                    <option value="neural_live">Live FinBERT</option>
                    <option value="synthetic">Replay / Synthetic</option>
                    <option value="mock">Keyword Mock</option>
                  </select>
                </div>
              </div>
            )}
          </div>

          {/* List of Risk Signals */}
          {activeView === 'signals' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
              {loading && signals.length === 0 ? (
                <LoadingSpinner message="Querying risk signals..." />
              ) : filteredSignals.length === 0 ? (
                <EmptyState
                  icon={<Newspaper size={32} color="var(--text-muted)" />}
                  title="No Risk Signals Match Filters"
                  description="Adjust your search criteria or trigger an ingestion run to generate new risk signals."
                  actionLabel="Replay Crisis Fixtures"
                  onAction={handleQuickReplay}
                  actionLoading={actionLoading}
                />
              ) : (
                filteredSignals.map((sig) => {
                  const isExpanded = expandedSignalId === sig.id;
                  return (
                    <div
                      key={sig.id}
                      className="card"
                      style={{
                        padding: '1.15rem',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '0.75rem',
                      }}
                    >
                      {/* Top metadata row: Category, Provenance, Timestamp */}
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.5rem' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem' }}>
                          <Badge variant="blue">
                            {sig.event_category.replace(/_/g, ' ')}
                          </Badge>
                          <ProvenanceBadge
                            source={sig.article?.source}
                            inferenceMode={sig.inference_mode}
                          />
                        </div>

                        <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                          {new Date(sig.created_at).toLocaleDateString()}{' '}
                          {new Date(sig.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </div>
                      </div>

                      {/* Title & External Link */}
                      <div>
                        <div style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--text-primary)', lineHeight: 1.35 }}>
                          {sig.article?.title || sig.impact_rationale || sig.id}
                        </div>
                        {sig.article?.url && (
                          <div style={{ marginTop: '4px' }}>
                            <a
                              href={sig.article.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              style={{
                                fontSize: '0.75rem',
                                color: 'var(--accent-primary)',
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: '3px',
                                textDecoration: 'none',
                              }}
                            >
                              <span>{sig.article.publisher || sig.article.source}</span>
                              <ExternalLink size={10} />
                            </a>
                          </div>
                        )}
                      </div>

                      {/* Metrics bar: FinBERT Sentiment + Impact Score + Entity Pills */}
                      <div
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          flexWrap: 'wrap',
                          gap: '0.65rem',
                          padding: '0.65rem 0.85rem',
                          backgroundColor: 'rgba(255, 255, 255, 0.02)',
                          borderRadius: 'var(--radius-md)',
                          border: '1px solid var(--border-subtle)',
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                            <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Sentiment:</span>
                            <SentimentBadge
                              sentimentLabel={sig.sentiment_label}
                              sentimentScore={sig.sentiment_score}
                              inferenceMode={sig.inference_mode}
                            />
                          </div>

                          <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                            <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Impact:</span>
                            <ImpactBadge impactScore={sig.impact_score} />
                          </div>
                        </div>

                        {/* Affected Entities */}
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', flexWrap: 'wrap' }}>
                          {sig.affected_entities && sig.affected_entities.length > 0 ? (
                            sig.affected_entities.map((e) => (
                              <Badge key={e.ticker} variant={e.is_primary_target ? 'amber' : 'neutral'} title={`${e.name} (${e.sector})`}>
                                {e.ticker} {e.is_primary_target && '★'}
                              </Badge>
                            ))
                          ) : (
                            <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>Macro / Market</span>
                          )}
                        </div>
                      </div>

                      {/* Expandable detail toggle & Stress Test Button */}
                      <div>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.5rem' }}>
                          <button
                            type="button"
                            onClick={() => setExpandedSignalId(isExpanded ? null : sig.id)}
                            style={{
                              background: 'transparent',
                              border: 'none',
                              color: 'var(--text-muted)',
                              cursor: 'pointer',
                              fontSize: '0.75rem',
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '4px',
                              padding: '2px 0',
                            }}
                          >
                            <span>{isExpanded ? 'Collapse Analysis Details' : 'View Impact Rationale & Evidence'}</span>
                            {isExpanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                          </button>

                          {onTriggerStressForSignal && (
                            <button
                              type="button"
                              onClick={() => onTriggerStressForSignal(sig)}
                              className="btn btn-outline"
                              style={{ fontSize: '0.7rem', padding: '0.2rem 0.5rem', gap: '4px' }}
                              title="Simulate automated factor transmission for this signal in Stress Testing Workspace"
                            >
                              <Sliders size={12} color="var(--accent-primary)" />
                              <span>Stress Test Signal</span>
                            </button>
                          )}
                        </div>

                        {isExpanded && (
                          <div
                            style={{
                              marginTop: '0.65rem',
                              padding: '0.85rem',
                              backgroundColor: 'rgba(0, 0, 0, 0.25)',
                              borderRadius: 'var(--radius-sm)',
                              border: '1px solid var(--border-subtle)',
                              display: 'flex',
                              flexDirection: 'column',
                              gap: '0.5rem',
                              fontSize: '0.8rem',
                            }}
                          >
                            <div>
                              <strong style={{ color: 'var(--text-secondary)', fontSize: '0.75rem' }}>Impact Rationale:</strong>
                              <div style={{ color: 'var(--text-primary)', marginTop: '2px' }}>{sig.impact_rationale}</div>
                            </div>

                            {sig.evidence && (
                              <div>
                                <strong style={{ color: 'var(--text-secondary)', fontSize: '0.75rem' }}>Key Evidence Snippet:</strong>
                                <div style={{ color: 'var(--text-muted)', fontStyle: 'italic', marginTop: '2px' }}>
                                  "{sig.evidence}"
                                </div>
                              </div>
                            )}

                            {sig.sentiment_probabilities && (
                              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                                <strong>
                                  {sig.inference_mode === 'neural_live'
                                    ? 'FinBERT Class Probabilities:'
                                    : sig.inference_mode === 'lexicon_fallback'
                                    ? 'Lexicon Probabilities:'
                                    : 'Model Probabilities:'}
                                </strong>{' '}
                                Pos: {((sig.sentiment_probabilities.positive || 0) * 100).toFixed(1)}% •
                                Neu: {((sig.sentiment_probabilities.neutral || 0) * 100).toFixed(1)}% •
                                Neg: {((sig.sentiment_probabilities.negative || 0) * 100).toFixed(1)}%
                              </div>
                            )}

                            {sig.article?.raw_content && (
                              <div>
                                <strong style={{ color: 'var(--text-secondary)', fontSize: '0.75rem' }}>Raw Content Excerpt:</strong>
                                <div style={{ color: 'var(--text-muted)', fontSize: '0.75rem', marginTop: '2px', lineHeight: 1.4 }}>
                                  {sig.article.raw_content.slice(0, 320)}...
                                </div>
                              </div>
                            )}

                            <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', borderTop: '1px solid var(--border-subtle)', paddingTop: '0.35rem' }}>
                              Signal ID: <span className="mono">{sig.id}</span> • Article ID: <span className="mono">{sig.article_id}</span> • Model: {sig.model_version}
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          )}

          {/* List of Raw Ingested Articles */}
          {activeView === 'articles' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
              {filteredArticles.length === 0 ? (
                <EmptyState
                  icon={<FileText size={32} color="var(--text-muted)" />}
                  title="No Ingested Articles Found"
                  description="Run an ingestion batch to fetch articles from live RSS, GDELT, or curated crisis replay fixtures."
                  actionLabel="Trigger Ingestion"
                  onAction={() => setIsModalOpen(true)}
                />
              ) : (
                filteredArticles.map((art) => (
                  <div key={art.id} className="card" style={{ padding: '1rem', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.5rem' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem' }}>
                        <Badge variant={art.source === 'gdelt' ? 'blue' : art.source === 'financial_rss' ? 'amber' : 'purple'}>
                          {art.source}
                        </Badge>
                        <span className="badge badge-green">{art.ingestion_status}</span>
                      </div>
                      <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                        {new Date(art.published_at).toLocaleDateString()}
                      </span>
                    </div>

                    <div style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                      {art.title}
                    </div>

                    <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', lineHeight: 1.4 }}>
                      {art.raw_content.slice(0, 240)}...
                    </div>

                    {art.url && (
                      <div style={{ marginTop: '2px' }}>
                        <a
                          href={art.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          style={{
                            fontSize: '0.75rem',
                            color: 'var(--accent-primary)',
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '3px',
                            textDecoration: 'none',
                          }}
                        >
                          <span>Original Publisher: {art.publisher || art.url}</span>
                          <ExternalLink size={10} />
                        </a>
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>
          )}
        </div>

        {/* Right Column: Interactive NLP Analyzer */}
        <div style={{ position: 'sticky', top: '80px' }}>
          <TextAnalysisCard onSignalCreated={loadFeedData} />
        </div>
      </div>

      {/* Ingestion Batch Execution Modal */}
      <IngestionModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onIngestComplete={loadFeedData}
      />
    </div>
  );
};
