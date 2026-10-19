import type { RiskSignalRead } from '../types/api';

export interface ScenarioMappingResult {
  scenarioId: string;
  scenarioName: string;
  mappingReason: string;
}

/**
 * Deterministically maps a RiskSignal to one of the 5 canonical stress scenarios,
 * mirroring backend/app/services/stress_testing/scenarios.py:map_signal_to_scenario.
 */
export function mapSignalToScenario(signal: RiskSignalRead): ScenarioMappingResult {
  const cat = signal.event_category?.toUpperCase() || '';
  const text = `${signal.impact_rationale || ''} ${signal.evidence || ''} ${signal.article?.title || ''}`.toLowerCase();

  if (cat === 'GEOPOLITICAL' || /\b(war|sanction|tariff|conflict|taiwan|military|missile|geopolitical)\b/.test(text)) {
    return {
      scenarioId: 'GEOPOLITICAL_ESCALATION',
      scenarioName: 'Geopolitical Escalation & Supply Chain Shock',
      mappingReason: 'Geopolitical event triggers flight to quality (Treasury yields decline) while supply disruption contracts margins.',
    };
  }

  if (cat === 'MACROECONOMIC') {
    if (/\b(rate|fed|hike|monetary|tightening|powell|cpi|inflation|yields)\b/.test(text)) {
      return {
        scenarioId: 'CENTRAL_BANK_RATE_HIKE',
        scenarioName: 'Central Bank Aggressive Monetary Tightening',
        mappingReason: 'Macroeconomic inflation or policy tightening triggers yield curve surge (+100 bps) and bond duration repricing.',
      };
    }
    return {
      scenarioId: 'MACROECONOMIC_RECESSION',
      scenarioName: 'Severe Macroeconomic Stagflation & Recession',
      mappingReason: 'Broad macroeconomic contraction triggers earnings recession and cyclical equity multiples compression.',
    };
  }

  if (cat === 'CREDIT_EVENT') {
    if (/\b(bank|liquidity|deposit|svb|run|contagion|interbank)\b/.test(text)) {
      return {
        scenarioId: 'BANKING_SECTOR_CRISIS',
        scenarioName: 'Wholesale Banking & Liquidity Run Crisis',
        mappingReason: 'Credit liquidity and banking distress triggers deposit outflow simulation and interbank spread blowout (+180 bps).',
      };
    }
    return {
      scenarioId: 'CREDIT_EVENT_OR_DEFAULT',
      scenarioName: 'Systemic Corporate Credit Event & Default',
      mappingReason: 'Corporate borrower credit event triggers corporate loan ECL surge (PD 3.5x) and bond spread blowout (+225 bps).',
    };
  }

  if (cat === 'REGULATORY_ACTION') {
    if (/\b(bank|capital|fdic|liquidity)\b/.test(text)) {
      return {
        scenarioId: 'BANKING_SECTOR_CRISIS',
        scenarioName: 'Wholesale Banking & Liquidity Run Crisis',
        mappingReason: 'Regulatory liquidity intervention triggers banking sector stress revaluation.',
      };
    }
    return {
      scenarioId: 'CREDIT_EVENT_OR_DEFAULT',
      scenarioName: 'Systemic Corporate Credit Event & Default',
      mappingReason: 'Regulatory enforcement or credit intervention triggers corporate credit haircut.',
    };
  }

  if (cat === 'EARNINGS_FINANCIAL_RESULTS') {
    return {
      scenarioId: 'MACROECONOMIC_RECESSION',
      scenarioName: 'Severe Macroeconomic Stagflation & Recession',
      mappingReason: 'Earnings deterioration triggers broader macroeconomic multiples contraction.',
    };
  }

  return {
    scenarioId: 'MACROECONOMIC_RECESSION',
    scenarioName: 'Severe Macroeconomic Stagflation & Recession',
    mappingReason: 'Fallback to canonical macroeconomic recession scenario.',
  };
}
