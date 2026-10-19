import { apiClient } from './apiClient';
import type {
  SignalListResponse,
  RiskSignalRead,
  TextAnalysisRequest,
  TextAnalysisResponse
} from '../types/api';

export interface SignalFilterParams {
  limit?: number;
  offset?: number;
  min_impact?: number;
  max_impact?: number;
  category?: string;
  ticker?: string;
  inference_mode?: string;
}

export const signalsService = {
  listSignals: async (params: SignalFilterParams = {}): Promise<SignalListResponse> => {
    return apiClient.get<SignalListResponse>('/api/v1/signals', {
      params: params as Record<string, string | number | undefined>,
    });
  },

  getSignal: async (signalId: string): Promise<RiskSignalRead> => {
    return apiClient.get<RiskSignalRead>(`/api/v1/signals/${signalId}`);
  },

  analyzeText: async (req: TextAnalysisRequest): Promise<TextAnalysisResponse> => {
    return apiClient.post<TextAnalysisResponse>('/api/v1/signals/analyze', req);
  },
};
