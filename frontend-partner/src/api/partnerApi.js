import axiosClient from './axiosClient';

export const partnerApi = {
  getDashboardStats: () =>
    axiosClient.get('/partner/dashboard'),

  getReferredClients: (params) =>
    axiosClient.get('/partner/referrals', { params }),

  getCommissions: (params) =>
    axiosClient.get('/partner/commissions', { params }),

  requestPayout: (payload) =>
    axiosClient.post('/partner/payouts/request', payload),

  getPayouts: () =>
    axiosClient.get('/partner/payouts'),

  getMarketingLinks: () =>
    axiosClient.get('/partner/links'),
};
