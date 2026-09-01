import axiosClient from './axiosClient';

export const usersApi = {
  getUsers: () =>
    axiosClient.get('/admin/users'),

  provisionUser: (userData) =>
    axiosClient.post('/admin/users', userData),

  updateUserStatus: (userId, active) =>
    axiosClient.put(`/admin/users/${userId}/status`, { active }),
};
