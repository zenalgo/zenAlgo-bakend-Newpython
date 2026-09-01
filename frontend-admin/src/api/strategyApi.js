import axiosClient from './axiosClient';

export const strategyApi = {
  getStrategies: (params) =>
    axiosClient.get('/admin/strategies', { params }),

  getStrategyById: (id) =>
    axiosClient.get(`/strategies/${id}`),

  createStrategy: (payload) =>
    axiosClient.post('/admin/strategies', payload),

  validateStrategy: (payload) =>
    axiosClient.post('/strategies/validate', payload),

  activatePaper: (id) =>
    axiosClient.post(`/admin/strategies/${id}/activate-paper`),

  activateLive: (id) =>
    axiosClient.post(`/admin/strategies/${id}/activate-live`),

  squareOff: (id) =>
    axiosClient.post(`/strategies/${id}/squareoff`),

  parseRule: (text, defaultTimeframe, ruleType) =>
    axiosClient.post('/strategy/rules/parse', { text, defaultTimeframe, ruleType }),
};
