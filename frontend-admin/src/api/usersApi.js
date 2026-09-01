import axiosClient from './axiosClient';

export const usersApi = {
  getUsers: (params) =>
    axiosClient.get('/admin/users', { params }),

  provisionUser: (userData) =>
    axiosClient.post('/admin/users', userData),

  updateUserStatus: (userId, active) =>
    axiosClient.put(`/admin/users/${userId}/status`, { active }),
};
