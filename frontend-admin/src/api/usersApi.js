import axiosClient from './axiosClient';

export const usersApi = {
  getUsers: () =>
    axiosClient.get('/users'),

  createUser: (userData) =>
    axiosClient.post('/users', userData),

  updateUserStatus: (userId, isActive) =>
    axiosClient.put(`/users/${userId}/status`, { isActive }),
};
