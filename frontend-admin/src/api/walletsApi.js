import axiosClient from './axiosClient';

export const walletsApi = {
  getWallet: () =>
    axiosClient.get('/wallets/me'),

  getTransactions: () =>
    axiosClient.get('/wallets/me/transactions'),

  deposit: (amount, referenceId, description) =>
    axiosClient.post('/wallets/me/deposit', {
      amount,
      referenceId,
      description,
      referenceType: 'BANK_TRANSFER',
    }),

  withdraw: (amount, referenceId, description) =>
    axiosClient.post('/wallets/me/withdraw', {
      amount,
      referenceId,
      description,
      referenceType: 'BANK_TRANSFER',
    }),
};
