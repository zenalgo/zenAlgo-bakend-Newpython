import axiosClient from './axiosClient';

export const plansApi = {
  getPublicPlans: (params) =>
    axiosClient.get('/admin/plans', { params }),

  getMySubscription: () =>
    axiosClient.get('/subscriptions/me'),

  createPlanAdmin: (planData) =>
    axiosClient.post('/admin/plans', planData),

  updatePlanAdmin: (planId, planData) =>
    axiosClient.put(`/admin/plans/${planId}`, planData),

  updatePlanStatus: (planId, active) =>
    axiosClient.put(`/admin/plans/${planId}/status`, { active }),
};
