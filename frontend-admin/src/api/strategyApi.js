import axiosClient from './axiosClient';

export const strategyApi = {
  // Strategy Management
  getStrategies: () =>
    axiosClient.get('/admin/strategies'),

  getStrategyById: (id) =>
    axiosClient.get(`/admin/strategies/${id}`),

  createStrategy: (payload) =>
    axiosClient.post('/admin/strategies', payload),

  updateStrategy: (id, payload) =>
    axiosClient.put(`/admin/strategies/${id}`, payload),

  deleteStrategy: (id) =>
    axiosClient.delete(`/strategies/${id}`),

  // Strategy Builder Utilities
  validateStrategy: (payload) =>
    axiosClient.post('/strategies/validate', payload),

  previewStrategy: (payload) =>
    axiosClient.post('/strategies/preview', payload),

  generateStrategyAI: (prompt) =>
    axiosClient.post('/strategies/generate', { prompt }),

  // Activation & Lifecycle
  activatePaper: (id) =>
    axiosClient.post(`/admin/strategies/${id}/activate-paper`),

  activateLive: (id) =>
    axiosClient.post(`/admin/strategies/${id}/activate-live`),

  squareOff: (id) =>
    axiosClient.post(`/strategies/${id}/squareoff`),
};
