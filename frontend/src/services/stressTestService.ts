import { apiClient } from './apiClient';
import type {
  StressScenarioDefinition,
  StressTestSimulationRequest,
  StressTestSimulationResponse,
  StressTestRunRead
} from '../types/api';

export const stressTestService = {
  listScenarios: async (): Promise<StressScenarioDefinition[]> => {
    return apiClient.get<StressScenarioDefinition[]>('/api/v1/stress-test/scenarios');
  },

  simulate: async (req: StressTestSimulationRequest): Promise<StressTestSimulationResponse> => {
    return apiClient.post<StressTestSimulationResponse>('/api/v1/stress-test/simulate', req);
  },

  listRuns: async (): Promise<StressTestRunRead[]> => {
    return apiClient.get<StressTestRunRead[]>('/api/v1/stress-test/runs');
  },

  getRun: async (runId: string): Promise<StressTestRunRead> => {
    return apiClient.get<StressTestRunRead>(`/api/v1/stress-test/runs/${runId}`);
  },
};
