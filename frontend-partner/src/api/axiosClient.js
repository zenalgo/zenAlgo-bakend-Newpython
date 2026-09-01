import axios from 'axios';

const API_BASE_URL = 'http://localhost:8000/api/v1';

export const axiosClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request Interceptor to inject stored JWT token
axiosClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('zenalgo_partner_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    config.headers['X-Client-App'] = 'zenalgo-partner-portal';
    return config;
  },
  (error) => Promise.reject(error)
);

// Response Interceptor to unwrap data and handle auth expiration
axiosClient.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const message = error.response?.data?.message || error.message || 'API request failed';
    if (error.response?.status === 401 || error.response?.data?.code === 'UNAUTHENTICATED') {
      console.warn('Session expired or invalid token:', message);
      localStorage.removeItem('zenalgo_partner_token');
      localStorage.removeItem('zenalgo_partner_user');
    }
    return Promise.reject(error.response?.data || { message });
  }
);

export default axiosClient;
