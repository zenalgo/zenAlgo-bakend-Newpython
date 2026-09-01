import axiosClient from './axiosClient';

export const brokerApi = {
  getBrokerAccounts: () =>
    axiosClient.get('/brokers/accounts'),

  createBrokerAccount: (accountData) =>
    axiosClient.post('/brokers/accounts', accountData),
};
