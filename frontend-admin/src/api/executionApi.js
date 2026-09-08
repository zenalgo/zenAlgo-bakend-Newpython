import axiosClient from './axiosClient';

export const executionApi = {
  getStrategyBatches: (strategyId, params) =>
    axiosClient.get(`/admin/execution/strategies/${strategyId}/batches`, { params }),

  getBatchDetails: (batchId) =>
    axiosClient.get(`/admin/execution/batches/${batchId}`),

  getBatchTraces: (batchId, params) =>
    axiosClient.get(`/admin/execution/batches/${batchId}/traces`, { params }),

  getBatchFailures: (batchId) =>
    axiosClient.get(`/admin/execution/batches/${batchId}/failures`),

  getTraceDetails: (traceId) =>
    axiosClient.get(`/admin/execution/traces/${traceId}`),

  getUserTraces: (userId, strategyId) =>
    axiosClient.get(`/admin/execution/users/${userId}/traces`, {
      params: { strategy_id: strategyId },
    }),

  getPlacedOrders: (strategyId, params) =>
    axiosClient.get(`/admin/execution/strategies/${strategyId}/placed-orders`, { params }),

  simulateExecution: (strategyId) =>
    axiosClient.post(`/admin/execution/strategies/${strategyId}/simulate-execution`),

  // --- Execution Logs (All Strategies) ---
  getAllExecutionLogs: (params) =>
    axiosClient.get('/admin/execution/logs', { params }),
};

// --- Connected Broker Users ---
export const brokerConnectionsApi = {
  getStats: () =>
    axiosClient.get('/admin/broker-connections/stats'),

  listConnectedUsers: (params) =>
    axiosClient.get('/admin/broker-connections', { params }),
};

// --- Reports ---
export const reportsApi = {
  getSummary: (days) =>
    axiosClient.get('/admin/reports/summary', { params: { days } }),

  getExecutionSummary: (days) =>
    axiosClient.get('/admin/reports/execution-summary', { params: { days } }),

  getDailyActivity: (days) =>
    axiosClient.get('/admin/reports/daily', { params: { days } }),

  getUserPerformance: (days, params) =>
    axiosClient.get('/admin/reports/user-performance', { params: { days, ...params } }),
};
