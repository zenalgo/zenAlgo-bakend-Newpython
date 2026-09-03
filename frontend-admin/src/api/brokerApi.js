import axiosClient from './axiosClient';

export const brokerApi = {
  getBrokerAccounts: () =>
    axiosClient.get('/brokers/accounts'),

  createBrokerAccount: (accountData) => {
    const brokerCode = accountData.brokerCode || 'DHAN';
    const credentials = accountData.credentials || {
      clientId: accountData.accountClientId,
      accessToken: accountData.accessToken,
    };
    return axiosClient.post(`/brokers/${brokerCode}/connect`, { credentials });
  },
};
