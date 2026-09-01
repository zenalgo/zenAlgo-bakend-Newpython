import axiosClient from './axiosClient';

export const plansApi = {
  getPublicPlans: () =>
    axiosClient.get('/subscriptions/plans'),

  getMySubscriptions: () =>
    axiosClient.get('/subscriptions/my'),

  subscribeToPlan: (planId) =>
    axiosClient.post('/subscriptions/subscribe', { planId }),

  // Admin Plan Management
  getAllPlansAdmin: () =>
    axiosClient.get('/subscriptions/admin/plans'),

  createPlanAdmin: (planData) =>
    axiosClient.post('/subscriptions/admin/plans', planData),

  updatePlanAdmin: (planId, planData) =>
    axiosClient.put(`/subscriptions/admin/plans/${planId}`, planData),
};
