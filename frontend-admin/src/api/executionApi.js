import axiosClient from './axiosClient';

export const executionApi = {
  // Batch Execution Tracking
  getStrategyBatches: (strategyId, date) =>
    axiosClient.get(`/admin/execution/strategies/${strategyId}/batches`, {
      params: { trading_date: date },
    }),

  getBatchDetails: (batchId) =>
    axiosClient.get(`/admin/execution/batches/${batchId}`),

  getBatchTraces: (batchId, status) =>
    axiosClient.get(`/admin/execution/batches/${batchId}/traces`, {
      params: { status },
    }),

  getBatchFailures: (batchId) =>
    axiosClient.get(`/admin/execution/batches/${batchId}/failures`),

  // User Trace & Timeline Stepper
  getTraceDetails: (traceId) =>
    axiosClient.get(`/admin/execution/traces/${traceId}`),

  getUserTraces: (userId, strategyId) =>
    axiosClient.get(`/admin/execution/users/${userId}/traces`, {
      params: { strategy_id: strategyId },
    }),

  // Placed Orders & Open Positions
  getPlacedOrders: (strategyId, status) =>
    axiosClient.get(`/admin/execution/strategies/${strategyId}/placed-orders`, {
      params: { status },
    }),
};
