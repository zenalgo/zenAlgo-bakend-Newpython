import axiosClient from './axiosClient';

export const paymentApi = {
  // Payment Methods
  getPaymentMethods: () =>
    axiosClient.get('/admin/payment-methods'),

  createPaymentMethod: (payload) =>
    axiosClient.post('/admin/payment-methods', payload),

  updatePaymentMethod: (id, payload) =>
    axiosClient.put(`/admin/payment-methods/${id}`, payload),

  togglePaymentMethodStatus: (id, isActive) =>
    axiosClient.put(`/admin/payment-methods/${id}/status`, { isActive }),

  deletePaymentMethod: (id) =>
    axiosClient.delete(`/admin/payment-methods/${id}`),

  // Subscription Approvals & UTR Verification
  getPendingSubscriptionRequests: () =>
    axiosClient.get('/admin/subscriptions/pending-requests'),

  approveSubscription: (paymentId, adminNotes) =>
    axiosClient.post(`/admin/subscriptions/${paymentId}/approve`, { adminNotes }),

  rejectSubscription: (paymentId, adminNotes) =>
    axiosClient.post(`/admin/subscriptions/${paymentId}/reject`, { adminNotes }),

  getPlanWalletLedger: () =>
    axiosClient.get('/admin/plan-wallet/ledger'),
};

export default paymentApi;
