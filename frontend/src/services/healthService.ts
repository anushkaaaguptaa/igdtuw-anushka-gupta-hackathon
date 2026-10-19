import { apiClient } from './apiClient';
import type { HealthResponse } from '../types/api';

export const healthService = {
  getHealth: async (): Promise<HealthResponse> => {
    return apiClient.get<HealthResponse>('/health');
  },
};
