import { apiClient } from './apiClient';
import type { HealthResponse } from '../types/api';

export const healthService = {
  getHealth: async (timeoutMs = 60000): Promise<HealthResponse> => {
    return apiClient.get<HealthResponse>('/health', { timeoutMs });
  },
};
