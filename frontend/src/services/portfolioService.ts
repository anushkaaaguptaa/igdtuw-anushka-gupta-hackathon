import { apiClient } from './apiClient';
import type {
  PortfolioRead,
  PortfolioExposureRead
} from '../types/api';

export const portfolioService = {
  listPortfolios: async (): Promise<PortfolioRead[]> => {
    return apiClient.get<PortfolioRead[]>('/api/v1/portfolios');
  },

  getPortfolio: async (portfolioId: string): Promise<PortfolioRead> => {
    return apiClient.get<PortfolioRead>(`/api/v1/portfolios/${portfolioId}`);
  },

  getExposure: async (portfolioId: string): Promise<PortfolioExposureRead> => {
    return apiClient.get<PortfolioExposureRead>(`/api/v1/portfolios/${portfolioId}/exposure`);
  },

  seedWholesalePortfolio: async (): Promise<PortfolioRead> => {
    return apiClient.post<PortfolioRead>('/api/v1/portfolios/sample/wholesale');
  },

  seedSamplePortfolio: async (): Promise<PortfolioRead> => {
    return apiClient.post<PortfolioRead>('/api/v1/portfolios/sample/seed');
  },
};
