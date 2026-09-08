import axiosClient from './axiosClient';

export const calcEngineApi = {
  startEngine: async (data) => {
    return axiosClient.post('/calc-engine/start', data);
  },

  stopEngine: async (symbol) => {
    return axiosClient.post(`/calc-engine/stop/${symbol}`);
  },

  getSnapshot: async (symbol, timeframe = '5m') => {
    return axiosClient.get(`/calc-engine/snapshot/${symbol}`, {
      params: { timeframe },
    });
  },

  getStatuses: async () => {
    return axiosClient.get('/calc-engine/status');
  },

  getSignals: async (symbol = null) => {
    const url = symbol ? `/calc-engine/signals/${symbol}` : '/calc-engine/signals';
    return axiosClient.get(url);
  },

  getConditions: async (symbol) => {
    return axiosClient.get(`/calc-engine/conditions/${symbol}`);
  },
};
