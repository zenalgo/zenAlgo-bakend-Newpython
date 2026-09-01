import axiosClient from './axiosClient';

export const authApi = {
  adminLogin: (email, password) =>
    axiosClient.post('/auth/admin/login', { email, password }),
  
  traderLogin: (email, password) =>
    axiosClient.post('/auth/login', { email, password }),

  register: (userData) =>
    axiosClient.post('/auth/register', userData),

  refreshToken: (refreshToken) =>
    axiosClient.post('/auth/refresh', { refreshToken }),
};
