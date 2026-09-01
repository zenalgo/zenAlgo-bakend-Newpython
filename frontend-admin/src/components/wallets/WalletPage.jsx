import React, { useState, useEffect } from 'react';
import { Wallet, ArrowDownLeft, ArrowUpRight, Plus, Minus, RefreshCw, Search, Filter } from 'lucide-react';
import { walletsApi } from '../../api/walletsApi';
import { Modal } from '../common/Modal';
import { Pagination } from '../common/Pagination';
import { useToast } from '../../context/ToastContext';

export const WalletPage = () => {
  const { addToast } = useToast();
  const [wallet, setWallet] = useState(null);
  const [transactions, setTransactions] = useState([]);
  const [loading, setLoading] = useState(true);

  // Filters & Pagination
  const [search, setSearch] = useState('');
  const [txTypeFilter, setTxTypeFilter] = useState('ALL');
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(10);
  
  // Deposit & Withdraw Modals
  const [isDepositOpen, setIsDepositOpen] = useState(false);
  const [isWithdrawOpen, setIsWithdrawOpen] = useState(false);
  const [amount, setAmount] = useState('25000');
  const [description, setDescription] = useState('Trading Margin Deposit');
  const [submitting, setSubmitting] = useState(false);

  const loadWalletData = async () => {
    setLoading(true);
    try {
      const params = {
        page,
        size: pageSize,
        tx_type: txTypeFilter !== 'ALL' ? txTypeFilter : undefined,
        search: search || undefined,
      };
      const [wRes, tRes] = await Promise.all([
        walletsApi.getWallet(),
        walletsApi.getTransactions(params),
      ]);
      setWallet(wRes.data || { balance: 0.0, availableMargin: 0.0 });
      setTransactions(tRes.data || []);
    } catch (err) {
      console.error(err);
      addToast(err.message || 'Failed to load wallet ledger', 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadWalletData();
  }, [page, pageSize, txTypeFilter]);

  useEffect(() => {
    const handler = setTimeout(() => {
      setPage(0);
      loadWalletData();
    }, 300);
    return () => clearTimeout(handler);
  }, [search]);

  const handleDeposit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      const refId = `DEP-${Date.now()}`;
      await walletsApi.deposit(parseFloat(amount), refId, description);
      addToast(`Deposited ₹${parseFloat(amount).toLocaleString('en-IN')} successfully!`, 'success');
      setIsDepositOpen(false);
      loadWalletData();
    } catch (err) {
      addToast(err.message || 'Deposit failed', 'error');
    } finally {
      setSubmitting(false);
    }
  };

  const handleWithdraw = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      const refId = `WTH-${Date.now()}`;
      await walletsApi.withdraw(parseFloat(amount), refId, description);
      addToast(`Withdrew ₹${parseFloat(amount).toLocaleString('en-IN')} successfully!`, 'success');
      setIsWithdrawOpen(false);
      loadWalletData();
    } catch (err) {
      addToast(err.message || 'Withdrawal failed', 'error');
    } finally {
      setSubmitting(false);
    }
  };

  const currentBal = wallet?.balance !== undefined ? parseFloat(wallet.balance) : 0.0;
  const availMargin = wallet?.availableMargin !== undefined ? parseFloat(wallet.availableMargin) : currentBal;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <h1 style={{ fontSize: '1.8rem', fontWeight: 800, color: '#fff' }}>Trading Wallet & Financial Ledger</h1>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>
            Real-time available margin, deposits, withdrawals, and transaction records.
          </p>
        </div>
        <div style={{ display: 'flex', gap: '10px' }}>
          <button onClick={loadWalletData} disabled={loading} className="btn btn-secondary">
            <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
            <span>Refresh Ledger</span>
          </button>
          <button onClick={() => { setAmount('10000'); setDescription('Margin Withdrawal'); setIsWithdrawOpen(true); }} className="btn btn-secondary">
            <Minus size={16} />
            <span>Withdraw</span>
          </button>
          <button onClick={() => { setAmount('25000'); setDescription('Margin Top-Up via NetBanking'); setIsDepositOpen(true); }} className="btn btn-emerald">
            <Plus size={16} />
            <span>Add Margin / Deposit</span>
          </button>
        </div>
      </div>

      {/* Balance Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '20px' }}>
        <div className="glass-panel" style={{ padding: '24px' }}>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>
            Total Wallet Balance
          </div>
          <div style={{ fontSize: '2.2rem', fontWeight: 800, color: '#fff', marginTop: '6px', fontFamily: 'Outfit, sans-serif' }}>
            ₹{currentBal.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
          </div>
          <div style={{ fontSize: '0.8rem', color: 'var(--accent-emerald)', marginTop: '8px' }}>
            ● 100% Margin Backed Ledger
          </div>
        </div>

        <div className="glass-panel" style={{ padding: '24px' }}>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>
            Available Trading Margin
          </div>
          <div style={{ fontSize: '2.2rem', fontWeight: 800, color: 'var(--accent-cyan)', marginTop: '6px', fontFamily: 'Outfit, sans-serif' }}>
            ₹{availMargin.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
          </div>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-dim)', marginTop: '8px' }}>
            Currency: {wallet?.currency || 'INR'}
          </div>
        </div>
      </div>

      {/* Transactions Table & Filters */}
      <div className="glass-panel" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
          <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: '#fff', margin: 0 }}>
            Transaction History Ledger
          </h3>

          <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', minWidth: '220px' }}>
              <Search size={16} color="var(--text-dim)" />
              <input
                type="text"
                placeholder="Search reference or description..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="input-field"
                style={{ padding: '6px 12px', fontSize: '0.85rem' }}
              />
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Filter size={14} color="var(--text-dim)" />
              <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>Type:</span>
              <select
                value={txTypeFilter}
                onChange={(e) => { setTxTypeFilter(e.target.value); setPage(0); }}
                className="input-field"
                style={{ width: '130px', padding: '6px 10px' }}
              >
                <option value="ALL">All Types</option>
                <option value="DEPOSIT">DEPOSIT</option>
                <option value="WITHDRAWAL">WITHDRAWAL</option>
              </select>
            </div>
          </div>
        </div>

        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>Tx ID</th>
                <th>Reference ID</th>
                <th>Type</th>
                <th>Amount (₹)</th>
                <th>Balance After (₹)</th>
                <th>Description</th>
                <th>Timestamp</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan="7" style={{ textAlign: 'center', padding: '30px', color: 'var(--text-muted)' }}>
                    Loading transactions...
                  </td>
                </tr>
              ) : transactions.length === 0 ? (
                <tr>
                  <td colSpan="7" style={{ textAlign: 'center', padding: '30px', color: 'var(--text-muted)' }}>
                    No transactions recorded matching filters. Click <strong>"Add Margin / Deposit"</strong> to test!
                  </td>
                </tr>
              ) : (
                transactions.map((tx) => {
                  const isDeposit = (tx.transactionType || tx.type || '').toUpperCase() === 'DEPOSIT';
                  const amountNum = parseFloat(tx.amount || 0);
                  const balAfterNum = parseFloat(tx.balanceAfter || tx.balance_after || 0);

                  return (
                    <tr key={tx.id}>
                      <td className="font-mono" style={{ color: 'var(--accent-cyan)', fontWeight: 600 }}>#{tx.id}</td>
                      <td className="font-mono" style={{ color: 'var(--text-dim)' }}>{tx.referenceId || tx.reference_id || '—'}</td>
                      <td>
                        <span className={`badge ${isDeposit ? 'badge-running' : 'badge-failed'}`}>
                          {isDeposit ? 'DEPOSIT' : 'WITHDRAWAL'}
                        </span>
                      </td>
                      <td style={{ fontWeight: 700, color: isDeposit ? 'var(--accent-emerald)' : 'var(--accent-rose)' }}>
                        {isDeposit ? `+₹${amountNum.toLocaleString('en-IN', { minimumFractionDigits: 2 })}` : `-₹${amountNum.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`}
                      </td>
                      <td className="font-mono" style={{ fontWeight: 600 }}>
                        ₹{balAfterNum.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                      </td>
                      <td style={{ color: 'var(--text-muted)' }}>{tx.description || 'Margin transfer'}</td>
                      <td style={{ fontSize: '0.8rem', color: 'var(--text-dim)' }}>
                        {new Date(tx.createdAt || tx.created_at || Date.now()).toLocaleTimeString()}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        <Pagination
          currentPage={page}
          pageSize={pageSize}
          totalItems={transactions.length >= pageSize ? (page + 2) * pageSize : (page * pageSize) + transactions.length}
          onPageChange={(newPage) => setPage(newPage)}
          onPageSizeChange={(newSize) => { setPageSize(newSize); setPage(0); }}
          pageSizeOptions={[5, 10, 20, 50]}
        />
      </div>

      {/* Deposit Modal */}
      <Modal isOpen={isDepositOpen} onClose={() => setIsDepositOpen(false)} title="Deposit Funds to Trading Margin Wallet">
        <form onSubmit={handleDeposit} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div>
            <label>Deposit Amount (₹)</label>
            <input
              type="number"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              className="input-field"
              required
            />
          </div>
          <div>
            <label>Remarks / Description</label>
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="input-field"
            />
          </div>
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '12px' }}>
            <button type="button" onClick={() => setIsDepositOpen(false)} className="btn btn-secondary">Cancel</button>
            <button type="submit" disabled={submitting} className="btn btn-emerald">
              {submitting ? 'Processing...' : 'Deposit Margin'}
            </button>
          </div>
        </form>
      </Modal>

      {/* Withdraw Modal */}
      <Modal isOpen={isWithdrawOpen} onClose={() => setIsWithdrawOpen(false)} title="Withdraw Funds from Margin Wallet">
        <form onSubmit={handleWithdraw} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div>
            <label>Withdrawal Amount (₹)</label>
            <input
              type="number"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              className="input-field"
              required
            />
          </div>
          <div>
            <label>Remarks / Reason</label>
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="input-field"
            />
          </div>
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '12px' }}>
            <button type="button" onClick={() => setIsWithdrawOpen(false)} className="btn btn-secondary">Cancel</button>
            <button type="submit" disabled={submitting} className="btn btn-danger">
              {submitting ? 'Processing...' : 'Withdraw Funds'}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
};

export default WalletPage;
