import { apiClient } from './apiClient';
import type {
  IngestTriggerRequest,
  IngestSummaryResponse,
  IngestStatusResponse,
  ArticleListResponse
} from '../types/api';

export interface ArticleFilterParams {
  limit?: number;
  offset?: number;
  source?: string;
  status?: string;
  search?: string;
}

export const ingestionService = {
  triggerIngestion: async (req: IngestTriggerRequest): Promise<IngestSummaryResponse> => {
    return apiClient.post<IngestSummaryResponse>('/api/v1/ingest/trigger', req);
  },

  getStatus: async (): Promise<IngestStatusResponse> => {
    return apiClient.get<IngestStatusResponse>('/api/v1/ingest/status');
  },

  listArticles: async (params: ArticleFilterParams = {}): Promise<ArticleListResponse> => {
    return apiClient.get<ArticleListResponse>('/api/v1/ingest/articles', {
      params: params as Record<string, string | number | undefined>,
    });
  },
};
