import axiosClient from './axiosClient';

export const traderApi = {
  getStrategies: (params) =>
    axiosClient.get('/strategies', { params }),

  getPlacedOrders: (strategyId) =>
    axiosClient.get('/execution/placed-orders', { params: { strategyId } }),

  getMySubscription: () =>
    axiosClient.get('/user/subscriptions/current'),

  getPlans: () =>
    axiosClient.get('/user/subscriptions/plans'),

  getWallet: () =>
    axiosClient.get('/wallet'),

  getWalletTransactions: () =>
    axiosClient.get('/wallet/transactions'),

  depositMargin: (amount) =>
    axiosClient.post('/wallet/deposit', { amount, remarks: 'Client portal instant margin deposit' }),

  simulateExecution: (strategyId) =>
    axiosClient.post('/execution/simulate', { strategyId }),

  squareOffStrategy: (strategyId) =>
    axiosClient.post(`/strategies/${strategyId}/squareoff`),

  // Broker APIs
  getBrokerStatus: () =>
    axiosClient.get('/brokers/status'),

  generateDhanConsent: (partnerId, partnerSecret) =>
    axiosClient.post('/brokers/dhan/auth/partner/generate-consent', { partnerId, partnerSecret }),
};
