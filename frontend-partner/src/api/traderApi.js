import axiosClient from './axiosClient';

export const traderApi = {
  getStrategies: (params) =>
    axiosClient.get('/strategies', { params }),

  getPlacedOrders: (strategyId) =>
    axiosClient.get('/execution/placed-orders', { params: { strategyId } }),

  getMySubscription: () =>
    axiosClient.get('/subscriptions/me'),

  getPlans: () =>
    axiosClient.get('/subscriptions/plans'),

  getActivePaymentMethods: () =>
    axiosClient.get('/subscriptions/payment-methods/active'),

  requestPlanActivation: (payload) =>
    axiosClient.post('/subscriptions/request-activation', payload),

  getWallet: () =>
    axiosClient.get('/wallets/me'),

  getWalletTransactions: () =>
    axiosClient.get('/wallets/me/transactions'),

  depositMargin: (amount) =>
    axiosClient.post('/wallets/me/deposit', { amount, remarks: 'Client portal instant margin deposit' }),

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
