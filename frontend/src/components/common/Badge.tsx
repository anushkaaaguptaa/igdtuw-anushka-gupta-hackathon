import React from 'react';

export interface BadgeProps {
  children: React.ReactNode;
  variant?: 'blue' | 'green' | 'red' | 'amber' | 'cyan' | 'purple' | 'neutral';
  icon?: React.ReactNode;
  className?: string;
  title?: string;
}

export const Badge: React.FC<BadgeProps> = ({
  children,
  variant = 'blue',
  icon,
  className = '',
  title,
}) => {
  return (
    <span className={`badge badge-${variant} ${className}`} title={title}>
      {icon && <span style={{ display: 'inline-flex', alignItems: 'center' }}>{icon}</span>}
      <span>{children}</span>
    </span>
  );
};

export const SentimentBadge: React.FC<{
  sentimentLabel: string;
  sentimentScore?: number;
  inferenceMode?: string;
}> = ({ sentimentLabel, sentimentScore, inferenceMode }) => {
  const label = sentimentLabel.toLowerCase();
  let variant: 'green' | 'red' | 'neutral' = 'neutral';
  if (label === 'positive' || (sentimentScore !== undefined && sentimentScore > 0.15)) {
    variant = 'green';
  } else if (label === 'negative' || (sentimentScore !== undefined && sentimentScore < -0.15)) {
    variant = 'red';
  }

  const scoreText = sentimentScore !== undefined ? ` (${sentimentScore > 0 ? '+' : ''}${sentimentScore.toFixed(2)})` : '';
  const tooltipTitle =
    inferenceMode === 'lexicon_fallback'
      ? 'Loughran-McDonald financial sentiment lexicon score: bounded in [-1.0, +1.0]'
      : inferenceMode === 'synthetic'
      ? 'Synthetic replay scenario sentiment score: bounded in [-1.0, +1.0]'
      : 'FinBERT continuous score: P(positive) - P(negative) bounded in [-1.0, +1.0]';

  return (
    <Badge variant={variant} title={tooltipTitle}>
      {label.toUpperCase()}{scoreText}
    </Badge>
  );
};

export const ImpactBadge: React.FC<{ impactScore: number }> = ({ impactScore }) => {
  let variant: 'green' | 'amber' | 'red' = 'green';
  let severityLabel = 'Low';

  if (impactScore >= 8) {
    variant = 'red';
    severityLabel = 'High';
  } else if (impactScore >= 5) {
    variant = 'amber';
    severityLabel = 'Medium';
  }

  return (
    <Badge variant={variant} title={`Impact Severity Scale 1-10: ${impactScore}/10 (${severityLabel})`}>
      Impact: {impactScore}/10 • {severityLabel}
    </Badge>
  );
};

export const ProvenanceBadge: React.FC<{
  source?: string;
  inferenceMode?: string;
}> = ({ source, inferenceMode }) => {
  const isReplay = source === 'replay_fixture' || source === 'replay' || inferenceMode === 'synthetic';

  if (isReplay) {
    return (
      <Badge variant="purple" title="Historical curated replay fixture (deterministic testbed)">
        Synthetic Replay
      </Badge>
    );
  }

  if (inferenceMode === 'neural_live') {
    return (
      <Badge variant="cyan" title="FinBERT deep neural sequence classification executed live">
        Neural Live (FinBERT)
      </Badge>
    );
  }

  if (inferenceMode === 'lexicon_fallback') {
    return (
      <Badge variant="amber" title="Loughran-McDonald financial sentiment lexicon fallback executed offline">
        Lexicon Fallback
      </Badge>
    );
  }

  if (inferenceMode === 'mock') {
    return (
      <Badge variant="neutral" title="Heuristic keyword mock mode">
        Mock Mode
      </Badge>
    );
  }

  return (
    <Badge variant="neutral" title={`Data Source: ${source || 'External'}`}>
      {source || 'Live Ingest'}
    </Badge>
  );
};
