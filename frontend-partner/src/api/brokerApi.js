import axiosClient from './axiosClient';

export const brokerApi = {
  // Generic Broker APIs
  getSupportedBrokers: () =>
    axiosClient.get('/brokers'),

  getActiveSession: () =>
    axiosClient.get('/brokers/active-session'),

  getBrokerFormConfig: (brokerCode) =>
    axiosClient.get(`/brokers/${brokerCode}/config`),

  connectBroker: (brokerCode, credentials) =>
    axiosClient.post(`/brokers/${brokerCode}/connect`, { credentials }),

  listAccounts: () =>
    axiosClient.get('/brokers/accounts'),

  disconnectAccount: (accountId) =>
    axiosClient.delete(`/brokers/accounts/${accountId}`),

  // Dhan-Specific APIs
  connectDhanTotp: (payload) =>
    axiosClient.post('/dhan/auth/individual/generate-token', payload),

  disconnectDhanSession: () =>
    axiosClient.delete('/dhan/auth/session'),

  getDhanSession: () =>
    axiosClient.get('/dhan/auth/session/me'),

  getDhanFunds: () =>
    axiosClient.get('/dhan/funds'),

  getDhanProfile: () =>
    axiosClient.get('/dhan/profile'),

  getDhanPositions: () =>
    axiosClient.get('/dhan/positions'),

  convertDhanPosition: (payload) =>
    axiosClient.post('/dhan/positions/convert', payload),

  getDhanHoldings: () =>
    axiosClient.get('/dhan/holdings'),

  getDhanOrders: () =>
    axiosClient.get('/dhan/orders'),

  placeDhanOrder: (payload) =>
    axiosClient.post('/dhan/orders', payload),

  cancelDhanOrder: (orderId) =>
    axiosClient.delete(`/dhan/orders/${orderId}`),

  getDhanTrades: () =>
    axiosClient.get('/dhan/trades'),

  calculateDhanMargin: (payload) =>
    axiosClient.post('/dhan/margincalculator', payload),

  getPortfolioSummary: () =>
    axiosClient.get('/dhan/portfolio-summary'),

  generatePartnerConsent: (payload) =>
    axiosClient.post('/dhan/auth/partner/generate-consent', payload || {}),

  // Scrip Master & Stock Search APIs
  searchInstruments: (query, broker = 'DHAN', limit = 20) =>
    axiosClient.get('/instruments/search', { params: { query, broker, limit } }),

  getInstrumentSectors: () =>
    axiosClient.get('/instruments/sectors'),

  getInstrumentQuote: (symbol, broker = 'DHAN') =>
    axiosClient.get(`/instruments/${symbol}/quote`, { params: { broker } }),
};

export default brokerApi;
