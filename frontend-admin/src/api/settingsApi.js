import axiosClient from './axiosClient';

export const settingsApi = {
  getOrderCap: async () => {
    return axiosClient.get('/admin/settings/order-cap');
  },
  updateOrderCap: async (maxOrderValueCap) => {
    return axiosClient.put('/admin/settings/order-cap', {
      maxOrderValueCap: parseFloat(maxOrderValueCap),
    });
  },
};
