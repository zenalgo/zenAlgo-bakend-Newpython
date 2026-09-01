import axiosClient from './axiosClient';

export const walletsApi = {
  getWallet: () =>
    axiosClient.get('/wallets/me'),

  getTransactions: () =>
    axiosClient.get('/wallets/me/transactions'),

  deposit: (amount, referenceId, remarks) =>
    axiosClient.post('/wallets/me/deposit', { amount, referenceId, remarks }),

  withdraw: (amount, remarks) =>
    axiosClient.post('/wallets/me/withdraw', { amount, remarks }),
};
